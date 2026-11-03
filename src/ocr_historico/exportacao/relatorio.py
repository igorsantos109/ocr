"""Relatórios HTML e CSV da fila de baixa confiança."""

from __future__ import annotations

import csv
import html
from collections.abc import Iterable
from pathlib import Path


def exportar_baixa_confianca(pasta: Path, base: str, paginas: Iterable[dict], limiar: float) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "baixa_confianca.csv"
    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(["pagina", "linha", "confianca", "prioridade", "texto"])
        for pagina in paginas:
            for linha in pagina.get("linhas", []):
                conf = linha.get("confianca")
                if conf is not None and float(conf) < limiar:
                    escritor.writerow(
                        [
                            pagina.get("numero"),
                            linha.get("numero"),
                            conf,
                            linha.get("prioridade", "alta"),
                            linha.get("texto", ""),
                        ]
                    )
    return destino


def exportar_relatorio_html(
    pasta: Path, base: str, nome: str, paginas: Iterable[dict], status: str, limiar: float
) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    paginas_lista = list(paginas)
    linhas = [
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Relatório OCR</title><style>body{font-family:system-ui;max-width:72rem;margin:auto;padding:1rem}"
        "table{width:100%;border-collapse:collapse}td,th{padding:.4rem;border-bottom:1px solid #8885}"
        ".baixa{background:#ffd6d6}</style></head><body>",
        f"<h1>Relatório: {html.escape(nome)}</h1><p>Status: <b>{html.escape(status)}</b> · limiar: {limiar}</p>",
        "<table><thead><tr><th>Página</th><th>Linha</th><th>Confiança</th><th>Prioridade</th><th>Texto</th></tr></thead><tbody>",
    ]
    total = 0
    revisao = 0
    for pagina in paginas_lista:
        for linha in pagina.get("linhas", []):
            total += 1
            conf = linha.get("confianca")
            baixa = conf is None or float(conf) < limiar
            revisao += int(baixa)
            classe = " class='baixa'" if baixa else ""
            conf_texto = "—" if conf is None else str(conf)
            linhas.append(
                f"<tr{classe}><td>{pagina.get('numero')}</td><td>{linha.get('numero')}</td>"
                f"<td>{conf_texto}</td><td>{html.escape(str(linha.get('prioridade', 'baixa')))}</td>"
                f"<td>{html.escape(str(linha.get('texto', '')))}</td></tr>"
            )
    linhas.extend(
        [
            "</tbody></table>",
            f"<p>{revisao} de {total} linha(s) na fila de revisão.</p>",
            "</body></html>",
        ]
    )
    destino = pasta / f"{base}_relatorio.html"
    destino.write_text("\n".join(linhas), encoding="utf-8")
    return destino
