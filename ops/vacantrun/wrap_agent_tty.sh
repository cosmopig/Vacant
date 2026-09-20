#!/usr/bin/env bash
# 這支在架構裡承重什麼：**`ops/vacantrun/wrap_agent.sh` 的互動式雙胞胎**。
#
# 2026-09-20 人類質疑：600 格（`DECISION_20260920_ABPI_VACANT_ONOFF_PREREG.md`）
# 全部走 `pi -p`＝一次性 headless，而**沒有人是那樣用 pi 的**。要回答這個質疑，
# 必須在 pi 真正的互動式 TUI 下再量一次中介與閘門。
#
# 🔴 **凍結的那一支一個 byte 都不准動**（98 個歸檔 run 靠它逐字可比）。
#    所以互動式那條路另外開這一支。
#
# ## 與 `wrap_agent.sh` 的差別——**只有兩處**，其餘逐字沿用
#
#   1. `exec pi -p --provider … "$PROMPT" < /dev/null`
#      ⇒ `exec pi    --provider … "$PROMPT"`
#      （拿掉 `-p`、拿掉 `< /dev/null`）
#   2. 只認得 `pi`。codex／opencode／claude／hermes 那四段**不複製**
#      ——它們的互動模式是另外四個題目，混在一支裡會讓「差別只有兩處」這句話變假。
#
#   其餘逐字相同：`PI_CODING_AGENT_DIR=$CFG`、同一份 `models.json`
#   （同 provider 形狀、同 `contextWindow`／`maxTokens`）、同樣的
#   `PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0`、同一段掛鉤安裝、
#   同一套 `$CFG` 收尾契約與掃地機。
#
# ## ⚠ 拿掉 `-p` **本身不夠**
#
# pi 0.85.1 `dist/main.js:resolveAppMode()`：
#
#     if (parsed.print || !stdinIsTTY || !stdoutIsTTY) return "print";
#
# ⇒ 三個充分條件。所以這一支**必須**跑在
#   `ops/vacantrun/tty_drive.py`（真 pty）＋ `vacant run --stdin inherit`
#   ＋ **不要 `--json`**（`--json` 會把 agent 的 stdout 導進檔案 ⇒ 非 tty
#   ⇒ pi 又落回 print 模式）底下。三個條件缺一，這一支就只是一支比較慢的
#   `wrap_agent.sh`，而且**不會報錯**——徵兆只有轉錄裡沒有 TUI escape sequence。
#
# ## ⚠ 互動式 TUI **不會自己結束**
#
# `interactive-mode.js`：跑完 initialMessage 之後進 `while (true) { getUserInput() … }`。
# ⇒ 這一格的「行程結束那一刻」是**模擬的人**按下 Ctrl-D 的那一刻，
#   不是「agent 宣告完成、退出碼 0 走人」。兩者不可混講。
set -uo pipefail

AGENT="${1:-}"
shift || true
if [ "$AGENT" != "pi" ] || [ $# -eq 0 ]; then
    echo "用法：wrap_agent_tty.sh pi <prompt...>（這一支只接 pi，理由見檔頭）" >&2
    exit 2
fi
PROMPT="$*"

if [ -z "${VACANT_RUN_PROXY:-}" ]; then
    echo "沒有 \${VACANT_RUN_PROXY}——這支要跑在 \`vacant run --\` 底下。停。" >&2
    exit 2
fi
BASE="${VACANT_RUN_PROXY%/}"
CFG="$(mktemp -d "${TMPDIR:-/tmp}/vacant-wrap-XXXXXX")"
trap 'rm -rf "$CFG"' EXIT INT TERM HUP

if command -v lsof >/dev/null 2>&1; then
    { find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'vacant-wrap-*' -type d -mmin +360 2>/dev/null \
      | while IFS= read -r _d; do
          [ "$_d" = "$CFG" ] && continue
          if [ "$(lsof +D "$_d" 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')" = "0" ]; then
              rm -rf "$_d" 2>/dev/null || true
          fi
        done; } || true
fi

MODEL="${VACANT_AGENT_MODEL:-gemma-4-12b-it-qat}"
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

# 掛鉤（`vacant-hook/1`）：與凍結那支逐字相同的那一段。**有 `$VACANT_HOOK_LOG` 才裝。**
# 這一輪兩臂**都**設 `VACANT_HOOK_LOG`（互動臂用它的 `agent_end` 當「做完了」的
# 確定性訊號），所以它是常數不是變因——但它**會多一通 canary**，判讀時要扣掉。
if [ -n "${VACANT_HOOK_LOG:-}" ]; then
    if "${VACANT_PY:-python3}" -c 'import os, pathlib, sys
from vacant_network.vrun import hookcli
rep = hookcli.install("pi", pathlib.Path(sys.argv[1]),
                      hook_log=os.environ["VACANT_HOOK_LOG"],
                      run_id=os.environ.get("VACANT_RUN_ID", ""),
                      proxy=os.environ.get("VACANT_RUN_PROXY"))
sys.stderr.write("HOOK_INSTALL target=%s\n" % (rep and rep.get("target")))' \
            "$CFG" ; then :; else
        echo "HOOK_INSTALL_FAILED（掛鉤沒裝成 ⇒ 收據會降級）" >&2
    fi
    export VACANT_HOOK_AGENT="${VACANT_HOOK_AGENT:-pi}"
fi

# ⇣⇣ 與凍結那支的**唯一實質差別**就是下面這一行 ⇣⇣
exec pi --provider vacantproxy --model m "$PROMPT"
