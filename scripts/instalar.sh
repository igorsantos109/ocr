#!/usr/bin/env bash
set -euo pipefail

CRIAR_LINKS=false
if [[ "${1:-}" == "--criar-links-desktop" ]]; then
  CRIAR_LINKS=true
elif [[ $# -gt 0 ]]; then
  echo "Uso: bash scripts/instalar.sh [--criar-links-desktop]" >&2
  exit 2
fi

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "AVISO: instalação projetada para Linux; continuando sem instalar pacotes de sistema."
fi
if command -v apt >/dev/null 2>&1; then
  echo "Dependências de sistema sugeridas (não serão instaladas automaticamente):"
  echo "  sudo apt install tesseract-ocr tesseract-ocr-por poppler-utils"
else
  echo "AVISO: apt não encontrado; instale Tesseract e Poppler pelo gerenciador da distribuição."
fi

PYTHON="${PYTHON:-python3}"
"$PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("É necessário Python 3.11 ou superior.")
PY

if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'

if [[ "$CRIAR_LINKS" == true ]]; then
  mkdir -p "$HOME/Desktop/OCRENTRADA" "$HOME/Desktop/OCRSAIDA"
  ln -sfn "$HOME/Desktop/OCRENTRADA" data/entrada
  ln -sfn "$HOME/Desktop/OCRSAIDA" output/OCRSAIDA
  echo "Links para Desktop criados/atualizados mediante opção explícita."
fi

.venv/bin/ocrhist diagnosticar
echo "Instalação concluída. Componentes opcionais ausentes não impedem o Marco 0."
