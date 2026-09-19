"""這支在架構裡承重什麼：**一份環境變數名單，不是 per-framework 程式碼**。

`vacant run` 要把 agent 的模型通道轉向到自己的 proxy。做這件事有兩條路：

  (a) 每支框架寫一段接線（pi 一段、Claude Code 一段、aider 一段…）——幾十段，
      而且每次上游改版就漂一次；
  (b) 認**環境變數**這個所有 SDK 共用的介面——一份名單，改版不漂。

本檔是 (b) 的那份名單，而且是**唯一**一份（launcher 不准另外寫死變數名）。

四個角色分開列，因為它們的語意不同：

  · `REDIRECT_VARS`  ——要被指向 proxy 的 base-url 變數。值有兩種形狀
    （`/v1` 結尾與根結尾），寫成 `(name, suffix)` 而不是靠呼叫端記得加。
  · `UPSTREAM_VARS`  ——從**父行程**讀真正上游位址用的（讀完就從子環境拿掉）。
  · `SECRET_VARS`    ——金鑰類。**從 agent 的 env 裡整個拿掉**，只留在 proxy
    行程裡；agent 拿到的是一個 sentinel 字串，proxy 在轉送時換回真鑰。
  · `CONFIG_ROUTE`   ——**吃設定不吃 base-url 變數的框架**那一份名單（2026-09-18
    加）。它不是 (b) 的例外，是 (a) 縮到最小：每一格只記「哪個變數能把設定
    整包搬走、要寫哪一個欄位」，接線仍然是一支讀 `$VACANT_RUN_PROXY` 的
    wrapper，不是 per-framework 的程式碼。

⚠ **誠實邊界（改碼請保留）**：

1. 這份名單擋得到「讀環境變數決定 base url」的框架。**擋不到用設定檔的框架**
   ——pi（@earendil-works/pi-coding-agent）的 provider `baseUrl` 寫在
   `models.json` 裡，內建 provider 的 baseUrl 甚至是編進 bundle 的常數，
   環境變數在那條路上完全沒有作用。那種框架要嘛把設定檔指向 proxy
   （`vacant run --port` 給一個固定埠就是為了這個），要嘛就沒被中介到。
   **「設了環境變數」不等於「被中介了」**——真正的證據是 proxy 的 wire log
   有沒有東西（`launcher` 會把 `requests_seen` 落進收據）。

   2026-09-18 把這一條**量出來**了（`docs/AGENT_COMPAT.md` 有逐格證據）：
   pi 0.85.1 只設 `OPENAI_BASE_URL` ⇒ 假上游 0 通，它跑去 `api.openai.com`
   拿了一個 401 回來。**反過來也有一格打臉靜態推論**：OpenCode 1.18.31 的
   binary 裡沒有 `OPENAI_BASE_URL` 這個字串，照 grep 會判「不吃環境變數」，
   實測卻**吃**——它的 provider 是 runtime 才載入的 `@ai-sdk/openai`，
   讀變數的是那包 SDK 不是 opencode 自己。⇒ **靜態掃字串不算證據，
   只有 wire log 算。**

   2026-09-19 補一刀，**方向相反**：OpenCode 那一格「吃環境變數」是真的，
   但**只對 models.dev 註冊表裡的模型 id 成立**。拿本地模型的 id
   （`gemma-4-12b-it-qat`）給內建 `openai` provider，它在**送出任何請求之前**
   就死在模型解析 ⇒ `requests_seen == 0`；換成 `gpt-4o-mini` ⇒ 9 通。
   ⇒ **「這個框架吃環境變數」本身不是一格布林值**，它跟模型 id 綁在一起。
   接本地模型仍然要走 `CONFIG_ROUTE`。

   2026-09-19 再補一刀，**方向又相反**：同一個位置（把不認得的模型 id 交給
   框架）**Claude Code 2.1.278 是放行不是擋**——它印一行
   `[claude-code:unrecognized_model]` 警告然後照送，真模型兩格都拿到
   （`docs/AGENT_COMPAT.md` §9.1 有逐字警告）。
   ⇒ **OpenCode 的「擋」與 Claude Code 的「放行」都是實測，不准從其中一格
   推另一格。** 代價是 Claude Code 會按 200k 假設做 auto-compact，長任務要自己
   設 `CLAUDE_CODE_MAX_CONTEXT_TOKENS`——而 auto-compact 會改變送出去的
   messages，也就是改變「逐字落盤」的內容（那一格**沒量過**）。

   同一天的**第三個資料點**：**Codex CLI 0.147.0 也是放行**——
   `warning: Model metadata for gemma-4-12b-it-qat not found. Defaulting to
   fallback metadata; …` 印完照送，六通全部 200
   （`docs/AGENT_COMPAT.md` §10.2 有逐字警告）。
   ⇒ 三家在這一格是 **2 放行 ∶ 1 擋**。那是三次實測不是一條規則，
   **第四家仍然要自己量**。

   2026-09-19 把「fallback metadata 退到什麼」也量了（`docs/AGENT_COMPAT.md`
   §11.4／§11.5），結論分兩半，**不可以混講**：
   · **形狀量到了**——退到的是 binary 裡編死的那一套，不是伺服器目錄那一套：
     頂層 `instructions` 20,751 字元（目錄那份是塞在 `input` 裡的 17,730 字元，
     sha256 不同）、頂層 `tools` 10 個（目錄模型改用 `input[0].additional_tools`）、
     `reasoning.summary="auto"`（目錄模型是 `reasoning.context="all_turns"`）、
     沒有 `text.verbosity`、少兩段多代理 developer 訊息。**送出去的 bytes 真的不一樣。**
     ⚠ 而且方向跟警告文字相反：在 LM Studio 這個上游上，**目錄模型那個 body 被退件
       （`invalid_union`），fallback 那個才跑得完**。
   · **數字沒量到**——fallback 假設的 context window **讀不出來**：wire body 裡沒有、
     `codex debug models` 只吐目錄、`codex doctor --json` 沒有、`codex exec --json`
     的事件流也沒有。用 `codex debug prompt-input` ＋ `-c model_context_window=N` 掃，
     量具在 32,768 以上就飽和 ⇒ **只推得出 ≥ 32,768 這個下界**。
     不知道那個數字也有辦法：**自己 `-c model_context_window=<真視窗>` 釘死**，
     跟 Claude Code 那格設 `CLAUDE_CODE_MAX_CONTEXT_TOKENS` 同一招。

   **第四個資料點（2026-09-19，Hermes Agent 0.19.0）：也是放行，而且連警告都沒有。**
   `provider: custom` 之下 Hermes 不查任何註冊表，`gemma-4-12b-it-qat` 原樣
   出現在 wire 的 `model` 欄位、六通全部 200（`docs/AGENT_COMPAT.md` §12.3）。
   ⇒ 四家在這一格是 **3 放行 ∶ 1 擋**。
   ⚠ **但那不是同一個位置的同一個問題**：OpenCode 擋的是**內建 provider**
   配上不在 models.dev 裡的 id；Hermes 這一格走的是自訂 provider，**本來就沒有
   註冊表可查**。「Hermes 對內建 provider 餵陌生 id 會怎樣」**沒量**。
   **仍然不准從任何一格推另一格。**

   同一天還踩到一個**量錯**，記在這裡因為它是本條的同型：用
   `strings -a <binary> | grep -c` 掃 Claude Code 的原生 binary，十三個變數
   **全是 0**，看起來像「不吃任何 `ANTHROPIC_*`」；真因是那台機器**沒有
   `strings`**，管線前段失敗、後段照樣印 0。改用 `grep -a` 直接掃，
   `ANTHROPIC_BASE_URL` 有 54 筆。⇒ **靜態掃字串不算證據，而且掃出 0
   之前要先確認掃得動。**
2. 名單漏一個變數＝那條路沒被中介，而且**不會有任何錯誤訊息**。這是 V0 已知
   的殘餘風險，唯一的結構性補法是出網封鎖（`block_egress.sh`，V3）：
   封鎖之後漏掉的那條路會**連不上**而不是**偷偷連上**。

   **2026-09-19 有了活體標本**（`docs/AGENT_COMPAT.md` §12.2 對照 C）：
   在 `vacant run` 底下把 `CUSTOM_BASE_URL` 拿掉、config 也不寫 base_url，
   Hermes **不報錯**，直接去打它編死的預設 `https://openrouter.ai/api/v1`：
   `requests_seen = 0`、`wire_by_protocol = {}`、**`agent_rc = 0`**、
   閘門照樣 `visible_fail`／exit 20。
   ⇒ **那一格跟一個真的拒交格在收據上只差 `requests_seen` 一個欄位。**
   這正是為什麼「我設了環境變數」不是證據、而 `requests_seen` 是。
   （那一通送出去的是 `Authorization: Bearer no-key-required`，
   launcher 的 sentinel 一次都沒出現——但**那是 Hermes 自己的 host-gate
   做的**（GHSA-76xc-57q6-vm5m／#28660），**不是 Vacant 給的保證**。）
3. 拿掉金鑰**不是**安全邊界：同一個 OS 使用者可以自己去讀 `~/.config`、
   keychain、或任何一個 agent 自己存的憑證。它降低的是「不小心直連」的機率，
   不是「刻意繞過」的可能（`vacant_network/controller.py:7-8` 的同一條邊界）。
4. **有一條路連設定都救不了**（⚠ 這一條**只講 ChatGPT 登入那一條**；
   API key／自訂 provider 那條 2026-09-19 已經是 L-real，見 `CONFIG_ROUTE["codex"]`）：
   Codex CLI 用 ChatGPT 登入時，模型通道是
   **寫死的 `wss://chatgpt.com/backend-api/codex/responses`**——WebSocket，
   而且 `chatgpt_base_url` 只搬得動它的外掛／遙測／設定那幾條 HTTP 請求，
   搬不動模型那一條（2026-09-18 實測，`RUST_LOG` trace 逐字留檔）。
   那一格**不是「還沒支援」，是本工具的邊界**：一個 HTTP 反向代理在那條路上
   不存在。詳見 `docs/AGENT_COMPAT.md` §Codex。
"""
from __future__ import annotations

