#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
while pgrep -f "harness_online.py.*online_05b_seed42" >/dev/null; do sleep 120; done
while pgrep -f "harness_online.py.*online_05b" >/dev/null; do sleep 60; done
exec /agent/repos/Vacant/.venv/bin/python harness_r2.py \
  --split holdout_answerable_ids --arms BLIND,VACANT \
  --model Qwen/Qwen2.5-0.5B-Instruct \
  --out data/holdout_05b \
  2>&1 | tee -a data/holdout_05b_run.log
