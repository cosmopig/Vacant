#!/usr/bin/env bash
# 這支在架構裡承重什麼：數位分身那一跑的 agent 命令（`vacant run -- <這一支>`）。
#
# 裁決：decisions/DECISION_20260924_TWIN_AGENT_RUN.md §一、§三。
# 呼叫端：ops/exhibit/twin/twinagent.py（`launcher.run` 的 argv 就是這一支）。
#
# 用法（由 launcher 起，不要手打）：
#   twin_agent.sh <段1指令> <段1第一句> <run_dir> <段2指令> <段2第一句>
#
#   ⚠ W3b（2026-10-01）一跑兩個 pi 回合：段 1 讀 TRAITS.md、寫 信.md；
#     然後 `twin_letter_guard.py` 做確定性關卡（TRAITS.md 移走、信防呆、世界與地上搬進房間）；
#     段 2 的房間裡沒有 TRAITS.md，只有 信.md、WORLD.md、地上/。兩個回合各自 `--no-session`。
#
#   · cwd ＝ 這位分身的拋棄式工作區（launcher 設的），裡面只有 TRAITS.md；
#   · `<run_dir>` ＝ 這位分身的 run-dir（工作區外）。pi 的設定目錄與 stderr 放這裡
#     ——撤回時整個刪掉（見裁決 §六）；
#   · `<system_prompt>`／`<first_message>` ＝ **全場逐字相同的固定字串**，
#     argv 裡沒有觀眾原文（特質只經由 `@TRAITS.md` 進到第一則訊息）。
#
# 跟 `ops/vacantrun/wrap_agent.sh pi` 的差別（都是刻意的）：
#   1. **工具收窄**：`--no-builtin-tools --tools ws_list,ws_read,ws_write`，
#      三個工具由 `pi_ext/twin_ws_tools.ts` 提供、只碰得到工作區。
#      內建 bash／read／write／edit／grep／find／ls 一個都不開。
#   2. **設定目錄放 run-dir 不放 /tmp**：wrap_agent.sh 是 `exec pi`，被 exec 取代的
#      bash 沒有 trap 可跑 ⇒ EXIT trap 永遠不會清掉 `/tmp/vacant-wrap-*`。
#      這裡的設定目錄跟著 run-dir 走，撤回時一起刪。
#   3. **stderr 導進 run-dir**：不然它會流進 loop 的 journal，而 journal 刪不到。
#   4. `--no-session`：不留 session 檔（那裡面會有 TRAITS.md 的全文）。
#
# ⚠ **根據閘門（2026-10-01，`grounding_gate.py`）**：twinagent 改用
#   `launcher.run(suite_dir=<run>/tests_visible, retry_arm="revise", max_attempts=3, feedback_into="both")`。
#   第 5 個參數（段 2 第一句）的尾端是 `{VACANT_FEEDBACK}`，launcher 第 1 次換成空字串（argv 與沒有閘門時
#   逐位元相同）、之後換成可見驗收的失敗原文。重改時只跑段 2（見 RETRY）。
#
# ⚠ **步驟紀錄（2026-09-28，契約 `plans/CONTRACT_PROCESS_20260928.md` §A）**：
#   `VACANT_TWIN_STEP_LOG` 從這一支自己拿到的 `$RUN_DIR`（工作區外）算出來，
#   不是從呼叫端的環境變數轉傳——Python 那一側是 ThreadPoolExecutor 平行跑
#   好幾位分身，`os.environ` 在執行緒之間不安全；這一支一支腳本一個行程，
#   自己算出來的路徑不會跟別的分身撞。檔名要跟 `twinagent.STEP_LOG_NAME` 同步。
#
# ⚠ **`--mode json`（2026-10-01，契約補充 `CONTRACT_PROCESS_20261001_ADDENDUM.md` §E）**：
#   pi 的 stdout 改成一行一個事件的 JSON（launcher 已把它整份落盤到
#   `<run_dir>/agent_stdout.log`），分身迴圈 tail 它轉成 `twin_say`。
#   形狀是在真 pi 0.85.1 上量的（`tests/fixtures/pi_json/`）。PLAN.md／產出走
#   工作區、收據走 launcher，都不讀 stdout，所以不受影響。
#   ⚠ 這個檔裡有 TRAITS.md 全文與工具參數（含分身寫的內容）——跟之前一樣只活在 run-dir，
#     撤回時整個刪；電視事件流只拿得到清過、≤80 字、過了 LEAK 防呆的 text。
#
# ⚠ 誠實邊界（改碼請保留）：
#   · 收住的是「模型叫得到的工具」，不是 pi 這個行程。pi（node）本身仍有完整的
#     檔案系統與網路權限；沒有 OS 沙箱包住它（展場機 1003 是 Windows）。
#     **例外（2026-09-24 VM 跑法）**：`VACANT_TWIN_ENCLOSE=on` 且在 vacant-dev 上時，
#     這一支（連同 launcher）整個跑在 bwrap 圍牆裡（`twinenclose.py`），pi 行程只看得到
#     最小 rootfs＋node＋repo（唯讀）＋自己的工作區與 run-dir、網路只有 Vacant 那扇門。
#     證據：`evidence_vm_20260924/probe_twin_enclosure.json`（負控制先跑）。
#   · `--tools` 白名單是 pi 0.85.1 的行為（vacant-dev 實測）。pi 改版要重跑
#     `ops/exhibit/twin/probe_pi_tools.py`。
#   · 這一支不保證被中介到。唯一算數的證據是 launcher 的 `requests_seen`。
set -uo pipefail