import os

#: 被指向 proxy 的 base-url 變數 → 該變數期望的路徑尾巴。
#:
#: `""` ＝ 指到 proxy 根（Anthropic 家族自己會補 `/v1/messages`）；
#: `"/v1"` ＝ 指到 `/v1`（OpenAI 家族自己會補 `/chat/completions`）。
#: 兩者混用是所有「base url 設錯」的來源，所以這裡寫死，不讓呼叫端拼字串。
REDIRECT_VARS: tuple[tuple[str, str], ...] = (
    # OpenAI 家族（含所有 OpenAI-compatible：LM Studio、vLLM、Ollama、
    # OpenRouter、Groq、Together、DeepSeek、xAI、Fireworks…）
    ("OPENAI_BASE_URL", "/v1"),
    ("OPENAI_API_BASE", "/v1"),
    ("OPENAI_BASE", "/v1"),
    ("OPENAI_API_HOST", ""),
    ("LITELLM_PROXY_API_BASE", "/v1"),
    ("OPENROUTER_BASE_URL", "/v1"),
    ("GROQ_BASE_URL", "/v1"),
    ("TOGETHER_BASE_URL", "/v1"),
    ("DEEPSEEK_BASE_URL", "/v1"),
    ("XAI_BASE_URL", "/v1"),
    ("MISTRAL_BASE_URL", "/v1"),
    ("FIREWORKS_BASE_URL", "/v1"),
    ("CEREBRAS_BASE_URL", "/v1"),
    ("OLLAMA_HOST", ""),
    # Hermes Agent（本 repo 的 `vacant_network/hermes_substrate.py` 與
    # `vacant_network/brains.py::HermesBrain` 都是設這一個）。
    # ~~未經 wire 實測~~ **2026-09-19 量掉了**：Hermes Agent **0.19.0**
    # （pip 裝進 vacant-dev 的 `/var/tmp/vacant_hermes/hv`，之前三台都沒有）×
    # `gemma-4-12b-it-qat`（LM Studio @1004）。拒交格 exit 20 ／交付格 exit 0、
    # `requests_seen` 6 ／ 6、收據 `--selftest` 先過再驗兩跑。逐字見
    # `docs/AGENT_COMPAT.md` §12。
    # ⚠ **這個變數一個人擋不住整條路**，它跟 `CONFIG_ROUTE["hermes"]` 是**一組**：
    #   Hermes 解 base_url 的順序是 `CUSTOM_BASE_URL` → config 的 `base_url`
    #   → `OPENROUTER_BASE_URL` → 編死的 `https://openrouter.ai/api/v1`，
    #   **但在那之前還有一道「有沒有選 provider」的閘**。HERMES_HOME 全新、
    #   只設本變數而沒有 provider ⇒ 停在 `No LLM provider configured`、
    #   `requests_seen == 0`（§12.2 對照 A）。**加一個 `--provider custom`
    #   或 config 一行 `provider: custom` 就夠**——那也是這一格與
    #   Claude Code 的「零接線」不同的地方。
    # ⚠ **好消息在另一個方向**：使用者本來就設好自訂 provider 時，本變數
    #   **蓋得過他 config 裡的 `base_url`**（§12.2 smoke D 實測）⇒ 那種情況
    #   確實是零接線。**兩句話都要講，不可以只講一句。**
    ("CUSTOM_BASE_URL", "/v1"),
    # Anthropic 家族（Claude Code 認 ANTHROPIC_BASE_URL——2026-09-18 假上游實測：
    # 收到 `POST /v1/messages?beta=true`，逐通完整 messages 陣列。
    # **2026-09-19 升到真模型**：Claude Code 2.1.278 ×
    # `gemma-4-12b-it-qat`（LM Studio @1003），拒交格 exit 20 ／交付格 exit 0，
    # `requests_seen` 5 ／ 4，零接線（本表這一格就是全部接線）。
    # ⚠ **那一格成立的前提不在本檔裡**：上游必須自己會講 Anthropic Messages。
    #    `wireproxy` 是反向代理**不是協定轉換器**，不會把 `/v1/messages` 改寫成
    #    `/v1/chat/completions`。1003 的 LM Studio 原生吃 `/v1/messages`
    #    （含 SSE 與 `tool_use`）所以不需要 shim；只講 OpenAI 的上游要自備轉換，
    #    而那一層不在本 repo 裡、也沒被量過。逐字見 `docs/AGENT_COMPAT.md` §9.0。
    # ⚠ **`/api/hello` 那一通會走 openai 路由出網**：Claude Code 啟動時探
    #    `$ANTHROPIC_BASE_URL/api/hello`，`wireproxy.route()` 只把 `/v1/messages`
    #    與 `/v1/complete` 判給 anthropic ⇒ 這一通落到 `VACANT_RUN_UPSTREAM_OPENAI`
    #    的預設 `https://api.openai.com`。沒 body、金鑰是 sentinel，但**是真的出網**。
    #    補法：`block_egress.sh`（V3），或把 openai 那條路也釘到本地（實測有效，§9.4）。
    ("ANTHROPIC_BASE_URL", ""),
    ("ANTHROPIC_API_URL", ""),
    # 本 repo 自己的腦（`vacant_network/brains.py`、`vacant_network/cli.py`）
    ("VACANT_MCP_BASE", ""),
    ("VACANT_ENDPOINT", ""),
)

