#!/bin/bash
# ops/gain/launch_harness_lcb2.sh — 等 PRIOR_RUN 收官後發射 **harness 六臂**
# （R460，`--arms OFF,CONFORM,OFF5,HPI,HOC,HMIX`，seed `g-r440-lcb2`，LCB v2 120 題）。
#
# ⚠ D9：**兩個後端、兩塊、併發跑**。本支發射的是兩個 run，不是一個：
#     block a = runs/g_r460_harness_lcb2_a  --offset 0  --n 60  → 100.119.113.56:1234
#     block b = runs/g_r460_harness_lcb2_b  --offset 60 --n 60  → 100.86.226.21:1234
#   兩塊各自 setsid、各自 flock、各自 launch.log，**同時**跑。
#
# 承重什麼：
#   (a) SPEC_GAIN §7「一端點一 run」——這條規則**沒有被放寬**，只是被逐字執行：
#       一顆後端同時只有一個 run。2026-09-07 15:40 實測，8765 那顆 hub 把
#       **100% 的請求路由到 1003**（6 次探針：1003 +6、1004 +0），而且併發越高
#       吞吐越差（n=8→12：206→175→144 tok/s）；兩顆直連後端各自在 n=4 熱身後
#       約 110–120 tok/s，服務的都是 gemma-4-12b-it-qat。
#       ⇒ 走 hub ＝ 只用到一張卡而且越推越慢。所以兩塊直連、各打各的。
#       **任何一塊都不准走 hub**（abort_hub_endpoint 硬擋，含 8765 字面）。
#   (b) R440G 閘門檢查得到 run 名字，**檢查不到** seed／題庫／題數／臂／端點；
#       那幾格打錯的話 run 會照跑，而且跑出來的東西看起來完全正常。所以擋在發射前。
#       ⚠ 而且它是**子字串**比對（`gain_run.py:1268`）⇒ 不帶 `_a`／`_b` 的舊名字
#       `g_r460_harness_lcb2` 會**照樣通過**閘門。本支因此自己再擋一次
#       （abort_unsuffixed_run_name）：D9 只授權帶塊名的那兩個。
#   (c) 本支與 launch_eq5_lcb3.sh 最大的兩個差別：**seed 是刻意重用的**、
#       以及**發射兩塊**。所以「新鮮度檢查」被換成「明文授權檢查」，
#       而且換成的版本**更嚴不是更鬆**。
#
# ⚠ seed 重用（DECISION §二-4）：
#   `g-r440-lcb2` 被 `runs/g_r447_conform_lcb2` 用過。既有的 abort_seed_not_fresh
#   （掃到任何命中就停）會擋下一個**我們刻意要的**設定：
#     * LCB v2 bank 就是 120 題、兩塊合起來 `--n 60 + --n 60` 取全部
#       ⇒ seed **只打亂順序、不抽樣** ⇒ 換 seed 不會換到別的題；
#     * 同 seed ⇒ 同題序 ⇒ block a 的 60 題就是 r447 的前 60 題（逐題同序）。
#   所以本支改成三道：
#     1. seed 要寫在 DECISION 內文（abort_seed_not_prereg，沿用）；
#     2. DECISION 內文要有逐字的授權句 `SEED_REUSE_AUTHORIZED: <seed> <- <run>`
#        （abort_seed_reuse_unauthorized）；
#     3. 掃過**所有** runs/*/summary.json，命中集合必須**恰好等於**授權句列出的集合
#        （abort_seed_reuse_set_mismatch）。多一個或少一個都停——
#        「少一個」代表 r447 不見了或讀不到，而**量不到不是通過**。
#
# ⚠ 併發（DECISION §十）：`gain_run.py` **沒有 worker 併發旋鈕，也不准加**。
#   round22/23/262 已量到對**同一個端點**併發送出會觸發 HTTP 500／逾時
#   （DECISION_20260824_SERIALIZE_CONCURRENT_CALLS.md）：client 端「併發」在單一
#   GPU／LM Studio 後端換不到真正的平行運算，只會讓排隊中的請求各自的 timeout 空轉。
#   ⇒ **runner 支援的最大 worker 併發度＝1（依序送出）**，寫在 WORKER_CONCURRENCY。
#   本 run 的平行度**不是**來自這個旋鈕，而是來自「兩個行程各打一顆自己的 GPU」
#   （BLOCK_PARALLELISM=2）：每顆卡上仍然是一次一個請求。
#   若哪天有人在 gain_run.py 裡加了 ThreadPoolExecutor，本支直接中止
#   （abort_concurrency_knob_appeared），逼他回來重新裁決這一格，而不是安靜沿用 1。
#
# 沿用 launch_lcb2.sh／launch_eq5_lcb2.sh／launch_eq5_lcb3.sh 經 R440E／round639
# 審查修過的守則：等待迴圈**錨行首**（未錨會匹配到 grep 自己＝條件恆為真）、
# 發射前重做單 run 檢查、探針驗 body 不只驗 200、目錄與 launch.log 已存在就停、
# 等 preflight ✓、flock 防重複發射。
#
# 用法（vacant-dev）：setsid nohup bash ops/gain/launch_harness_lcb2.sh >/dev/null 2>&1 < /dev/null &
#            立刻發射（不等 PRIOR_RUN）：bash ops/gain/launch_harness_lcb2.sh now
#            換等待目標：PRIOR_RUN=runs/g_rXXX_foo bash ops/gain/launch_harness_lcb2.sh
set -u
ROOT="$HOME/vacant"; REPO="$ROOT/Vacant"; LOG="$ROOT/logs/launch_harness_lcb2.log"
MODEL="gemma-4-12b-it-qat"
DEC="DECISION_20260907_R460_HARNESS_PREREG.md"
SEED="g-r440-lcb2"
ARMS="OFF,CONFORM,OFF5,HPI,HOC,HMIX"
BANK_FILE="ops/gain/data/lcb_bank_v2.jsonl"
# D9：兩塊、兩顆直連後端。名字與端點是**一組**，改一邊就要改另一邊。
OUT_A="runs/g_r460_harness_lcb2_a"
OFFSET_A=0
N_A=60
API_A="http://100.119.113.56:1234/v1/chat/completions"
OUT_B="runs/g_r460_harness_lcb2_b"
OFFSET_B=60
N_B=60
API_B="http://100.86.226.21:1234/v1/chat/completions"
# 任何一塊的端點含 HUB_MARK 就停（D9 明文禁止走 hub）
HUB_MARK="8765"
# 不帶 _a/_b 的舊名字：R440G 是子字串比對、擋不掉它，本支擋
UNSUFFIXED="g_r460_harness_lcb2"
WORKER_CONCURRENCY=1          # runner 支援的最大值；理由見檔頭的併發那一段
BLOCK_PARALLELISM=2           # 平行度來自這裡：兩個行程、兩顆 GPU、各自序列送出
PRIOR_RUN="${PRIOR_RUN:-runs/g_r449c_eq5_lcb3}"
WAIT_PAT="^python3 ops/gain/gain_run\.py --out $PRIOR_RUN"

