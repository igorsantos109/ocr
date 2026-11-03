#!/usr/bin/env bash
# Ativa os motores locais instalados em espaço de usuário (sem root).
# Uso: source scripts/ativar_modelos.sh
# Efeito: PATH + LD_LIBRARY_PATH + TESSDATA_PREFIX para o Tesseract 5.5
# instalado em .deps/tess, e baixa por.traineddata (best) se ausente.
# Idempotente: pode ser executado várias vezes.
_ATIVAR_RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$_ATIVAR_RAIZ/.deps/tess/usr/bin:$PATH"
export LD_LIBRARY_PATH="$_ATIVAR_RAIZ/.deps/tess/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export TESSDATA_PREFIX="$_ATIVAR_RAIZ/.deps/tess/usr/share/tesseract-ocr/5/tessdata"
# HOME é somente-leitura neste host: caches e dados de modelos no workspace.
export XDG_CACHE_HOME="$_ATIVAR_RAIZ/.deps/cache"
export XDG_DATA_HOME="$_ATIVAR_RAIZ/.deps/share"
export EASYOCR_MODULE_PATH="$_ATIVAR_RAIZ/.deps/models/easyocr"
mkdir -p "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$EASYOCR_MODULE_PATH" 2>/dev/null || true
if [[ "${OCRHIST_ATIVAR_SOMENTE_AMBIENTE:-0}" != "1" ]]; then
if [[ ! -s "$_ATIVAR_RAIZ/data/modelos/tesseract/por.traineddata" ]]; then
  mkdir -p "$_ATIVAR_RAIZ/data/modelos/tesseract"
  echo "[ativar_modelos] baixando por.traineddata (tessdata_best)…"
  curl -sSL -o "$_ATIVAR_RAIZ/data/modelos/tesseract/por.traineddata" \
    https://github.com/tesseract-ocr/tessdata_best/raw/main/por.traineddata
fi
if [[ -s "$_ATIVAR_RAIZ/data/modelos/tesseract/por.traineddata" ]]; then
  cp -u "$_ATIVAR_RAIZ/data/modelos/tesseract/por.traineddata" "$TESSDATA_PREFIX/por.traineddata" 2>/dev/null || true
fi

# EasyOCR: pacote e modelos são instalados no ambiente local, sem root.
# O modelo FP32 é intencional: esta máquina não expõe AVX2 e o quantizado
# pode abortar com SIGILL.
if [[ -x "$_ATIVAR_RAIZ/.venv/bin/python" ]]; then
  if ! "$_ATIVAR_RAIZ/.venv/bin/python" -c 'import easyocr' >/dev/null 2>&1; then
    echo "[ativar_modelos] instalando EasyOCR…" >&2
    env -u npm_config_allow_scripts "$_ATIVAR_RAIZ/.venv/bin/pip" install easyocr >/dev/null
  fi
  if [[ ! -s "$EASYOCR_MODULE_PATH/craft_mlt_25k.pth" || ! -s "$EASYOCR_MODULE_PATH/latin_g2.pth" ]]; then
    echo "[ativar_modelos] baixando modelos EasyOCR (português)…" >&2
    "$_ATIVAR_RAIZ/.venv/bin/python" - <<'PY'
import os
import easyocr

easyocr.Reader(
    ['pt'],
    gpu=False,
    model_storage_directory=os.environ['EASYOCR_MODULE_PATH'],
    download_enabled=True,
    quantize=False,
    verbose=False,
)
PY
  fi
  # Kraken: modelo de reconhecimento de texto impresso, além do blla de layout.
  if ! find "$_ATIVAR_RAIZ/data/modelos/kraken" -maxdepth 1 -name '*.mlmodel' ! -name 'blla*' -print -quit 2>/dev/null | grep -q .; then
    if command -v kraken >/dev/null 2>&1; then
      echo "[ativar_modelos] baixando modelo Kraken de impressão…" >&2
      kraken get 10.5281/zenodo.2577813 >/dev/null 2>&1 || true
      _kraken_model="$(find "$XDG_DATA_HOME/htrmopo" -name 'en_best.mlmodel' -print -quit 2>/dev/null || true)"
      if [[ -n "$_kraken_model" ]]; then
        cp -u "$_kraken_model" "$_ATIVAR_RAIZ/data/modelos/kraken/en_best.mlmodel"
      fi
    fi
  fi
fi
fi
unset _ATIVAR_RAIZ _kraken_model
command -v tesseract >/dev/null && tesseract --version 2>/dev/null | head -1
