"""Revisor LLM local — desativado por padrão, somente sugestão auditável.

Especificação §9.8:
- `enabled: false` por padrão; nada é enviado sem comando explícito.
- Envia somente linhas selecionadas (IDs), nunca o lote inteiro sem confirmação.
- Endpoint local configurável (`base_url`, compatível Ollama/OpenAI-local).
- Retorno JSON validado por Pydantic; erro/JSON inválido não interrompe o lote.
- Nunca substitui o texto diplomático; marca para confirmação humana.
- Guarda prompt, resposta, modelo e data em log/auditoria (tabela `correcoes`
  com origem `llm_sugerido` e `tipo_correcao=sugestao_llm`, sem alterar texto).
"""

from __future__ import annotations

import json
import re
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from ..database import fabrica_sessoes, inicializar_banco
from ..models import Correcao, Linha, agora


class SugestaoLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto_original: str = Field(min_length=1)
    sugestao: str = Field(min_length=1)
    tipo: Literal["caractere", "palavra", "pontuacao", "segmentacao", "outro"] = "caractere"
    justificativa_curta: str = Field(default="", max_length=500)
    confianca: float = Field(ge=0.0, le=1.0)
    exige_revisao_visual: bool = True


TIPOS_VALIDOS = ("caractere", "palavra", "pontuacao", "segmentacao", "outro")


def _prompt_revisao(texto: str) -> str:
    return (
        "Você revisa transcrições OCR de documentos históricos brasileiros. "
        "Responda SOMENTE com JSON válido no schema "
        '{"texto_original, sugestao, tipo, justificativa_curta, confianca, exige_revisao_visual}. '
        "O campo tipo usa EXATAMENTE um destes valores: caractere, palavra, pontuacao, segmentacao, outro. "
        "Sem raciocínio, sem cercas de código: apenas o objeto JSON. "
        "Não modernize grafia histórica sem necessidade; aponte apenas confusões prováveis de caracteres. "
        f'Texto OCR: "{texto}"'
    )


def _normalizar_tipo(valor: object) -> str:
    """Mapeia variações livres ("confusão de caracteres") para o enum do schema."""
    import unicodedata

    bruto = str(valor or "").strip().lower()
    texto = "".join(c for c in unicodedata.normalize("NFKD", bruto) if not unicodedata.combining(c))
    for candidato in TIPOS_VALIDOS:
        if candidato in texto:
            return candidato
    if "caracter" in texto or "letra" in texto or "ocr" in texto:
        return "caractere"
    return "outro"


@dataclass(frozen=True)
class ResultadoSugestao:
    linha_id: str
    texto_original: str
    sugestao: SugestaoLLM | None
    modelo: str
    erro: str | None = None
    bruto: str | None = None


def _chamar_endpoint(base_url: str, model: str, prompt: str, timeout: int) -> str:
    # tenta Ollama (/api/generate) e depois OpenAI-local (/v1/chat/completions)
    base = base_url.rstrip("/")
    corpo_ollama = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    # Qwen3 pensa antes de responder (lento em CPU); o sufixo /no_think do
    # template desliga o raciocínio sem afetar outros modelos.
    conteudo_chat = prompt + " /no_think" if "qwen3" in model.lower() else prompt
    corpo_chat = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": conteudo_chat}],
            "temperature": 0,
            "max_tokens": 1024,
        }
    ).encode("utf-8")
    for caminho, corpo in [
        ("/api/generate", corpo_ollama),
        ("/v1/chat/completions", corpo_chat),
    ]:
        req = urllib.request.Request(
            base + caminho, data=corpo, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
        # Ollama: {"response": "..."} ; OpenAI: {"choices":[{"message":{"content":"..."}}]}
        if isinstance(dados, dict):
            if isinstance(dados.get("response"), str):
                return dados["response"]
            choices = dados.get("choices")
            if isinstance(choices, list) and choices:
                content = choices[0].get("message", {}).get("content")
                if isinstance(content, str):
                    return content
    raise ConnectionError(f"LLM local indisponível em {base_url} (tente iniciar o Ollama).")


def _remover_think(texto: str) -> str:
    """Remove blocos <think>…</think> de modelos de raciocínio (Qwen3, DeepSeek-R1)."""
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL | re.IGNORECASE).strip()


def _extrair_json(texto: str) -> str:
    texto = _remover_think(texto.strip())
    # remove cercas de código ```json ... ```
    if texto.startswith("```"):
        partes = texto.splitlines()
        partes = [p for p in partes if not p.strip().startswith("```")]
        texto = "\n".join(partes).strip()
    # se houver texto extra, tenta recortar o primeiro objeto {...}
    if not texto.startswith("{"):
        ini = texto.find("{")
        fim = texto.rfind("}")
        if ini != -1 and fim != -1 and fim > ini:
            texto = texto[ini : fim + 1]
    return texto


