#!/bin/bash
# ops/gain/launch_conform.sh — 等 E3 收官後發射 CONFORM 實跑（R440R 預註冊）。
#
# 承重什麼：SPEC_GAIN §7 一端點一 run。CONFORM 是 R440P 裁決出來的新機制
# （驗收閘門取代評審委員會），本支負責「E3 自然退出 -> 檢查 -> 發射」，
# 沿用 launch_e1.sh 經審查修正過的守則（R440E）：發射前重做單 run 檢查、
# 探針驗 body 不只驗 200、launch.log 只追加且已存在就停、等 preflight ✓ 才算成功。
#
# 用法（vacant-dev）：setsid nohup bash ops/gain/launch_conform.sh [wait_pid] \
#                     >/dev/null 2>&1 < /dev/null &
set -u
ROOT="$HOME/vacant"; REPO="$ROOT/Vacant"; LOG="$ROOT/logs/launch_conform.log"
HUB="http://100.119.113.56:8765/v1/chat/completions"
MODEL="gemma-4-12b-it-qat"
OUT="runs/g_r444_conform_mbpp"
DEC="DECISION_20260903_R440R_CONFORM_LIVE_PREREG.md"
# ⚠ 一定要錨行首。未錨版 `ps -eo cmd | grep -q "gain_run.py --out runs/..."`
#   會匹配到 **grep 自己的命令列**（它就長成 `grep -q gain_run.py --out runs/...`），
#   於是條件恆為真、這個迴圈永遠不會結束＝排程器安靜地永遠不發射。
#   2026-09-03 round639 實測：未錨版對「不存在的 run」300/300 為真；
#   錨行首版對不存在的 run 0/100、對真的在跑的 E3 100/100。
#   這正是 LOOP_PROMPT 記過的同一個坑（pgrep -f 匹配到自己），
#   本檔下方 `n=$(ps -eo cmd | grep -c "^python3 ...")` 已經錨了，這一行漏掉。
WAIT_PAT="^python3 ops/gain/gain_run\.py --out runs/g_r443_gemma_lcb"

mkdir -p "$ROOT/logs"
say()    { printf '%s  %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" | tee -a "$LOG"; }
finish() { say "CONFORM_LAUNCH_RESULT=$1"; exit "${2:-1}"; }

exec 9>"$ROOT/.launch_conform.lock"
flock -n 9 || { say "duplicate launch_conform ignored (pid $$)"; exit 2; }

cd "$REPO" || finish abort_no_repo

# ── 1. 等 E3 自然退出（§7）────────────────────────────────────────
if [ "${1:-}" != "now" ]; then
  say "waiting for E3 to finish ($WAIT_PAT)"
  while ps -eo cmd | grep -q "$WAIT_PAT"; do sleep 60; done
  say "E3 gone; settling 60s for summary.json"
  sleep 60
fi

# ── 2. 發射前守則（R440E 的審查發現，逐條）──────────────────────────
git pull -q --ff-only origin feat/v2-four-stages 2>/dev/null || say "warn: pull failed, using local HEAD"
say "HEAD: $(git log --oneline -1)"
n=$(ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py")
[ "$n" -eq 0 ] || { say "ABORT: $n gain_run.py still running"; finish abort_other_run; }
[ -d "$OUT" ] && [ -z "$(ls -A "$OUT" 2>/dev/null)" ] && rmdir "$OUT" && say "removed empty $OUT"
[ -e "$OUT" ] && { say "ABORT: $OUT exists"; finish abort_dir_exists; }
[ -e "$OUT.launch.log" ] && { say "ABORT: $OUT.launch.log exists (prior evidence)"; finish abort_launchlog_exists; }
[ -f "$DEC" ] || { say "ABORT: $DEC missing (R440G gate needs it)"; finish abort_no_decision; }

# gemma 仍單獨在卡上？只用 8765（列表順序：已載入的排前面）
first=$(curl -s -m 15 "http://100.119.113.56:8765/v1/models" \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["data"][0]["id"] if d.get("data") else "none")' 2>/dev/null)
say "8765 first model = $first"

ok=0
for i in 1 2 3; do
  code=$(curl -s -m 120 -o "$ROOT/logs/conform_probe_$i.json" -w '%{http_code}' "$HUB" \
         -H 'Content-Type: application/json' \
         -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":16,\"temperature\":0}" || true)
  body=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1]))
    c = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    print("yes" if ("error" not in d and c.strip()) else "no")
except Exception:
    print("no")' "$ROOT/logs/conform_probe_$i.json")
  say "probe $i -> HTTP $code body_ok=$body"
  [ "$code" = "200" ] && [ "$body" = "yes" ] && ok=$((ok + 1))
done
[ "$ok" -eq 3 ] || finish "abort_probe_${ok}of3"

# ── 3. 發射 ──────────────────────────────────────────────────────
say "launching CONFORM -> $OUT"
curl -s -m 15 "http://100.119.113.56:8765/v1/models" > "$OUT.backend.json" 2>/dev/null || true
PYTHONUNBUFFERED=1 \
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
VACANT_GAIN_API="$HUB" CLINE_KEYS=/nonexistent \
setsid nohup python3 ops/gain/gain_run.py --out "$OUT" --n 179 \
  --decision "$DEC" --seed g-r212-route-20260828 \
  --arms OFF,CONFORM,OFF5 --bank evalplus --models "$MODEL" \
  --request-timeout-s 600 --review-timeout-s 380 --probe-sample 0 \
  >>"$OUT.launch.log" 2>&1 < /dev/null 9>&- &
pid=$!
sleep 3
ps -o cmd= -p "$pid" 2>/dev/null | grep -q gain_run.py \
  || pid=$(ps -eo pid,cmd | grep "gain_run\.py --out $OUT " | grep -v grep | awk '{print $1}' | head -1)
say "CONFORM pid=${pid:-none}; waiting for preflight (instrument 179/179 first)"
for _ in $(seq 1 90); do
  sleep 10
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    say "exited early; tail: $(tail -c 700 "$OUT.launch.log" | tr '\n' '|')"; finish exited_early
  fi
  if grep -q '✓' "$OUT.launch.log" 2>/dev/null || [ -e "$OUT/summary.json" ]; then
    say "preflight passed; head: $(head -c 500 "$OUT.launch.log" | tr '\n' '|')"
    finish "launched pid=$pid" 0
  fi
done
finish "launch_pending_timeout pid=$pid" 0
