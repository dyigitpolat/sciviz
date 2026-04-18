#!/usr/bin/env bash
# Create .venv and install sciviz in editable mode with optional PDF/PNG deps.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "error: ${PY} not found; set PYTHON to a Python 3.10+ interpreter." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install -U pip
pip install -e ".[pdf]"

echo
echo "Done. Activate the environment with:"
echo "  source .venv/bin/activate"
