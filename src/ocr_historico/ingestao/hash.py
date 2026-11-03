"""SHA-256 por streaming, sem carregar o arquivo inteiro na memória."""

from __future__ import annotations

import hashlib
from pathlib import Path


def calcular_sha256(caminho: Path | str, bloco: int = 65536) -> str:
    caminho = Path(caminho)
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        while True:
            parte = arquivo.read(bloco)
            if not parte:
                break
            digest.update(parte)
    return digest.hexdigest()
