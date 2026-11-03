"""Utilidades de PDF via PyMuPDF: contagem, camada textual e renderização."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

LIMIAR_CHARS_CAMADA_TEXTUAL = 50


@dataclass(frozen=True)
class InfoPdf:
    paginas: int
    tem_texto: bool
    total_chars: int


def info_pdf(caminho: Path | str) -> InfoPdf:
    """Retorna número de páginas e se há camada textual utilizável."""
    total = 0
    with fitz.open(caminho) as doc:
        paginas = doc.page_count
        for pagina in doc:
            total += len(pagina.get_text("text").strip())
    return InfoPdf(
        paginas=paginas,
        tem_texto=total >= LIMIAR_CHARS_CAMADA_TEXTUAL,
        total_chars=total,
    )


def dimensoes_pdf_px(caminho: Path | str, dpi: int) -> list[tuple[int, int]]:
    """Dimensões em pixels de cada página no DPI pedido, sem renderizar."""
    with fitz.open(caminho) as doc:
        return [(round(pagina.rect.width * dpi / 72), round(pagina.rect.height * dpi / 72)) for pagina in doc]


def renderizar_pagina(caminho: Path | str, numero: int, dpi: int, destino: Path) -> Path:
    """Renderiza uma página (1-based) em PNG no DPI pedido.

    O PDF original nunca é modificado; a derivada é salva em `destino`.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(caminho) as doc:
        if numero < 1 or numero > doc.page_count:
            raise ValueError(f"Página {numero} fora do intervalo (1–{doc.page_count})")
        pagina = doc[numero - 1]
        pix = pagina.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
        pix.save(destino)
    return destino
