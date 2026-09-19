#!/usr/bin/env bash
# 這支在架構裡承重什麼：**把 `envmap.CONFIG_ROUTE` 那份名單變成可執行的**。
#
# `vacant run` 的模型通道轉向對「讀環境變數決定 base url」的框架是零接線
# （`envmap.REDIRECT_VARS` 已經設好了）。但有三個常用 agent 不是那種：
# pi、Codex、OpenCode 的 base url 在設定裡。本檔就是那三段接線，
# **每段都在 runtime 讀 `$VACANT_RUN_PROXY`**——所以：
#
#   · 不必 `--port` 固定埠（launcher 用 ephemeral port 就好）；
#   · 不必動使用者自己的 `~/.pi/agent/models.json`／`~/.codex/config.toml`／
#     `~/.config/opencode/opencode.json`（各自都有「把設定目錄整個搬走」的變數）。
#
# 用法（`--` 之後就是這一支）：
#
#   python3 ops/vacantrun/launcher.py --suite tests_visible --run-dir ~/.vacant-run/x -- \
#       ops/vacantrun/wrap_agent.sh pi "把 solution.py 寫完"
#
#   第一個參數 ∈ {pi, codex, opencode, claude}；其餘原樣當成 prompt。
#   模型用 `VACANT_AGENT_MODEL` 指定（預設見各段）。
#
# ⚠ **誠實邊界（改碼請保留）**
#
# 1. **這一支不保證被中介到。** 唯一算數的證據是 launcher 落下的
#    `run_*.json` 裡的 `requests_seen` 與 `wire_*/index.jsonl` 的 path。
#    逐格實測見 `docs/AGENT_COMPAT.md`。
# 2. **Codex 用 `codex login`（ChatGPT 帳號）時這一支救不了**：那條路的模型通道是
#    寫死的 `wss://chatgpt.com/backend-api/codex/responses`，設定搬不動。
#    本檔走的是「自訂 provider ＋ API key」那條。沒有 `OPENAI_API_KEY` 就會
#    401 而不是偷偷走回 ChatGPT——**那是刻意的，fail-visible 勝過沉默的洞**。
# 3. 這裡的版本是 2026-09-18 假上游實測的那幾個（pi 0.85.1、codex-cli 0.153.2、
#    opencode 1.18.31、Claude Code 2.1.276）；2026-09-19 的真模型輪用的是
#    opencode 1.18.31、Claude Code 2.1.278、**codex-cli 0.147.0**（vacant-dev
#    上本來就有的那一份）。**同一格兩個版本號不可以混寫成一個。**
#    **上游改版這支就會漂，漂了的徵兆是 `requests_seen == 0`，不是這支報錯。**
set -uo pipefail

AGENT="${1:-}"
shift || true
if [ -z "$AGENT" ] || [ $# -eq 0 ]; then
    echo "用法：wrap_agent.sh <pi|codex|opencode|claude> <prompt...>" >&2
    exit 2
fi
PROMPT="$*"

if [ -z "${VACANT_RUN_PROXY:-}" ]; then
    echo "沒有 \$VACANT_RUN_PROXY——這支要跑在 \`vacant run --\` 底下。停。" >&2
    exit 2
fi
BASE="${VACANT_RUN_PROXY%/}"
# 每次跑用一個新的設定目錄：設定是**這一次 run 的產物**，不是使用者的狀態。
CFG="$(mktemp -d "${TMPDIR:-/tmp}/vacant-wrap-XXXXXX")"
trap 'rm -rf "$CFG"' EXIT

case "$AGENT" in
pi)
    # `envmap.CONFIG_ROUTE["pi"]`：PI_CODING_AGENT_DIR ＋ models.json
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
    # ⚠ `pi -p` 不給 `< /dev/null` 會永久卡住（2026-09-18 實測，V0 已知）。
    exec pi -p --provider vacantproxy --model m "$PROMPT" < /dev/null
    ;;
codex)
    # `envmap.CONFIG_ROUTE["codex"]`：CODEX_HOME ＋ 一個**新** provider id。
    # 內建 id `openai` 不准覆寫（codex 會 fail-closed 報錯），所以取名 vacantproxy。
    MODEL="${VACANT_AGENT_MODEL:-gpt-5.6-sol}"
    WIRE="${VACANT_CODEX_WIRE:-responses}"      # responses｜chat
    export CODEX_HOME="$CFG"
    cat > "$CFG/config.toml" <<EOF
