#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROWS=data/holdout_05b_confirmatory/rows.jsonl
TARGET=512
META=data/holdout_05b_confirmatory/run_meta.json
while true; do
  n=$(wc -l <"$ROWS" 2>/dev/null || echo 0)
  now=$(date +%s)
  stop1030=$(TZ=Asia/Taipei date -d '2026-11-29 10:30' +%s)
  stop1130=$(TZ=Asia/Taipei date -d '2026-11-29 11:30' +%s)
  pgrep -f 'harness_r2.py.*holdout_05b_confirmatory' >/dev/null && run=1 || run=0
  if [ "$n" -ge "$TARGET" ] && [ "$run" -eq 0 ]; then
    reason=confirmatory_complete
    break
  fi
  if [ "$n" -ge "$TARGET" ] && [ "$run" -eq 1 ]; then
    sleep 15
    continue
  fi
  if [ "$now" -ge "$stop1130" ]; then reason=deadline_1130_taipei; break; fi
  if [ "$now" -ge "$stop1030" ] && [ "$run" -eq 1 ] && [ "$n" -lt "$TARGET" ]; then
  reason=interim_1030_wont_finish; pkill -f 'harness_r2.py.*holdout_05b_confirmatory' || true; sleep 5; break; fi
  sleep 45
done
n=$(wc -l <"$ROWS")
cat >"$META" <<EOF
{"stopping_reason":"$reason","n_rows":$n,"target_rows":$TARGET,"confirmatory_tasks_expected":128,"arms":4,"ended_at_utc":"$(date -u -Iseconds)"}
EOF
/agent/repos/Vacant/.venv/bin/python recompute_r2.py --rows "$ROWS" --out data/holdout_05b_confirmatory/summary.json --meta "$META" >data/holdout_05b_confirmatory/recompute_stdout.json
echo "GATE_DONE reason=$reason n=$n" >data/holdout_05b_confirmatory/GATE_DONE.txt
# 1.5B filing after holdout gate (prereg: only if wall time; exploratory subset)
cd filing
nohup /agent/repos/Vacant/.venv/bin/python harness_online.py \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --subset data/subset_prereg_seed42.json \
  --out data/online_15b_seed42 \
  >>data/online_15b_seed42_run.log 2>&1 &
echo $! >data/online_15b_pid.txt