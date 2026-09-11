#!/bin/bash
# ops/gain/launch_harness_rep_block.sh — 發射 **一塊** R460R 複製跑
# （五次複製 × 六塊 ＝ 30 塊，`DECISION_20260911_R460R_FIVE_REPLICATIONS_PREREG.md`）。
#
# 這支在架構裡承重什麼：**它是 30 塊唯一的發射入口**，而且它只發一塊。
# 「排程」（誰先跑、跑在哪顆卡上、掛了要不要重排）全部在
# `ops/gain/schedule_harness_reps.py`；本支只負責「這一塊發射之前必須成立的事」。
# 兩件事分開的理由：R460 的 `launch_harness_lcb2.sh` 把拓撲檢查與發射綁在一起
# （六塊、每顆三塊），而 R460R 的拓撲是**排程器當場決定的**——
# 把「每顆端點幾塊」這種平衡規則留在發射器裡，它量的就不是它想量的東西了
# （R460 §二-5 已經為了同一個理由修訂過一次）。
#
# 沿用 `launch_harness_lcb2.sh` 經 R440E／round639／round460e-2／round460h 審查
# 修過的每一道 preflight，逐條對應（`tests/test_r460r_scheduler.py` 對釘）：
#   · R440G 預註冊閘門（DECISION 內文要有 run 名字）＋ `--offset`／`--gauge-scope`
#     ／seed／`--request-timeout-s` 都要逐字寫在 DECISION 裡；
#   · 目錄與 launch.log 已存在就停（收官證據不准被覆蓋）；
#   · 舊名字擋掉（R440G 是子字串比對，擋不掉 `_a`／`_b` 那種）；
#   · **hub 禁止**（`8765` 字面）；
#   · **探針 max_tokens 512**（round460e-2：16 會被 reasoning 吃光、content 交空白，
#     後端是好的、紅的是量具）；body 檢查**不放寬**（仍要求 content 非空）；
#   · `/v1/models` 要回得出模型；三次 chat 探針要**三次全過**；
#   · **seed 授權集合相等**檢查（比新鮮度檢查更嚴，見下面 SEED_AUTHORIZED_SET）；
#   · `ThreadPoolExecutor(` 一出現就停（併發旋鈕變了要重新裁決）；
#   · 每一塊自己的 `flock`、自己的 `launch.log`、自己的 `backend.json`、`setsid`。
#
# ⚠ **本支不做的事**（刻意）：不等 PRIOR_RUN、不檢查「有沒有別的 gain_run 在跑」、
#   不檢查端點上有幾塊。前兩件在 R460R 之下**會擋掉自己人**（排程器一次要開四塊，
#   彼此都是「別的 gain_run」）；第三件是排程器的槽位在管，而槽位算的是「這一刻」，
#   比表上的塊數準。⇒ **併發上限的牙齒在排程器與 analyzer 兩邊**
#   （`analyze_r460.py` 的 `endpoint_concurrency_exceeded` 從 calls.jsonl 的時間窗重算）。
#
# 用法（由排程器呼叫；也可以手動發一塊）：
#   TAG=r1a1 OUT=runs/g_r460r1_harness_lcb2_a1 OFFSET=0 SEED=g-r460r1-lcb2 \
#   API=http://100.86.226.21:1234/v1/chat/completions \
#   bash ops/gain/launch_harness_rep_block.sh
set -u
ROOT="${VACANT_ROOT:-$HOME/vacant}"; REPO="${VACANT_REPO:-$ROOT/Vacant}"
LOG="$ROOT/logs/launch_harness_rep_block.log"
MODEL="gemma-4-12b-it-qat"
DEC="${DEC:-DECISION_20260911_R460R_FIVE_REPLICATIONS_PREREG.md}"
ARMS="OFF,CONFORM,OFF5,HPI,HOC,HMIX"
BANK_FILE="ops/gain/data/lcb_bank_v2.jsonl"
N_BLOCK=20
REQUEST_TIMEOUT_S=1200        # R460 §二-1 的實驗條件，一個字不動
PROBE_MAX_TOKENS=512          # round460e-2；與 harness_arms.WIRE_PROBE_MAX_TOKENS 對齊
GAUGE_SCOPE=bank              # R1：**這次每一塊都是 bank**（12/12，不受切法影響）
HUB_MARK="8765"
# R460R 的 30 個授權塊名（＝ seed 掃描的自己人清單）。
ALL_OUTS=""
for k in 1 2 3 4 5; do
  for t in a1 a2 a3 b1 b2 b3; do
    ALL_OUTS="$ALL_OUTS runs/g_r460r${k}_harness_lcb2_${t}"
  done
