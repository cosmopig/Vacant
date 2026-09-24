#!/usr/bin/env bash
# 這支在架構裡承重什麼：數位分身那一跑的 agent 命令（`vacant run -- <這一支>`）。
#
# 裁決：decisions/DECISION_20260924_TWIN_AGENT_RUN.md §一、§三。
# 呼叫端：ops/exhibit/twin/twinagent.py（`launcher.run` 的 argv 就是這一支）。
#
# 用法（由 launcher 起，不要手打）：
#   twin_agent.sh <run_dir> <system_prompt> <first_message>
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

RUN_DIR="${1:-}"
SYS="${2:-}"
MSG="${3:-}"
if [ -z "$RUN_DIR" ] || [ -z "$SYS" ] || [ -z "$MSG" ]; then
    echo "用法：twin_agent.sh <run_dir> <system_prompt> <first_message>" >&2
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

if [ ! -f TRAITS.md ]; then
    echo "工作區裡沒有 TRAITS.md（cwd=$(pwd)）。停。" >&2
    exit 3
fi
if [ ! -f "$EXT" ]; then
    echo "找不到工具擴充 $EXT。停（不准退回內建工具）。" >&2
    exit 3
fi

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

# ⚠ `< /dev/null`：`pi -p` 不給會永久卡住（2026-09-18 實測，V0 已知）。
exec "$PI_BIN" -p --provider vacantproxy --model m \
    --no-builtin-tools --tools ws_list,ws_read,ws_write \
    -e "$EXT" \
    --no-extensions --no-skills --no-context-files --no-prompt-templates \
    --no-themes --no-approve --offline --no-session \
    --system-prompt "$SYS" \
    @TRAITS.md "$MSG" < /dev/null
