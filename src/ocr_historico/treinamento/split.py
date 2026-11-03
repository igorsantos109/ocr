"""Divisão determinística por grupo para evitar vazamento documental."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def dividir_manifesto(
    caminho: Path | str,
    destino: Path | str,
    proporcoes: tuple[float, float, float] = (0.8, 0.1, 0.1),
    grupo: str = "documento",
) -> dict[str, int]:
    """Divide registros por documento/escrevente, nunca linhas aleatórias.

    Registros sem o grupo solicitado usam `documento`; grupos são ordenados
    lexicalmente para que a divisão seja reprodutível.
    """
    if abs(sum(proporcoes) - 1.0) > 1e-6 or any(p < 0 for p in proporcoes):
        raise ValueError("proporções devem ser não negativas e somar 1")
    if grupo not in {"documento", "escrevente"}:
        raise ValueError("grupo deve ser documento ou escrevente")
    manifesto = Path(caminho)
    if manifesto.is_dir():
        manifesto = manifesto / "manifest.jsonl"
    registros: list[dict[str, Any]] = [
        json.loads(linha) for linha in manifesto.read_text(encoding="utf-8").splitlines() if linha.strip()
    ]
    grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for registro in registros:
        chave = str(registro.get(grupo) or registro.get("documento") or "desconhecido")
        grupos[chave].append(registro)
    nomes = sorted(grupos)
    total_grupos = len(nomes)
    cortes = (round(total_grupos * proporcoes[0]), round(total_grupos * (proporcoes[0] + proporcoes[1])))
    conjuntos = {
        "treino": nomes[: cortes[0]],
        "validacao": nomes[cortes[0] : cortes[1]],
        "teste": nomes[cortes[1] :],
    }
    base = Path(destino)
    contagem: dict[str, int] = {}
    for nome, chaves in conjuntos.items():
        pasta = base / nome
        pasta.mkdir(parents=True, exist_ok=True)
        registros_saida = [item for chave in chaves for item in grupos[chave]]
        (pasta / "manifest.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in registros_saida),
            encoding="utf-8",
        )
        contagem[nome] = len(registros_saida)
    return contagem
