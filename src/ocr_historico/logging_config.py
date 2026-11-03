"""Logging legível e opcionalmente serializado em arquivo."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now().astimezone().isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def configurar_logging(diretorio: Path | str | None = None, jsonl: bool = False) -> logging.Logger:
    logger = logging.getLogger("ocr_historico")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler: logging.Handler
    if diretorio is not None:
        pasta = Path(diretorio)
        pasta.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(pasta / "ocr_historico.log", encoding="utf-8")
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if jsonl else logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
