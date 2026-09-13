#!/bin/bash
# ops/gain/launch_lcb2.sh — 等 r446（EQ5）收官後發射 CONFORM 的 LCB v2 實跑（R440Z）。
#
# 承重什麼：SPEC_GAIN §7 一端點一 run。沿用 launch_conform.sh 經 R440E／round639 修過的守則：
# 等待迴圈**錨行首**（未錨會匹配到 grep 自己）、發射前重做單 run 檢查、探針驗 body、
# 目錄與 launch.log 已存在就停、等 preflight ✓。
#
# 用法（vacant-dev）：setsid nohup bash ops/gain/launch_lcb2.sh >/dev/null 2>&1 < /dev/null &
#            立刻發射（不等）：bash ops/gain/launch_lcb2.sh now
set -u
ROOT="$HOME/vacant"; REPO="$ROOT/Vacant"; LOG="$ROOT/logs/launch_lcb2.log"
HUB="http://100.119.113.56:8765/v1/chat/completions"
MODEL="gemma-4-12b-it-qat"
OUT="runs/g_r447_conform_lcb2"
DEC="DECISION_20260904_R440Z_LCB2_PREREG.md"
WAIT_PAT="^python3 ops/gain/gain_run\.py --out runs/g_r446_eq5_mbpp"

mkdir -p "$ROOT/logs"
say()    { printf '%s  %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" | tee -a "$LOG"; }
finish() { say "LCB2_LAUNCH_RESULT=$1"; exit "${2:-1}"; }

exec 9>"$ROOT/.launch_lcb2.lock"
flock -n 9 || { say "duplicate launch_lcb2 ignored (pid $$)"; exit 2; }
cd "$REPO" || finish abort_no_repo

if [ "${1:-}" != "now" ]; then
  say "waiting for r446 to finish ($WAIT_PAT)"
  while ps -eo cmd | grep -q "$WAIT_PAT"; do sleep 60; done
  say "r446 gone; settling 60s"; sleep 60
fi

git pull -q --ff-only origin feat/v2-four-stages 2>/dev/null || say "warn: pull failed, using local HEAD"
say "HEAD: $(git log --oneline -1)"
n=$(ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py")
[ "$n" -eq 0 ] || { say "ABORT: $n gain_run.py still running"; finish abort_other_run; }
[ -d "$OUT" ] && [ -z "$(ls -A "$OUT" 2>/dev/null)" ] && rmdir "$OUT" && say "removed empty $OUT"
[ -e "$OUT" ] && { say "ABORT: $OUT exists"; finish abort_dir_exists; }
[ -e "$OUT.launch.log" ] && { say "ABORT: $OUT.launch.log exists"; finish abort_launchlog_exists; }
[ -f "$DEC" ] || { say "ABORT: $DEC missing"; finish abort_no_decision; }
[ -f ops/gain/data/lcb_bank_v2.jsonl ] || { say "ABORT: lcb_bank_v2.jsonl missing (pull?)"; finish abort_no_bank; }

first=$(curl -s -m 15 "http://100.119.113.56:8765/v1/models" \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["data"][0]["id"] if d.get("data") else "none")' 2>/dev/null)
say "8765 first model = $first"
ok=0
for i in 1 2 3; do
  code=$(curl -s -m 120 -o "$ROOT/logs/lcb2_probe_$i.json" -w '%{http_code}' "$HUB" \
         -H 'Content-Type: application/json' \
         -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":16,\"temperature\":0}" || true)
  body=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1])); c = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    print("yes" if ("error" not in d and c.strip()) else "no")
except Exception: print("no")' "$ROOT/logs/lcb2_probe_$i.json")
  say "probe $i -> HTTP $code body_ok=$body"
  [ "$code" = "200" ] && [ "$body" = "yes" ] && ok=$((ok + 1))
done
[ "$ok" -eq 3 ] || finish "abort_probe_${ok}of3"

say "launching -> $OUT"
curl -s -m 15 "http://100.119.113.56:8765/v1/models" > "$OUT.backend.json" 2>/dev/null || true
PYTHONUNBUFFERED=1 VACANT_GAIN_API="$HUB" CLINE_KEYS=/nonexistent \
setsid nohup python3 ops/gain/gain_run.py --out "$OUT" --n 120 \
  --decision "$DEC" --seed g-r440-lcb2 --arms OFF,CONFORM,OFF5 --bank lcb2 --models "$MODEL" \
  --request-timeout-s 600 --review-timeout-s 380 --probe-sample 0 \
  >>"$OUT.launch.log" 2>&1 < /dev/null 9>&- &
pid=$!
sleep 3
ps -o cmd= -p "$pid" 2>/dev/null | grep -q gain_run.py \
  || pid=$(ps -eo pid,cmd | grep "gain_run\.py --out $OUT " | grep -v grep | awk '{print $1}' | head -1)
say "pid=${pid:-none}; waiting for preflight"
for _ in $(seq 1 90); do
  sleep 10
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    say "exited early; tail: $(tail -c 700 "$OUT.launch.log" | tr '\n' '|')"; finish exited_early
  fi
  if grep -q '✓' "$OUT.launch.log" 2>/dev/null; then
    say "preflight passed; head: $(head -c 400 "$OUT.launch.log" | tr '\n' '|')"; finish "launched pid=$pid" 0
  fi
done
finish "launch_pending_timeout pid=$pid" 0