mkdir -p "$ROOT/logs"
say()    { printf '%s  %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" | tee -a "$LOG"; }
finish() { say "HARNESS_LCB2_LAUNCH_RESULT=$1"; exit "${2:-1}"; }

exec 9>"$ROOT/.launch_harness_lcb2.lock"
flock -n 9 || { say "duplicate launch_harness_lcb2 ignored (pid $$)"; exit 2; }
cd "$REPO" || finish abort_no_repo

# 本支自己**不准**跑別人的 run；只有 OUT_A／OUT_B 兩塊算「自己人」。
count_other_runs() {
  ps -eo cmd | grep "^python3 ops/gain/gain_run\.py" \
    | grep -v -- "--out $OUT_A " | grep -v -- "--out $OUT_B " | wc -l | tr -d ' '
}

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
n=$(count_other_runs)
[ "$n" -eq 0 ] || { say "ABORT: $n 個別的 gain_run.py 還在跑"; finish abort_other_run; }
for OUT in "$OUT_A" "$OUT_B"; do
  [ -d "$OUT" ] && [ -z "$(ls -A "$OUT" 2>/dev/null)" ] && rmdir "$OUT" && say "removed empty $OUT"
  [ -e "$OUT" ] && { say "ABORT: $OUT exists"; finish abort_dir_exists; }
  [ -e "$OUT.launch.log" ] && { say "ABORT: $OUT.launch.log exists"; finish abort_launchlog_exists; }
done
[ -f "$DEC" ] || { say "ABORT: $DEC missing (R440G 閘門要它)"; finish abort_no_decision; }
[ -f "$BANK_FILE" ] || { say "ABORT: $BANK_FILE missing (LCB v2 題庫，120 題)"; finish abort_no_bank; }

# R440G 是子字串比對 ⇒ 不帶塊名的舊 run 名字會照樣通過它。D9 只授權兩塊，本支自己擋。
for OUT in "$OUT_A" "$OUT_B"; do
  case "$(basename "$OUT")" in
    "$UNSUFFIXED") say "ABORT: $OUT 是不帶 _a/_b 的舊名字，D9 沒有授權它"; finish abort_unsuffixed_run_name ;;
  esac
