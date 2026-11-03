"""Exportação hOCR simples com regiões e linhas auditáveis."""

from __future__ import annotations

import html
from collections.abc import Iterable
from pathlib import Path


def exportar_hocr(pasta: Path, base: str, paginas: Iterable[dict]) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    linhas = ['<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"></head><body>']
    for pagina in paginas:
        numero = pagina.get("numero", 0)
        largura = pagina.get("qualidade", {}).get("largura") or 0
        altura = pagina.get("qualidade", {}).get("altura") or 0
        linhas.append(f'<div class="ocr_page" id="page_{numero}" title="bbox 0 0 {largura} {altura}">')
        for linha in pagina.get("linhas", []):
            x = linha.get("x", 0)
            y = linha.get("y", 0)
            w = linha.get("largura", 0)
            h = linha.get("altura", 0)
            conf = linha.get("confianca")
            conf_txt = "" if conf is None else f"; x_wconf {round(float(conf) * 100)}"
            texto = html.escape(str(linha.get("texto", "")))
            linhas.append(
                f'<span class="ocr_line" id="line_{numero}_{linha.get("numero", 0)}" '
                f'title="bbox {x} {y} {x + w} {y + h}{conf_txt}">{texto}</span><br>'
            )
        linhas.append("</div>")
    linhas.append("</body></html>")
    destino = pasta / f"{base}.hocr"
    destino.write_text("\n".join(linhas), encoding="utf-8")
    return destino
