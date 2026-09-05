#!/bin/bash
# ops/gain/launch_eq5_seed2.sh — 等 r447（CONFORM on LCB v2）收官後發射 EQ5 的
# **獨立重複**（R448，另一顆 seed、同一批 371 題）。
#
# 承重什麼：SPEC_GAIN §7 一端點一 run，以及 R446 §五 的推翻條件
# 「若獨立第二批 EQ5（不同 seed）的 b/c 方向翻轉 ⇒ 本結果降為探索性」——
# 那個條件到現在沒有資料可判，這支就是去把它變成可判。
#
# 沿用 launch_lcb2.sh 經 R440E／round639 審查修過的守則：
#   等待迴圈**錨行首**（未錨會匹配到 grep 自己＝條件恆為真）、發射前重做單 run 檢查、
#   探針驗 body 不只驗 200、目錄與 launch.log 已存在就停、等 preflight ✓。
# 本支比 launch_lcb2.sh 多三道，理由都寫在該行上：
#   (1) 前一個 run 既沒在跑、也還沒 terminal ⇒ 停（不搶端點，也不假裝它跑完了）；
#   (2) seed 必須與 r446 不同（抄回舊 seed＝這個 run 不是重複，是第二次同條件跑）；
#   (3) DECISION 內文必須寫到這顆 seed（R440G 只檢查 run 名字，檢查不到 seed）。
#
# 用法（vacant-dev）：setsid nohup bash ops/gain/launch_eq5_seed2.sh >/dev/null 2>&1 < /dev/null &
#            立刻發射（不等 r447）：bash ops/gain/launch_eq5_seed2.sh now
set -u
ROOT="$HOME/vacant"; REPO="$ROOT/Vacant"; LOG="$ROOT/logs/launch_eq5_seed2.log"
HUB="http://100.119.113.56:8765/v1/chat/completions"
MODEL="gemma-4-12b-it-qat"
OUT="runs/g_r448_eq5_mbpp_seed2"
DEC="DECISION_20260904_R448_EQ5_REPLICATION_PREREG.md"
SEED="g-r448-eq5-seed2"
R446_SEED="g-r212-route-20260828"
BANK_FILE=".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
PRIOR="runs/g_r447_conform_lcb2"
WAIT_PAT="^python3 ops/gain/gain_run\.py --out runs/g_r447_conform_lcb2"

mkdir -p "$ROOT/logs"
say()    { printf '%s  %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" | tee -a "$LOG"; }
finish() { say "EQ5_SEED2_LAUNCH_RESULT=$1"; exit "${2:-1}"; }

exec 9>"$ROOT/.launch_eq5_seed2.lock"
flock -n 9 || { say "duplicate launch_eq5_seed2 ignored (pid $$)"; exit 2; }
cd "$REPO" || finish abort_no_repo

if [ "${1:-}" != "now" ]; then
  if ps -eo cmd | grep -q "$WAIT_PAT"; then
    say "waiting for r447 to finish ($WAIT_PAT)"
    while ps -eo cmd | grep -q "$WAIT_PAT"; do sleep 60; done
    say "r447 gone; settling 60s"; sleep 60
  else
    # r447 沒在跑有兩種可能：已經收官，或者還沒發射／中途死掉。
    # 只有第一種准往下走——否則這支會在 r447 發射之前先占住端點，
    # 而「誰先搶到」不是實驗設計該有的變因。
    term=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1])); print("yes" if d.get("run_terminal") is True else "no")
except Exception: print("no")' "$PRIOR/summary.json")
    [ "$term" = "yes" ] || { say "ABORT: r447 既沒在跑也還沒 terminal (run_terminal=$term)"; finish abort_prior_not_terminal; }
    say "r447 already terminal; proceeding"
  fi
fi

