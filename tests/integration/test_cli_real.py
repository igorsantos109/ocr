"""Integração do Marco 0: diagnóstico real pela CLI instalada."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


@pytest.mark.integration
class TestDiagnosticoReal:
    def test_script_diagnostico_retorna_cero(self) -> None:
        resultado = subprocess.run(
            [".venv/bin/ocrhist", "diagnosticar"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert resultado.returncode == 0, resultado.stderr
        assert "Entrada padrão" in resultado.stdout
        assert "Banco SQLite" in resultado.stdout
