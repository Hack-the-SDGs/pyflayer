#!/usr/bin/env bash
# Format + check the whole project in one go.
#   ./scripts/format.sh              # format + check, stop on error
#   ./scripts/format.sh --check      # check only, no writes (CI mode)
#
# Order matches AGENTS.md "檢查指令" section.

set -euo pipefail

cd "$(dirname "$0")/.."

MODE="${1:-format}"

echo "[1/5] regenerate stubs…"
uv run python scripts/generate_stubs.py

if [[ "$MODE" == "--check" ]]; then
    echo "[2/5] ruff format --check…"
    uv run ruff format --check src scripts tests
else
    echo "[2/5] ruff format…"
    uv run ruff format src scripts tests
fi

echo "[3/5] ruff check…"
uv run ruff check src scripts tests

echo "[4/5] pyright…"
uv run pyright src/

echo "[5/5] pytest (unit)…"
uv run pytest -m "not integration" --tb=short -q

echo "✓ all green"