git pull -q --ff-only origin feat/v2-four-stages 2>/dev/null || say "warn: pull failed, using local HEAD"
say "HEAD: $(git log --oneline -1)"
n=$(ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py")
[ "$n" -eq 0 ] || { say "ABORT: $n gain_run.py still running"; finish abort_other_run; }
[ -d "$OUT" ] && [ -z "$(ls -A "$OUT" 2>/dev/null)" ] && rmdir "$OUT" && say "removed empty $OUT"
[ -e "$OUT" ] && { say "ABORT: $OUT exists"; finish abort_dir_exists; }
[ -e "$OUT.launch.log" ] && { say "ABORT: $OUT.launch.log exists"; finish abort_launchlog_exists; }
[ -f "$DEC" ] || { say "ABORT: $DEC missing (R440G 閘門要它)"; finish abort_no_decision; }
[ -f "$BANK_FILE" ] || { say "ABORT: $BANK_FILE missing (EvalPlus 官方包)"; finish abort_no_bank; }
# 重複的定義就是「換一顆 seed」。抄回 r446 那顆的話，跑出來的是第二次同條件的 run，
# 不是重複——而且兩者在 rows 裡長得一模一樣，事後分不出來。所以擋在發射前。
[ "$SEED" != "$R446_SEED" ] || { say "ABORT: SEED 等於 r446 的 $R446_SEED，這樣不是重複"; finish abort_seed_not_fresh; }
# R440G 只檢查 DECISION 內文有沒有 run 名字，檢查不到 seed；seed 打錯不會被它擋下。
grep -q -- "$SEED" "$DEC" || { say "ABORT: $DEC 內文沒有寫到 seed $SEED"; finish abort_seed_not_prereg; }

first=$(curl -s -m 15 "http://100.119.113.56:8765/v1/models" \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["data"][0]["id"] if d.get("data") else "none")' 2>/dev/null)
say "8765 first model = $first"
ok=0
for i in 1 2 3; do
  code=$(curl -s -m 120 -o "$ROOT/logs/eq5_seed2_probe_$i.json" -w '%{http_code}' "$HUB" \
         -H 'Content-Type: application/json' \
         -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":16,\"temperature\":0}" || true)
  body=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1])); c = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    print("yes" if ("error" not in d and c.strip()) else "no")
except Exception: print("no")' "$ROOT/logs/eq5_seed2_probe_$i.json")
  say "probe $i -> HTTP $code body_ok=$body"
  [ "$code" = "200" ] && [ "$body" = "yes" ] && ok=$((ok + 1))
done
[ "$ok" -eq 3 ] || finish "abort_probe_${ok}of3"

say "launching -> $OUT (seed=$SEED, n=371 offset=0, 與 r446 唯一的差別就是 seed)"
curl -s -m 15 "http://100.119.113.56:8765/v1/models" > "$OUT.backend.json" 2>/dev/null || true
PYTHONUNBUFFERED=1 \
VACANT_EVALPLUS_PATH="$BANK_FILE" \
VACANT_GAIN_API="$HUB" CLINE_KEYS=/nonexistent \
setsid nohup python3 ops/gain/gain_run.py --out "$OUT" --n 371 --offset 0 \
  --decision "$DEC" --seed "$SEED" --arms EQ5 --bank evalplus --models "$MODEL" \
  --request-timeout-s 600 --review-timeout-s 380 --probe-sample 0 \
  >>"$OUT.launch.log" 2>&1 < /dev/null 9>&- &
pid=$!
sleep 3
ps -o cmd= -p "$pid" 2>/dev/null | grep -q gain_run.py \
  || pid=$(ps -eo pid,cmd | grep "gain_run\.py --out $OUT " | grep -v grep | awk '{print $1}' | head -1)
say "pid=${pid:-none}; waiting for preflight (量具要先跑完 371/371)"
for _ in $(seq 1 90); do
  sleep 10
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    say "exited early; tail: $(tail -c 700 "$OUT.launch.log" | tr '\n' '|')"; finish exited_early
  fi
  if grep -q '✓' "$OUT.launch.log" 2>/dev/null || [ -e "$OUT/summary.json" ]; then
    say "preflight passed; head: $(head -c 600 "$OUT.launch.log" | tr '\n' '|')"; finish "launched pid=$pid" 0
  fi
done
finish "launch_pending_timeout pid=$pid" 0