done
# Fable R4 逐字：「seed authorization check extended to the 30 names + r447」。
# r447 與 R460 六塊用的是 **g-r440-lcb2**，而本 run 五顆 seed 都是新的
# ⇒ 把它們放進排除清單對這五顆 seed 是**可證明的 no-op**（它們永遠不會命中）。
# 照樣寫進來，因為 R4 指名了它，而且哪天有人把本支拿去發一顆重用的 seed 時
# 這一格才不會變成「當初為什麼少了一個名字」。
SEED_SCAN_EXCLUDE="$ALL_OUTS runs/g_r447_conform_lcb2"
for t in a1 a2 a3 b1 b2 b3; do
  SEED_SCAN_EXCLUDE="$SEED_SCAN_EXCLUDE runs/g_r460_harness_lcb2_${t}"
done
# 不帶塊名／不帶複製編號的舊名字：R440G 是子字串比對，擋不掉它們。
STALE_NAMES="g_r460r_harness_lcb2 g_r460_harness_lcb2 g_r460_harness_lcb2_a g_r460_harness_lcb2_b"

TAG="${TAG:?TAG 必須給（例：r1a1）}"
OUT="${OUT:?OUT 必須給（例：runs/g_r460r1_harness_lcb2_a1）}"
OFFSET="${OFFSET:?OFFSET 必須給（0/20/40/60/80/100）}"
SEED="${SEED:?SEED 必須給（例：g-r460r1-lcb2）}"
API="${API:?API 必須給（直連端點，不准 hub）}"

mkdir -p "$ROOT/logs"
# ── UTF-8 安全的位元組截斷（2026-09-11 事故修補）──────────────────────────
# `head -c N`／`tail -c N` 是**按位元組**切的，而 launch.log 裡全是中文
# ⇒ 切點落在一個 3 byte 字元中間就會吐出半個字元（實測 `\xe4\xb8` 收尾）。
# 那半個字元沿著本支的 stdout 一路傳回排程器，而排程器的
# `subprocess.run(..., text=True)` 會 **UnicodeDecodeError 當場死掉**——
# 2026-09-11 11:04:01Z 的 R529 排程器與（同一種寫法的）R460R 排程器都是這樣死的。
# ⇒ 截斷之後一律過一次 `iconv -c`（丟掉不合法的位元組序列）。
# 排程器那一端也改成 `errors="replace"`；**兩邊都修**，因為
# 「壞位元組不該讓排程器死」與「不要產生壞位元組」是兩條不同的紅線。
u8() { iconv -c -f UTF-8 -t UTF-8 2>/dev/null || cat; }

say()    { printf '%s  [%s] %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$TAG" "$*" | tee -a "$LOG"; }
finish() { say "REP_BLOCK_LAUNCH_RESULT=$1"; exit "${2:-1}"; }

cd "$REPO" || finish abort_no_repo

# ── preflight ────────────────────────────────────────────────────────────
[ -f "$DEC" ] || { say "ABORT: $DEC missing（R440G 閘門要它）"; finish abort_no_decision; }
[ -f "$BANK_FILE" ] || { say "ABORT: $BANK_FILE missing"; finish abort_no_bank; }
grep -q -- "$(basename "$OUT")" "$DEC" || { say "ABORT: $DEC 內文沒有寫到 $OUT"; finish abort_block_not_prereg; }
grep -q -- "--offset $OFFSET" "$DEC" || { say "ABORT: $DEC 內文沒有寫到 --offset $OFFSET"; finish abort_offset_not_prereg; }
grep -q -- "--gauge-scope $GAUGE_SCOPE" "$DEC" || { say "ABORT: $DEC 內文沒有寫到 --gauge-scope $GAUGE_SCOPE"; finish abort_gauge_not_prereg; }
grep -q -- "$SEED" "$DEC" || { say "ABORT: $DEC 內文沒有寫到 seed $SEED"; finish abort_seed_not_prereg; }
grep -q -- "--request-timeout-s $REQUEST_TIMEOUT_S" "$DEC" || {
  say "ABORT: $DEC 內文沒有寫到 --request-timeout-s $REQUEST_TIMEOUT_S"; finish abort_timeout_not_prereg; }

case "$API" in
  *"$HUB_MARK"*) say "ABORT: 端點含 $HUB_MARK（hub）——禁止任何一塊走 hub"; finish abort_hub_endpoint ;;
