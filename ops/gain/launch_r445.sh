#!/bin/bash
# ops/gain/launch_r445.sh — 發射 R445 全庫擴充 run（DECISION_20260903_R445_...）。
# 沿用 launch_conform.sh 經 R440E 審查修正過的守則：ps 一律錨行首（未錨會匹配到
# grep 自己＝條件恆為真）、探針驗 body 不只驗 200、launch.log 已存在就停、
# 等 preflight ✓ 才算成功。
set -u
ROOT="$HOME/vacant"; REPO="$ROOT/Vacant"; LOG="$ROOT/logs/launch_r445.log"
HUB="http://100.119.113.56:8765/v1/chat/completions"
MODEL="gemma-4-12b-it-qat"
OUT="runs/g_r445_conform_mbpp_ext"
DEC="DECISION_20260903_R445_CONFORM_BANK_EXTENSION.md"

mkdir -p "$ROOT/logs"
say()    { printf '%s  %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" | tee -a "$LOG"; }
finish() { say "R445_LAUNCH_RESULT=$1"; exit "${2:-1}"; }

exec 9>"$ROOT/.launch_r445.lock"
flock -n 9 || { say "duplicate launch_r445 ignored (pid $$)"; exit 2; }
cd "$REPO" || finish abort_no_repo

say "HEAD: $(git log --oneline -1)"
n=$(ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py")
[ "$n" -eq 0 ] || { say "ABORT: $n gain_run.py still running (SPEC_GAIN §7 一端點一 run)"; finish abort_other_run; }
[ -d "$OUT" ] && [ -z "$(ls -A "$OUT" 2>/dev/null)" ] && rmdir "$OUT" && say "removed empty $OUT"
[ -e "$OUT" ] && { say "ABORT: $OUT exists"; finish abort_dir_exists; }
[ -e "$OUT.launch.log" ] && { say "ABORT: $OUT.launch.log exists (prior evidence)"; finish abort_launchlog_exists; }
[ -f "$DEC" ] || { say "ABORT: $DEC missing (R440G gate needs it)"; finish abort_no_decision; }

first=$(curl -s -m 15 "http://100.119.113.56:8765/v1/models" \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["data"][0]["id"] if d.get("data") else "none")' 2>/dev/null)
say "8765 first model = $first"

ok=0
for i in 1 2 3; do
  code=$(curl -s -m 120 -o "$ROOT/logs/r445_probe_$i.json" -w '%{http_code}' "$HUB" \
         -H 'Content-Type: application/json' \
         -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":16,\"temperature\":0}" || true)
  body=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1]))
    c = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    print("yes" if ("error" not in d and c.strip()) else "no")
except Exception:
    print("no")' "$ROOT/logs/r445_probe_$i.json")
  say "probe $i -> HTTP $code body_ok=$body"
  [ "$code" = "200" ] && [ "$body" = "yes" ] && ok=$((ok + 1))
done
[ "$ok" -eq 3 ] || finish "abort_probe_${ok}of3"

say "launching R445 -> $OUT (offset=179 n=192, 與 r444 零重疊)"
curl -s -m 15 "http://100.119.113.56:8765/v1/models" > "$OUT.backend.json" 2>/dev/null || true
PYTHONUNBUFFERED=1 \
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
VACANT_GAIN_API="$HUB" CLINE_KEYS=/nonexistent \
setsid nohup python3 ops/gain/gain_run.py --out "$OUT" --n 192 --offset 179 \
  --decision "$DEC" --seed g-r212-route-20260828 \
  --arms OFF,CONFORM,OFF5 --bank evalplus --models "$MODEL" \
  --request-timeout-s 600 --review-timeout-s 380 --probe-sample 0 \
  >>"$OUT.launch.log" 2>&1 < /dev/null 9>&- &
pid=$!
sleep 3
ps -o cmd= -p "$pid" 2>/dev/null | grep -q gain_run.py \
  || pid=$(ps -eo pid,cmd | grep "gain_run\.py --out $OUT " | grep -v grep | awk '{print $1}' | head -1)
say "R445 pid=${pid:-none}; waiting for preflight (instrument 192/192 first)"
for _ in $(seq 1 90); do
  sleep 10
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    say "exited early; tail: $(tail -c 700 "$OUT.launch.log" | tr '\n' '|')"; finish exited_early
  fi
  if grep -q '✓' "$OUT.launch.log" 2>/dev/null || [ -e "$OUT/summary.json" ]; then
    say "preflight passed; head: $(head -c 600 "$OUT.launch.log" | tr '\n' '|')"
    finish "launched pid=$pid" 0
  fi
done
finish "launch_pending_timeout pid=$pid" 0
