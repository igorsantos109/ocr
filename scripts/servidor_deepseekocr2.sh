#!/usr/bin/env bash
# Sobe o llama-server com DeepSeek-OCR-2 (visão) para o motor `deepseek_ocr2`.
# Local, sem downloads: exige GGUF + mmproj em /mnt/RESERVA2/models/OCR/DeepSeek-OCR-2.
# Placa RX 580 via Vulkan; padrão CPU estável (LVP).
# Uso: bash scripts/servidor_deepseekocr2.sh [--port 8084] [--gpu|--cpu] [--gguf ARQ]
set -euo pipefail

PORT="8084"
MODEL_DIR_DS="/mnt/RESERVA2/models/OCR/DeepSeek-OCR-2"
# q8_0 é o padrão: o Q4_K_M (MoE) comete erros de leitura e entra em loop;
# o q8_0 transcreve bem e continua rápido. Use --gguf para trocar.
GGUF_DS="deepseek-ocr-2-q8_0.gguf"
MMPROJ_DS="mmproj-deepseek-ocr-2-q8_0.gguf"
MODO="cpu"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --gguf) GGUF_DS="$2"; shift 2;;
    --gpu) MODO="gpu"; shift;;
    --cpu) MODO="cpu"; shift;;
    -h|--help)
      echo "Uso: bash scripts/servidor_deepseekocr2.sh [--port 8084] [--gpu|--cpu] [--gguf ARQ]"
      exit 0;;
    *) echo "Opção desconhecida: $1" >&2; exit 2;;
  esac
done

if ! command -v llama-server >/dev/null 2>&1; then
  echo "ERRO: llama-server não encontrado no PATH." >&2
  exit 1
fi

MODEL="$MODEL_DIR_DS/$GGUF_DS"
MMPROJ_F="$MODEL_DIR_DS/$MMPROJ_DS"
ALIAS="DeepSeek-OCR-2"

if [[ ! -f "$MODEL" ]]; then
  echo "ERRO: modelo não encontrado em $MODEL" >&2
  echo "      Baixe explicitamente (uma vez) com:" >&2
  echo "        hf download sabafallah/DeepSeek-OCR-2-GGUF deepseek-ocr-2-q8_0.gguf \\" >&2
  echo "          mmproj-deepseek-ocr-2-q8_0.gguf --local-dir $MODEL_DIR_DS" >&2
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
  echo "Servidor DeepSeek-OCR-2 — PLACA DE VÍDEO (Vulkan) em http://127.0.0.1:${PORT} ($ALIAS)"
  exec llama-server -m "$MODEL" --mmproj "$MMPROJ_F" -a "$ALIAS" --host 127.0.0.1 --port "$PORT" -c 8192 --temp 0 -fa off -ngl 99 --mmproj-offload
else
  export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json
  export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/lvp_icd.json
  echo "Servidor DeepSeek-OCR-2 — CPU estável (LVP) em http://127.0.0.1:${PORT} ($ALIAS)"
  echo "       Para placa RX 580: bash scripts/servidor_deepseekocr2.sh --gpu --port $PORT"
  exec llama-server -m "$MODEL" --mmproj "$MMPROJ_F" -a "$ALIAS" --host 127.0.0.1 --port "$PORT" -c 8192 --temp 0 -fa off -ngl 0 --no-mmproj-offload
fi
