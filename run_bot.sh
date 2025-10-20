#!/usr/bin/env bash
set -euo pipefail

# Change to the script directory
cd "$(dirname "$0")"

# Create virtual environment if it does not exist
if [ ! -d ".venv" ] || [ ! -x ".venv/bin/python" ]; then
  echo "[setup] Creating virtual environment in .venv ..."
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv .venv
  else
    python -m venv .venv
  fi
fi

# Activate the virtual environment
# shellcheck source=/dev/null
. ".venv/bin/activate"

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
if [ -f "requirements.txt" ]; then
  pip install -r requirements.txt
fi

# Create runtime directories
mkdir -p data logs reports

export PYTHONUNBUFFERED=1

echo "[run] Starting bot..."
exec python bot.py
