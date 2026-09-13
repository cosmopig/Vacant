#!/bin/bash
# ops/gain/launch_r529_block.sh — 發射 **一塊** R529 跨題庫跑
# （`DECISION_20260911_R529_CROSS_BANK_PREREG.md`）。
#
# 這支在架構裡承重什麼：**它是 R529 全部塊唯一的發射入口**，而且它只發一塊。
# 排程（誰先跑、跑在哪一格、掛了要不要重排、現在准開幾槽）全部在
# `ops/gain/schedule_queue.py`；本支只負責「這一塊發射之前必須成立的事」。
#
# 與 `launch_harness_rep_block.sh`（R460R 那一支）的差別，只有一件事：
# **R460R 的塊形狀是寫死的（lcb2／n=20／六臂），R529 的四個題目集形狀都不一樣**
# ⇒ bank／bank_filter／n／offset／seed 由排程器帶進來。
# 參數化之後，「這一塊是不是預註冊過的」就不能再靠「DECISION 裡有沒有出現
# `--offset 0`」這種**逐項**子字串比對了——四個題目集裡到處都是 `--offset 0`，
# 逐項比對會讓「lcb3-hard 的 offset 0」通過「evalplus 的 offset 0」那一行。
# ⇒ 改成**整組比對**：DECISION 必須有一行逐字的
#
#     R529_BLOCK: <name> bank=<bank> filter=<filter|-> n=<n> offset=<offset> seed=<seed>
#
# 少一個欄位、錯一個數字，這一行就對不上，塊就發不出去。
#
# 其餘 preflight 逐條沿用 R460R 那一支（經 R440E／round639／round460e-2／round460h
# 審查修過的每一道）：
#   · R440G 預註冊閘門（DECISION 要在、要寫得到這一塊）；
#   · 目錄與 launch.log 已存在就停（收官證據不准被覆蓋）；
#   · **hub 禁止**（`8765` 字面）；
#   · **探針 max_tokens 512**（round460e-2），body 要求 content 非空；
#   · `/v1/models` 要回得出模型；三次 chat 探針要**三次全過**；
#   · **seed 授權集合相等**檢查；自己人清單裡的每一個名字**也要寫在 DECISION 裡**
#     （否則排程器可以自己遞一份清單把別的 run 洗白）；
#   · `ThreadPoolExecutor(` 一出現就停；
#   · 每一塊自己的 `flock`、自己的 `launch.log`、自己的 `backend.json`、`setsid`。
#
# 用法（由排程器呼叫；也可以手動發一塊）：
#   TAG=r529lcb3m1 OUT=runs/g_r529_lcb3m_a1 OFFSET=0 SEED=g-r529-lcb3 \
#   BANK=lcb3 BANK_FILTER=difficulty=medium N_BLOCK=20 \
#   ARMS=OFF,CONFORM,HMIX REQUEST_TIMEOUT_S=900 REVIEW_TIMEOUT_S=380 \
#   GAUGE_SCOPE=bank MODEL=gemma-4-12b-it-qat \
#   SEED_SCAN_EXCLUDE="runs/g_r529_lcb3m_a1 …" \
#   API=http://100.86.226.21:1234/v1/chat/completions \
#   bash ops/gain/launch_r529_block.sh
set -u
ROOT="${VACANT_ROOT:-$HOME/vacant}"; REPO="${VACANT_REPO:-$ROOT/Vacant}"
LOG="$ROOT/logs/launch_r529_block.log"
DEC="${DEC:-DECISION_20260911_R529_CROSS_BANK_PREREG.md}"
PROBE_MAX_TOKENS=512          # round460e-2；與 harness_arms.WIRE_PROBE_MAX_TOKENS 對齊
HUB_MARK="8765"

