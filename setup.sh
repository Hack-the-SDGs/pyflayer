#!/usr/bin/env bash
# setup.sh -- one-shot install for minethon.
#
# Installs:
#   1. Python dependencies via `uv sync` (includes JSPyBridge).
#   2. Pinned npm packages into JSPyBridge's bundled node_modules so
#      `require()` at runtime never triggers a surprise lazy install.
#
# Requires:
#   - uv (https://docs.astral.sh/uv/)
#   - Node.js >= 22  (mineflayer 4.37 requires engines.node >=22)

set -euo pipefail

cd "$(dirname "$0")"

# --- Node.js version check ------------------------------------------------

if ! command -v node >/dev/null 2>&1; then
  echo "error: 'node' not found. Install Node.js 22+ before running setup.sh." >&2
  exit 1
fi

NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]")
if [ "$NODE_MAJOR" -lt 22 ]; then
  echo "error: Node.js 22+ required; found $(node -v)." >&2
  exit 1
fi

# --- uv check --------------------------------------------------------------

if ! command -v uv >/dev/null 2>&1; then
  echo "error: 'uv' not found. Install from https://docs.astral.sh/uv/" >&2
  exit 1
fi

# --- 1/2: Python dependencies ---------------------------------------------

echo "[1/2] syncing Python dependencies via uv..."
uv sync --quiet

# --- 2/2: pre-install pinned npm packages ---------------------------------
# JSPyBridge lazily installs missing packages on first require(); we front-
# load them so the first run isn't network-bound and the versions stay
# reproducible.

JS_DIR=$(uv run --quiet python -c "import javascript, os; print(os.path.join(os.path.dirname(javascript.__file__), 'js'))")

if [ ! -d "$JS_DIR" ]; then
  echo "error: JSPyBridge bundled js/ dir not found at $JS_DIR." >&2
  exit 1
fi

echo "[2/2] installing pinned npm packages into $JS_DIR ..."
# Versions must match the constants in src/minethon/_bridge.py.
(
  cd "$JS_DIR"
  npm install --silent --no-audit --no-fund \
    mineflayer@4.37.0 \
    vec3@0.1.10 \
    mineflayer-pathfinder@2.4.5
)

cat <<'EOF'

Setup complete.

Next steps:
  cp examples/demos/drasl_auth/.env.example examples/demos/drasl_auth/.env
  # edit .env with your credentials
  uv run --env-file examples/demos/drasl_auth/.env examples/demos/drasl_auth/main.py
EOF
