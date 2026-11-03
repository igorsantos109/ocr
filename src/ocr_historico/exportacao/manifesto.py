"""Manifesto preservável dos produtos de um documento."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..ingestao.hash import calcular_sha256


def exportar_manifesto(
    pasta: Path | str,
    *,
    documento: dict[str, Any],
    paginas: list[dict[str, Any]],
    inventario: dict[str, Any] | None = None,
    preservacao: dict[str, Any] | None = None,
    artefatos: list[dict[str, Any]] | None = None,
    qualidade: dict[str, Any] | None = None,
) -> Path:
    """Escreve ``manifest.json`` sem alterar o manifesto JSON legado."""
    destino = Path(pasta)
    destino.mkdir(parents=True, exist_ok=True)
    catalogo = list(artefatos or [])
    conhecidos = {str(item.get("caminho")) for item in catalogo}
    for arquivo in sorted(destino.rglob("*")):
        if not arquivo.is_file() or arquivo.name == "manifest.json" or str(arquivo) in conhecidos:
            continue
        try:
            catalogo.append(
                {
                    "caminho": str(arquivo.relative_to(destino)),
                    "tamanho_bytes": arquivo.stat().st_size,
                    "sha256": calcular_sha256(arquivo),
                    "status": "gerado",
                }
            )
        except OSError:
            catalogo.append({"caminho": str(arquivo.relative_to(destino)), "status": "indisponivel"})
    carga = {
        "schema_version": "1.0",
        "criado_em": datetime.now().astimezone().isoformat(),
        "documento": documento,
        "paginas": paginas,
        "inventario": inventario,
        "preservacao": preservacao,
        "artefatos": catalogo,
        "qualidade": qualidade,
    }
    caminho = destino / "manifest.json"
    caminho.write_text(json.dumps(carga, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho
