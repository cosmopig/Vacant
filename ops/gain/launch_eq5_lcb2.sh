#!/bin/bash
# ops/gain/launch_eq5_lcb2.sh — 等 PRIOR_RUN 收官後發射 **EQ5 在 LCB v2（難題）上的第一次跑**
# （R449B，`runs/g_r449_eq5_lcb2`，seed `g-r449-eq5-lcb2`）。
#
# 承重什麼：
#   (a) SPEC_GAIN §7「一端點一 run」——8765 只有一顆 GPU，兩個 run 同時打會互相把
#       請求推過 timeout，而那看起來會像「模型變差了」。
#   (b) DECISION_20260906_R448_FABLE_AUDIT_REPLICATED.md §六 第二條推翻條件：
#       「若在 LCB 上跑 EQ5（同候選設計）而 CI 跨 0 ⇒ §四 的話要加『僅在 MBPP+ 量級的
#       題目上』」——那條到現在沒有資料可判，這支就是去把它變成可判。
#   (c) R440G 閘門檢查得到 run 名字、檢查不到 seed／題庫／題數；那幾格打錯的話 run 會
#       照跑，而且跑出來的東西看起來完全正常。所以擋在發射前。
#
# PRIOR_RUN（環境變數，預設 runs/g_r448_eq5_mbpp_seed2，該 run 已 run_terminal=true）
# ＝要等哪一個 run 收官才發射。寫成環境變數而不是寫死，是因為誰佔著端點會換
# （2026-09 之間換過 r447 → r461 → r448），腳本本體不該跟著端點換人就要改。
# **WAIT_PAT 與 abort_prior_not_terminal 的 terminal 檢查都讀這同一個變數**，
# 只改一邊會讓等待迴圈跟中止檢查看的不是同一個 run。
#
# 沿用 launch_lcb2.sh／launch_eq5_seed2.sh 經 R440E／round639 審查修過的守則：
#   等待迴圈**錨行首**（未錨會匹配到 grep 自己＝條件恆為真）、發射前重做單 run 檢查、
#   探針驗 body 不只驗 200、目錄與 launch.log 已存在就停、等 preflight ✓。
# 本支比 launch_eq5_seed2.sh 多／改的三道，理由都寫在該行上：
#   (1) seed 新鮮度**改成掃過所有 `runs/*/summary.json`**，不是跟單一顆舊 seed 比字串——
#       repo 裡已經有 42 個 summary.json、9 顆不同的 seed，跟其中一顆比等於沒比；
#   (2) 題庫檔改檢查 `ops/gain/data/lcb_bank_v2.jsonl`（LCB v2 不吃 EvalPlus 官方包）；
#   (3) DECISION 內文必須同時寫到 run 名字（R440G 自己會檢）與這顆 seed（它檢不到）。
#
# 用法（vacant-dev）：setsid nohup bash ops/gain/launch_eq5_lcb2.sh >/dev/null 2>&1 < /dev/null &
#            立刻發射（不等 PRIOR_RUN）：bash ops/gain/launch_eq5_lcb2.sh now
#            換等待目標：PRIOR_RUN=runs/g_rXXX_foo bash ops/gain/launch_eq5_lcb2.sh
set -u
ROOT="$HOME/vacant"; REPO="$ROOT/Vacant"; LOG="$ROOT/logs/launch_eq5_lcb2.log"
HUB="http://100.119.113.56:8765/v1/chat/completions"
MODEL="gemma-4-12b-it-qat"
OUT="runs/g_r449_eq5_lcb2"
DEC="DECISION_20260906_R449B_EQ5_LCB2_PREREG.md"
SEED="g-r449-eq5-lcb2"
BANK_FILE="ops/gain/data/lcb_bank_v2.jsonl"
PRIOR_RUN="${PRIOR_RUN:-runs/g_r448_eq5_mbpp_seed2}"
WAIT_PAT="^python3 ops/gain/gain_run\.py --out $PRIOR_RUN"

mkdir -p "$ROOT/logs"
say()    { printf '%s  %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" | tee -a "$LOG"; }
finish() { say "EQ5_LCB2_LAUNCH_RESULT=$1"; exit "${2:-1}"; }

exec 9>"$ROOT/.launch_eq5_lcb2.lock"
flock -n 9 || { say "duplicate launch_eq5_lcb2 ignored (pid $$)"; exit 2; }
cd "$REPO" || finish abort_no_repo

if [ "${1:-}" != "now" ]; then
  if ps -eo cmd | grep -q "$WAIT_PAT"; then
    say "waiting for PRIOR_RUN=$PRIOR_RUN to finish ($WAIT_PAT)"
    while ps -eo cmd | grep -q "$WAIT_PAT"; do sleep 60; done
    say "PRIOR_RUN=$PRIOR_RUN gone; settling 60s"; sleep 60
  else
    # PRIOR_RUN 沒在跑有兩種可能：已經收官，或者還沒發射／中途死掉。
    # 只有第一種准往下走——否則這支會在 PRIOR_RUN 發射之前先占住端點，
    # 而「誰先搶到」不是實驗設計該有的變因。
    term=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1])); print("yes" if d.get("run_terminal") is True else "no")