model = "$MODEL"
model_provider = "vacantproxy"
approval_policy = "never"
sandbox_mode = "danger-full-access"
EOF
    # ⚠ **選用、預設不設**：`VACANT_CODEX_REASONING_EFFORT`。沒設的話上面那份
    #   config.toml 與 2026-09-18／09-19 兩輪實測**逐位元相同**（這一段一個字都不寫）。
    #   設了（例如 `none`）才多一行 `model_reasoning_effort`。
    #   為什麼留這個鉤子：2026-09-19 在 1003（LM Studio ×`gemma-4-12b-it-qat`，
    #   **預設開思考**）上量到，Codex 的 `/v1/responses` 這條路會有一種**跑不完**
    #   的失敗——模型吐了 94,776 個 `response.reasoning_text.delta`、一個
    #   `output_text` 都沒有、713 秒還沒 `response.completed`。
    #   三跑裡踩到一次。`model_reasoning_effort = "none"` 之後 request body 變成
    #   `reasoning: {"effort": "none", …}`、回應的 `reasoning_tokens` 落到 0，
    #   拒交／交付兩格都收得了工。逐字見 `docs/AGENT_COMPAT.md` §10.7。
    #   ⚠ 這是**觀測到的緩解**不是保證：n 很小，而且它把推理整個關掉，
    #     換題換模型都可能不成立。
    if [ -n "${VACANT_CODEX_REASONING_EFFORT:-}" ]; then
        printf 'model_reasoning_effort = "%s"\n' \
            "$VACANT_CODEX_REASONING_EFFORT" >> "$CFG/config.toml"
    fi
    cat >> "$CFG/config.toml" <<EOF

[model_providers.vacantproxy]
name = "vacant proxy"
base_url = "$BASE/v1"
env_key = "OPENAI_API_KEY"
wire_api = "$WIRE"
EOF
    exec codex exec --skip-git-repo-check "$PROMPT" < /dev/null
    ;;
opencode)
    # OpenCode **也**吃 OPENAI_BASE_URL（實測），所以這一段只在要指定自訂
    # provider（例如本地模型）時才需要。走內建 openai provider 的話零接線。
    MODEL="${VACANT_AGENT_MODEL:-gemma-4-12b-it-qat}"
    export OPENCODE_CONFIG_DIR="$CFG"
    export OPENCODE_DISABLE_PROJECT_CONFIG=1
    export OPENCODE_CONFIG_CONTENT="$(cat <<EOF
{"provider":{"vacantproxy":{"name":"vacant proxy",
 "npm":"@ai-sdk/openai-compatible",
 "options":{"baseURL":"$BASE/v1","apiKey":"${OPENAI_API_KEY:-sk-vacant-run}"},
 "models":{"$MODEL":{"name":"m"}}}},
 "model":"vacantproxy/$MODEL",
 "permission":{"edit":"allow","bash":"allow","webfetch":"allow"}}
EOF
)"
    exec opencode run --pure --log-level ERROR -m "vacantproxy/$MODEL" "$PROMPT" < /dev/null
    ;;
claude)
    # Claude Code 吃 ANTHROPIC_BASE_URL（launcher 已經設好）⇒ 這一段只做**隔離**：
    # 不清掉這些變數，子 Claude Code 會去碰正在跑的那個 session 的狀態。
    export CLAUDE_CONFIG_DIR="$CFG"
    unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SESSION_ID
    unset CLAUDE_CODE_CHILD_SESSION CLAUDE_CODE_SESSION_ATTENDED
    unset CLAUDE_CODE_MESSAGING_SOCKET CLAUDE_CODE_MESSAGING_TOKEN
    unset CLAUDE_CODE_EXECPATH CLAUDE_PID CLAUDE_EFFORT AI_AGENT
    # 有設 CLAUDE_CODE_USE_OPENAI 的話它會改走 OpenAI wire——兩條 launcher 都認得，
    # 但收據上的 `by_wire` 會不一樣，所以這裡明確清掉，讓那一格的口徑是固定的。
    unset CLAUDE_CODE_USE_OPENAI OPENAI_MODEL
    export DISABLE_TELEMETRY=1 DISABLE_ERROR_REPORTING=1 DISABLE_AUTOUPDATER=1
    export DISABLE_NON_ESSENTIAL_MODEL_CALLS=1
    [ -n "${VACANT_AGENT_MODEL:-}" ] && export ANTHROPIC_MODEL="$VACANT_AGENT_MODEL"
    exec claude -p "$PROMPT" --dangerously-skip-permissions < /dev/null
    ;;
*)
    echo "不認得的 agent：$AGENT（有 pi｜codex｜opencode｜claude）。停。" >&2
    exit 2
    ;;
esac