#: 從父行程讀真上游用的變數，依**偏好順序**。`(wire, names)`。
#: wire ∈ {"openai", "anthropic"} ＝ `wireproxy.route()` 的兩條路由。
UPSTREAM_VARS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("openai", ("VACANT_RUN_UPSTREAM_OPENAI", "OPENAI_BASE_URL",
                "OPENAI_API_BASE", "OPENAI_BASE")),
    ("anthropic", ("VACANT_RUN_UPSTREAM_ANTHROPIC", "ANTHROPIC_BASE_URL",
                   "ANTHROPIC_API_URL")),
)

#: 每條路由的**公開 API** 位址。
#:
#: ⚠ **2026-09-19 之後這不再是「沒指定時的預設值」。** 它現在只在使用者
#:   **明講**要走公開 API 時才會被選到（`--allow-public-upstream`，或
#:   `VACANT_RUN_ALLOW_PUBLIC_UPSTREAM=1`）。改名成 `PUBLIC_UPSTREAM` 會
#:   更貼切，但 `DEFAULT_UPSTREAM` 這個名字被 README ×3、
#:   `docs/AGENT_COMPAT.md`、`tests/test_vrun_upstream_provenance.py` 引著，
#:   所以保留名字、改掉**語意**，並且把差別寫在 `describe_upstreams`。
DEFAULT_UPSTREAM: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
}

