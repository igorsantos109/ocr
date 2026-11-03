#!/usr/bin/env bash
# Sobe o llama-server com PaddleOCR-VL-1.6 para o motor `paddle_vl`.
# Local, sem downloads: se o GGUF estiver ausente, apenas indica a URL.
# Uso: bash scripts/servidor_vl.sh [--port 8081] [--model-dir DIR]
set -euo pipefail

PORT="8081"
MODEL_DIR="/mnt/RESERVA2/models/OCR/PaddleOCR-VL-1.6"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --model-dir) MODEL_DIR="$2"; shift 2;;
    -h|--help)
      echo "Uso: bash scripts/servidor_vl.sh [--port 8081] [--model-dir DIR]"
      exit 0;;
    *) echo "Opção desconhecida: $1" >&2; exit 2;;
  esac
done

MODEL="$MODEL_DIR/PaddleOCR-VL-1.6-GGUF.gguf"
MMPROJ="$MODEL_DIR/PaddleOCR-VL-1.6-GGUF-mmproj.gguf"

if ! command -v llama-server >/dev/null 2>&1; then
  echo "ERRO: llama-server não encontrado no PATH." >&2
  exit 1
fi
if [[ ! -f "$MODEL" ]]; then
  echo "ERRO: modelo não encontrado em $MODEL" >&2
  echo "Baixe de: https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6-GGUF" >&2
  echo "(coloque o .gguf e o -mmproj em $MODEL_DIR; nada é baixado sozinho)" >&2
  exit 1
fi
if [[ ! -f "$MMPROJ" ]]; then
  echo "AVISO: mmproj não encontrado em $MMPROJ; visão pode falhar." >&2
fi

echo "Servidor PaddleOCR-VL em http://127.0.0.1:${PORT} (Ctrl+C para encerrar)"
echo "Confira com: .venv/bin/ocrhist diagnosticar | grep PaddleOCR-VL"
# -ngl 0 = CPU. Com GPU NVIDIA, troque para -ngl 99.
exec llama-server \
  -m "$MODEL" \
  --mmproj "$MMPROJ" \
  --host 127.0.0.1 --port "$PORT" \
  -c 16384 -np 4 --temp 0 -ngl 0
