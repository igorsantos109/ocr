#!/usr/bin/env bash
set -euo pipefail
# Treino/fine-tuning Kraken — Marco 5, CPU-first, sem download silencioso.
# Uso:
#   bash scripts/treinar_kraken.sh data/treinamento/cartas_1891/ground_truth --epocas 20 --modelo-base data/modelos/kraken/base.mlmodel
#   bash scripts/treinar_kraken.sh --help

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo "Uso: bash scripts/treinar_kraken.sh DATASET [--epocas 20] [--modelo-base CAMINHO] [--saida CAMINHO] [--dry-run] [--executar]"
  echo ""
  .venv/bin/ocrhist treinar kraken --help
  exit 0
fi

if [[ $# -lt 1 ]]; then
  echo "ERRO: informe o dataset (pasta ground_truth ou manifest.jsonl)." >&2
  echo "Ex.: bash scripts/treinar_kraken.sh data/treinamento/cartas_1891/ground_truth --dry-run" >&2
  exit 2
fi

DATASET="$1"
shift

# repassa opções para a CLI (epocas, modelo-base, saida, dry-run, executar)
EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --epocas) EXTRA+=(--epocas "$2"); shift 2;;
    --modelo-base) EXTRA+=(--modelo-base "$2"); shift 2;;
    --saida) EXTRA+=(--saida "$2"); shift 2;;
    --dry-run) EXTRA+=(--dry-run); shift;;
    --executar) EXTRA+=(--executar); shift;;
    *) echo "Opção desconhecida: $1" >&2; exit 2;;
  esac
done

echo "[treinar_kraken] Dataset: $DATASET"
echo "[treinar_kraken] Python: $(.venv/bin/python --version 2>&1)"
.venv/bin/ocrhist diagnosticar | grep -E "Kraken|Python|Banco" || true
echo ""

if ! .venv/bin/python -c "import kraken" 2>/dev/null; then
  echo "AVISO: Kraken não instalado no .venv. Comando será preparado em dry-run." >&2
  echo "Instale com: .venv/bin/pip install 'kraken>=5.0'  (extra htr)" >&2
  EXTRA+=(--dry-run)
fi

set -x
.venv/bin/ocrhist treinar kraken "$DATASET" "${EXTRA[@]}"