#: **沒有人指定那條路由的上游時，指到這裡。**
#:
#: 這支在架構裡承重什麼（2026-09-19，門檻三）：`9eeb1d9e` 加了
#: `upstreams_defaulted` 之後，「沒指定的 wire 會落到公開 API」這件事
#: **看得見了，但路還在**——而看得見沒有擋住任何東西。實例兩個，都量過：
#:
#:   · Claude Code 啟動探 `$ANTHROPIC_BASE_URL/api/hello`，被 `route()`
#:     判成 openai wire。那一跑只釘了 anthropic ⇒ 那一通去
#:     `https://api.openai.com/api/hello`，**真的出網**，去了一家那一跑
#:     根本沒在用的廠商。
#:   · pi 的 40 格每一格 `upstreams_defaulted: ['anthropic']`
#:     （沒有流量走過去，但路留著）。
#:
#: 現在那條路指到這個字串。`wireproxy` 認得它，在**開任何連線之前**就
#: fail-closed 回 502 ⇒ 不解析 DNS、不送任何 bytes、離線也成立（展場要求）。
#: `.invalid` 是 RFC 2606 保留的 TLD（**保證**解析不出來），所以就算哪天
#: 有人繞過 `wireproxy` 的那道檢查拿這個字串去連，結果也是連不上而不是
#: 連到別人家——「漏掉的那條路要連不上，不是偷偷連上」（envmap 邊界 2）。
SINK_UPSTREAM = "http://unspecified-upstream.vacant.invalid"

