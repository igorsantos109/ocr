"""Exportação TSV compatível com os campos do Tesseract."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path


def exportar_tsv(pasta: Path, base: str, paginas: Iterable[dict]) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{base}.tsv"
    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter="\t")
        escritor.writerow(["page_num", "line_num", "left", "top", "width", "height", "conf", "text"])
        for pagina in paginas:
            for linha in pagina.get("linhas", []):
                escritor.writerow(
                    [
                        pagina.get("numero", ""),
                        linha.get("numero", ""),
                        linha.get("x", 0),
                        linha.get("y", 0),
                        linha.get("largura", 0),
                        linha.get("altura", 0),
                        "" if linha.get("confianca") is None else linha.get("confianca"),
                        linha.get("texto", ""),
                    ]
                )
    return destino