done
[ -e "runs/$UNSUFFIXED" ] && { say "ABORT: runs/$UNSUFFIXED 存在——那是 D9 之前的單塊名字，不准用"; finish abort_unsuffixed_run_name; }
grep -q -- "$OUT_A" "$DEC" || { say "ABORT: $DEC 內文沒有寫到 $OUT_A"; finish abort_block_not_prereg; }
grep -q -- "$OUT_B" "$DEC" || { say "ABORT: $DEC 內文沒有寫到 $OUT_B"; finish abort_block_not_prereg; }

# D9：端點是實驗條件。兩塊不准同端點、任何一塊都不准走 hub。
[ "$API_A" != "$API_B" ] || { say "ABORT: 兩塊指到同一個端點 $API_A"; finish abort_same_endpoint; }
case "$API_A$API_B" in
  *"$HUB_MARK"*) say "ABORT: 端點含 $HUB_MARK（hub）——D9 禁止任何一塊走 hub"; finish abort_hub_endpoint ;;
esac
say "block a → $API_A　block b → $API_B（兩塊直連、不經 hub）"

# 併發：runner 現在是依序送出。哪天有人加了 ThreadPoolExecutor，這一格的
# 「最大值＝1」就過期了 ⇒ 停下來讓他重新裁決，不要安靜沿用。
if grep -q "ThreadPoolExecutor(" ops/gain/gain_run.py; then
  say "ABORT: gain_run.py 出現 ThreadPoolExecutor( ——併發旋鈕變了，WORKER_CONCURRENCY=$WORKER_CONCURRENCY 這格要重新裁決"
  finish abort_concurrency_knob_appeared
fi
say "worker 併發度 = $WORKER_CONCURRENCY（runner 支援的最大值；每顆後端仍是一次一個請求）；區塊平行度 = $BLOCK_PARALLELISM（兩個行程、兩顆 GPU）"

# R440G 只檢查 DECISION 內文有沒有 run 名字，檢查不到 seed；seed 打錯不會被它擋下。
grep -q -- "$SEED" "$DEC" || { say "ABORT: $DEC 內文沒有寫到 seed $SEED"; finish abort_seed_not_prereg; }