#: 明講「我真的要走公開 API」的環境變數逃生口。
#: 旗標版本是 `vacant run --allow-public-upstream`；這個變數是給 wrapper
#: 腳本用的（`ops/gain/r5xx/*_queue.sh` 那種改不動 argv 的地方）。
#: **兩條都必須是明講的**——沒有「印個警告然後照樣走」這個選項，
#: 因為那就是 2026-09-19 之前的狀態，而它沒用。
ALLOW_PUBLIC_VAR = "VACANT_RUN_ALLOW_PUBLIC_UPSTREAM"


def is_sink(url: str) -> bool:
    """這個上游位址是不是那個「拒絕一切」的本機 sink？

    `wireproxy._handle_inner` 用它做 fail-closed 判斷。用 `startswith`
    而不是 `==`，因為 `join_upstream()` 會在後面接 path。
    """
    return str(url).startswith(SINK_UPSTREAM)


def public_upstream_allowed(env: dict[str, str] | None = None) -> bool:
    """使用者有沒有**明講**「沒指定的 wire 可以走公開 API」。"""
    e = dict(os.environ if env is None else env)
    return e.get(ALLOW_PUBLIC_VAR, "").strip().lower() in ("1", "true", "yes", "on")

#: 金鑰類：**從子行程的 env 整個拿掉**，換成 sentinel。
SECRET_VARS: tuple[str, ...] = (
    "OPENAI_API_KEY", "OPENAI_ADMIN_KEY", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID",
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
    "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_RESOURCE_NAME",
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY",
    "GROQ_API_KEY", "MISTRAL_API_KEY", "DEEPSEEK_API_KEY", "TOGETHER_API_KEY",
    "OPENROUTER_API_KEY", "XAI_API_KEY", "FIREWORKS_API_KEY",
    "PERPLEXITY_API_KEY", "CEREBRAS_API_KEY", "COHERE_API_KEY",
    "HUGGINGFACE_API_KEY", "HF_TOKEN", "REPLICATE_API_TOKEN",
    "VACANT_MCP_API_KEY", "VACANT_API_KEY",
)

#: 兩條路由各自的「金鑰放在哪個 header」。proxy 換鑰時照這一份。
AUTH_HEADERS: dict[str, tuple[str, str]] = {
    # wire -> (header 名, 值的樣板；{key} 會被換成真鑰)
    "openai": ("authorization", "Bearer {key}"),
    "anthropic": ("x-api-key", "{key}"),
}

#: 真鑰所在的環境變數，依路由。
KEY_VARS: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY", "VACANT_MCP_API_KEY", "VACANT_API_KEY"),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
}

