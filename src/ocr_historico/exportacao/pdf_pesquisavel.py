"""PDF pesquisável via OCRmyPDF opcional ou fallback PyMuPDF local."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

import fitz
from PIL import Image


def _texto_pagina(pagina: dict) -> str:
    return str(pagina.get("texto_diplomatico") or pagina.get("texto_bruto") or "")


def exportar_pdf_pesquisavel(
    pasta: Path,
    base: str,
    original: Path | str,
    paginas: Iterable[dict],
) -> tuple[Path | None, str]:
    """Tenta OCRmyPDF apenas quando instalado; fallback não envia nada à rede."""
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{base}_pesquisavel.pdf"
    original_path = Path(original)
    if shutil.which("ocrmypdf") and original_path.suffix.lower() == ".pdf":
        processo = subprocess.run(
            ["ocrmypdf", "--skip-text", str(original_path), str(destino)],
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        if processo.returncode == 0 and destino.is_file():
            return destino, "ocrmypdf"
    paginas_lista = list(paginas)
    try:
        with fitz.open() as saida:
            for item in paginas_lista:
                imagem = item.get("imagem_original") or item.get("imagem_pre_processada")
                if not imagem or not Path(imagem).is_file():
                    continue
                with Image.open(imagem) as img:
                    largura, altura = img.size
                page = saida.new_page(width=largura, height=altura)
                page.insert_image(page.rect, filename=str(imagem))
                texto = _texto_pagina(item)
                if texto:
                    # Caixa ampla + render_mode=3 mantém o texto invisível, mas pesquisável.
                    caixa = fitz.Rect(1, 1, max(2, largura - 1), max(2, altura - 1))
                    page.insert_textbox(caixa, texto, fontsize=8, render_mode=3)
            if saida.page_count:
                saida.save(destino)
                return destino, "pymupdf_fallback"
    except (OSError, ValueError, fitz.FileDataError):
        return None, "indisponível"
    return None, "indisponível"
