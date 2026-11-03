"""TXT bruto e diplomático por documento."""

from __future__ import annotations

from pathlib import Path


def exportar_txts(pasta: Path, base: str, brutos: list[str], diplomaticos: list[str]) -> dict[str, Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    bruto_path = pasta / f"{base}_bruto.txt"
    diplomatico_path = pasta / f"{base}_diplomatico.txt"
    bruto_path.write_text("\n\n".join(brutos) + "\n", encoding="utf-8")
    diplomatico_path.write_text("\n\n".join(diplomaticos) + "\n", encoding="utf-8")
    return {"bruto": bruto_path, "diplomatico": diplomatico_path}
