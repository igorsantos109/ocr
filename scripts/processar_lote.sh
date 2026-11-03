#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/ativar_modelos.sh >/dev/null 2>&1 || true
exec .venv/bin/ocrhist processar "$@"
