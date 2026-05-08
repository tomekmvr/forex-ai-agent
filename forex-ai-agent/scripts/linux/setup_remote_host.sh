#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${1:-$HOME/apps/forex-ai-agent}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Project dir: $PROJECT_DIR"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Missing project directory: $PROJECT_DIR" >&2
  exit 1
fi

cd "$PROJECT_DIR"

if [[ ! -f ".env" ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Setup complete."
echo "Edit .env and then run:"
echo ".venv/bin/python -m src.admin.run_http"