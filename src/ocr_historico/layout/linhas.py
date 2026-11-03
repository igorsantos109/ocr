"""Segmentação de linhas para manuscritos — Kraken (blla) + fallback OpenCV.

- Quando Kraken (kraken.lib.segmentation) está instalado e um modelo blla é
  encontrado, usa a segmentação oficial e retorna polígonos/caixas.
- Caso contrário, aplica um fallback leve baseado em projeção horizontal e
  contornos: não promete precisão de HTR, apenas preserva a interface PAGE-XML
  e o fluxo de auditoria. O fallback sempre marca `metodo="fallback"` para que a
  confiança seja penalizada e a linha vá para revisão.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

try:
    import cv2
    import numpy as np

    _TEM_CV2 = True
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    _TEM_CV2 = False


@dataclass(frozen=True)
class CaixaLinha:
    numero: int
    x: int
    y: int
    largura: int
    altura: int
    baseline: tuple[int, int, int, int] | None = None  # x1,y1,x2,y2 aproximado


@dataclass(frozen=True)
class SegmentacaoResultado:
    linhas: tuple[CaixaLinha, ...]
    metodo: str  # "kraken" | "fallback" | "kraken_indisponivel"
    aviso: str | None = None


def _tem_kraken() -> bool:
    return importlib.util.find_spec("kraken") is not None


def fallback_segmentar_linhas(imagem_path: Path | str) -> SegmentacaoResultado:
    """Segmentação conservadora por contornos, sem Kraken.

    - Converte para cinza, binariza OTSU, dilata horizontalmente e encontra
      contornos que representam linhas.
    - Filtra por altura mínima e largura mínima para evitar ruído.
    - Ordena por y e depois x (ordem de leitura simples topo→baixo).
    """
    caminho = Path(imagem_path)
    if not caminho.is_file():
        return SegmentacaoResultado(linhas=(), metodo="fallback", aviso=f"Imagem não encontrada: {caminho}")
    try:
        with Image.open(caminho) as img:
            largura, altura = img.size
            cinza = img.convert("L")
            if not _TEM_CV2:
                # sem OpenCV: devolve linha única cobrindo página (não quebra lote)
                return SegmentacaoResultado(
                    linhas=(CaixaLinha(numero=1, x=0, y=0, largura=largura, altura=altura),),
                    metodo="fallback",
                    aviso="OpenCV ausente; página tratada como linha única.",
                )
            arr = np.array(cinza)
            _, binaria = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            # dilatar horizontalmente para unir caracteres da mesma linha
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, largura // 40), 3))
            dilatada = cv2.dilate(binaria, kernel, iterations=1)
            contours, _ = cv2.findContours(dilatada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            caixas: list[tuple[int, int, int, int]] = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if h < max(8, altura // 80) or w < largura // 10:
                    continue
                # margem para não cortar descendentes
                y0 = max(0, y - 2)
                h0 = min(altura - y0, h + 4)
                caixas.append((x, y0, w, h0))
            if not caixas:
                return SegmentacaoResultado(
                    linhas=(CaixaLinha(numero=1, x=0, y=0, largura=largura, altura=altura),),
                    metodo="fallback",
                    aviso="Nenhuma linha detectada; página tratada como linha única.",
                )
            caixas.sort(key=lambda b: (b[1], b[0]))
            linhas = tuple(
                CaixaLinha(numero=i + 1, x=x, y=y, largura=w, altura=h)
                for i, (x, y, w, h) in enumerate(caixas)
            )
            return SegmentacaoResultado(linhas=linhas, metodo="fallback")
    except Exception as exc:  # noqa: BLE001 - nunca quebra lote
        return SegmentacaoResultado(linhas=(), metodo="fallback", aviso=f"Falha na segmentação fallback: {exc}")


def _kraken_segmentar(imagem_path: Path | str) -> SegmentacaoResultado | None:
    """Tenta segmentação via kraken.blla; retorna None se indisponível."""
    if not _tem_kraken():
        return None
    try:
        from PIL import Image as PILImage  # noqa: F401

        # procura modelo blla padrão em data/modelos/kraken
        raiz = Path(__file__).resolve().parents[3]
        candidatos = [
            raiz / "data" / "modelos" / "kraken" / "blla.mlmodel",
            raiz / "data" / "modelos" / "kraken" / "segmentation.mlmodel",
        ]
        modelo_path = next((p for p in candidatos if p.is_file()), None)
        if modelo_path is None:
            return None
        # tenta inferência (CPU)
        # Nota: kraken.blla.segment pode exigir torch; se falhar, cai no fallback
        try:
            from kraken import blla  # type: ignore[import-not-found]

            from kraken.lib import vgsl  # type: ignore[import-not-found]

            # Kraken 7 exige o objeto VGSL de segmentação; versões antigas
            # aceitavam o caminho diretamente.
            modelo = vgsl.TorchVGSLModel.load_model(str(modelo_path))
            with PILImage.open(imagem_path) as im:
                seg = blla.segment(im, model=modelo)  # type: ignore[attr-defined]
            # Kraken 7 retorna containers.Segmentation com BBoxLine/BaselineLine.
            linhas: list[CaixaLinha] = []
            entradas = getattr(seg, "lines", None) or (seg.get("lines", []) if isinstance(seg, dict) else [])
            for idx, entry in enumerate(entradas, start=1):
                bbox = getattr(entry, "bbox", None)
                if bbox and len(bbox) == 4:
                    x0, y0, x1, y1 = map(int, bbox)
                    x, y, w, h = x0, y0, max(1, x1 - x0), max(1, y1 - y0)
                else:
                    boundary = getattr(entry, "boundary", None)
                    if boundary is None and isinstance(entry, dict):
                        bbox = entry.get("bbox")
                        boundary = entry.get("boundary")
                    if bbox and len(bbox) == 4:
                        x0, y0, x1, y1 = map(int, bbox)
                        x, y, w, h = x0, y0, max(1, x1 - x0), max(1, y1 - y0)
                    elif boundary and len(boundary) >= 4:
                        xs = [p[0] for p in boundary]
                        ys = [p[1] for p in boundary]
                        x, y = int(min(xs)), int(min(ys))
                        w, h = max(1, int(max(xs) - x)), max(1, int(max(ys) - y))
                    else:
                        continue
                linhas.append(CaixaLinha(numero=idx, x=x, y=y, largura=w, altura=h))
            if linhas:
                return SegmentacaoResultado(linhas=tuple(linhas), metodo="kraken")
        except Exception:
            return None
        return None
    except Exception:
        return None


def segmentar_linhas(imagem_path: Path | str, preferencia: str = "kraken") -> SegmentacaoResultado:
    """Ponto de entrada único para o pipeline.

    - Se preferência é kraken e o motor está disponível, usa-o.
    - Caso contrário, retorna fallback conservador.
    - Nunca levanta; sempre retorna ao menos um SegmentacaoResultado.
    """
    if preferencia == "kraken":
        kraken_res = _kraken_segmentar(imagem_path)
        if kraken_res is not None:
            return kraken_res
        # kraken solicitado mas indisponível → fallback com aviso
        fallback = fallback_segmentar_linhas(imagem_path)
        aviso_extra = "Kraken/blla indisponível; usando fallback."
        aviso = f"{aviso_extra} {fallback.aviso or ''}".strip()
        return SegmentacaoResultado(linhas=fallback.linhas, metodo="fallback", aviso=aviso)
    return fallback_segmentar_linhas(imagem_path)