SYS1="${1:-}"
MSG1="${2:-}"
RUN_DIR="${3:-}"
SYS="${4:-}"
MSG="${5:-}"
if [ -z "$SYS1" ] || [ -z "$MSG1" ] || [ -z "$RUN_DIR" ] || [ -z "$SYS" ] || [ -z "$MSG" ]; then
    echo "用法：twin_agent.sh <段1指令> <段1第一句> <run_dir> <段2指令> <段2第一句>" >&2
    exit 2
fi
if [ -z "${VACANT_RUN_PROXY:-}" ]; then
    echo "沒有 \${VACANT_RUN_PROXY}——這支要跑在 \`vacant run --\` 底下。停。" >&2
    exit 2
fi
mkdir -p "$RUN_DIR"
exec 2>>"$RUN_DIR/agent_stderr.log"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT="$HERE/pi_ext/twin_ws_tools.ts"
PI_BIN="${VACANT_TWIN_PI:-pi}"
BASE="${VACANT_RUN_PROXY%/}"
MODEL="${VACANT_AGENT_MODEL:-gemma-4-12b-it-qat}"

# ── 第 1 次 spawn：工作區裡有 TRAITS.md ⇒ 兩段都跑。
# ── 第 2、3 次（根據閘門把回饋帶回來重改，`vacant run` 的 revise 臂）：TRAITS.md 早被關卡移走、
#    信已經寫好 ⇒ **只跑段 2**（信不重寫、特質不回來）。回饋由 launcher 接在第 5 個參數的尾端。
RETRY=0
if [ ! -f TRAITS.md ]; then
    if [ -f 信.md ] && [ -f "$RUN_DIR/letter_guard.json" ] && [ -d 地上 ]; then
        RETRY=1
    else
        echo "工作區裡沒有 TRAITS.md，也不是重改（cwd=$(pwd)）。停。" >&2
        exit 3
    fi
fi
# 上一次的驗收紀錄絕不沿用：這一次 pi 結束後 `grounding_gate prepare` 會重寫；
# 它沒跑成，四格窗就見不到紀錄（一律不亮），不是用舊的。
rm -f "$RUN_DIR/tests_visible/_ledger.py"
if [ ! -f "$EXT" ]; then
    echo "找不到工具擴充 $EXT。停（不准退回內建工具）。" >&2
    exit 3
