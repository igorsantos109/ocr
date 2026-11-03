"""Motor olmOCR via llama-server local (OpenAI-compatível, CPU-first).

olmOCR (Allen AI, Apache 2.0) é um VLM de 7B derivado do Qwen2-VL e ajustado
especificamente para OCR de documentos: ordem de leitura natural e saída em
Markdown (tabelas viram tabelas). Este adaptador segue o mesmo padrão do motor
`paddle_vl`: envia a imagem colorida original ao `llama-server` local e recebe
texto, sem depender de pacotes extras nem baixar nada.

Limites honestos (nunca inventar coordenadas):
- o endpoint de chat do VLM não retorna caixas; por isso o resultado é UMA
  linha cobrindo a página inteira, com `confianca=None` (vai para revisão
  alta) e `aviso` explícito. Nada de caixas proporcionais fabricadas.
- `recognize_lines` não é suportado (recorte de linha num VLM de página não
  faz sentido); o mixin `MotorPagina` já levanta `NotImplementedError`.
- o toolkit oficial do olmOCR aplica "ancoragem" (várias amostragens e voto);
  aqui há UMA passada com `temperature=0` — mais fraco contra alucinação, por
  isso a revisão humana continua obrigatória.
"""

from __future__ import annotations

import base64
import io
import json
import urllib.request
from pathlib import Path

from PIL import Image

from .base import LinhaRec, MotorIndisponivel, MotorPagina, RecognitionConfig, ResultadoPagina

# Backend local padrão: Qwen3-VL-8B em :8082 (scripts/servidor_qwen3vl.sh).
# O GGUF allenai/olmOCR-2-7B-1025 original não está presente neste host;
# para usá-lo, passe base_url + modelo explícitos.
MODELO_PADRAO = "Qwen3VL-8B-Instruct"
BASE_PADRAO = "http://127.0.0.1:8082"
DIR_MODELO = "/mnt/RESERVA2/models/OCR/olmOCR-2-7B"

MENSAGEM_SERVIDOR = (
    "Servidor olmOCR indisponível. Suba o llama-server local com "
    "'bash scripts/servidor_olmocr.sh' (requer o GGUF + mmproj em "
    f"{DIR_MODELO}/, sem download automático) "
    "ou use --engine paddleocr."
)

PROMPT_DIPLOMATICO = (
    "Transcreva literalmente o texto visível nesta imagem de documento histórico "
    "brasileiro (impresso, datilografado ou manuscrito, em português). "
    "Responda em Markdown seguindo a ordem natural de leitura; tabelas viram "
    "tabelas Markdown. Regras: preserve a grafia original (não modernize); não "
    "expanda abreviaturas; não complete lacunas nem invente palavras; marque "
    "trechos ilegíveis como [ilegível]. Responda SOMENTE com a transcrição, "
    "sem comentários."
)


def _url(config: RecognitionConfig) -> str:
    return (config.base_url or BASE_PADRAO).rstrip("/")


def _modelo(config: RecognitionConfig) -> str:
    if config.modelo and config.modelo not in {"best", "default"}:
        return config.modelo
    return MODELO_PADRAO


def _ping(base: str, timeout: float = 3.0) -> bool:
    for caminho in ("/health", "/v1/models"):
        try:
            with urllib.request.urlopen(base + caminho, timeout=timeout) as resp:
                if 200 <= resp.status < 300:
                    return True
        except Exception:
            continue
    return False


def _modelos_servidos(base: str, timeout: float = 5.0) -> list[str]:
    """Lista os IDs de modelo anunciados em /v1/models; [] se indeterminado."""
    try:
        with urllib.request.urlopen(base + "/v1/models", timeout=timeout) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    ids: list[str] = []
    for origem in (dados.get("models"), dados.get("data")):
        if isinstance(origem, list):
            for item in origem:
                if isinstance(item, dict):
                    for chave in ("id", "name", "model"):
                        valor = item.get(chave)
                        if isinstance(valor, str) and valor:
                            ids.append(valor)
                            break
    return ids


