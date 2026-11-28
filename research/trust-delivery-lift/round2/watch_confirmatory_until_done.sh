#!/usr/bin/env bash
# Count-only watch; no row peeking. Stops at TARGET rows, 10:30 interim, or 11:30 hard stop.
set -euo pipefail
cd "$(dirname "$0")"
ROWS_FILE=data/holdout_05b_confirmatory/rows.jsonl
TARGET_ROWS=512
LOG=data/holdout_05b_confirmatory/watch.log
DEADLINE_INTERIM=$(TZ=Asia/Taipei date -d '2026-11-29 10:30' +%s)
DEADLINE_STOP=$(TZ=Asia/Taipei date -d '2026-11-29 11:30' +%s)
mkdir -p data/holdout_05b_confirmatory
echo "watch start $(date -u -Iseconds)" >>"$LOG"
while true; now=$(date +%s); n=$(wc -l <"$ROWS_FILE" 2>/dev/null || echo 0); pgrep -f "harness_r2.py.*holdout_05b_confirmatory" >/dev/null && running=1 || running=0; echo "$(date -u -Iseconds) rows=$n target=$TARGET_ROWS running=$running" >>"$LOG"; if [ "$n" -ge "$TARGET_ROWS" ]; then echo COMPLETE >>"$LOG"; exit 0; fi; if [ "$now" -ge "$DEADLINE_STOP" ]; then echo STOP_1130_TAIPEI >>"$LOG"; exit 2; fi; if [ "$now" -ge "$DEADLINE_INTERIM" ] && [ "$running" -eq 1 ]; then rate=0; if [ -f data/holdout_05b_confirmatory/watch_rate.txt ]; then rate=$(cat data/holdout_05b_confirmatory/watch_rate.txt); fi; remain=$((TARGET_ROWS - n)); if [ "$rate" != "0" ] && [ "$remain" -gt 0 ]; then eta=$((remain * rate)); if [ $((now + eta)) -gt "$DEADLINE_STOP" ]; then echo INTERIM_1030_WONT_FINISH >>"$LOG"; pkill -f "harness_r2.py.*holdout_05b_confirmatory" || true; exit 3; fi; fi; fi; sleep 30; done