TAG="${TAG:?TAG 必須給（例：r529lcb3m1）}"
OUT="${OUT:?OUT 必須給（例：runs/g_r529_lcb3m_a1）}"
OFFSET="${OFFSET:?OFFSET 必須給}"
SEED="${SEED:?SEED 必須給}"
API="${API:?API 必須給（直連端點，不准 hub）}"
BANK="${BANK:?BANK 必須給（lcb3／evalplus／humanevalplus）}"
BANK_FILTER="${BANK_FILTER:-}"
N_BLOCK="${N_BLOCK:?N_BLOCK 必須給}"
ARMS="${ARMS:?ARMS 必須給（例：OFF,CONFORM,HMIX）}"
MODEL="${MODEL:-gemma-4-12b-it-qat}"
REQUEST_TIMEOUT_S="${REQUEST_TIMEOUT_S:?REQUEST_TIMEOUT_S 必須給}"
REVIEW_TIMEOUT_S="${REVIEW_TIMEOUT_S:-380}"
GAUGE_SCOPE="${GAUGE_SCOPE:-bank}"
SEED_SCAN_EXCLUDE="${SEED_SCAN_EXCLUDE:?SEED_SCAN_EXCLUDE 必須給（佇列裡全部塊的 out）}"
BACKEND_META="${BACKEND_META:-{\}}"
SLOT_ID="${SLOT_ID:-}"
SLOT_HOST="${SLOT_HOST:-}"
# ── 推論模式（DECISION_20260912_R529_FABLE_AUDIT_CROSS_BANK.md §十一）──────
# 同一顆 gemma-4 在 1003（LM Studio 0.4.24）被跑成 thinking、在 1004（0.4.17）
# 不是 ⇒ **同一個模型檔、兩種推論條件**。2026-09-13 Fable 實測：兩台都吃
# OpenAI 相容的頂層 `reasoning_effort`，1003 加上 `"none"` 之後與 1004 完全一致。
# 預設 none ＝ 與 R460／R460R 實際跑到的非 thinking 條件對齊。
# `default` ＝ **不送這個欄位**（2026-09-13 之前的行為）。
REASONING_EFFORT="${REASONING_EFFORT:-none}"
RE_FIELD=""
[ "$REASONING_EFFORT" = "default" ] || RE_FIELD=",\"reasoning_effort\":\"$REASONING_EFFORT\""

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
finish() { say "R529_BLOCK_LAUNCH_RESULT=$1"; exit "${2:-1}"; }

cd "$REPO" || finish abort_no_repo

# ── 題庫檔要在（fail-closed 的第一格：資料不在就不是「跑不出來」而是沒接上）──
case "$BANK" in
  lcb)           BANK_FILE="ops/gain/data/lcb_bank_v1.jsonl" ;;
  lcb2)          BANK_FILE="ops/gain/data/lcb_bank_v2.jsonl" ;;
  lcb3)          BANK_FILE="ops/gain/data/lcb_bank_v3.jsonl" ;;
  evalplus)      BANK_FILE=".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz" ;;
  humanevalplus) BANK_FILE=".vacant-private/evalplus/HumanEvalPlus-v0.1.10.jsonl.gz" ;;
  *) say "ABORT: 認不得的 BANK=$BANK"; finish abort_unknown_bank ;;
esac

# ── preflight ────────────────────────────────────────────────────────────
[ -f "$DEC" ] || { say "ABORT: $DEC missing（R440G 閘門要它）"; finish abort_no_decision; }
[ -f "$BANK_FILE" ] || { say "ABORT: $BANK_FILE missing（bank=$BANK）"; finish abort_no_bank; }

# **整組**預註冊比對：一行逐字，欄位全中才算這一塊被註冊過。
REG_FILTER="${BANK_FILTER:--}"
REG_LINE="R529_BLOCK: $(basename "$OUT") bank=$BANK filter=$REG_FILTER n=$N_BLOCK offset=$OFFSET seed=$SEED"
grep -qF -- "$REG_LINE" "$DEC" || {
  say "ABORT: $DEC 沒有逐字的『$REG_LINE』"; finish abort_block_not_prereg; }
say "預註冊行對上：$REG_LINE"

# 三個**全佇列共用**的實驗條件也要寫在 DECISION 裡（改了要重新裁決）。
grep -q -- "--arms $ARMS" "$DEC" || { say "ABORT: $DEC 沒有寫到 --arms $ARMS"; finish abort_arms_not_prereg; }
grep -q -- "--gauge-scope $GAUGE_SCOPE" "$DEC" || { say "ABORT: $DEC 沒有寫到 --gauge-scope $GAUGE_SCOPE"; finish abort_gauge_not_prereg; }
grep -q -- "--request-timeout-s $REQUEST_TIMEOUT_S" "$DEC" || {
  say "ABORT: $DEC 沒有寫到 --request-timeout-s $REQUEST_TIMEOUT_S"; finish abort_timeout_not_prereg; }

case "$API" in
  *"$HUB_MARK"*) say "ABORT: 端點含 $HUB_MARK（hub）——禁止任何一塊走 hub"; finish abort_hub_endpoint ;;