#: **吃設定不吃 base-url 變數的框架**：一格記一個 agent，值是「怎麼把它指過來」。
#:
#: 為什麼這也放在 envmap 而不是散在各處：本檔的承重是**一份名單**。
#: 名單漏一格的後果（那條路沒被中介、而且沒有錯誤訊息）對設定檔路線一模一樣，
#: 所以它該跟環境變數住在同一個檔，被同一雙眼睛看。
#:
#: 每一格的欄位：
#:   `relocate` ——把整份設定搬到別處的環境變數。**有這個就不必動使用者的檔案**，
#:                也不必 `--port` 固定埠：wrapper 在 runtime 讀 `$VACANT_RUN_PROXY`
#:                現寫一份。`None` ＝只能改使用者自己那份（那才需要固定埠）。
#:   `file`     ——要寫的檔名（相對 `relocate` 指的目錄）；`None` ＝設定直接是變數值。
#:   `field`    ——base url 落在哪個欄位。
#:   `wire`     ——實測到的 wire protocol。
#:   `measured` ——**實測日期**。空字串＝沒量過，不准當成可用。
#:
#: ⚠ 這份表是**觀測紀錄**不是規格：上游改版它就漂。漂了的徵兆是
#:   `requests_seen == 0`，不是這裡的字串變紅。
CONFIG_ROUTE: dict[str, dict[str, str | None]] = {
    # pi（@earendil-works/pi-coding-agent）0.85.1
    "pi": {
        "relocate": "PI_CODING_AGENT_DIR",      # 預設 ~/.pi/agent
        "file": "models.json",
        "field": 'providers.<id>.baseUrl（＋ api="openai-completions"）',
        "wire": "openai",
        "measured": "2026-09-18",
    },
    # Codex CLI。⚠ 只有 **API key／自訂 provider** 那條路；
    # ChatGPT 登入那條是寫死的 wss://，設定搬不動（見本檔誠實邊界 4）。
    # **2026-09-19 升到真模型**：codex-cli **0.147.0**（vacant-dev 上本來就有的那一份）
    # × `gemma-4-12b-it-qat`（LM Studio @1003），拒交格 exit 20 ／交付格 exit 0，
    # `requests_seen` 4 ／ 5，wire 全部是 `POST /v1/responses -> 200`。
    # 逐字落盤見 `docs/AGENT_COMPAT.md` §10。
    # ⚠ **版本要連機器一起講**：假上游那一輪量的是 0.153.2（別台），真模型這一輪是
    #   0.147.0。同一格兩個版本號不可以混寫成一個。
    # ⚠ **那一格成立的前提不在本檔裡**：上游必須自己會講 **Responses API**
    #   （`POST /v1/responses`）。`wireproxy` 是反向代理不是協定轉換器，`route()`
    #   只是把「不是 /v1/messages 也不是 /v1/complete」的 path 歸到 openai 照轉。
    #   1003 的 LM Studio 原生吃 `/v1/responses`（含 SSE 與 function tool）所以不需要
    #   shim；只有 chat/completions 的上游本來要改 `VACANT_CODEX_WIRE=chat`——
    #   **2026-09-19 量了，那條打不開**：0.147.0 在**載入 config 的那一步**就退件
    #   （`Error loading config.toml: \`wire_api = "chat"\` is no longer supported.`；
    #   serde 的 `unknown variant` 只列得出 `responses` 一個變體；`codex features list`
    #   104 個旗標裡也沒有相關的開關）。⇒ `requests_seen = 0`、`agent_rc = 1`，
    #   **等級是 L-none 不是 L-fake**：中介從來沒發生，「沒量到」≠「量到 0」。
    #   ⚠ 那是**關於 0.147.0 與兩個公開開關**的陳述，不是「Codex 不支援
    #     chat/completions」，也不知道 0.153.2 會怎樣。逐字見 §11.1。
    # ⚠ **一種跑不完的失敗**：1003 預設開思考，而 Codex 的 body 帶
    #   `reasoning: {"summary": "auto"}` 沒有 `effort` ⇒ 三跑裡有一跑在推理裡繞圈
    #   （94,776 個 `reasoning_text.delta`、0 個 `output_text`、713 秒沒收尾）。
    #   `wrap_agent.sh` 的 `VACANT_CODEX_REASONING_EFFORT`（**預設不設**）可以關掉推理，
    #   已驗兩格都收得了工——但那是**觀測到的緩解不是保證**（n 很小，而且它把推理整個
    #   關掉，別的題可能因此答得更差）。詳見 `docs/AGENT_COMPAT.md` §10.7。
    "codex": {
        "relocate": "CODEX_HOME",               # 預設 ~/.codex
        "file": "config.toml",
        # ⚠ `wire_api` 在 0.147.0 上**只剩 `"responses"` 一個值**（2026-09-19 實測，
        #   §11.1）；`"chat"` 會在 config 載入時被退件。0.153.2 沒試過。
        "field": 'model_providers.<新 id>.base_url（＋ wire_api="responses"；'
                 '0.147.0 不收 "chat"；內建 id `openai` 不准覆寫，會 fail-closed 報錯)',
        "wire": "openai",
        "measured": "2026-09-19（真模型 0.147.0；2026-09-18 假上游 0.153.2）",
    },
    # OpenCode 1.18.31。它**也**吃 OPENAI_BASE_URL（見誠實邊界 1），所以這一格
    # 本來記成「要指定自訂 provider 時才用」。**2026-09-19 用真模型量完要改口徑**：
    # 內建 `openai` provider 只吃 models.dev 註冊表裡的模型 id，拿到本地模型的 id
    # （LM Studio 的 `gemma-4-12b-it-qat`）會在**送出任何請求之前**死在模型解析
    # ⇒ `requests_seen == 0`。⇒ **要指到本地模型，這一格不是選項是必經之路。**
    # 真模型的拒交／交付兩格（exit 20 ／ exit 0）走的就是這一條，
    # 逐字落盤見 `docs/AGENT_COMPAT.md` §8。
    "opencode": {
        "relocate": "OPENCODE_CONFIG_CONTENT",  # 值直接就是整份 JSON
        "file": None,
        "field": "provider.<id>.options.baseURL",
        "wire": "openai",
        "measured": "2026-09-19（真模型；2026-09-18 假上游）",
    },
    # Hermes Agent（Nous Research，PyPI `hermes-agent`）**0.19.0**。
    # ~~沒量過~~ **2026-09-19 用真模型量掉了**（`docs/AGENT_COMPAT.md` §12）：
    # vacant-dev ＋ 1004 的 `gemma-4-12b-it-qat`，拒交格 exit 20（`requests_seen=6`、
    # `visible 1/2`）／交付格 exit 0（`requests_seen=6`、`visible 2/2`）。
    #
    # ⚠ 三個欄位的口徑，每一個都是實測不是推論：
    # 1. `relocate`＝`HERMES_HOME`：整份設定＋sessions＋skills 都搬走，
    #    跑完 `~/.hermes` **不存在**（實測：那台機器上從頭到尾沒有這個目錄）
    #    ⇒ 使用者自己的 Hermes 狀態與憑證一個 byte 都沒碰到。
    # 2. `field`＝`model.provider` **和** `model.base_url`，**兩個一起才成立**。
    #    舊註解只寫了 base_url，那是從 `hermes_substrate.py::CONFIG_YAML` 反推的，
    #    **反推漏了 provider 那一半**：少了它會停在 `No LLM provider configured`、
    #    `requests_seen == 0`（§12.2 對照 A）。
    #    ⚠ 舊註解裡的 `provider: vllm` 在 0.19.0 是 `custom` 的別名
    #    （`auth.resolve_provider`），不是獨立 provider。
    # 3. `wire`＝`openai`：實測 `POST /v1/chat/completions`（SSE、`stream:true`、
    #    17 個 tools、每通重放完整 messages），**外加** 每跑兩通
    #    `GET /api/v1/models` 的探測——那條 path **不在** 設定的 base_url 底下
    #    （base 是 `<proxy>/v1`，它打的是 `<proxy>/api/v1/models`）。
    #    在 LM Studio 上回 200 是因為 LM Studio 自己有一套 `/api/v1` REST API；
    #    **換一個嚴格的 OpenAI 相容上游那一通會 404**，本節沒量過那樣會不會壞。
    "hermes": {
        "relocate": "HERMES_HOME",
        "file": "config.yaml",
        "field": "model.provider: custom ＋ model.base_url"
                 "（CUSTOM_BASE_URL 環境變數蓋得過 base_url，但蓋不掉 provider）",
        "wire": "openai",
        "measured": "2026-09-19（真模型，Hermes Agent 0.19.0）",
    },
}


