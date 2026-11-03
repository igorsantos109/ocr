"""Fábrica de motores a partir do nome configurado."""

from __future__ import annotations

from typing import cast

from .base import RecognitionConfig, RecognitionEngine
from .deepseekocr2_engine import DeepSeekOCR2Engine
from .easyocr_engine import EasyOCREngine
from .ensemble import EnsembleEngine
from .glmocr_engine import GLMOCREngine
from .kraken_engine import KrakenEngine
from .olmoc_engine import OlmOCREngine
from .opcionais import CalamariEngine, SuryaEngine
from .paddle_engine import PaddleOCREngine
from .pdf_text_engine import PdfTextEngine
from .qwen3vl_engine import Qwen3VLEngine
from .tesseract_engine import TesseractEngine

_MOTORES = {
    "tesseract": TesseractEngine,
    "kraken": KrakenEngine,
    "easyocr": EasyOCREngine,
    "pdf_texto": PdfTextEngine,
    "qwen3_vl": Qwen3VLEngine,
    "glm_ocr": GLMOCREngine,
    "deepseek_ocr2": DeepSeekOCR2Engine,
    "olmocr": OlmOCREngine,
    "paddleocr": PaddleOCREngine,
    "surya": SuryaEngine,
    "calamari": CalamariEngine,
}

# Metadados pequenos e serializáveis para a GUI explicar o motor escolhido.
_MOTOR_INFO: dict[str, dict[str, str]] = {
    "qwen3_vl": {
        "descricao": "Qwen3-VL 4B: visão de página inteira, leve e rápido para documentos históricos.",
        "endpoint": "http://127.0.0.1:8082",
        "modelo": "Qwen3VL-4B-Instruct",
    },
    "glm_ocr": {
        "descricao": "GLM-OCR: alta precisão em layout e tabelas, saída estruturada.",
        "endpoint": "http://127.0.0.1:8082",
        "modelo": "GLM-OCR",
    },
    "deepseek_ocr2": {
        "descricao": "DeepSeek-OCR-2: MoE 3,4B especializado em documentos, saída Markdown.",
        "endpoint": "http://127.0.0.1:8084",
        "modelo": "DeepSeek-OCR-2",
    },
    "olmocr": {
        "descricao": "olmOCR local: ordem natural de leitura e saída Markdown, sem caixas por linha.",
        "endpoint": "http://127.0.0.1:8082",
        "modelo": "Qwen3VL-8B-Instruct",
    },
    "paddleocr": {
        "descricao": "PaddleOCR clássico com caixas e confiança por região.",
        "endpoint": "local",
        "modelo": "modelos locais",
    },
    "tesseract": {
        "descricao": "OCR CPU estável para texto impresso e datilografado.",
        "endpoint": "local",
        "modelo": "por",
    },
}


# Ordem de degradação quando o motor pedido não está no PATH (CPU-first).
ORDEM_FALLBACK = ("paddleocr", "tesseract", "easyocr", "kraken")


def motores_conhecidos() -> list[str]:
    return sorted([*_MOTORES, "ensemble", "auto"])


def motor_disponivel(nome: str) -> bool:
    """Consulta `available()` sem efeitos colaterais (sem download)."""
    if nome not in _MOTORES:
        return False
    return bool(cast(RecognitionEngine, _MOTORES[nome]()).available())


def listar_motores(config: object | None = None) -> list[dict[str, object]]:
    """Diretório compacto para a GUI: nome + disponibilidade + motivo.

    Motores de servidor (qwen3_vl/glm_ocr/olmocr) usam `available_com_config` com a
    configuração padrão: servidor no ar servindo modelo sem visão conta como
    indisponível, com o motivo explícito — em vez de falhar só no OCR.
    """
    saida: list[dict[str, object]] = []
    for nome in sorted(_MOTORES):
        motor = cast(RecognitionEngine, _MOTORES[nome]())
        verifica = getattr(motor, "available_com_config", None)
        if callable(verifica):
            if nome == "qwen3_vl":
                servidor_cfg = getattr(config, "qwen3vl", None)
            elif nome == "glm_ocr":
                servidor_cfg = getattr(config, "glmocr", None)
            elif nome == "deepseek_ocr2":
                servidor_cfg = getattr(config, "deepseekocr2", None)
            elif nome == "olmocr":
                servidor_cfg = getattr(config, "olmocr", None)
            else:
                servidor_cfg = None
            cfg = RecognitionConfig(
                engine=nome,
                base_url=str(getattr(servidor_cfg, "base_url", "") or ""),
                modelo=str(getattr(servidor_cfg, "model", "") or "best"),
                timeout_segundos=int(getattr(servidor_cfg, "timeout_seconds", 300) or 300),
                max_lado_px=int(getattr(servidor_cfg, "max_lado_px", 1024) or 1024),
            )
            disponivel = bool(verifica(cfg))
            motivo = ""
            if not disponivel:
                motivo = (
                    "servidor ativo com modelo sem visão"
                    if bool(motor.available())
                    else "servidor fora do ar"
                )
            info = dict(_MOTOR_INFO.get(nome, {}))
            if servidor_cfg is not None:
                info["endpoint"] = str(getattr(servidor_cfg, "base_url", info.get("endpoint", "")))
                info["modelo"] = str(getattr(servidor_cfg, "model", info.get("modelo", "")))
            saida.append({"nome": nome, "disponivel": disponivel, "motivo": motivo, **info})
        else:
            info = _MOTOR_INFO.get(nome, {})
            saida.append({"nome": nome, "disponivel": bool(motor.available()), "motivo": "", **info})
    return saida


def resolver_engine(pedido: str | None) -> tuple[str, str | None]:
    """Devolve (motor efetivo, aviso de fallback). `auto` escolhe o primeiro disponível."""
    if pedido in {None, "", "auto"}:
        for candidato in ORDEM_FALLBACK:
            if motor_disponivel(candidato):
                return candidato, None
        raise ValueError("Nenhum motor de OCR disponível neste host (tesseract/paddleocr/easyocr/kraken).")
    if pedido in _MOTORES and motor_disponivel(pedido):
        return pedido, None
    for candidato in ORDEM_FALLBACK:
        if motor_disponivel(candidato):
            return candidato, f"Motor {pedido} indisponível; usando {candidato}."
    raise ValueError(f"Motor {pedido!r} indisponível e nenhum fallback (tesseract/paddleocr/easyocr/kraken) no PATH.")


def criar_engine(nome: str, secundarios: list[RecognitionEngine] | None = None) -> RecognitionEngine:
    if nome == "ensemble":
        motores: list[RecognitionEngine] = secundarios or [
            TesseractEngine(),  # type: ignore[list-item]
            PdfTextEngine(),  # type: ignore[list-item]
        ]
        return EnsembleEngine(motores)
    try:
        return cast(RecognitionEngine, _MOTORES[nome]())
    except KeyError:
        raise ValueError(f"Motor desconhecido: {nome!r}. Motores: {', '.join(motores_conhecidos())}.") from None
