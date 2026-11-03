"""Métricas de avaliação textual."""

from .metricas import ResultadoMetrica, calcular_cer, calcular_wer

__all__ = ["ResultadoMetrica", "calcular_cer", "calcular_wer"]
