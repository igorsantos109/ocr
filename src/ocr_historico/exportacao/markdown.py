"""Markdown estruturado por documento."""

from __future__ import annotations

from pathlib import Path


def exportar_markdown(pasta: Path, base: str, titulo: str, diplomaticos: list[str]) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    partes = [f"# {titulo}", ""]
    for numero, texto in enumerate(diplomaticos, start=1):
        partes.append(f"## Página {numero}")
        partes.append("")
        partes.append(texto if texto.strip() else "*[página sem texto reconhecido]*")
        partes.append("")
    saida = pasta / f"{base}.md"
    saida.write_text("\n".join(partes), encoding="utf-8")
    return saida
