#!/usr/bin/env bash
# 這支在架構裡承重什麼：**把 `envmap.CONFIG_ROUTE` 那份名單變成可執行的**。
#
# `vacant run` 的模型通道轉向對「讀環境變數決定 base url」的框架是零接線
# （`envmap.REDIRECT_VARS` 已經設好了）。但有四個常用 agent 不是那種：
# pi、Codex、OpenCode、Hermes 的 base url 在設定裡。本檔就是那四段接線，
# **每段都在 runtime 讀 `$VACANT_RUN_PROXY`**——所以：
#
#   · 不必 `--port` 固定埠（launcher 用 ephemeral port 就好）；
#   · 不必動使用者自己的 `~/.pi/agent/models.json`／`~/.codex/config.toml`／
#     `~/.config/opencode/opencode.json`／`~/.hermes/config.yaml`
#     （各自都有「把設定目錄整個搬走」的變數）。
#
# 用法（`--` 之後就是這一支）：
#
#   python3 ops/vacantrun/launcher.py --suite tests_visible --run-dir ~/.vacant-run/x -- \
#       ops/vacantrun/wrap_agent.sh pi "把 solution.py 寫完"
#
#   第一個參數 ∈ {pi, codex, opencode, claude, hermes}；其餘原樣當成 prompt。
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
#    上本來就有的那一份）、**Hermes Agent 0.19.0**（2026-09-19 用 pip 裝進
#    `/var/tmp/vacant_hermes/hv`，vacant-dev 上本來沒有）。
#    **同一格兩個版本號不可以混寫成一個。**
#    **上游改版這支就會漂，漂了的徵兆是 `requests_seen == 0`，不是這支報錯。**
set -uo pipefail

