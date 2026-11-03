"""Adaptadores locais de reconhecimento (Marco 2)."""

from .base import (
    LinhaRec,
    MotorIndisponivel,
    MotorPagina,
    RecognitionConfig,
    RecognitionEngine,
    ResultadoPagina,
)
from .factory import criar_engine, motores_conhecidos

__all__ = [
    "LinhaRec",
    "MotorIndisponivel",
    "MotorPagina",
    "RecognitionConfig",
    "RecognitionEngine",
    "ResultadoPagina",
    "criar_engine",
    "motores_conhecidos",
]