esac
[ -d "$OUT" ] && [ -z "$(ls -A "$OUT" 2>/dev/null)" ] && rmdir "$OUT" && say "removed empty $OUT"
[ -e "$OUT" ] && { say "ABORT: $OUT exists"; finish abort_dir_exists; }
[ -e "$OUT.launch.log" ] && { say "ABORT: $OUT.launch.log exists"; finish abort_launchlog_exists; }

if grep -q "ThreadPoolExecutor(" ops/gain/gain_run.py; then
  say "ABORT: gain_run.py 出現 ThreadPoolExecutor( ——併發旋鈕變了，要重新裁決"
  finish abort_concurrency_knob_appeared
fi

# 自己人清單裡的每一個名字都要真的寫在 DECISION 裡——否則排程器可以自己遞一份
# 清單，把「別的 run 也用過這顆 seed」洗成「那是自己人」。
for own in $SEED_SCAN_EXCLUDE; do
  grep -q -- "$(basename "$own")" "$DEC" || {
    say "ABORT: 自己人清單裡的 $own 沒有寫在 $DEC 裡"; finish abort_own_list_not_prereg; }
done

# ── seed 授權集合（比新鮮度檢查更嚴；R460 §二-4 的同一條紀律）──────────
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
PROBE_RT="-"        # 最後一次探針量到的 reasoning_tokens（進 backend_meta.json）
for i in 1 2 3; do
  code=$(curl -s -m 120 -o "$ROOT/logs/r529_${TAG}_probe_$i.json" -w '%{http_code}' "$API" \
         -H 'Content-Type: application/json' \
         -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":$PROBE_MAX_TOKENS,\"temperature\":0$RE_FIELD}" || true)
  # body_ok 的判準**一個字沒改**（content 非空）；後面兩欄是**新增的觀測**，
  # 不參與通過與否（§十一 的處置：先記錄，要不要擋由預註冊決定）。
  probe_out=$(python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1])); c = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    u = d.get("usage") or {}
    rt = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
    print("yes" if ("error" not in d and c.strip()) else "no",
          "-" if rt is None else rt, u.get("completion_tokens", "-"))
except Exception: print("no - -")' "$ROOT/logs/r529_${TAG}_probe_$i.json")
  body=$(printf '%s\n' "$probe_out" | awk '{print $1}')
  rt=$(printf '%s\n' "$probe_out" | awk '{print $2}')
  ct=$(printf '%s\n' "$probe_out" | awk '{print $3}')
  say "probe $i -> HTTP $code body_ok=$body reasoning_tokens=$rt completion_tokens=$ct (reasoning_effort=$REASONING_EFFORT)"
  [ "$rt" = "-" ] || PROBE_RT="$rt"
  case "$rt" in
    ''|-|0) ;;
    *) say "WARN: probe $i 的 reasoning_tokens=$rt ≠ 0，但已送出 reasoning_effort=$REASONING_EFFORT ——這一塊跑的是 **thinking 模式**，與非 thinking 的塊不是同一個推論條件（§十一）。**不擋**，只記錄。" ;;
  esac
  [ "$code" = "200" ] && [ "$body" = "yes" ] && ok=$((ok + 1))