fi

# ⚠ 檔名 twin_steps.ndjson 與 twinagent.STEP_LOG_NAME 是同一個字面值，改一邊要改兩邊。
export VACANT_TWIN_STEP_LOG="$RUN_DIR/twin_steps.ndjson"

CFG="$RUN_DIR/pi_cfg"
rm -rf "$CFG"
mkdir -p "$CFG"
export PI_CODING_AGENT_DIR="$CFG"
export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0
cat > "$CFG/models.json" <<EOF
{"providers":{"vacantproxy":{
  "baseUrl":"$BASE/v1",
  "api":"openai-completions",
  "apiKey":"${OPENAI_API_KEY:-sk-vacant-run}",
  "compat":{"supportsDeveloperRole":false,"supportsReasoningEffort":false},
  "models":[{"id":"$MODEL","name":"m","contextWindow":262144,"maxTokens":16384}]}}}
EOF

PY="${VACANT_TWIN_PY:-python3}"
COMMON=(-p --mode json --provider vacantproxy --model m
    --no-builtin-tools --tools ws_list,ws_read,ws_write
    -e "$EXT"
    --no-extensions --no-skills --no-context-files --no-prompt-templates
    --no-themes --no-approve --offline --no-session)

if [ "$RETRY" -eq 0 ]; then
    # ── 段 1：讀 TRAITS.md、寫 信.md ──
    # ⚠ `< /dev/null`：`pi -p` 不給會永久卡住（2026-09-18 實測，V0 已知）。
    "$PI_BIN" "${COMMON[@]}" --system-prompt "$SYS1" @TRAITS.md "$MSG1" < /dev/null
    RC1=$?

    # ── 關卡：TRAITS.md 一定在這裡被移走（不管段 1 成不成功） ──
    "$PY" "$HERE/twin_letter_guard.py" "$(pwd)" "$RUN_DIR"
    GRC=$?
    if [ "$GRC" -ne 0 ]; then
        echo "信沒有寫出來（段 1 rc=$RC1，關卡 rc=$GRC）。不進段 2。" >&2
        exit 4
    fi
fi

# ── 整跑時間預算（`twinagent.RUN_BUDGET_S`，預設 420 秒）：這一次 pi 最多跑 min(單次上限, 剩下的預算) 秒；
#    重改時剩不到 `min_attempt_s`（預設 60 秒）⇒ 不再開 pi（SKIP）。被切掉的那一次照樣 prepare，但標 GATE_CUT=1
#    （電視演「時間到」，不演成四個錯）。沒有預算設定（舊呼叫）⇒ 不限。
CUT=0
LIM=$("$PY" "$HERE/grounding_gate.py" limit "$RUN_DIR" "$RETRY" 2>/dev/null || echo 0)
if [ "$LIM" = "SKIP" ]; then
    echo "整跑預算剩不到下限，這一次不開 pi。" >&2
    RC2=124; CUT=1
else
    # ── 段 2：房間裡只有 信.md、WORLD.md、地上/ ──
    "$PY" "$HERE/grounding_gate.py" runlimited "${LIM:-0}" -- "$PI_BIN" "${COMMON[@]}" --system-prompt "$SYS" @信.md "$MSG"
    RC2=$?
    [ "$RC2" -eq 124 ] && CUT=1
fi

# ── 根據閘門的紀錄：pi 已經結束（分身改不到），凍結與驗收還沒開始 ──
# 重寫 tests_visible/_ledger.py，並把這一次的四格結果預先寫成旁註（先於 gate_ran）。
# 失敗不改變這一跑的結束碼；沒有 _ledger.py 時四格窗一律不亮。
GATE_CUT="$CUT" "$PY" "$HERE/grounding_gate.py" prepare "$(pwd)" "$RUN_DIR" || true
exit "$RC2"
