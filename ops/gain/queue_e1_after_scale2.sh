#!/bin/bash
# ops/gain/queue_e1_after_scale2.sh — 把 E1（R440 gemma-only）排在 8765 現役 run 之後。
#
# 承重什麼：SPEC_GAIN §7 一端點一 run。人類 2026-09-01 指令要 E1「立刻排隊」，
# 但 8765 上 scale2 ON 還在跑，且 gemma 在 1004 上沒載入（VRAM 被 qwen 佔滿，
# JIT 載入被取消）。這支腳本在 vacant-dev 背景等現役 run 自然退出，然後：
#   1. 再確認沒有任何 gain_run.py 在跑（總綱錨行首檢查）
#   2. 經 1004 的 LM Studio REST v1 載 gemma（先試「與 qwen 並存」，失敗才卸 qwen）
#   3. 經 hub 8765 對 gemma 連問 3 次，3/3 要 200 才發射（round447 口徑）
#   4. 用決定性 run 的 request_policy 發射 E1，唯一差異＝--models
# 每一步寫進 ~/vacant/logs/queue_e1.log；最後一行 E1_LAUNCH_RESULT=... 是機器可讀結論。
# 決策脈絡：DECISION_20260902_R440C_E1_QUEUE_GEMMA_BACKEND.md
#
# 用法（vacant-dev）：setsid nohup bash ~/vacant/bin/queue_e1_after_scale2.sh <pid> \
#                     >/dev/null 2>&1 < /dev/null &
set -u
ROOT="$HOME/vacant"; REPO="$ROOT/Vacant"; LOG="$ROOT/logs/queue_e1.log"
WAIT_PID="${1:-2513538}"
LMS="http://100.86.226.21:1234"                       # 1004：hub 唯一 reachable 的 backend
HUB="http://100.119.113.56:8765/v1/chat/completions"
GEMMA="gemma-4-12b-it-qat"
QWEN_INST="qwen_qwen3.6-35b-a3b"
OUT="runs/g_r441_gemma_only_mbpp"                     # R440 預註冊的名字，不改
GEMMA_CTX=32768

mkdir -p "$ROOT/logs"
say() { printf '%s  %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" >>"$LOG"; }
finish() { say "E1_LAUNCH_RESULT=$1"; exit "${2:-1}"; }

exec 9>"$ROOT/.queue_e1.lock"
flock -n 9 || { echo "queue_e1 已在跑（.queue_e1.lock）" >&2; exit 0; }

say "queue_e1 start: waiting for pid $WAIT_PID to exit"
while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 30; done
say "pid $WAIT_PID exited"
sleep 20                                              # 讓 summary.json 落盤

# ── 1. 單 run 紀律 ───────────────────────────────────────────────────
n=$(ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py")
[ "$n" -eq 0 ] || { say "ABORT: $n gain_run.py still running"; finish abort_other_run; }
[ -e "$REPO/$OUT" ] && { say "ABORT: $REPO/$OUT already exists"; finish abort_dir_exists; }

# ── 2. gemma 載入（1004 REST v1）────────────────────────────────────────
curl -s -m 15 "$LMS/api/v1/models" >"$ROOT/logs/queue_e1_models_before.json" || true
say "models_before saved ($(wc -c <"$ROOT/logs/queue_e1_models_before.json") bytes)"

lms_post() {  # $1=path $2=json → 印 HTTP code；回應存 queue_e1_last.json
  curl -s -m 600 -o "$ROOT/logs/queue_e1_last.json" -w '%{http_code}' \
       -X POST "$LMS$1" -H 'Content-Type: application/json' -d "$2" || echo 000
}
last_body() { head -c 400 "$ROOT/logs/queue_e1_last.json" 2>/dev/null | tr '\n' ' '; }
gemma_loaded() {
  curl -s -m 15 "$LMS/api/v1/models" | python3 -c '
import sys, json
d = json.load(sys.stdin)
print("yes" if any(m["key"] == sys.argv[1] and m["loaded_instances"] for m in d["models"]) else "no")' "$GEMMA" 2>/dev/null || echo "unknown"
}
try_load() {  # 先帶 context_length，被拒再退回裸 model
  for body in "{\"model\":\"$GEMMA\",\"context_length\":$GEMMA_CTX}" "{\"model\":\"$GEMMA\"}"; do
    code=$(lms_post /api/v1/models/load "$body")
    say "load $body -> HTTP $code: $(last_body)"
    sleep 5
    [ "$(gemma_loaded)" = "yes" ] && return 0
  done
  return 1
}

if [ "$(gemma_loaded)" = "yes" ]; then
  say "gemma already loaded on 1004"
elif try_load; then
  say "step A ok: gemma loaded alongside qwen (zero disruption)"
else
  say "step A failed; step B: unload $QWEN_INST then load gemma (restore: DECISION R440C §六)"
  for body in "{\"instance_id\":\"$QWEN_INST\"}" "{\"model\":\"$QWEN_INST\"}"; do
    code=$(lms_post /api/v1/models/unload "$body")
    say "unload $body -> HTTP $code: $(last_body)"
    [ "$code" = "200" ] && break
  done
  sleep 15
  try_load || { say "ABORT: gemma cannot be loaded even after unloading qwen"; finish abort_gemma_load_failed; }
  say "step B ok: qwen unloaded, gemma loaded"
fi
curl -s -m 15 "$LMS/api/v1/models" >"$ROOT/logs/queue_e1_models_after.json" || true

# ── 3. 健康探針：經 hub，3/3 要 200 ─────────────────────────────────────
ok=0
for i in 1 2 3; do
  S=$(date +%s)
  code=$(curl -s -m 180 -o "$ROOT/logs/queue_e1_probe_$i.json" -w '%{http_code}' "$HUB" \
        -H 'Content-Type: application/json' \
        -d "{\"model\":\"$GEMMA\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":16,\"temperature\":0}" || echo 000)
  E=$(( $(date +%s) - S ))
  say "probe $i via hub -> HTTP $code in ${E}s: $(head -c 200 "$ROOT/logs/queue_e1_probe_$i.json" 2>/dev/null | tr '\n' ' ')"
  [ "$code" = "200" ] && ok=$((ok + 1))
done
[ "$ok" -eq 3 ] || { say "ABORT: hub probe $ok/3"; finish "abort_probe_${ok}of3"; }

# ── 4. 發射 E1 ────────────────────────────────────────────────────────
cd "$REPO" || finish abort_no_repo
say "launching E1 -> $OUT"
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
VACANT_GAIN_API="$HUB" \
CLINE_KEYS=/nonexistent \
setsid nohup python3 ops/gain/gain_run.py --out "$OUT" --n 179 \
  --seed g-r212-route-20260828 --models "$GEMMA" \
  --request-timeout-s 600 --review-timeout-s 380 \
  >"$OUT.launch.log" 2>&1 < /dev/null 9>&- &
sleep 120
pid=$(ps -eo pid,cmd | grep "python3 ops/gain/gain_run\.py --out $OUT " | grep -v grep | awk '{print $1}' | head -1)
if [ -n "$pid" ]; then
  say "E1 running pid=$pid; launch.log head: $(head -c 400 "$OUT.launch.log" | tr '\n' '|')"
  finish "launched pid=$pid" 0
else
  say "E1 exited within 120s; launch.log tail: $(tail -c 800 "$OUT.launch.log" | tr '\n' '|')"
  finish exited_early
fi
