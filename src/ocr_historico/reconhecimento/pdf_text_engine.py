"""Extração direta de texto de PDF com camada textual (sem OCR visual)."""

from __future__ import annotations

from pathlib import Path

import fitz

from .base import LinhaRec, MotorIndisponivel, MotorPagina, RecognitionConfig, ResultadoPagina


class PdfTextEngine(MotorPagina):
    """Lê a camada textual do PDF preservando a página; sem confiança do motor."""

    name = "pdf_texto"

    def available(self) -> bool:
        return True

    def recognize_page(
        self, image_path: Path | str, config: RecognitionConfig, numero_pagina: int = 1
    ) -> ResultadoPagina:
        caminho = Path(image_path)
        if caminho.suffix.lower() != ".pdf":
            raise MotorIndisponivel("PdfTextEngine exige o PDF original como entrada.")
        try:
            with fitz.open(caminho) as doc:
                if numero_pagina < 1 or numero_pagina > doc.page_count:
                    raise MotorIndisponivel(f"Página {numero_pagina} fora do PDF.")
                texto = doc[numero_pagina - 1].get_text("text").strip()
        except MotorIndisponivel:
            raise
        except Exception as erro:
            raise MotorIndisponivel(f"Falha ao extrair texto do PDF: {erro}") from erro
        linhas = tuple(
            LinhaRec(numero=i, x=0, y=0, largura=0, altura=0, texto=parte, confianca=None)
            for i, parte in enumerate([trecho for trecho in texto.splitlines() if trecho.strip()], start=1)
        )
        return ResultadoPagina(
            texto_bruto=texto,
            linhas=linhas,
            confianca_media=None,
            motor=self.name,
            aviso="Texto extraído da camada do PDF; sem confiança do motor.",
        )
