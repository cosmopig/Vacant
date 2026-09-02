#!/bin/bash
# ops/gain/launch_e1.sh — E1（R440 gemma-only）發射器：round440c watcher 經審查後的修正版。
#
# 承重什麼：SPEC_GAIN §7 一端點一 run、R440 預註冊、決定性 run 的 request_policy。
# round440c 的 watcher 經三個獨立審查者找碴（DECISION_20260902_R440E），修掉的洞：
#   1. 發射前**重做**單 run 檢查（載入／探針要幾分鐘，迴圈可能在這段起別的 run）
#   2. gemma 載入後**驗 context_length**，不等於預註冊值就停；快照存進 run package
#   3. hub 探針驗 body（8765 會回 200＋error body，brain_cline.py:129-135 就是為此寫的）
#   4. `--probe-sample 0`：決定性 run（g_r342/g_r356）的量具驗證是 179/179，不是預設 12
#   5. launch.log 只追加、已存在就不覆蓋（失敗證據不能被重試沖掉）
#   6. 用 $! 抓 pid，等到 preflight 的 ✓ 真的出現才算 launched
#   7. 預設**不卸任何模型**（1004 不是本 VM，卸模型是人類決定）；UNLOAD_FIRST=1 才卸
#
# 用法（vacant-dev，repo 根目錄）：
#   bash ops/gain/launch_e1.sh prep      # 載 gemma＋驗 ctx（可獨立先跑）
#   bash ops/gain/launch_e1.sh launch    # 探針 3/3 → 重檢 → 發射 → 等 preflight
#   bash ops/gain/launch_e1.sh all
# 環境：UNLOAD_FIRST=1（先卸所有非 gemma 的 LLM 實例）、GEMMA_CTX=32768
set -u
ROOT="$HOME/vacant"; REPO="$ROOT/Vacant"; LOG="$ROOT/logs/launch_e1.log"
LMS="http://100.86.226.21:1234"                       # 1004：hub 唯一 reachable 的 backend
HUB="http://100.119.113.56:8765/v1/chat/completions"
GEMMA="gemma-4-12b-it-qat"
GEMMA_CTX="${GEMMA_CTX:-32768}"
OUT="runs/g_r441_gemma_only_mbpp"                     # R440 預註冊的名字，不改

mkdir -p "$ROOT/logs"
say()    { printf '%s  %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" | tee -a "$LOG"; }
finish() { say "E1_LAUNCH_RESULT=$1"; exit "${2:-1}"; }

exec 9>"$ROOT/.launch_e1.lock"
flock -n 9 || { say "duplicate launch_e1 invocation ignored (pid $$, arg ${1:-none})"; exit 2; }

models_json()  { curl -s -m 15 "$LMS/api/v1/models"; }
loaded_table() { models_json | python3 -c '
import sys, json
d = json.load(sys.stdin)
for m in d["models"]:
    for i in m["loaded_instances"]:
        print(m["key"], i["id"], i["config"].get("context_length"), i["config"].get("parallel"))' 2>/dev/null; }
gemma_ctx()    { models_json | python3 -c '
import sys, json
d = json.load(sys.stdin)
print(next((str(i["config"].get("context_length")) for m in d["models"]
            if m["key"] == sys.argv[1] for i in m["loaded_instances"]), "no"))' "$GEMMA" 2>/dev/null || echo unknown; }
post() { curl -s -m 600 -o "$ROOT/logs/launch_e1_last.json" -w '%{http_code}' \
              -X POST "$LMS$1" -H 'Content-Type: application/json' -d "$2" || true; }
last() { head -c 400 "$ROOT/logs/launch_e1_last.json" 2>/dev/null | tr '\n' ' '; }

prep() {
  say "prep: backend before:"; loaded_table | sed 's/^/    /' | tee -a "$LOG"
  models_json > "$ROOT/logs/launch_e1_models_before.json"
  if [ "${UNLOAD_FIRST:-0}" = "1" ]; then
    for inst in $(loaded_table | awk -v g="$GEMMA" '$1!=g{print $2}'); do
      for body in "{\"instance_id\":\"$inst\"}" "{\"model\":\"$inst\"}"; do
        code=$(post /api/v1/models/unload "$body"); say "unload $body -> HTTP $code: $(last)"
        [ "$code" = "200" ] && break
      done
    done
    sleep 10
  fi
  ctx=$(gemma_ctx)
  if [ "$ctx" = "no" ]; then
    code=$(post /api/v1/models/load "{\"model\":\"$GEMMA\",\"context_length\":$GEMMA_CTX}")
    say "load gemma ctx=$GEMMA_CTX -> HTTP $code: $(last)"
    sleep 5; ctx=$(gemma_ctx)
    if [ "$ctx" = "no" ] && [ "$code" = "400" ] && grep -qi "context_length" "$ROOT/logs/launch_e1_last.json"; then
      code=$(post /api/v1/models/load "{\"model\":\"$GEMMA\"}")
      say "load gemma (bare, field rejected) -> HTTP $code: $(last)"
      sleep 5; ctx=$(gemma_ctx)
    fi
  else
    say "gemma already loaded (ctx=$ctx)"
  fi
  [ "$ctx" = "$GEMMA_CTX" ] || { say "ABORT: gemma ctx=$ctx, expected $GEMMA_CTX"; finish "abort_gemma_ctx_${ctx}"; }
  models_json > "$ROOT/logs/launch_e1_models_after.json"
  say "prep ok: backend after:"; loaded_table | sed 's/^/    /' | tee -a "$LOG"
  others=$(loaded_table | awk -v g="$GEMMA" '$1!=g{print $1}' | tr '\n' ',')
  say "resident_non_gemma=[${others}]  (R440C P0 要求空；非空＝條件變更，要寫進 DECISION)"
}

probe() {
  ok=0
  for i in 1 2 3; do
    S=$(date +%s)
    code=$(curl -s -m 120 -o "$ROOT/logs/launch_e1_probe_$i.json" -w '%{http_code}' "$HUB" \
           -H 'Content-Type: application/json' \
           -d "{\"model\":\"$GEMMA\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":16,\"temperature\":0}" || true)
    E=$(( $(date +%s) - S ))
    body_ok=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1]))
    c = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    print("yes" if ("error" not in d and c.strip()) else "no")
except Exception:
    print("no")' "$ROOT/logs/launch_e1_probe_$i.json")
    say "probe $i -> HTTP $code body_ok=$body_ok in ${E}s: $(head -c 160 "$ROOT/logs/launch_e1_probe_$i.json" 2>/dev/null | tr '\n' ' ')"
    [ "$code" = "200" ] && [ "$body_ok" = "yes" ] && ok=$((ok + 1))
  done
  [ "$ok" -eq 3 ] || finish "abort_probe_${ok}of3"
}

