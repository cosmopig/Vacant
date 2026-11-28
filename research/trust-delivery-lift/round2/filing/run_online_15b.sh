#!/bin/bash
# Queue after 0.5B run completes (same prereg subset).
set -euo pipefail
cd "$(dirname "$0")"
while pgrep -f "harness_online.py.*online_05b_seed42" >/dev/null; do sleep 60; done
ROOT=/agent/repos/Vacant/research/trust-delivery-lift/round2/filing
exec /agent/repos/Vacant/.venv/bin/python "$ROOT/harness_online.py" \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --subset "$ROOT/data/subset_prereg_seed42.json" \
  --out "$ROOT/data/online_15b_seed42" \
  2>&1 | tee "$ROOT/data/online_15b_seed42_run.log"