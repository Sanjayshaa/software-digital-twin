#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$SCRIPT_DIR/backend:$PYTHONPATH"
export POSTGRES_SERVER="127.0.0.1"
exec "$SCRIPT_DIR/.venv/bin/pytest" "$@"