done
[ "$ok" -eq 3 ] || { say "ABORT: 探針只過 $ok/3"; finish "abort_probe_only_$ok"; }
# LM Studio 版本：`/v1/models` 與 HTTP header 都不帶（2026-09-11 實測）。
# `/api/v0/models` 是 LM Studio 自己的 REST 面；能問到就問，問不到就記 `-`
# ——**不是**回頭去猜。宣稱版本仍然只能靠人回報（backend_meta.declared）。
LMS_VER=$(curl -s -m 10 "${base%/v1}/api/v0/models" 2>/dev/null | python3 -c '
import sys, json
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if "version" in k.lower() and isinstance(v, (str, int, float)):
                return str(v)
        for v in o.values():
            r = walk(v)
            if r: return r
    elif isinstance(o, list):
        for v in o:
            r = walk(v)
            if r: return r
    return ""
try: print(walk(json.load(sys.stdin)) or "-")
except Exception: print("-")' || echo "-")
say "probe lmstudio_version(/api/v0) = $LMS_VER　reasoning_effort=$REASONING_EFFORT　probe_reasoning_tokens=$PROBE_RT"

# ── 發射 ─────────────────────────────────────────────────────────────────
lock="$ROOT/.launch_r529_${TAG}.lock"
FILTER_ARGS=()
[ -n "$BANK_FILTER" ] && FILTER_ARGS=(--bank-filter "$BANK_FILTER")
say "launching -> $OUT (bank=$BANK filter=${BANK_FILTER:--} seed=$SEED n=$N_BLOCK offset=$OFFSET arms=$ARMS api=$API slot=${SLOT_ID:-?} gauge-scope=$GAUGE_SCOPE lock=$lock)"
curl -s -m 15 "$base/models" > "$OUT.backend.json" 2>/dev/null || true
printf '%s\n' "$API" > "$OUT.endpoint"     # 排程器重啟後靠它把塊認回原本的槽
# 2026-09-11：兩台後端的 LM Studio 版本不同（1003 0.4.24.0／1004 0.4.17.0）
# ⇒ 每一塊都要說得出自己跑在哪一台、那台是什麼版本，否則跨 block 的絕對值
# 會混進一個看不見的版本差。⚠ 版本是**人回報的**（`lms version`），
# runner 查證不到（/v1/models 與 HTTP header 都不帶版本，2026-09-11 實測）
# ⇒ 連同 `version_source` 一起落盤，不准被引用成「我們量到的」。
python3 - "$OUT" "$API" "${SLOT_ID:-}" "${SLOT_HOST:-}" "${BACKEND_META:-{\}}" \
         "$REASONING_EFFORT" "$PROBE_RT" "$LMS_VER" <<'PY' || say "WARN: backend_meta 寫入失敗（不擋發射）"
import json, sys, datetime, pathlib
out, api, slot, host, meta_s, effort, probe_rt, lms_ver = sys.argv[1:9]
try:
    meta = json.loads(meta_s) if meta_s.strip() else {}
except ValueError:
    meta = {"parse_error": meta_s[:200]}
raw = None
try:
    raw = json.loads(pathlib.Path(out + ".backend.json").read_text(encoding="utf-8"))
except Exception:
    pass
# `-` ＝ 探針沒拿到這一格。**不要**把它寫成 0：「沒回報 reasoning」與
# 「reasoning 是 0」在 §十一 裡是兩件不同的事，混掉就等於量不到當通過。
rt = None if probe_rt in ("", "-") else int(probe_rt)
pathlib.Path(out + ".backend_meta.json").write_text(json.dumps({
    "endpoint": api, "slot_id": slot, "slot_host": host,
    "declared": meta,
    "probed_models": raw,
    # ── 2026-09-13（§十一）：推論模式是實驗條件，逐塊落盤 ──────────────
    "reasoning_effort": effort,
    "probe_reasoning_tokens": rt,
    "probe_reasoning_ok": (None if rt is None else rt == 0),
    "lmstudio_version_probed": (None if lms_ver in ("", "-") else lms_ver),
    "probed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "honesty": ("lmstudio_version 是人回報的宣稱，本 runner 查不到；"
                "probed_models 才是這一塊自己量到的證據。"
                "probe_reasoning_tokens 是**探針那一通**量到的，"
                "不保證整塊都在同一個推論模式（模型中途被重載就可能變）；"
                "reasoning_effort 是**請求端要求的**，只有 chat() 送得出去"
                "（generate() 被 T12 釘死）。"),
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
PYTHONUNBUFFERED=1 \
VACANT_GAIN_API="$API" CLINE_KEYS=/nonexistent \
setsid nohup flock -n "$lock" python3 ops/gain/gain_run.py --out "$OUT" --n "$N_BLOCK" --offset "$OFFSET" \
  --decision "$DEC" --seed "$SEED" --arms "$ARMS" --bank "$BANK" "${FILTER_ARGS[@]}" \
  --record-bank-field --models "$MODEL" \
  --request-timeout-s "$REQUEST_TIMEOUT_S" --review-timeout-s "$REVIEW_TIMEOUT_S" --retries 4 \
  --reasoning-effort "$REASONING_EFFORT" \
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
# ⚠ 量具在 evalplus／humanevalplus 上是**全題庫**跑（371／153 題 × 四次沙箱），
#   實測 6–12 分鐘 ⇒ 等待窗要比 R460R 那支（15 分）寬，否則會把「量具還在跑」
#   報成 launch_pending_timeout。這裡給 40 分鐘，只影響**回報**不影響 runner。
say "pid=$pid; waiting for preflight（量具兩個方向＋可見閘門覆蓋 $N_BLOCK/$N_BLOCK）"
for _ in $(seq 1 240); do
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
