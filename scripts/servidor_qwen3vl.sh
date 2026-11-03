#!/usr/bin/env bash
# Sobe o llama-server com Qwen3-VL-8B (visão real) para os motores
# `paddle_vl` e `olmocr` (ambos reconfigurados p/ :8082 em configs/).
# Local, sem downloads: usa o GGUF + mmproj já presentes em
# /mnt/RESERVA2/models/OCR/.
#
# Placa de vídeo: RX 580 (Polaris, GCN4) via Vulkan (RADV).
# - Por padrão roda em CPU-estável via LVP (lavaPipe) para garantir
#   100% funcional sem travar o driver amdgpu (evita D-state).
# - Use --gpu para tentar aceleração na RX 580 (requer GPU livre;
#   após hang em amdgpu_info_ioctl é necessário reboot).
#
# Uso: bash scripts/servidor_qwen3vl.sh [--port 8082] [--gpu|--cpu] [--model-dir DIR]
set -euo pipefail

PORT="8082"
MODEL_DIR="/mnt/RESERVA2/models/OCR"
GGUF="Qwen3VL-8B-Instruct-Q4_K_M.gguf"
MMPROJ="mmproj-Qwen3VL-8B-Instruct-F16.gguf"
ALIAS="Qwen3VL-8B-Instruct"
MODO="cpu"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --model-dir) MODEL_DIR="$2"; shift 2;;
    --gpu) MODO="gpu"; shift;;
    --cpu) MODO="cpu"; shift;;
    -h|--help)
      echo "Uso: bash scripts/servidor_qwen3vl.sh [--port 8082] [--gpu|--cpu] [--model-dir DIR]"
      echo "  --gpu  tenta Vulkan na RX 580 (placa de vídeo); pode travar se GPU em D-state"
      echo "  --cpu  força CPU estável via LVP (padrão, 100% funcional)"
      exit 0;;
    *) echo "Opção desconhecida: $1" >&2; exit 2;;
  esac
done

MODEL="$MODEL_DIR/$GGUF"
MMPROJ_F="$MODEL_DIR/$MMPROJ"

if ! command -v llama-server >/dev/null 2>&1; then
  echo "ERRO: llama-server não encontrado no PATH." >&2
  exit 1
fi
if [[ ! -f "$MODEL" ]]; then
  echo "ERRO: modelo não encontrado em $MODEL" >&2
  exit 1
fi
if [[ ! -f "$MMPROJ_F" ]]; then
  echo "ERRO: mmproj não encontrado em $MMPROJ_F (visão não funciona sem ele)." >&2
  exit 1
fi

# Verifica se há processos presos em D (amdgpu) que impedem Vulkan
if [[ "$MODO" == "gpu" ]]; then
  if ps -eo stat,wchan | grep -q "amdgpu"; then
    echo "AVISO: GPU em estado D (amdgpu_info_ioctl) detectada. Vulkan pode travar." >&2
    echo "       Reboot recomendado: sudo reboot  (ou: sudo bash -c 'echo 1 > /sys/bus/pci/devices/0000:04:00.0/reset' )" >&2
    echo "       Continuando com --gpu mesmo assim..." >&2
  fi
  echo "Servidor VL (Qwen3-VL-8B) — PLACA DE VÍDEO (Vulkan/RADV) em http://127.0.0.1:${PORT}"
  echo "Confira com: .venv/bin/ocrhist diagnosticar | grep -E 'olmOCR|PaddleOCR-VL'"
  # RX 580: tenta offload; se travar, use --cpu
  exec llama-server \
    -m "$MODEL" \
    --mmproj "$MMPROJ_F" \
    -a "$ALIAS" \
    --host 127.0.0.1 --port "$PORT" \
    -c 8192 --temp 0 -ngl 99 --mmproj-offload
else
  # CPU-estável: força LVP (Vulkan software) para não tocar no amdgpu
  # Isso garante 100% funcional no programa, mesmo com GPU travada.
  export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json
  export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/lvp_icd.json
  echo "Servidor VL (Qwen3-VL-8B) — CPU estável (LVP, sem placa) em http://127.0.0.1:${PORT}"
  echo "       Para usar a placa RX 580: bash scripts/servidor_qwen3vl.sh --gpu --port $PORT"
  echo "Confira com: .venv/bin/ocrhist diagnosticar | grep -E 'olmOCR|PaddleOCR-VL'"
  exec llama-server \
    -m "$MODEL" \
    --mmproj "$MMPROJ_F" \
    -a "$ALIAS" \
    --host 127.0.0.1 --port "$PORT" \
    -c 8192 --temp 0 -ngl 0 --no-mmproj-offload
fi
