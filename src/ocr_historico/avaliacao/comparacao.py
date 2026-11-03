"""Comparação de arquivos para a CLI avaliar."""

from __future__ import annotations

from pathlib import Path

from .metricas import ResultadoMetrica, calcular_cer, calcular_wer


def avaliar_arquivos(
    referencia: Path | str, hipotese: Path | str, normalizar: bool = False
) -> tuple[ResultadoMetrica, ResultadoMetrica]:
    ref = Path(referencia).read_text(encoding="utf-8")
    hyp = Path(hipotese).read_text(encoding="utf-8")
    return calcular_cer(ref, hyp, normalizar), calcular_wer(ref, hyp, normalizar)
