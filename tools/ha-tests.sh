#!/usr/bin/env bash
# Lance les tests d'intégration Home Assistant (Linux / WSL : le harnais HA exige Linux).
# Usage : bash tools/ha-tests.sh [arguments pytest]
set -euo pipefail
export PATH="$PATH:/snap/bin:$HOME/.local/bin"
VENV="${HCO_VENV:-$HOME/hco-venv}"
if [ ! -x "$VENV/bin/python" ]; then
  uv venv -q -p 3.13 "$VENV"
  VIRTUAL_ENV="$VENV" uv pip install -q pytest-homeassistant-custom-component
fi
cd "$(dirname "$0")/.."
exec "$VENV/bin/python" -m pytest -p no:cacheprovider tests "$@"
