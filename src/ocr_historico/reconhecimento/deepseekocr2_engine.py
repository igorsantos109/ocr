"""Motor DeepSeek-OCR-2 via llama-server local (OpenAI-compatível, CPU-first).

Como funciona: o `llama-server` serve o DeepSeek-OCR-2 (GGUF + mmproj) com
API OpenAI-compatível em `127.0.0.1`. Este adaptador envia a imagem da
página e o prompt de documento do modelo (`<|grounding|>...` + regras
diplomáticas em PT), recebendo texto — sem depender de GPU nem baixar nada.

Limites honestos (nunca inventar coordenadas):
- o endpoint de chat do VLM não retorna caixas; por isso o resultado é UMA
  linha cobrindo a página inteira, com `confianca=None` (vai para revisão
  alta) e `aviso` explícito. Nada de caixas proporcionais fabricadas.
- `recognize_lines` não é suportado (recorte de linha num VLM de página não
  faz sentido); o mixin `MotorPagina` já levanta `NotImplementedError`.
"""

from __future__ import annotations

import base64
import io
import json
import urllib.request
from pathlib import Path

from PIL import Image

from .base import LinhaRec, MotorIndisponivel, MotorPagina, RecognitionConfig, ResultadoPagina

MENSAGEM_SERVIDOR = (
    "Servidor DeepSeek-OCR-2 indisponível. Suba o llama-server local com "
    "'bash scripts/servidor_deepseekocr2.sh' (requer GGUF + mmproj locais, "
    "sem download automático) "
    "ou use --engine tesseract."
)

PROMPT_DIPLOMATICO = (
    # Prompt oficial do modelo, apenas ele: qualquer instrução extra
    # (mesmo "responda somente com a transcrição") tira o modelo do modo
    # grounding e ele passa a comentar em vez de transcrever.
    "<|grounding|>Convert the document to markdown. "
)


# Backend local padrão: DeepSeek-OCR-2 em :8084
# (scripts/servidor_deepseekocr2.sh). A :8081 deste host serve o LLM
# textual e a :8082 é compartilhada pelos outros VLMs.
BASE_PADRAO = "http://127.0.0.1:8084"
MODELO_PADRAO = "DeepSeek-OCR-2"


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
    return any(p in baixo for p in ("deepseek-ocr", "deepseek_ocr", "deepseekocr", "ocr-2", "ocr2", "vision", "vl-"))


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
    # PNG sem perda, sempre: este modelo entra em loop de repetição com os
    # artefatos do JPEG (mesmo q90), enquanto o PNG transcreve corretamente.
    with Image.open(caminho) as img:
        rgb = img.convert("RGB")
        rgb.thumbnail((max_lado, max_lado))
        largura, altura = rgb.size
        buf = io.BytesIO()
        rgb.save(buf, format="PNG")
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


def _degenerado(texto: str, janela: int = 8, minimo_chars: int = 500, diversidade_min: float = 0.1) -> bool:
    """Detecta loop de repetição (ex. "COCOCO...") pela diversidade de n-gramas.

    Calibrado neste host: texto real mede >= 0.25, loop mede ~0.001.
    Textos curtos (< 500 chars) passam direto — vão para revisão humana de
    qualquer forma (confianca=None). DRY foi avaliado e descartado: com os
    valores do teste upstream ele aborta a transcrição legítima junto.
    """
    if len(texto) < minimo_chars:
        return False
    ngrams = [texto[i : i + janela] for i in range(len(texto) - janela + 1)]
    return len(set(ngrams)) / len(ngrams) < diversidade_min


class DeepSeekOCR2Engine(MotorPagina):
    """Transcrição VLM de página inteira via servidor local. Sem GPU obrigatória."""

    name = "deepseek_ocr2"

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
            raise MotorIndisponivel(f"Imagem não encontrada para DeepSeek-OCR-2: {caminho}")
        base = _url(config)
        if not _ping(base, timeout=5.0):
            raise MotorIndisponivel(f"{MENSAGEM_SERVIDOR} (base: {base})")
        solicitado = _modelo(config)
        divergencia = _conferir_modelo(base, solicitado)
        if divergencia is not None:
            raise MotorIndisponivel(
                f"Servidor VL em {base} com modelo inadequado ({divergencia}). "
                f"Suba o DeepSeek-OCR-2 com 'bash scripts/servidor_deepseekocr2.sh' ou ajuste --vl-url/--vl-modelo."
            )
        try:
            b64, largura, altura = _imagem_base64(caminho, max_lado=config.max_lado_px or 1024)
        except (OSError, ValueError) as exc:
            raise MotorIndisponivel(f"Falha ao ler imagem para DeepSeek-OCR-2: {exc}") from exc
        corpo = json.dumps(
            {
                "model": solicitado,
                "temperature": 0,
                # teto obrigatório: em modo grounding o modelo nem sempre
                # emite EOS sozinho (gera milhares de tokens até o timeout).
                "max_tokens": 2048,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT_DIPLOMATICO},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
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
        if _degenerado(texto):
            raise MotorIndisponivel(
                "O modelo entrou em loop de repetição nesta imagem "
                "(típico de foto com artefatos). Prefira um scan limpo ou "
                "o motor qwen3_vl, mais lento porém fiel em fotos."
            )
        linha = LinhaRec(
            numero=1,
            x=0,
            y=0,
            largura=largura,
            altura=altura,
            texto=texto,
            confianca=None,
        )
        return ResultadoPagina(
            texto_bruto=texto,
            linhas=(linha,),
            confianca_media=None,
            motor=self.name,
            aviso="VLM sem caixas por linha; página tratada como bloco único — revisão visual obrigatória.",
        )
