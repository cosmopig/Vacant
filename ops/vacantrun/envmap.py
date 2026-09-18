"""這支在架構裡承重什麼：**一份環境變數名單，不是 per-framework 程式碼**。

`vacant run` 要把 agent 的模型通道轉向到自己的 proxy。做這件事有兩條路：

  (a) 每支框架寫一段接線（pi 一段、Claude Code 一段、aider 一段…）——幾十段，
      而且每次上游改版就漂一次；
  (b) 認**環境變數**這個所有 SDK 共用的介面——一份名單，改版不漂。

本檔是 (b) 的那份名單，而且是**唯一**一份（launcher 不准另外寫死變數名）。

三個角色分開列，因為它們的語意不同：

  · `REDIRECT_VARS`  ——要被指向 proxy 的 base-url 變數。值有兩種形狀
    （`/v1` 結尾與根結尾），寫成 `(name, suffix)` 而不是靠呼叫端記得加。
  · `UPSTREAM_VARS`  ——從**父行程**讀真正上游位址用的（讀完就從子環境拿掉）。
  · `SECRET_VARS`    ——金鑰類。**從 agent 的 env 裡整個拿掉**，只留在 proxy
    行程裡；agent 拿到的是一個 sentinel 字串，proxy 在轉送時換回真鑰。

⚠ **誠實邊界（改碼請保留）**：

1. 這份名單擋得到「讀環境變數決定 base url」的框架。**擋不到用設定檔的框架**
   ——pi（@earendil-works/pi-coding-agent）的 provider `baseUrl` 寫在
   `models.json` 裡，內建 provider 的 baseUrl 甚至是編進 bundle 的常數，
   環境變數在那條路上完全沒有作用。那種框架要嘛把設定檔指向 proxy
   （`vacant run --port` 給一個固定埠就是為了這個），要嘛就沒被中介到。
   **「設了環境變數」不等於「被中介了」**——真正的證據是 proxy 的 wire log
   有沒有東西（`launcher` 會把 `requests_seen` 落進收據）。
2. 名單漏一個變數＝那條路沒被中介，而且**不會有任何錯誤訊息**。這是 V0 已知
   的殘餘風險，唯一的結構性補法是出網封鎖（`block_egress.sh`，V3）：
   封鎖之後漏掉的那條路會**連不上**而不是**偷偷連上**。
3. 拿掉金鑰**不是**安全邊界：同一個 OS 使用者可以自己去讀 `~/.config`、
   keychain、或任何一個 agent 自己存的憑證。它降低的是「不小心直連」的機率，
   不是「刻意繞過」的可能（`vacant/controller.py:7-8` 的同一條邊界）。
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
    # Anthropic 家族（Claude Code 認 ANTHROPIC_BASE_URL）
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


def discover_upstreams(env: dict[str, str] | None = None) -> dict[str, str]:
    """從父行程的環境變數推出兩條路由各自的真上游。找不到就用預設。"""
    e = dict(os.environ if env is None else env)
    out: dict[str, str] = {}
    for wire, names in UPSTREAM_VARS:
        val = next((e[n].strip() for n in names if e.get(n, "").strip()), "")
        out[wire] = val or DEFAULT_UPSTREAM[wire]
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
