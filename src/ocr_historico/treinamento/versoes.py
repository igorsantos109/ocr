"""Registro simples de versões de modelos HTR (SQLite + manifest local)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def agora_iso() -> str:
    return datetime.now().astimezone().isoformat()


@dataclass(frozen=True)
class VersaoModelo:
    id: str
    modelo_path: str
    dataset: str
    epocas: int
    criado_em: str
    cer: float | None = None
    wer: float | None = None
    observacao: str | None = None


def registrar_versao(
    modelo: Path | str,
    dataset: Path | str,
    epocas: int = 0,
    cer: float | None = None,
    wer: float | None = None,
    observacao: str | None = None,
    registro: Path | str = Path("data/modelos/kraken/versoes.jsonl"),
) -> VersaoModelo:
    registro_path = Path(registro)
    registro_path.parent.mkdir(parents=True, exist_ok=True)
    versao = VersaoModelo(
        id=uuid.uuid4().hex[:8],
        modelo_path=str(modelo),
        dataset=str(dataset),
        epocas=epocas,
        criado_em=agora_iso(),
        cer=cer,
        wer=wer,
        observacao=observacao,
    )
    with registro_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(versao.__dict__, ensure_ascii=False) + "\n")
    return versao


def listar_versoes(registro: Path | str = Path("data/modelos/kraken/versoes.jsonl")) -> list[VersaoModelo]:
    p = Path(registro)
    if not p.is_file():
        return []
    versoes: list[VersaoModelo] = []
    for linha in p.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            d = json.loads(linha)
            versoes.append(VersaoModelo(**d))
        except Exception:
            continue
    return sorted(versoes, key=lambda v: v.criado_em, reverse=True)