# ── seed 重用授權（取代新鮮度檢查；理由見檔頭）──────────────────────────
# 授權句逐字：`SEED_REUSE_AUTHORIZED: <seed> <- runs/a, runs/b`
auth=$(grep -m1 -E "^SEED_REUSE_AUTHORIZED: $SEED <- " "$DEC" | sed -E "s/^SEED_REUSE_AUTHORIZED: $SEED <- //")
[ -n "$auth" ] || { say "ABORT: $DEC 沒有逐字的授權句 'SEED_REUSE_AUTHORIZED: $SEED <- …'"; finish abort_seed_reuse_unauthorized; }
say "seed 重用授權集合：$auth"
scan=$(python3 - "$SEED" "$auth" <<'PY'
import glob, json, sys
seed, auth = sys.argv[1], sys.argv[2]
allowed = sorted({x.strip().rstrip(",") for x in auth.split(",") if x.strip()})
files = sorted(glob.glob("runs/*/summary.json"))
hits = []
for f in files:
    try:
        if json.load(open(f, encoding="utf-8")).get("seed") == seed:
            hits.append(f.rsplit("/summary.json", 1)[0])
    except Exception:
        pass
hits = sorted(set(hits))
print(len(files), "OK" if hits == allowed else "MISMATCH",
      ("|".join(hits) if hits else "-"), ("|".join(allowed) if allowed else "-"))
PY
)
n_files=$(printf '%s\n' "$scan" | awk 'NR==1{print $1}')
verdict=$(printf '%s\n' "$scan" | awk 'NR==1{print $2}')
hit_list=$(printf '%s\n' "$scan" | awk 'NR==1{print $3}')
allow_list=$(printf '%s\n' "$scan" | awk 'NR==1{print $4}')
case "$n_files" in ''|*[!0-9]*) say "ABORT: seed 掃描沒有回傳數字（scan=$scan）"; finish abort_seed_reuse_set_mismatch ;; esac
[ "$n_files" -gt 0 ] || { say "ABORT: runs/*/summary.json 一個都沒掃到——量不到不是通過"; finish abort_seed_reuse_set_mismatch; }
[ "$verdict" = "OK" ] || { say "ABORT: seed $SEED 的使用集合與授權不符（實際=$hit_list 授權=$allow_list）"; finish abort_seed_reuse_set_mismatch; }
say "seed $SEED 的使用集合 = 授權集合（$hit_list）；掃過 $n_files 個 runs/*/summary.json"

# ── 探針：每一塊探**自己的**後端，不探 hub ────────────────────────────
probe_backend() {   # $1=tag $2=chat endpoint
  tag="$1"; api="$2"; base="${api%/chat/completions}"
  first=$(curl -s -m 15 "$base/models" \
          | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["data"][0]["id"] if d.get("data") else "none")' 2>/dev/null)
  say "[$tag] $base/models first model = $first"
  # ⚠ 回傳碼刻意全部 ≥ 1：`return $ok` 在 ok=0（三次全掛）時會是 0＝成功，
  #   那正是「後端整個死掉」的情形，絕對不能被讀成通過。所以偏移成 10+ok。
  [ -n "$first" ] && [ "$first" != "none" ] || { say "[$tag] ABORT: /v1/models 沒有回任何模型"; return 9; }
  ok=0
  for i in 1 2 3; do
    code=$(curl -s -m 120 -o "$ROOT/logs/harness_lcb2_${tag}_probe_$i.json" -w '%{http_code}' "$api" \
           -H 'Content-Type: application/json' \
           -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":16,\"temperature\":0}" || true)
    body=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1])); c = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    print("yes" if ("error" not in d and c.strip()) else "no")
except Exception: print("no")' "$ROOT/logs/harness_lcb2_${tag}_probe_$i.json")
    say "[$tag] probe $i -> HTTP $code body_ok=$body"
    [ "$code" = "200" ] && [ "$body" = "yes" ] && ok=$((ok + 1))
  done
  [ "$ok" -eq 3 ] || { say "[$tag] ABORT: 探針只過 $ok/3"; return $((10 + ok)); }
  # 多輪線路探針（HARNESS_STUDY §4.0.2）：四則訊息（system／user／assistant／user）。
  # 這裡只記錄，**不**在發射器裡決定模式——模式由 runner 自己的 probe_wire_mode
  # 決定並落盤，兩個地方各自判會出現「發射器說 multiturn、rows 說 flattened」這種對不上的狀態。
  mt=$(curl -s -m 120 -o "$ROOT/logs/harness_lcb2_${tag}_multiturn_probe.json" -w '%{http_code}' "$api" \
       -H 'Content-Type: application/json' \
       -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"system\",\"content\":\"Reply with exactly: OK\"},{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"},{\"role\":\"assistant\",\"content\":\"OK\"},{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":16,\"temperature\":0}" || true)
  say "[$tag] multiturn wire probe -> HTTP $mt（僅記錄；模式由 runner 落盤在 harness_wire_mode）"
  return 0
}

