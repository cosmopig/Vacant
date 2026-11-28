#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export TOKENIZERS_PARALLELISM=false
exec /agent/repos/Vacant/.venv/bin/python harness_r2.py \
  --split holdout_answerable_ids \
  --arms BLIND,VACANT,MAJ3,LPB3 \
  --exclude-ids data/holdout_05b/pilot_excluded_tasks.json \
  --out data/holdout_05b_confirmatory \
  2>&1 | tee -a data/holdout_05b_confirmatory_run.log