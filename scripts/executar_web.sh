#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# O servidor web não deve bloquear a abertura da GUI baixando modelos opcionais.
# A preparação completa continua disponível ao chamar ativar_modelos.sh diretamente.
export OCRHIST_ATIVAR_SOMENTE_AMBIENTE=1
source scripts/ativar_modelos.sh >/dev/null 2>&1 || true
unset OCRHIST_ATIVAR_SOMENTE_AMBIENTE
exec .venv/bin/ocrhist web "$@"