launch() {
  cd "$REPO" || finish abort_no_repo
  [ "$(gemma_ctx)" = "$GEMMA_CTX" ] || { say "ABORT: gemma not loaded at ctx=$GEMMA_CTX (run prep first)"; finish abort_gemma_not_ready; }
  probe
  n=$(ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py")
  [ "$n" -eq 0 ] || { say "ABORT: $n gain_run.py running at launch time"; finish abort_other_run_at_launch; }
  # R440G 閘門在 mkdir 之後才檢查：被拒絕的啟動會留下空目錄，那不是實驗產物，清掉即可
  [ -d "$OUT" ] && [ -z "$(ls -A "$OUT" 2>/dev/null)" ] && rmdir "$OUT" && say "removed empty $OUT left by a rejected launch"
  [ -e "$OUT" ] && { say "ABORT: $OUT exists"; finish abort_dir_exists; }
  [ -e "$OUT.launch.log" ] && { say "ABORT: $OUT.launch.log exists (previous attempt's evidence; not overwriting)"; finish abort_launchlog_exists; }
  cp "$ROOT/logs/launch_e1_models_after.json" "$OUT.backend.json" 2>/dev/null || models_json > "$OUT.backend.json"
  say "launching E1 -> $OUT (backend snapshot: $OUT.backend.json)"
  PYTHONUNBUFFERED=1 \
  VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
  VACANT_GAIN_API="$HUB" CLINE_KEYS=/nonexistent \
  setsid nohup python3 ops/gain/gain_run.py --out "$OUT" --n 179 \
    --decision DECISION_20260902_R440E_E1_PRELAUNCH_REVIEW_AND_1004_BLOCKER.md \
    --seed g-r212-route-20260828 --models "$GEMMA" \
    --request-timeout-s 600 --review-timeout-s 380 --probe-sample 0 \
    >>"$OUT.launch.log" 2>&1 < /dev/null 9>&- &
  pid=$!
  sleep 3
  ps -o cmd= -p "$pid" 2>/dev/null | grep -q "gain_run.py" \
    || pid=$(ps -eo pid,cmd | grep "python3 ops/gain/gain_run\.py --out $OUT " | grep -v grep | awk '{print $1}' | head -1)
  say "E1 pid=${pid:-none}; waiting for preflight ✓ (instrument 179/179 runs first, zero API calls)"
  for t in $(seq 1 90); do
    sleep 10
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null || [ "$(ps -o stat= -p "$pid" 2>/dev/null | cut -c1)" = "Z" ]; then
      say "E1 exited early; launch.log tail: $(tail -c 800 "$OUT.launch.log" | tr '\n' '|')"; finish exited_early
    fi
    if grep -q '✓' "$OUT.launch.log" 2>/dev/null || [ -e "$OUT/summary.json" ]; then
      say "preflight passed; launch.log head: $(head -c 600 "$OUT.launch.log" | tr '\n' '|')"
      finish "launched pid=$pid" 0
    fi
  done
  say "pid alive but no preflight ✓ after 900s; launch.log tail: $(tail -c 600 "$OUT.launch.log" | tr '\n' '|')"
  finish "launch_pending_timeout pid=$pid" 0
}

case "${1:-}" in
  prep)   prep ;;
  launch) launch ;;
  all)    prep; launch ;;
  *) echo "usage: $0 prep|launch|all   (env: UNLOAD_FIRST=1, GEMMA_CTX=32768)" >&2; exit 2 ;;
esac