AGENT="${1:-}"
shift || true
if [ -z "$AGENT" ] || [ $# -eq 0 ]; then
    echo "用法：wrap_agent.sh <pi|codex|opencode|claude|hermes> <prompt...>" >&2
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

# ── 收尾契約（2026-09-20 補；與 `gateshim` 的三層同一套）────────────────────
# ⚠ **原本只有 `trap … EXIT`，而 EXIT trap 擋不住 `SIGKILL`。**
#   pbgate 那幾批用 `timeout 1200` 外包、報告裡好幾格 `agent_rc=-9`
#   ⇒ 被 `-9` 砍的那一份永遠留在 `/tmp`。2026-09-20 在 vacant-dev 上數到
#   **467 個殘留、共約 7.4 GB**，磁碟被吃到 **98%**（那台只有 38G，
#   而這個 repo 的紀律是「塞爆會讓實驗安靜寫壞」）。
#
#   層 1  EXIT trap                    一般結束、失敗、Python 例外
#   層 2  INT/TERM/HUP 也走同一個 trap   溫和的終止（原本沒有）
#   層 3  **下一跑開場的掃地機**          `SIGKILL`／斷電
#
# ⚠ **能說的是「不累積」不是「當下不留」**：被 `kill -9` 的那一份**會**留到
#   下一次有人跑這支。穩態 O(1) 不是 O(N)。這支從此不跑，那一份就一直在。
trap 'rm -rf "$CFG"' EXIT INT TERM HUP

# 掃地機：只動**自己這個前綴**、**六小時以上**、而且**沒有行程開著**的。
# ⚠ 三道門缺一不可——並行跑的別格也在 `/tmp/vacant-wrap-*` 底下。
#   `lsof` 不在就**不掃**（問不出來 ⇒ 不動，鐵律 3：沒量到 ≠ 量到 0）。
#   整段包在 `|| true` 裡：**掃地失敗不可以讓這一跑失敗**。
if command -v lsof >/dev/null 2>&1; then
    { find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'vacant-wrap-*' -type d -mmin +360 2>/dev/null \
      | while IFS= read -r _d; do
          [ "$_d" = "$CFG" ] && continue
          if [ "$(lsof +D "$_d" 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')" = "0" ]; then
              rm -rf "$_d" 2>/dev/null || true
          fi
        done; } || true
fi

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
    # ⚠ `VACANT_CODEX_WIRE=chat` 在 **codex-cli 0.147.0 上打不開**（2026-09-19 實測）：
    #   codex 在載入 config 的那一步就退件（`wire_api = "chat"` is no longer supported；
    #   serde 只列得出 `responses` 一個變體），`requests_seen = 0`、`agent_rc = 1`。
    #   **那是 L-none（中介沒發生）不是「閘門擋下來」**——逐字見 AGENT_COMPAT §11.1。
    #   鉤子留著不動：behaviour 不改，換版本／換 codex 分支時它仍然是唯一的開關。
    WIRE="${VACANT_CODEX_WIRE:-responses}"      # responses（0.147.0 只收這個）
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
hermes)
    # `envmap.CONFIG_ROUTE["hermes"]`：HERMES_HOME ＋ config.yaml（Hermes Agent 0.19.0）。
    #
    # ⚠ **`provider: custom` 這一行是必要的，不是裝飾。** HERMES_HOME 全新、
    #    只有 launcher 設好的 `CUSTOM_BASE_URL` 而**沒有 provider** ⇒ Hermes
    #    在送出任何請求之前就停在
    #    `No LLM provider configured. Run \`hermes model\` …`
    #    ⇒ `requests_seen = 0`、`agent_rc = 1`，而閘門照樣判 `visible_fail`／exit 20。
    #    **那是假的拒交格**（L-none），不准讀成閘門有牙齒。實測見
    #    `docs/AGENT_COMPAT.md` §12.2 的對照 A。
    #
    # ⚠ **base_url 也寫進 config，即使 `CUSTOM_BASE_URL` 實測會蓋過它**（§12.2 的
    #    smoke D）。理由是**失效方向**：Hermes 0.19.0 解 base_url 的順序是
    #      `--base-url` → `CUSTOM_BASE_URL` → config 的 `base_url`
    #      → `OPENROUTER_BASE_URL` → **編死的 `https://openrouter.ai/api/v1`**
    #      （`hermes_constants.py:1259`）。
    #    兩個都沒有的話它**不報錯，安靜地去打公開 API**——實測對照 C：
    #    `requests_seen = 0`、`agent_rc = 0`、agent 印 `HTTP 401: Missing
    #    Authentication header`。**那是 `envmap` 誠實邊界 2 的活體標本。**
    #    config 寫死 base_url 就把這條 fail-open 的尾巴堵回 proxy。
    MODEL="${VACANT_AGENT_MODEL:-gemma-4-12b-it-qat}"
    # Hermes 自己要求 agent 用途至少 64,000 context，低於就在啟動時拒絕。
    CTX="${VACANT_HERMES_CONTEXT:-65536}"
    HERMES_BIN="${VACANT_HERMES_BIN:-hermes}"
    export HERMES_HOME="$CFG"
    cat > "$CFG/config.yaml" <<EOF
model:
  provider: custom
  default: $MODEL
  base_url: $BASE/v1
  context_length: $CTX
EOF
    # `-z` ＝ one-shot（無 TTY、approvals 自動放行）；`--yolo` 再把危險指令的
    # 確認關掉。工具集用預設（實測預設的 17 個工具裡 `write_file` 就夠寫檔）。
    exec "$HERMES_BIN" -z "$PROMPT" --yolo < /dev/null
    ;;
*)
    # ⚠ `${AGENT}` 的大括號不是風格：緊接在後面的是全形「（」，
    #   macOS 的 bash 3.2 會把那幾個 byte 併進變數名 ⇒ `set -u` 直接
    #   `AGENT?: unbound variable`，**原本要印的那行說明反而印不出來**
    #   （2026-09-19 實測；這是既有的坑，不是新的）。
    echo "不認得的 agent：${AGENT}（有 pi｜codex｜opencode｜claude｜hermes）。停。" >&2
    exit 2
    ;;
esac
