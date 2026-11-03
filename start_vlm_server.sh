#!/usr/bin/env bash
# Sobe o llama-server com PaddleOCR-VL-1.6 (GGUF baixado em ia-sh/models)
# Deixe este processo rodando em um terminal separado.
set -e
MODEL_DIR="/home/igor/ia-sh/models/PaddleOCR-VL-1.6"
MODEL="$MODEL_DIR/PaddleOCR-VL-1.6-GGUF.gguf"
MMPROJ="$MODEL_DIR/PaddleOCR-VL-1.6-GGUF-mmproj.gguf"

if [ ! -f "$MODEL" ]; then
  echo "ERRO: modelo nao encontrado em $MODEL"
  echo "Baixe de: https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6-GGUF"
  exit 1
fi

# -ngl 0 = CPU (sem GPU NVIDIA neste ambiente). Se tiver GPU, use -ngl 99.
# -np 4 deve coincidir com VLM_CONCURRENCY no notebook.
exec llama-server \
  -m "$MODEL" \
  --mmproj "$MMPROJ" \
  --host 127.0.0.1 --port 8081 \
  -c 16384 -np 4 --temp 0 -ngl 0
