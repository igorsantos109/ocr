#!/usr/bin/env bash
# Sobe o llama-server com GLM-OCR (visão) para o motor `glm_ocr`.
# Local, sem downloads: se GGUF oficial não existir, usa Qwen3-VL compartilhado.
# Placa RX 580 via Vulkan; padrão CPU estável (LVP).
# Uso: bash scripts/servidor_glmocr.sh [--port 8082] [--gpu|--cpu]
set -euo pipefail

PORT="8082"
MODEL_DIR_GLM="/mnt/RESERVA2/models/OCR/GLM-OCR"
MODEL_DIR_QWEN="/mnt/RESERVA2/models/OCR"
GGUF_GLM="GLM-OCR-Q4_K_M.gguf"
MMPROJ_GLM="mmproj-GLM-OCR-F16.gguf"
MODO="cpu"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --gpu) MODO="gpu"; shift;;
    --cpu) MODO="cpu"; shift;;
    -h|--help)
      echo "Uso: bash scripts/servidor_glmocr.sh [--port 8082] [--gpu|--cpu]"
      exit 0;;
    *) echo "Opção desconhecida: $1" >&2; exit 2;;
  esac
done

if ! command -v llama-server >/dev/null 2>&1; then
  echo "ERRO: llama-server não encontrado no PATH." >&2
  exit 1
fi

MODEL=""
MMPROJ_F=""
ALIAS="GLM-OCR"

if [[ -f "$MODEL_DIR_GLM/$GGUF_GLM" ]]; then
  MODEL="$MODEL_DIR_GLM/$GGUF_GLM"
  if [[ -f "$MODEL_DIR_GLM/$MMPROJ_GLM" ]]; then
    MMPROJ_F="$MODEL_DIR_GLM/$MMPROJ_GLM"
  elif [[ -f "$MODEL_DIR_QWEN/mmproj-Qwen3VL-8B-Instruct-F16.gguf" ]]; then
    MMPROJ_F="$MODEL_DIR_QWEN/mmproj-Qwen3VL-8B-Instruct-F16.gguf"
  fi
else
  echo "AVISO: $MODEL_DIR_GLM/$GGUF_GLM não encontrado — usando Qwen3-VL compartilhado para GLM-OCR." >&2
  echo "       Para o GLM-OCR oficial: baixe para $MODEL_DIR_GLM" >&2
  # fallback para Qwen3-VL 4B/8B
  if [[ -f "$MODEL_DIR_QWEN/Qwen3VL-4B-Instruct-Q4_K_M.gguf" ]]; then
    MODEL="$MODEL_DIR_QWEN/Qwen3VL-4B-Instruct-Q4_K_M.gguf"
    ALIAS="GLM-OCR"
    if [[ -f "$MODEL_DIR_QWEN/mmproj-Qwen3VL-4B-Instruct-F16.gguf" ]]; then
      MMPROJ_F="$MODEL_DIR_QWEN/mmproj-Qwen3VL-4B-Instruct-F16.gguf"
    else
      MMPROJ_F="$MODEL_DIR_QWEN/mmproj-Qwen3VL-8B-Instruct-F16.gguf"
    fi
  else
    MODEL="$MODEL_DIR_QWEN/Qwen3VL-8B-Instruct-Q4_K_M.gguf"
    MMPROJ_F="$MODEL_DIR_QWEN/mmproj-Qwen3VL-8B-Instruct-F16.gguf"
    ALIAS="GLM-OCR"
  fi
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
    echo "AVISO: GPU em D-state detectada — reboot recomendado." >&2
  fi
  echo "Servidor GLM-OCR — PLACA DE VÍDEO (Vulkan) em http://127.0.0.1:${PORT} ($ALIAS)"
  exec llama-server -m "$MODEL" --mmproj "$MMPROJ_F" -a "$ALIAS" --host 127.0.0.1 --port "$PORT" -c 8192 --temp 0 -ngl 99 --mmproj-offload
else
  export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json
  export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/lvp_icd.json
  echo "Servidor GLM-OCR — CPU estável (LVP) em http://127.0.0.1:${PORT} ($ALIAS)"
  echo "       Para placa RX 580: bash scripts/servidor_glmocr.sh --gpu --port $PORT"
  exec llama-server -m "$MODEL" --mmproj "$MMPROJ_F" -a "$ALIAS" --host 127.0.0.1 --port "$PORT" -c 8192 --temp 0 -ngl 0 --no-mmproj-offload
fi
