.PHONY: instalar teste lint tipo diagnosticar

instalar:
	bash scripts/instalar.sh

teste:
	.venv/bin/python -m pytest

lint:
	.venv/bin/ruff check src tests

tipo:
	.venv/bin/mypy src/ocr_historico

diagnosticar:
	.venv/bin/ocrhist diagnosticar
