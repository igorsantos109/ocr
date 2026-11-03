"""Fixtures compartilhadas do Marco 0."""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def raiz_projeto() -> Path:
    return RAIZ


@pytest.fixture
def diretorio_tmp(tmp_path: Path) -> Path:
    return tmp_path
