"""JSON completo de auditoria (schema_version 1.0)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def exportar_json(
    pasta: Path,
    base: str,
    documento: dict[str, Any],
    execucao: dict[str, Any],
    paginas: list[dict[str, Any]],
) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    carga = {
        "schema_version": "1.0",
        "documento": documento,
        "execucao": execucao,
        "paginas": paginas,
    }
    saida = pasta / f"{base}.json"
    saida.write_text(json.dumps(carga, ensure_ascii=False, indent=2), encoding="utf-8")
    return saida


def agora_iso() -> str:
    return datetime.now().astimezone().isoformat()