esac
for stale in $STALE_NAMES; do
  [ "$(basename "$OUT")" = "$stale" ] && { say "ABORT: $OUT 是舊名字 $stale"; finish abort_stale_run_name; }
done
[ -d "$OUT" ] && [ -z "$(ls -A "$OUT" 2>/dev/null)" ] && rmdir "$OUT" && say "removed empty $OUT"
[ -e "$OUT" ] && { say "ABORT: $OUT exists"; finish abort_dir_exists; }
[ -e "$OUT.launch.log" ] && { say "ABORT: $OUT.launch.log exists"; finish abort_launchlog_exists; }

if grep -q "ThreadPoolExecutor(" ops/gain/gain_run.py; then
  say "ABORT: gain_run.py 出現 ThreadPoolExecutor( ——併發旋鈕變了，要重新裁決"
  finish abort_concurrency_knob_appeared
fi

# ── seed 授權集合（比新鮮度檢查更嚴；R460 §二-4 的同一條紀律）──────────
# DECISION 內文要有逐字的 `SEED_AUTHORIZED_SET: <seed> <- <集合或 NONE>`，
# 而 runs/*/summary.json 掃到的使用集合（扣掉自己人）必須**恰好等於**它。
# 多一個或少一個都停——「少一個」代表被引用的那個 run 不見了，而**量不到不是通過**。
auth=$(grep -m1 -E "^SEED_AUTHORIZED_SET: $SEED <- " "$DEC" | sed -E "s/^SEED_AUTHORIZED_SET: $SEED <- //")
[ -n "$auth" ] || { say "ABORT: $DEC 沒有逐字的 'SEED_AUTHORIZED_SET: $SEED <- …'"; finish abort_seed_authorization_missing; }
say "seed 授權集合：$auth"
scan=$(python3 - "$SEED" "$auth" "$SEED_SCAN_EXCLUDE" <<'PY'
import glob, json, sys
seed, auth, own_s = sys.argv[1], sys.argv[2], sys.argv[3]
allowed = sorted({x.strip().rstrip(",") for x in auth.split(",") if x.strip()})
if allowed == ["NONE"]:
    allowed = []
own = {x.strip() for x in own_s.split() if x.strip()}
files = sorted(glob.glob("runs/*/summary.json"))
hits, skipped = [], []
for f in files:
    try:
        if json.load(open(f, encoding="utf-8")).get("seed") == seed:
            run = f.rsplit("/summary.json", 1)[0]
            (skipped if run in own else hits).append(run)
    except Exception:
        pass
hits = sorted(set(hits))
print(len(files), "OK" if hits == allowed else "MISMATCH",
      ("|".join(hits) if hits else "-"), ("|".join(allowed) if allowed else "-"),
      ("|".join(sorted(set(skipped))) if skipped else "-"))
PY
)
n_files=$(printf '%s\n' "$scan" | awk 'NR==1{print $1}')
verdict=$(printf '%s\n' "$scan" | awk 'NR==1{print $2}')
hit_list=$(printf '%s\n' "$scan" | awk 'NR==1{print $3}')
allow_list=$(printf '%s\n' "$scan" | awk 'NR==1{print $4}')
own_list=$(printf '%s\n' "$scan" | awk 'NR==1{print $5}')
case "$n_files" in ''|*[!0-9]*) say "ABORT: seed 掃描沒有回傳數字（scan=$scan）"; finish abort_seed_scan_broken ;; esac
[ "$n_files" -gt 0 ] || { say "ABORT: runs/*/summary.json 一個都沒掃到——量不到不是通過"; finish abort_seed_scan_empty; }
[ "$verdict" = "OK" ] || { say "ABORT: seed $SEED 的使用集合與授權不符（實際=$hit_list 授權=$allow_list）"; finish abort_seed_set_mismatch; }
say "seed $SEED 使用集合 = 授權集合（$hit_list）；掃過 $n_files 個 summary.json；排除（不計入）：$own_list"

