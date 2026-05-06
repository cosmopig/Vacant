#!/usr/bin/env bash
# Vacant — one-line installer.
#
# Usage:
#   curl -LsSf https://raw.githubusercontent.com/cosmopig/Vacant/main/install.sh | bash
#
# What it does:
#   1. Installs uv (Astral's Python package manager) if not present
#   2. Clones https://github.com/cosmopig/Vacant into ~/Vacant
#   3. Runs `uv sync --all-extras`
#   4. Prints next steps
#
# After install:
#   vacant demo law_firm                      # run a demo scenario (mock substrate)
#   vacant demo self_replication --seed=314   # lineage / D-series scenario
#   uv run streamlit run src/vacant/mvp/dashboard.py   # launch the dashboard

set -euo pipefail

REPO_URL="${VACANT_REPO_URL:-https://github.com/cosmopig/Vacant.git}"
INSTALL_DIR="${VACANT_INSTALL_DIR:-$HOME/Vacant}"

echo ""
echo "  Vacant — responsibility-layer residency form for AI agents"
echo "  ─────────────────────────────────────────────────────────"
echo ""

# ── 1. Ensure uv is installed ────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
  echo "  → uv not found, installing via Astral's official script..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # shellcheck disable=SC1091
  if [ -f "$HOME/.local/bin/env" ]; then
    . "$HOME/.local/bin/env"
  fi
  if ! command -v uv >/dev/null 2>&1; then
    echo "  ✗ uv install failed — please install it manually:"
    echo "    https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
fi
echo "  ✓ uv $(uv --version | awk '{print $2}')"

# ── 2. Clone or update repo ──────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "  → existing clone found at $INSTALL_DIR — pulling latest"
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "  → cloning $REPO_URL → $INSTALL_DIR"
  git clone --depth=1 "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
echo "  ✓ source at $INSTALL_DIR ($(git rev-parse --short HEAD))"

# ── 3. Sync deps ─────────────────────────────────────────────────────────
echo "  → uv sync (this may take a minute)..."
uv sync --all-extras --quiet
echo "  ✓ dependencies installed"

# ── 4. Verify install ────────────────────────────────────────────────────
if uv run vacant --help >/dev/null 2>&1; then
  echo "  ✓ vacant CLI ready"
else
  echo "  ✗ vacant CLI not callable — please file an issue"
  exit 1
fi

cat <<EOF

  ─────────────────────────────────────────────────────────
  Done. Next steps:

    cd $INSTALL_DIR

    # Run a demo scenario
    uv run vacant demo law_firm
    uv run vacant demo self_replication --seed=314

    # Launch the Streamlit dashboard (network + lineage + scenario UI)
    uv run streamlit run src/vacant/mvp/dashboard.py

    # Run the test suite
    uv run pytest

  Docs:
    - Main guide:    $INSTALL_DIR/CLAUDE.md
    - Demo runbook:  $INSTALL_DIR/docs/RUNBOOK.md
    - 5-min defense: $INSTALL_DIR/docs/DEMO_SCRIPT.md
  ─────────────────────────────────────────────────────────

EOF
