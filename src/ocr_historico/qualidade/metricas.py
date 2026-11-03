"""Métricas de qualidade de imagem, sempre conservadoras sem OpenCV."""

from __future__ import annotations

from dataclasses import dataclass, field
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

LIMIAR_NITIDEZ_BAIXA = 40.0
LIMIAR_CONTRASTE_BAIXO = 12.0
LIMIAR_LARGA_BAIXA = 1000


@dataclass(frozen=True)
class MetricasQualidade:
    largura: int
    altura: int
    resolucao_efetiva: int
    dpi: int | None
    nitidez: float | None
    contraste: float | None
    luminosidade: float | None
    area_escura: float | None
    paginas_vazias: bool = False
    muito_clara: bool = False
    muito_escura: bool = False
    desfocada: bool = False
    baixa_resolucao: bool = False
    flags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def score(self) -> float | None:
        if self.nitidez is None or self.contraste is None:
            return None
        pontos = 1.0
        if self.desfocada:
            pontos -= 0.35
        if self.baixa_resolucao:
            pontos -= 0.25
        if self.muito_clara or self.muito_escura:
            pontos -= 0.2
        nitidez_ok = self.nitidez >= LIMIAR_NITIDEZ_BAIXA
        contraste_ok = self.contraste >= LIMIAR_CONTRASTE_BAIXO
        if not nitidez_ok:
            pontos -= 0.2
        if not contraste_ok:
            pontos -= 0.2
        return round(max(0.0, min(1.0, pontos)), 3)

    @property
    def baixa(self) -> bool:
        return bool(self.flags)

    def to_dict(self) -> dict[str, object]:
        return {
            "largura": self.largura,
            "altura": self.altura,
            "resolucao_efetiva": self.resolucao_efetiva,
            "dpi": self.dpi,
            "nitidez": self.nitidez,
            "contraste": self.contraste,
            "luminosidade": self.luminosidade,
            "area_escura": self.area_escura,
            "score": self.score,
            "flags": list(self.flags),
        }


def avaliar_imagem(caminho: Path | str, dpi: int | None = None) -> MetricasQualidade:
    """Mede indicadores de qualidade de uma imagem de página."""
    caminho = Path(caminho)
    with Image.open(caminho) as img:
        largura, altura = img.size
        dpi_info = dpi or (round(img.info["dpi"][0]) if isinstance(img.info.get("dpi"), tuple) else None)
    flags: list[str] = []
    nitidez: float | None
    contraste: float | None
    luminosidade: float | None
    area_escura: float | None
    if _TEM_CV2:
        cinza = cv2.imread(str(caminho), cv2.IMREAD_GRAYSCALE)
        if cinza is None:
            return MetricasQualidade(largura, altura, min(largura, altura), dpi_info, None, None, None, None)
        nitidez = float(cv2.Laplacian(cinza, cv2.CV_64F).var())
        contraste = float(np.std(cinza))
        luminosidade = float(np.mean(cinza))
        area_escura = float(np.mean(cinza < 128))
        if luminosidade > 245:
            flags.append("muito_clara")
        if luminosidade < 40:
            flags.append("muito_escura")
        if nitidez < LIMIAR_NITIDEZ_BAIXA:
            flags.append("desfocada")
        if contraste < LIMIAR_CONTRASTE_BAIXO:
            flags.append("contraste_baixo")
        if area_escura < 0.001:
            flags.append("pagina_vazia")
    else:
        nitidez = contraste = luminosidade = area_escura = None
        flags.append("sem_opencv")
    resolucao_efetiva = min(largura, altura)
    if resolucao_efetiva < LIMIAR_LARGA_BAIXA:
        flags.append("baixa_resolucao")
    return MetricasQualidade(
        largura=largura,
        altura=altura,
        resolucao_efetiva=resolucao_efetiva,
        dpi=dpi_info,
        nitidez=nitidez,
        contraste=contraste,
        luminosidade=luminosidade,
        area_escura=area_escura,
        paginas_vazias="pagina_vazia" in flags,
        muito_clara="muito_clara" in flags,
        muito_escura="muito_escura" in flags,
        desfocada="desfocada" in flags,
        baixa_resolucao="baixa_resolucao" in flags,
        flags=tuple(flags),
    )