except Exception: print("no")' "$PRIOR_RUN/summary.json")
    [ "$term" = "yes" ] || { say "ABORT: PRIOR_RUN=$PRIOR_RUN 既沒在跑也還沒 terminal (run_terminal=$term)"; finish abort_prior_not_terminal; }
    say "PRIOR_RUN=$PRIOR_RUN already terminal; proceeding"
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
[ -f "$BANK_FILE" ] || { say "ABORT: $BANK_FILE missing (LCB v2 題庫，120 題)"; finish abort_no_bank; }

# seed 新鮮度：**掃過所有 runs/*/summary.json**，不是跟某一顆舊 seed 比字串。
# 抄到一顆用過的 seed，跑出來的是「同抽樣再跑一次」而不是新的一批，
# 而 rows 裡沒有任何欄位事後分得出這兩件事的差別——只有發射時擋得住。
# 掃到 0 個 summary.json 也要停：那是「沒接上」不是「都很新鮮」。
scan=$(python3 - "$SEED" <<'PY'
import glob, json, sys
seed = sys.argv[1]
files = sorted(glob.glob("runs/*/summary.json"))
hits = []
for f in files:
    try:
        if json.load(open(f, encoding="utf-8")).get("seed") == seed:
            hits.append(f)
    except Exception:
        pass
print(len(files), len(hits), ",".join(hits) if hits else "-")
PY
)
n_files=$(printf '%s\n' "$scan" | awk 'NR==1{print $1}')
n_hits=$(printf '%s\n' "$scan" | awk 'NR==1{print $2}')
hit_list=$(printf '%s\n' "$scan" | awk 'NR==1{print $3}')
case "$n_files" in ''|*[!0-9]*) say "ABORT: seed 掃描沒有回傳數字（scan=$scan）"; finish abort_seed_not_fresh ;; esac
case "$n_hits"  in ''|*[!0-9]*) say "ABORT: seed 掃描沒有回傳數字（scan=$scan）"; finish abort_seed_not_fresh ;; esac
[ "$n_files" -gt 0 ] || { say "ABORT: runs/*/summary.json 一個都沒掃到——量不到不是通過"; finish abort_seed_not_fresh; }
[ "$n_hits" -eq 0 ] || { say "ABORT: seed $SEED 已經被用過（$hit_list）"; finish abort_seed_not_fresh; }
say "seed $SEED 新鮮：掃過 $n_files 個 runs/*/summary.json，0 個用過它"

# R440G 只檢查 DECISION 內文有沒有 run 名字，檢查不到 seed；seed 打錯不會被它擋下。
grep -q -- "$SEED" "$DEC" || { say "ABORT: $DEC 內文沒有寫到 seed $SEED"; finish abort_seed_not_prereg; }

first=$(curl -s -m 15 "http://100.119.113.56:8765/v1/models" \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["data"][0]["id"] if d.get("data") else "none")' 2>/dev/null)
say "8765 first model = $first"
ok=0
for i in 1 2 3; do
  code=$(curl -s -m 120 -o "$ROOT/logs/eq5_lcb2_probe_$i.json" -w '%{http_code}' "$HUB" \
         -H 'Content-Type: application/json' \
         -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":16,\"temperature\":0}" || true)
  body=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1])); c = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    print("yes" if ("error" not in d and c.strip()) else "no")
except Exception: print("no")' "$ROOT/logs/eq5_lcb2_probe_$i.json")
  say "probe $i -> HTTP $code body_ok=$body"
  [ "$code" = "200" ] && [ "$body" = "yes" ] && ok=$((ok + 1))
done
[ "$ok" -eq 3 ] || finish "abort_probe_${ok}of3"

say "launching -> $OUT (seed=$SEED, bank=lcb2, n=120 offset=0；與 r446/r448 的差別＝題庫＋題數＋seed)"
curl -s -m 15 "http://100.119.113.56:8765/v1/models" > "$OUT.backend.json" 2>/dev/null || true
PYTHONUNBUFFERED=1 \
VACANT_GAIN_API="$HUB" CLINE_KEYS=/nonexistent \
setsid nohup python3 ops/gain/gain_run.py --out "$OUT" --n 120 --offset 0 \
  --decision "$DEC" --seed "$SEED" --arms EQ5 --bank lcb2 --models "$MODEL" \
  --request-timeout-s 600 --review-timeout-s 380 --probe-sample 0 \
  >>"$OUT.launch.log" 2>&1 < /dev/null 9>&- &
pid=$!
sleep 3
ps -o cmd= -p "$pid" 2>/dev/null | grep -q gain_run.py \
  || pid=$(ps -eo pid,cmd | grep "gain_run\.py --out $OUT " | grep -v grep | awk '{print $1}' | head -1)
say "pid=${pid:-none}; waiting for preflight (量具要先跑完 12/12 兩個方向)"
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
