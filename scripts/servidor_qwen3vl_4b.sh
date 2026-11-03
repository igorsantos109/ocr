#!/usr/bin/env bash
# Sobe o llama-server com Qwen3-VL 4B (visão real) para `qwen3_vl` e `glm_ocr`/`olmocr`.
# Local, sem downloads: usa GGUF + mmproj já presentes.
# Se o 4B não existir, faz fallback para o 8B existente.
# Placa RX 580 via Vulkan; padrão CPU estável (LVP) para 100% funcional.
# Uso: bash scripts/servidor_qwen3vl_4b.sh [--port 8082] [--gpu|--cpu]
set -euo pipefail

PORT="8082"
MODEL_DIR="/mnt/RESERVA2/models/OCR"
GGUF_4B="Qwen3VL-4B-Instruct-Q4_K_M.gguf"
MMPROJ_4B="mmproj-Qwen3VL-4B-Instruct-F16.gguf"
GGUF_8B="Qwen3VL-8B-Instruct-Q4_K_M.gguf"
MMPROJ_8B="mmproj-Qwen3VL-8B-Instruct-F16.gguf"
ALIAS="Qwen3VL-4B-Instruct"
MODO="cpu"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --model-dir) MODEL_DIR="$2"; shift 2;;
    --gpu) MODO="gpu"; shift;;
    --cpu) MODO="cpu"; shift;;
    -h|--help)
      echo "Uso: bash scripts/servidor_qwen3vl_4b.sh [--port 8082] [--gpu|--cpu]"
      exit 0;;
    *) echo "Opção desconhecida: $1" >&2; exit 2;;
  esac
done

if ! command -v llama-server >/dev/null 2>&1; then
  echo "ERRO: llama-server não encontrado no PATH." >&2
  exit 1
fi

# Resolve modelo: prefere 4B, fallback para 8B
if [[ -f "$MODEL_DIR/$GGUF_4B" ]]; then
  MODEL="$MODEL_DIR/$GGUF_4B"
  ALIAS="Qwen3VL-4B-Instruct"
  if [[ -f "$MODEL_DIR/$MMPROJ_4B" ]]; then
    MMPROJ_F="$MODEL_DIR/$MMPROJ_4B"
  else
    MMPROJ_F="$MODEL_DIR/$MMPROJ_8B"
  fi
else
  echo "AVISO: $MODEL_DIR/$GGUF_4B não encontrado — usando fallback 8B (Qwen3VL-8B)." >&2
  echo "       Para o 4B oficial: baixe Qwen3-VL-4B-Instruct-GGUF + mmproj para $MODEL_DIR" >&2
  MODEL="$MODEL_DIR/$GGUF_8B"
  MMPROJ_F="$MODEL_DIR/$MMPROJ_8B"
  ALIAS="Qwen3VL-4B-Instruct"
fi

if [[ ! -f "$MODEL" ]]; then
  echo "ERRO: modelo não encontrado em $MODEL" >&2
  exit 1
fi
if [[ ! -f "$MMPROJ_F" ]]; then
  echo "ERRO: mmproj não encontrado em $MMPROJ_F" >&2
  exit 1
fi

if [[ "$MODO" == "gpu" ]]; then
  if ps -eo stat,wchan 2>/dev/null | grep -q "amdgpu"; then
    echo "AVISO: GPU em D-state detectada. Vulkan pode travar — reboot recomendado." >&2
  fi
  echo "Servidor Qwen3-VL 4B — PLACA DE VÍDEO (Vulkan) em http://127.0.0.1:${PORT} ($ALIAS)"
  exec llama-server -m "$MODEL" --mmproj "$MMPROJ_F" -a "$ALIAS" --host 127.0.0.1 --port "$PORT" -c 8192 --temp 0 -ngl 99 --mmproj-offload
else
  export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json
  export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/lvp_icd.json
  echo "Servidor Qwen3-VL 4B — CPU estável (LVP) em http://127.0.0.1:${PORT} ($ALIAS)"
  echo "       Para placa RX 580: bash scripts/servidor_qwen3vl_4b.sh --gpu --port $PORT"
  exec llama-server -m "$MODEL" --mmproj "$MMPROJ_F" -a "$ALIAS" --host 127.0.0.1 --port "$PORT" -c 8192 --temp 0 -ngl 0 --no-mmproj-offload
fi