def discover_upstreams(env: dict[str, str] | None = None, *,
                       allow_public: bool = False) -> dict[str, str]:
    """從父行程的環境變數推出兩條路由各自的真上游。

    ⚠ **沒指定的那條路現在指到 `SINK_UPSTREAM`，不是公開 API**
      （除非 `allow_public=True`）。回傳的**形狀**沒變（`{wire: url}`）。
    """
    return {w: v["url"]
            for w, v in describe_upstreams(env, allow_public=allow_public).items()}


def describe_upstreams(env: dict[str, str] | None = None, *,
                       allow_public: bool = False) -> dict[str, dict]:
    """同上，但**連「這個位址是誰指定的」一起回**。

    ⚠ **為什麼要有這一支**（2026-09-19）：`vacant run` 的全部意義是中介，
    但收據原本**沒有記 bytes 去了誰的伺服器、那個位址是誰指定的**。
    於是這件事發生了而沒有人看得到——

      Claude Code 啟動時會探 `$ANTHROPIC_BASE_URL/api/hello`。
      `route()` 只把 `/v1/messages`／`/v1/complete` 判給 anthropic，
      其餘一律落到 openai ⇒ 那一通用的是 **openai 的上游**。
      而使用者只指定了 anthropic（→ 本機 1003），openai 沒指定
      ⇒ 它走 `DEFAULT_UPSTREAM["openai"]` ＝ **`https://api.openai.com`**，
      **真的出網，去了一家使用者這一跑根本沒在用的廠商。**

    那一通是空的 HEAD、金鑰是 sentinel，所以沒有洩漏內容。
    **但「這次沒洩漏」與「這條路不會洩漏」是兩件事**，而原本的收據
    連「有這麼一通」都說不出來。

    `source` 的兩種值（**形狀凍結**，README 與既有測試引著）：
      `"env:<VAR>"`  使用者（或 wrapper）明講的
      `"default"`    **沒有人指定**
    `fallback` 說的是「沒人指定的時候落到哪」（2026-09-19 加）：
      `None`       有人指定，沒有 fallback 這回事
      `"sink"`     **預設**：落到 `SINK_UPSTREAM`，會被 `wireproxy` 擋下來
      `"public"`   使用者**明講**要走公開 API（`allow_public=True`）

    ## 2026-09-19：從「看得見」改成「擋得住」（門檻三）

    本函式原本做的事是**讓那個洞看得見**，而看得見沒有擋住任何東西。
    現在沒指定的 wire 解析到 `SINK_UPSTREAM`，於是：

      · **那條路上真的有流量時** ⇒ 被擋在本機，一個 byte 都不出去，
        而且 `wire_<ARM>/index.jsonl` 會留下那一通的原文（鐵律 3）。
      · **那條路上沒有流量時** ⇒ 行為**逐位元不變**。pi 的 40 格
        （`upstreams_defaulted: ['anthropic']`、零 anthropic 流量）
        不受任何影響——這是選 sink 而不是「拒絕啟動」的主要理由：
        「這條路沒人指定」**不等於**「這一跑會用到這條路」，
        在還沒發生之前就拒絕啟動，等於用一個沒量到的東西判一個罪。
      · **兩條上游都釘死的跑**（五 agent 矩陣 20 格、
        `runs/v1_five_agent_matrix_20260919/controls.sh`）⇒ 完全不受影響，
        `fallback` 兩條都是 `None`。

    ⚠ **誠實邊界（改碼請保留）**：sink 擋的是「**沒人指定的那條路由**」。
      它**擋不住**使用者自己把上游指到公開 API（那是明講的，本來就該放行），
      也**擋不住** agent 繞過 proxy 直連（`vacant_network/controller.py:7-8` 的同一條
      邊界；結構性補法仍然是 `block_egress.sh`，V3）。
    """
    e = dict(os.environ if env is None else env)
    out: dict[str, dict] = {}
    for wire, names in UPSTREAM_VARS:
        src, val = "", ""
        for n in names:
            if e.get(n, "").strip():
                src, val = f"env:{n}", e[n].strip()
                break
        if val:
            out[wire] = {"url": val, "source": src, "defaulted": False,
                         "fallback": None}
        elif allow_public:
            out[wire] = {"url": DEFAULT_UPSTREAM[wire], "source": "default",
                         "defaulted": True, "fallback": "public"}
        else:
            out[wire] = {"url": SINK_UPSTREAM, "source": "default",
                         "defaulted": True, "fallback": "sink"}
    return out