# ── 探針：只探這一塊真的會用到的那顆端點 ───────────────────────────────
base="${API%/chat/completions}"
first=$(curl -s -m 15 "$base/models" \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["data"][0]["id"] if d.get("data") else "none")' 2>/dev/null)
say "$base/models first model = $first"
[ -n "$first" ] && [ "$first" != "none" ] || { say "ABORT: /v1/models 沒有回任何模型"; finish abort_probe_models; }
ok=0
for i in 1 2 3; do
  code=$(curl -s -m 120 -o "$ROOT/logs/rep_${TAG}_probe_$i.json" -w '%{http_code}' "$API" \
         -H 'Content-Type: application/json' \
         -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":$PROBE_MAX_TOKENS,\"temperature\":0}" || true)
  body=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1])); c = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    print("yes" if ("error" not in d and c.strip()) else "no")
except Exception: print("no")' "$ROOT/logs/rep_${TAG}_probe_$i.json")
  say "probe $i -> HTTP $code body_ok=$body"
  [ "$code" = "200" ] && [ "$body" = "yes" ] && ok=$((ok + 1))
done
[ "$ok" -eq 3 ] || { say "ABORT: 探針只過 $ok/3"; finish "abort_probe_only_$ok"; }

# ── 發射 ─────────────────────────────────────────────────────────────────
lock="$ROOT/.launch_rep_${TAG}.lock"
say "launching -> $OUT (seed=$SEED bank=lcb2 n=$N_BLOCK offset=$OFFSET arms=$ARMS api=$API gauge-scope=$GAUGE_SCOPE lock=$lock)"
curl -s -m 15 "$base/models" > "$OUT.backend.json" 2>/dev/null || true
printf '%s\n' "$API" > "$OUT.endpoint"     # 排程器重啟後靠它把塊認回原本的槽
PYTHONUNBUFFERED=1 \
VACANT_GAIN_API="$API" CLINE_KEYS=/nonexistent \
setsid nohup flock -n "$lock" python3 ops/gain/gain_run.py --out "$OUT" --n "$N_BLOCK" --offset "$OFFSET" \
  --decision "$DEC" --seed "$SEED" --arms "$ARMS" --bank lcb2 --models "$MODEL" \
  --request-timeout-s "$REQUEST_TIMEOUT_S" --review-timeout-s 380 --retries 4 \
  --probe-sample 0 --gauge-scope "$GAUGE_SCOPE" \
  >>"$OUT.launch.log" 2>&1 < /dev/null 9>&- &

# `$!` 是 setsid 的 pid（fork 完就結束）⇒ 不能拿來當存活訊號；用 ps 找真的 runner。
# ⚠ `flock` 那一行也含「python3 ops/gain/gain_run.py --out …」⇒ 用 `$2 == "python3"` 濾掉。
find_pid() {
  ps -eo pid,cmd | grep "gain_run\.py --out $OUT " | grep -v grep \
    | awk '$2 == "python3" {print $1}' | head -1
}
sleep 3
pid=$(find_pid)
for _ in 1 2 3 4 5 6 7 8 9; do
  [ -n "$pid" ] && break
  sleep 3; pid=$(find_pid)
done
[ -n "$pid" ] || { say "30 秒內沒看到 runner 行程（flock 被別人握著？）; tail: $(tail -c 700 "$OUT.launch.log" | u8 | tr '\n' '|')"; finish abort_no_runner_process; }
say "pid=$pid; waiting for preflight（量具兩個方向＋可見閘門覆蓋 $N_BLOCK/$N_BLOCK）"
for _ in $(seq 1 90); do
  sleep 10
  if ! kill -0 "$pid" 2>/dev/null; then
    say "exited early; tail: $(tail -c 700 "$OUT.launch.log" | u8 | tr '\n' '|')"
    finish exited_early
  fi
  if grep -q '✓' "$OUT.launch.log" 2>/dev/null || [ -e "$OUT/summary.json" ]; then
    say "preflight passed; head: $(head -c 600 "$OUT.launch.log" | u8 | tr '\n' '|')"
    finish "launched_pid_$pid" 0
  fi
done
say "launch_pending_timeout pid=$pid"
finish "launch_pending_timeout_pid_$pid" 0
