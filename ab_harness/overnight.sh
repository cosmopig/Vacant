#!/bin/bash
# overnight.sh — the durable wave-2 runner.
#
# Design decisions that matter for the numbers, not just for scheduling:
#
# * TRIAD ORDER. One task's three arms run back to back before moving on. If the
#   daily free quota runs out mid-batch, what exists is complete triads rather
#   than a lopsided pile of one arm -- which is what a paired test needs.
# * RESUMABLE. A cell with rec.json is skipped, so the runner can be killed and
#   restarted without losing or double-counting anything.
# * QUOTA-AWARE. On a 429 it sleeps and retries the SAME task later. It never
#   records a rate-limited attempt as a result: an exhausted quota is not the
#   agent failing, and recording it as one would be a fabricated data point.
# * The RPL arm calls the real `vacant loop` binary, not a reimplementation.
#
# Daily budget: the free tier is 1000 requests/day at the account level
# (X-RateLimit-Limit: 1000). An opencode run costs roughly 15-20 requests, so
# ~50-65 agent runs/day. 90 tasks x 3 arms x (1..3 attempts) needs several days.
# That is why this loops across days instead of trying to finish in one night.
set -u
ROOT=/home/user1/ab-20260928
PY=$ROOT/venv/bin/python
W2=$ROOT/ab_harness/wave2.py
LOG=$ROOT/logs/overnight.log
STRATUM=${STRATUM:-}
MAXATT=${MAXATT:-3}
TIMEOUT=${TIMEOUT:-600}

mkdir -p "$ROOT/logs"
export PATH=$HOME/.opencode/bin:$PATH
export OPENROUTER_API_KEY=$(cat $ROOT/.openrouter_key)

log() { echo "[$(date -u +%H:%M:%S)] $*" >> "$LOG"; }

quota_left () {
  # returns remaining requests, or -1 if it cannot be read
  curl -sS --max-time 20 -o /tmp/_q.json -w "%{http_code}" \
    https://openrouter.ai/api/v1/chat/completions \
    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"stealth/space-bunny-alpha","messages":[{"role":"user","content":"ok"}],"max_tokens":1}' \
    2>/dev/null | grep -q 429 && echo 0 || echo 1
}

log "=== overnight runner start (stratum='${STRATUM:-all}', maxatt=$MAXATT) ==="

while :; do
  # 1. is there anything left?
  todo=$($PY - "$STRATUM" <<'PY'
import pathlib, sys
stratum = sys.argv[1] or None
bank = pathlib.Path("/home/user1/ab-20260928/r535_bank")
out = pathlib.Path("/home/user1/ab-20260928/runs2")
left = []
for d in sorted(bank.iterdir()):
    # Only real task dirs. The bank also carries a `_verify` scratch dir the
    # gauge leaves behind, and counting it as a task silently inflates n.
    if not d.is_dir() or not (d.name.startswith("s1_") or d.name.startswith("s2_")):
        continue
    if stratum and not d.name.startswith(stratum.lower() + "_"):
        continue
    if not all((out / f"{d.name}__{a}" / "rec.json").exists()
               for a in ("PC", "RP0", "RPL")):
        left.append(d.name)
print(len(left))
print("\n".join(left))
PY
)
  n=$(echo "$todo" | head -1)
  if [ "${n:-0}" = "0" ]; then
    log "=== all triads complete; nothing left to do ==="
    break
  fi
  log "remaining triads: $n"

  # 2. is there quota?
  if [ "$(quota_left)" = "0" ]; then
    log "quota exhausted (429) — sleeping 20 min, will resume the SAME task"
    sleep 1200
    continue
  fi

  task=$(echo "$todo" | sed -n '2p')
  for ARM in PC RP0 RPL; do
    if [ -f "$ROOT/runs2/${task}__${ARM}/rec.json" ]; then
      log "  $task $ARM already done, skip"
      continue
    fi
    log "  running $task $ARM"
    $PY "$W2" --arm "$ARM" --task "$task" --max-attempts "$MAXATT" \
        --timeout "$TIMEOUT" >> "$LOG" 2>&1
    # a 429 inside the cell leaves no rec.json -> it will be retried, not counted
    if [ -f "$ROOT/runs2/${task}__${ARM}/rec.json" ]; then
      log "  $task $ARM recorded"
    else
      log "  $task $ARM produced no rec.json (quota? crash?) — will retry later"
    fi
    sleep 3
  done
done
log "=== overnight runner finished ==="
