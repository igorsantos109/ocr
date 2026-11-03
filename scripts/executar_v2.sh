#!/usr/bin/env bash
# Sobe o OCR Studio V2 (build de produção) para uso local.
# Uso: bash scripts/executar_v2.sh [--port 5199] [--no-build]
set -euo pipefail
cd "$(dirname "$0")/../frontend"

PORT="5199"
BUILD=true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --no-build) BUILD=false; shift;;
    -h|--help) echo "Uso: bash scripts/executar_v2.sh [--port 5199] [--no-build]"; exit 0;;
    *) echo "Opção desconhecida: $1" >&2; exit 2;;
  esac
done

export NPM_CONFIG_CACHE=/home/igor/ia-sh/OCR/.deps/npm-cache
export NPM_CONFIG_LOGLEVEL=error
if [[ "$BUILD" == true ]]; then
  env -u npm_config_allow_scripts npm run build
fi
exec env -u npm_config_allow_scripts ./node_modules/.bin/vite preview --host 127.0.0.1 --port "$PORT" --strictPort