def _parece_vl(texto: str) -> bool:
    baixo = texto.lower()
    return any(
        p in baixo
        for p in (
            "olmocr", "olm-ocr", "olmo", "glm-ocr", "glm", "qwen2-vl", "qwen2_vl", "qwen2.5-vl",
            "qwen3-vl", "qwen3vl", "qwen-vl", "vision", "vl-",
        )
    )


def _conferir_modelo(base: str, solicitado: str) -> str | None:
    """Devolve aviso se o servidor serve outro modelo; None se compatível/indeterminado."""
    servidos = _modelos_servidos(base)
    if not servidos:
        return None
    if solicitado in servidos:
        return None
    if any(_parece_vl(s) for s in servidos):
        return None
    return f"servidor serve {servidos[0]!r}, não {solicitado!r} (sem visão/VL)"


def _imagem_base64(caminho: Path, max_lado: int = 2048) -> tuple[str, int, int]:
    with Image.open(caminho) as img:
        rgb = img.convert("RGB")
        rgb.thumbnail((max_lado, max_lado))
        largura, altura = rgb.size
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode("ascii"), largura, altura


def _extrair_texto(resposta: dict) -> str:
    try:
        conteudo = resposta["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise MotorIndisponivel(f"Resposta inesperada do servidor VL: {resposta!r:.200}") from exc
    if isinstance(conteudo, str):
        return conteudo.strip()
    if isinstance(conteudo, list):
        partes = [p.get("text", "") for p in conteudo if isinstance(p, dict) and p.get("type") == "text"]
        return "\n".join(partes).strip()
    return str(conteudo).strip()


class OlmOCREngine(MotorPagina):
    """Transcrição VLM de página inteira via servidor local. Sem GPU obrigatória."""

    name = "olmocr"

    def available(self) -> bool:
        return _ping(_url(RecognitionConfig(engine=self.name)))

    def available_com_config(self, config: RecognitionConfig) -> bool:
        """Disponibilidade contra a URL configurada (pipeline usa quando existe).

        Servidor ativo mas com modelo sem visão/VL conta como indisponível,
        com o detalhe registrado pelo `recognize_page`.
        """
        base = _url(config)
        if not _ping(base):
            return False
        return _conferir_modelo(base, _modelo(config)) is None

    def recognize_page(
        self, image_path: Path | str, config: RecognitionConfig, numero_pagina: int = 1
    ) -> ResultadoPagina:
        caminho = Path(image_path)
        if not caminho.is_file():
            raise MotorIndisponivel(f"Imagem não encontrada para olmOCR: {caminho}")
        base = _url(config)
        if not _ping(base, timeout=5.0):
            raise MotorIndisponivel(f"{MENSAGEM_SERVIDOR} (base: {base})")
        solicitado = _modelo(config)
        divergencia = _conferir_modelo(base, solicitado)
        if divergencia is not None:
            raise MotorIndisponivel(
                f"Servidor VL em {base} com modelo inadequado ({divergencia}). "
                f"Suba o olmOCR com 'bash scripts/servidor_olmocr.sh' ou ajuste --vl-url/--vl-modelo."
            )
        try:
            b64, largura, altura = _imagem_base64(caminho, max_lado=config.max_lado_px or 1024)
        except (OSError, ValueError) as exc:
            raise MotorIndisponivel(f"Falha ao ler imagem para olmOCR: {exc}") from exc
        corpo = json.dumps(
            {
                "model": solicitado,
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT_DIPLOMATICO},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        ],
                    }
                ],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            base + "/v1/chat/completions", data=corpo, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=config.timeout_segundos or 300) as resp:
                resposta = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - converte em erro acionável
            raise MotorIndisponivel(f"Falha ao consultar o servidor VL em {base}: {exc}") from exc
        texto = _extrair_texto(resposta)
        if not texto:
            raise MotorIndisponivel("O servidor VL retornou transcrição vazia; revise a imagem ou o modelo.")
        linha = LinhaRec(
            numero=1, x=0, y=0, largura=largura, altura=altura, texto=texto, confianca=None,
        )
        return ResultadoPagina(
            texto_bruto=texto,
            linhas=(linha,),
            confianca_media=None,
            motor=self.name,
            aviso="VLM sem caixas por linha; página tratada como bloco único — revisão visual obrigatória.",
        )
