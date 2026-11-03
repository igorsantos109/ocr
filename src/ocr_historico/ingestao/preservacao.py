"""Cópia opcional e verificável dos arquivos originais."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .hash import calcular_sha256
from .inventario import ItemInventario


@dataclass(frozen=True)
class ArtefatoPreservado:
    origem: str
    destino: str | None
    sha256: str
    copiado: bool
    verificado: bool


def preservar_original(
    item: ItemInventario,
    raiz_destino: Path | str,
    sha256: str | None = None,
    *,
    modo: str = "copy",
    sobrescrever: bool = False,
    verificar_hash: bool = True,
) -> ArtefatoPreservado:
    """Preserva um arquivo sem alterar a origem, com escrita atômica."""
    origem = Path(item.caminho)
    digest = sha256 or item.sha256 or calcular_sha256(origem)
    if modo == "none":
        return ArtefatoPreservado(str(origem), None, digest, False, True)
    raiz = Path(raiz_destino)
    if modo == "content_addressed":
        destino = raiz / "sha256" / digest[:2] / digest / origem.name
    else:
        relativo = Path(item.caminho_relativo) if item.caminho_relativo else Path(origem.name)
        destino = raiz / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    verificado = destino.is_file() and (not verificar_hash or calcular_sha256(destino) == digest)
    if verificado and not sobrescrever:
        return ArtefatoPreservado(str(origem), str(destino), digest, False, True)
    parcial = destino.with_name(destino.name + ".part")
    try:
        if parcial.exists():
            parcial.unlink()
        shutil.copyfile(origem, parcial)
        if verificar_hash and calcular_sha256(parcial) != digest:
            raise OSError(f"Hash divergente ao preservar {origem}")
        os.replace(parcial, destino)
    finally:
        if parcial.exists():
            parcial.unlink()
    return ArtefatoPreservado(str(origem), str(destino), digest, True, True)
