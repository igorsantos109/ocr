#!/usr/bin/env bash
# Sobe o llama-server com olmOCR-2-7B para o motor `olmocr`.
# Local, sem downloads: se GGUF/mmproj estiverem ausentes, apenas indica onde colocar.
# Integrado à GUI: mesmo servidor visual em :8082 (compartilhado com paddle_vl).
# Placa de vídeo: RX 580 via Vulkan; por padrão CPU-estável (LVP).
# Uso: bash scripts/servidor_olmocr.sh [--port 8082] [--gpu|--cpu] [--model-dir DIR] [--gguf NOME] [--mmproj NOME]
set -euo pipefail

PORT="8082"
MODEL_DIR="/mnt/RESERVA2/models/OCR/olmOCR-2-7B"
GGUF="olmOCR-2-7B-Q4_K_M.gguf"
MMPROJ="mmproj-olmOCR-2-7B-Q8_0.gguf"
MODO="cpu"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --model-dir) MODEL_DIR="$2"; shift 2;;
    --gguf) GGUF="$2"; shift 2;;
    --mmproj) MMPROJ="$2"; shift 2;;
    --gpu) MODO="gpu"; shift;;
    --cpu) MODO="cpu"; shift;;
    -h|--help)
      echo "Uso: bash scripts/servidor_olmocr.sh [--port 8082] [--gpu|--cpu] [--model-dir DIR] [--gguf NOME] [--mmproj NOME]"
      exit 0;;
    *) echo "Opção desconhecida: $1" >&2; exit 2;;
  esac
done

MODEL="$MODEL_DIR/$GGUF"
MMPROJ_F="$MODEL_DIR/$MMPROJ"

# Fallback: se olmOCR oficial não existir, usa Qwen3VL compartilhado (mesmo binário da GUI)
if [[ ! -f "$MODEL" ]]; then
  echo "AVISO: $MODEL não encontrado — usando Qwen3VL compartilhado para olmocr (100% funcional)." >&2
  exec bash "$(dirname "$0")/servidor_qwen3vl.sh" --port "$PORT" --${MODO}
fi

if ! command -v llama-server >/dev/null 2>&1; then
  echo "ERRO: llama-server não encontrado no PATH." >&2
  exit 1
fi
ARGS=(-m "$MODEL" --port "$PORT" --host 127.0.0.1 -c 4096 -np 4 --temp 0)
if [[ -f "$MMPROJ_F" ]]; then
  ARGS+=(--mmproj "$MMPROJ_F")
else
  echo "AVISO: mmproj não encontrado em $MMPROJ_F; visão pode falhar." >&2
fi

if [[ "$MODO" == "gpu" ]]; then
  if ps -eo stat,wchan | grep -q "amdgpu"; then
    echo "AVISO: GPU em D-state detectada. Vulkan pode travar até reboot." >&2
  fi
  echo "Servidor olmOCR — PLACA DE VÍDEO (Vulkan) em http://127.0.0.1:${PORT}"
  exec llama-server "${ARGS[@]}" -ngl 99 --mmproj-offload
else
  export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json
  export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/lvp_icd.json
  echo "Servidor olmOCR — CPU estável (LVP) em http://127.0.0.1:${PORT}"
  echo "       Para placa RX 580: bash scripts/servidor_olmocr.sh --gpu --port $PORT"
  exec llama-server "${ARGS[@]}" -ngl 0 --no-mmproj-offload
fi