# rc 9 ＝ /v1/models 沒回模型；rc 10+k ＝ 三次 chat 探針只過 k 次。
probe_backend a "$API_A" || finish "abort_probe_a_rc$?"
probe_backend b "$API_B" || finish "abort_probe_b_rc$?"

# ── 發射：兩塊各自 setsid、各自 flock、各自 launch.log ────────────────
launch_block() {   # $1=tag $2=OUT $3=offset $4=n $5=api
  tag="$1"; OUT="$2"; off="$3"; nn="$4"; api="$5"
  lock="$ROOT/.launch_harness_lcb2_${tag}.lock"
  say "[$tag] launching -> $OUT (seed=$SEED[重用，授權見 $DEC §二-4], bank=lcb2, n=$nn offset=$off, arms=$ARMS, api=$api, lock=$lock)"
  curl -s -m 15 "${api%/chat/completions}/models" > "$OUT.backend.json" 2>/dev/null || true
  PYTHONUNBUFFERED=1 \
  VACANT_GAIN_API="$api" CLINE_KEYS=/nonexistent \
  setsid nohup flock -n "$lock" python3 ops/gain/gain_run.py --out "$OUT" --n "$nn" --offset "$off" \
    --decision "$DEC" --seed "$SEED" --arms "$ARMS" --bank lcb2 --models "$MODEL" \
    --request-timeout-s 600 --review-timeout-s 380 --retries 4 --probe-sample 0 \
    >>"$OUT.launch.log" 2>&1 < /dev/null 9>&- &
  # `$!` 是 setsid 的 pid，它 fork 完就結束 ⇒ 不能拿來當存活訊號。改用 ps 找。
  # ⚠ `flock` 的那一行也含「python3 ops/gain/gain_run.py --out …」⇒ 會誤中。
  #   用 `$2 == "python3"` 只取真正的 runner 行程。
  find_pid() {
    ps -eo pid,cmd | grep "gain_run\.py --out $OUT " | grep -v grep \
      | awk '$2 == "python3" {print $1}' | head -1
  }
  sleep 3
  pid=$(find_pid)
  # setsid＋flock＋python 起來可能超過 3 秒；先給它 30 秒再判定沒起來。
  for _ in 1 2 3 4 5 6 7 8 9; do
    [ -n "$pid" ] && break
    sleep 3; pid=$(find_pid)
  done
  say "[$tag] pid=${pid:-none}; waiting for preflight (量具要先跑完兩個方向＋可見閘門覆蓋 $nn/$nn)"
  [ -n "$pid" ] || { say "[$tag] 30 秒內沒看到 runner 行程（flock 被別人握著？）; tail: $(tail -c 700 "$OUT.launch.log" | tr '\n' '|')"; return 1; }
  for _ in $(seq 1 90); do
    sleep 10
    if ! kill -0 "$pid" 2>/dev/null; then
      say "[$tag] exited early; tail: $(tail -c 700 "$OUT.launch.log" | tr '\n' '|')"; return 1
    fi
    if grep -q '✓' "$OUT.launch.log" 2>/dev/null || [ -e "$OUT/summary.json" ]; then
      say "[$tag] preflight passed; head: $(head -c 600 "$OUT.launch.log" | tr '\n' '|')"
      say "[$tag] launched pid=$pid"; return 0
    fi
  done
  say "[$tag] launch_pending_timeout pid=$pid"; return 0
}

launch_block a "$OUT_A" "$OFFSET_A" "$N_A" "$API_A" || finish exited_early_a
n=$(count_other_runs)
[ "$n" -eq 0 ] || { say "ABORT: block a 起來之後冒出 $n 個別的 gain_run.py"; finish abort_other_run; }
launch_block b "$OUT_B" "$OFFSET_B" "$N_B" "$API_B" || finish exited_early_b

say "兩塊都已發射；收官一律兩塊一起餵給 analyzer："
say "  python3 ops/gain/analyze_r460.py --run $OUT_A $OUT_B --bank lcb2 --rescore-turn1"
finish "launched_both" 0