def validar_sugestao(bruto: str, texto_original: str) -> SugestaoLLM:
    payload = json.loads(_extrair_json(bruto))
    if isinstance(payload, dict) and "tipo" in payload:
        payload = {**payload, "tipo": _normalizar_tipo(payload["tipo"])}
    sug = SugestaoLLM.model_validate(payload)
    # Tolerante a pequena divergência entre texto_original respondido e enviado:
    # a auditoria guarda ambos (prompt + resposta), sem bloquear a sugestão.
    _ = (sug.texto_original, texto_original)
    return sug


def sugerir_linhas(
    banco: Path | str,
    linha_ids: list[str],
    base_url: str = "http://127.0.0.1:11434",
    model: str = "qwen2.5:7b-instruct",
    timeout_seconds: int = 120,
    usuario: str | None = None,
    log_dir: Path | str | None = None,
) -> list[ResultadoSugestao]:
    """Gera sugestões para linhas selecionadas, sem alterar nenhum texto.

    Cada chamada grava um registro `correcoes` com origem `llm_sugerido` e
    `tipo_correcao=sugestao_llm` contendo prompt+resposta na observação,
    permitindo auditoria completa. Falhas por linha não interrompem o lote.
    """
    engine = inicializar_banco(banco)
    resultados: list[ResultadoSugestao] = []
    log_base = Path(log_dir) if log_dir else Path("data/processamento/cache/llm")
    log_base.mkdir(parents=True, exist_ok=True)
    with fabrica_sessoes(engine)() as sessao:
        linhas = sessao.scalars(select(Linha).where(Linha.id.in_(linha_ids))).all() if linha_ids else []
        mapa = {lin.id: lin.texto_diplomatico for lin in linhas}
    for lid in linha_ids:
        original = mapa.get(lid)
        if original is None:
            resultados.append(
                ResultadoSugestao(
                    linha_id=lid, texto_original="", sugestao=None, modelo=model, erro="Linha não encontrada"
                )
            )
            continue
        prompt = _prompt_revisao(original)
        try:
            bruto = _chamar_endpoint(base_url, model, prompt, timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - por linha, sem abortar lote
            resultados.append(
                ResultadoSugestao(linha_id=lid, texto_original=original, sugestao=None, modelo=model, erro=str(exc))
            )
            continue
        try:
            sug = validar_sugestao(bruto, original)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            resultados.append(
                ResultadoSugestao(
                    linha_id=lid,
                    texto_original=original,
                    sugestao=None,
                    modelo=model,
                    erro=f"Resposta inválida: {exc}",
                    bruto=bruto,
                )
            )
            continue
        # auditoria: registra sem alterar texto
        with fabrica_sessoes(engine)() as sessao:
            sessao.add(
                Correcao(
                    id=uuid.uuid4().hex,
                    linha_id=lid,
                    texto_anterior=original,
                    texto_corrigido=sug.sugestao,
                    tipo_correcao="sugestao_llm",
                    origem="llm_sugerido",
                    usuario=usuario,
                    observacao=json.dumps(
                        {
                            "prompt": prompt,
                            "resposta_bruta": bruto,
                            "modelo": model,
                            "base_url": base_url,
                            "tipo": sug.tipo,
                            "justificativa": sug.justificativa_curta,
                            "confianca_llm": sug.confianca,
                            "exige_revisao_visual": sug.exige_revisao_visual,
                            "data": datetime.now().astimezone().isoformat(),
                        },
                        ensure_ascii=False,
                    ),
                    criado_em=agora(),
                )
            )
            sessao.commit()
        # log em arquivo por linha
        try:
            (log_base / f"{lid}.json").write_text(
                json.dumps(
                    {"linha_id": lid, "prompt": prompt, "resposta": bruto, "modelo": model},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass
        resultados.append(
            ResultadoSugestao(linha_id=lid, texto_original=original, sugestao=sug, modelo=model, bruto=bruto)
        )
    return resultados


def listar_sugestoes(banco: Path | str, linha_id: str) -> list[Correcao]:
    engine = inicializar_banco(banco)
    with fabrica_sessoes(engine)() as sessao:
        return list(
            sessao.scalars(
                select(Correcao)
                .where(Correcao.linha_id == linha_id, Correcao.origem == "llm_sugerido")
                .order_by(Correcao.criado_em.desc())
            ).all()
        )
