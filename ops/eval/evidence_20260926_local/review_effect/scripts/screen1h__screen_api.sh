#!/bin/bash
# PROPOSAL (untested; written read-only during review 2026-09-26): one-hour API screen, A vs C,
# gemma-4-26b think-on (same config as the paid batch that the task list was selected from).
# Usage: screen_api.sh <variant wheel> <jobs dir> [tag prefix]
# Prereq (the running :18900 proxy is LOCAL-ONLY: models=[gemma-4-12b-it-qat], upstreams w401/1003, no key):
#   start a SECOND proxy with the paid config + paid ledger, so the 4.80 USD hard cap (3.4026 spent) still binds:
#   /home/user/Vacant/.venv/bin/python /home/user/Vacant/ops/eval/orproxy.py \
#       --config $S/evalrun/proxy.json --out $S/evalrun/ledger --host 0.0.0.0 --port 18901
# Suite "api": U = 18 easy formal tasks whose paid g4 A run hit the 15-turn cap without an answer;
#              K = random.Random(20260927).sample(paid g4 A correct & A trial <= 300 s, 8). 26 pairs, 52 runs.
# Expected: ~42 min at 3 pairs (6 containers), ~61 min at 2 pairs; ~0.68 USD (paid per-task costs).
set -uo pipefail
S=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad
REPO=/home/user/Vacant; H=$S/study/src/harbor
W=$1; J=$2; PFX=${3:-scrapi1}; PAIRS=${PAIRS:-3}; STOP_AT=${STOP_AT:-4.60}
export DABSTEP_PINNED=$S/dabstep_pinned/formal
mkdir -p "$J/logs"
TASKS=$(python3 -c "import random;t='3 7 10 15 16 17 18 19 39 43 47 48 58 62 65 69 71 72 8 12 25 30 35 42 56 63'.split();random.Random(20260927).shuffle(t);print(' '.join(t))")
spent() { python3 -c "import json;print(json.load(open('$S/evalrun/ledger/summary.json'))['spent_usd'])"; }
for t in $TASKS; do
  while [ "$(jobs -rp | wc -l)" -ge $((2*PAIRS)) ]; do sleep 5; done
  python3 -c "import sys;sys.exit(0 if float('$(spent)') < $STOP_AT else 1)" || { echo "budget stop before $t"; break; }
  for arm in A C; do
    tag="$PFX-g4-on-$arm-$t"
    bash "$REPO/ops/eval/pilot/run_one.sh" "$H" "$J" "$W" "$t" g4 on "$arm" \
      "http://172.17.0.1:18901/t/$tag/think/on/api/v1" > "$J/logs/$t-$arm.log" 2>&1 &
    sleep 2   # run_one.sh has no --job-name; Harbor's default job name is a 1-second timestamp (RUNLOG §4 collision)
  done
done
wait
echo "done; spent $(spent)"