def discover_keys(env: dict[str, str] | None = None) -> dict[str, str]:
    """兩條路由各自的真鑰（拿不到就空字串——proxy 照樣轉送，由上游拒絕）。"""
    e = dict(os.environ if env is None else env)
    return {wire: next((e[n] for n in names if e.get(n)), "")
            for wire, names in KEY_VARS.items()}


def build_child_env(proxy_url: str, sentinel: str, *,
                    env: dict[str, str] | None = None,
                    extra: dict[str, str] | None = None) -> tuple[dict[str, str], dict]:
    """組出要交給 agent 的環境。回 `(child_env, meta)`。

    `meta` 落進收據，因為「哪些變數被改掉、哪些被拿掉」本身就是證據——
    事後有人問「它到底有沒有被轉向」，看的是這一份，不是本檔的原始碼。
    """
    base = dict(os.environ if env is None else env)
    child = dict(base)
    redirected: dict[str, str] = {}
    for name, suffix in REDIRECT_VARS:
        child[name] = proxy_url.rstrip("/") + suffix
        redirected[name] = child[name]
    stripped: list[str] = []
    for name in SECRET_VARS:
        if name in child:
            del child[name]
            stripped.append(name)
    # 每條路由給一個 sentinel 金鑰：agent 手上沒有真鑰，但 SDK 仍然願意送出請求
    # （多數 SDK 缺 key 會在本機就 raise，那樣連 wire 都到不了）。
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        child[name] = sentinel
    child["VACANT_RUN_PROXY"] = proxy_url
    child["VACANT_RUN_SENTINEL"] = sentinel
    if extra:
        child.update(extra)
    meta = {
        "proxy_url": proxy_url,
        "redirected": sorted(redirected),
        "stripped": sorted(stripped),
        "sentinel_vars": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
        "note": ("環境變數名單擋不到用設定檔的框架（pi 的 models.json、"
                 "內建 provider 的編譯期 baseUrl）——見本檔 docstring 邊界 1。"),
    }
    return child, meta
