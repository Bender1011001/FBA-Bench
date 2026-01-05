#!/bin/bash
# Thin wrapper to run the tenant env generator Python script.
# Usage: ./generate_tenant_env.sh [args] (same as python generate_tenant_env.py)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/generate_tenant_env.py"

if [[ ! -f "$PYTHON_SCRIPT" ]]; then
  echo "Error: Python script not found at $PYTHON_SCRIPT" >&2
  exit 1
fi

python "$PYTHON_SCRIPT" "$@"