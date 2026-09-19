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
2. 名單漏一個變數＝那條路沒被中介，而且**不會有任何錯誤訊息**。這是 V0 已知
   的殘餘風險，唯一的結構性補法是出網封鎖（`block_egress.sh`，V3）：
   封鎖之後漏掉的那條路會**連不上**而不是**偷偷連上**。
3. 拿掉金鑰**不是**安全邊界：同一個 OS 使用者可以自己去讀 `~/.config`、
   keychain、或任何一個 agent 自己存的憑證。它降低的是「不小心直連」的機率，
   不是「刻意繞過」的可能（`vacant/controller.py:7-8` 的同一條邊界）。
4. **有一條路連設定都救不了**：Codex CLI 用 ChatGPT 登入時，模型通道是
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
    # Hermes Agent（本 repo 的 `vacant/hermes_substrate.py` 與
    # `vacant/brains.py::HermesBrain` 都是設這一個）。
    # ⚠ **未經 wire 實測**：Hermes 在 Mac 與 vacant-dev、vacant-clean1 上都沒裝
    #   （2026-09-18 查），所以這一格的證據等級是「本 repo 自己的呼叫端這樣寫」，
    #   不是「假上游看到過一通」。名單多一個變數只是多設一個環境變數（無害），
    #   漏一個才會靜靜地沒被中介——所以放進來，但不准讀成已驗證。
    ("CUSTOM_BASE_URL", "/v1"),
    # Anthropic 家族（Claude Code 認 ANTHROPIC_BASE_URL——2026-09-18 實測：
    # 假上游收到 `POST /v1/messages?beta=true`，逐通完整 messages 陣列）
    ("ANTHROPIC_BASE_URL", ""),
    ("ANTHROPIC_API_URL", ""),
    # 本 repo 自己的腦（`vacant/brains.py`、`vacant/cli.py`）
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

#: 每條路由在沒有任何環境變數指定時的預設上游。
DEFAULT_UPSTREAM: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
}

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
    # Codex CLI 0.153.2。⚠ 只有 **API key／自訂 provider** 那條路；
    # ChatGPT 登入那條是寫死的 wss://，設定搬不動（見本檔誠實邊界 4）。
    "codex": {
        "relocate": "CODEX_HOME",               # 預設 ~/.codex
        "file": "config.toml",
        "field": 'model_providers.<新 id>.base_url（＋ wire_api="responses"｜"chat"；'
                 "內建 id `openai` 不准覆寫，會 fail-closed 報錯)",
        "wire": "openai",
        "measured": "2026-09-18",
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
    # Hermes Agent。**沒量過**——三台機器上都沒裝（2026-09-18）。
    # 欄位是從 `vacant/hermes_substrate.py::CONFIG_YAML` 反推的。
    "hermes": {
        "relocate": "HERMES_HOME",
        "file": "config.yaml",
        "field": "model.base_url（另有 CUSTOM_BASE_URL 環境變數，同樣未實測）",
        "wire": "openai",
        "measured": "",
    },
}


def discover_upstreams(env: dict[str, str] | None = None) -> dict[str, str]:
    """從父行程的環境變數推出兩條路由各自的真上游。找不到就用預設。"""
    return {w: v["url"] for w, v in describe_upstreams(env).items()}


def describe_upstreams(env: dict[str, str] | None = None) -> dict[str, dict]:
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

    `source` 的三種值：
      `"env:<VAR>"`  使用者（或 wrapper）明講的
      `"default"`    **沒有人指定，用的是公開 API 的預設值**
      本函式不判斷哪一種比較好——它只負責讓那個差別**寫得出來**。
    """
    e = dict(os.environ if env is None else env)
    out: dict[str, dict] = {}
    for wire, names in UPSTREAM_VARS:
        src, val = "", ""
        for n in names:
            if e.get(n, "").strip():
                src, val = f"env:{n}", e[n].strip()
                break
        out[wire] = ({"url": val, "source": src, "defaulted": False} if val
                     else {"url": DEFAULT_UPSTREAM[wire],
                           "source": "default", "defaulted": True})
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
