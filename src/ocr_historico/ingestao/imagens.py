"""Leitura de imagens e TIFF multipágina, com métricas leves de qualidade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

try:
    import cv2
    import numpy as np

    _TEM_CV2 = True
except ImportError:  # pragma: no cover - ambiente sem OpenCV
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    _TEM_CV2 = False

LIMIAR_LARGURA_BAIXA = 1000


@dataclass(frozen=True)
class InfoImagem:
    quadros: int
    largura: int
    altura: int
    dpi: int | None
    nitidez: float | None
    contraste: float | None
    resolucao_baixa: bool


def _metricas(caminho: Path) -> tuple[float | None, float | None]:
    if not _TEM_CV2:
        return None, None
    try:
        img = cv2.imread(str(caminho), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None, None
        nitidez = float(cv2.Laplacian(img, cv2.CV_64F).var())
        contraste = float(np.std(img))
        return nitidez, contraste
    except Exception:
        return None, None


def info_imagem(caminho: Path | str) -> InfoImagem:
    """Descreve uma imagem; TIFF multipágina conta cada quadro como página."""
    caminho = Path(caminho)
    with Image.open(caminho) as img:
        quadros = getattr(img, "n_frames", 1)
        largura, altura = img.size
        dpi_info = img.info.get("dpi")
        dpi = round(dpi_info[0]) if isinstance(dpi_info, tuple) and dpi_info else None
    nitidez, contraste = _metricas(caminho)
    return InfoImagem(
        quadros=quadros,
        largura=largura,
        altura=altura,
        dpi=dpi,
        nitidez=nitidez,
        contraste=contraste,
        resolucao_baixa=min(largura, altura) < LIMIAR_LARGURA_BAIXA,
    )
