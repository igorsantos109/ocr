#!/usr/bin/env bash
# Finaliza o OCR Studio e o servidor visual Paddle VL iniciado pela GUI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_PIDFILE="$ROOT/logs/ocr-web.pid"
VL_PIDFILE="$ROOT/logs/paddle-vl.pid"

parar_pidfile() {
  local pidfile="$1"
  local esperado="$2"
  [[ -s "$pidfile" ]] || return 0
  local pid cmd
  pid="$(tr -dc '0-9' < "$pidfile")"
  [[ -n "$pid" ]] || { rm -f "$pidfile"; return 0; }
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pidfile"
    return 0
  fi
  cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  if [[ "$esperado" == "VLM" ]]; then
    [[ "$cmd" == *Qwen3VL* || "$cmd" == *olmOCR* || "$cmd" == *servidor_qwen3vl.sh* || "$cmd" == *servidor_olmocr.sh* ]] || {
      echo "PID $pid não corresponde a um servidor VLM; não foi encerrado."
      rm -f "$pidfile"
      return 0
    }
  elif [[ "$cmd" != *"$esperado"* ]]; then
    echo "PID $pid não corresponde ao processo esperado; não foi encerrado."
    rm -f "$pidfile"
    return 0
  fi
  kill "$pid" 2>/dev/null || true
  for _ in {1..20}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
}

parar_processos() {
  local padrao="$1"
  local pids pid pai="$PPID" cmd alvos=""
  pids="$(pgrep -f "$padrao" 2>/dev/null || true)"
  for pid in $pids; do
    [[ "$pid" == "$$" || "$pid" == "$pai" ]] && continue
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    # O pgrep também pode encontrar o shell que contém o padrão no comando;
    # só aceitamos o executável real, nunca um shell/terminal chamador.
    if [[ "$padrao" == *ocrhist* ]]; then
      [[ "$cmd" == "$ROOT/.venv/bin/"* && "$cmd" == *"ocrhist web"* ]] || continue
    else
      [[ "$cmd" == */llama-server\ * && ("$cmd" == *Qwen3VL* || "$cmd" == *olmOCR*) && "$cmd" == *"--port 8082"* ]] || continue
    fi
    alvos+=" $pid"
  done
  for pid in $alvos; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in $alvos; do
    for _ in {1..12}; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
}

# Primeiro encerra o VLM; depois encerra a interface web. Os padrões também
# cobrem processos antigos sem pidfile, que podem manter a GUI desatualizada.
parar_pidfile "$VL_PIDFILE" "VLM"
parar_processos "llama-server.*Qwen3VL.*--port 8082"
parar_processos "llama-server.*olmOCR.*--port 8082"
parar_pidfile "$WEB_PIDFILE" "ocrhist web"
parar_processos "$ROOT/.venv/bin/ocrhist web"

if command -v notify-send >/dev/null 2>&1; then
  notify-send "OCR Studio" "Software finalizado." >/dev/null 2>&1 || true
fi
echo "OCR Studio finalizado."
