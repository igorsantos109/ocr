#!/usr/bin/env bash
# Alterna o painel web local do OCR Studio.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$ROOT/logs/ocr-web.pid"
LOGFILE="$ROOT/logs/ocr-web.log"
URL="http://127.0.0.1:7860"
OPEN_URL="$URL/?ocrstudio=$(date +%s)"

mkdir -p "$ROOT/logs"

ler_pid() {
  [[ -s "$PIDFILE" ]] || return 1
  local pid
  pid="$(tr -dc '0-9' < "$PIDFILE")"
  [[ -n "$pid" ]] || return 1
  if kill -0 "$pid" 2>/dev/null; then
    local cmd
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    if [[ "$cmd" == *"$ROOT/.venv/bin/ocrhist web"* ]]; then
      printf '%s\n' "$pid"
      return 0
    fi
  fi
  rm -f "$PIDFILE"
  return 1
}

if pid="$(ler_pid)" || [[ -s "$ROOT/logs/paddle-vl.pid" ]] || pgrep -f "$ROOT/.venv/bin/ocrhist web" >/dev/null 2>&1; then
  "$ROOT/scripts/finalizar_ocr.sh"
  exit 0
fi

cd "$ROOT"
nohup "$ROOT/scripts/executar_web.sh" --host 127.0.0.1 --port 7860 \
  >>"$LOGFILE" 2>&1 &
pid=$!
printf '%s\n' "$pid" > "$PIDFILE"

# Aguarda o servidor responder antes de abrir o painel no navegador.
for _ in {1..40}; do
  if command -v curl >/dev/null 2>&1 && curl -fsS "$URL" >/dev/null 2>&1; then
    if command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$OPEN_URL" >/dev/null 2>&1 &
    fi
    echo "OCR Studio ligado em $URL"
    exit 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$PIDFILE"
    echo "Falha ao iniciar o OCR Studio. Consulte: $LOGFILE" >&2
    exit 1
  fi
  sleep 0.25
done

echo "OCR Studio iniciado; o painel pode levar mais alguns segundos para responder."
echo "Registro: $LOGFILE"
