# 把 Vacant 嫁接到你的客戶端

[English](INTEGRATION.md) · [繁體中文](INTEGRATION.zh-TW.md)

實戰教學：把一個 vacant 真的接到 MCP-aware client（Claude Desktop、
Cursor、Zed、`@modelcontextprotocol/inspector`，或任何會講 MCP 線協議
的東西）。**5 分鐘內** 跑完第一次呼叫；**再花 10 分鐘** 弄懂
`ClientInheritedSubstrate` — 讓 vacant **不需要自帶 API key**、透過
MCP `sampling/createMessage` 借用呼叫端 LLM 的那個 substrate。

只想看理論的話請讀
[`architecture/THEORY_V5.md`](../architecture/THEORY_V5.md)。
這份文件純操作。

---

## 1 · 先決條件

| 工具 | 版本 | 用途 |
|---|---|---|
| Python | ≥ 3.12 | 專案 requires-python |
| [`uv`](https://docs.astral.sh/uv/) | 最新 | 相依 / venv 管理 |
| 一個 MCP-aware client | 任意 | Claude Desktop / Cursor / Zed / MCP Inspector / 你自己用 SDK 寫的 |

clone + 安裝：

```bash
git clone https://github.com/cosmopig/Vacant.git
cd Vacant
uv sync --all-extras
```

煙霧測試：

```bash
uv run vacant --help            # Typer help；列出所有 subcommand
uv run vacant serve --help      # 確認 serve 命令掛上了
```

### MCP client 相容性

| Client | stdio | sampling/createMessage |
|---|---|---|
| Claude Desktop | ✓ | ✓（≥ 1.x 版本） |
| Cursor | ✓ | ✓（近期版本） |
| Zed | ✓ | ✗（純消費端） |
| `@modelcontextprotocol/inspector` | ✓ | ✓（直接 pass-through） |
| `mcp` Python SDK（`ClientSession`） | ✓ | ✓（用 `sampling_callback=`） |

`ClientInheritedSubstrate` 唯一需要的就是 sampling 反向通道。沒有
sampling 的 client 還是能呼叫 `vacant_describe` 跟 `vacant_call`，
但 `vacant_call_with_sampling` 會壞掉。

---

## 2 · 5 分鐘 Quickstart

### 2.1 開一個 local vacant

```bash
mkdir -p ~/.vacant
uv run vacant init alice
# {"name": "alice", "vacant_id": "<64-hex>"}
```

這會寫 `~/.vacant/alice/{key.json,logbook.jsonl,meta.json}`，
key 檔案是 0600。

### 2.2（可選）發布 halo 到 local registry

只想接 MCP 的話可以跳過。要把 alice 推到 registry：

```bash
# 一個終端：跑 registry server（P4 — 細節見 RUNBOOK.md）
uv run uvicorn vacant.registry.rpc:build_app --port 8080

# 另一個終端：
export VACANT_REGISTRY_URL=http://127.0.0.1:8080
uv run vacant publish --capability "echo" \
  --endpoint http://127.0.0.1:8443/a2a/message/send
uv run vacant status
```

### 2.3 把 vacant 跑成 server

```bash
uv run vacant serve --name alice --port 8443
# {"name":"alice","vacant_id":"<hex>","host":"127.0.0.1","port":8443,"mcp":false}
```

確認跑起來：

```bash
curl -s http://127.0.0.1:8443/health
# {"vacant_id":"<hex>","state":"LOCAL","name":"alice"}

curl -s http://127.0.0.1:8443/card | jq
# capability_card_blob_hex + halo_version
```

### 2.4 透過 MCP 接到 Claude Desktop / Cursor

把 vacant 寫進 client 的 MCP config。Claude Desktop 在
`~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "vacant-alice": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/Vacant",
        "run",
        "python",
        "-m",
        "vacant.cli.mcp_serve_test_runner",
        "alice"
      ]
    }
  }
}
```

> **為什麼用 `mcp_serve_test_runner` 而不是 `vacant serve --mcp`？**
> `vacant serve --mcp` 會 **同時** 跑 HTTP 跟 MCP — 兩個 transport
> 都要的時候用。`mcp_serve_test_runner` 是純 stdio，這正是大部分
> MCP client 在 driver 的形狀。看你部署的需求挑。

重啟 Claude Desktop。會看到三個工具浮上來：

* `vacant_describe` — capability text + halo metadata
* `vacant_call` — 收一個簽過名的 A2A envelope，走跟 HTTP path
  一樣的簽章驗證 + replay protection
* `vacant_call_with_sampling` — 借用 client 的 LLM（下一節）

問 Claude：「用 vacant-alice 的 vacant_describe 工具」。應該會回
vacant_id 跟你設的 capability text。

### 2.5（加碼）用 MCP Inspector 直接驅動

```bash
npx @modelcontextprotocol/inspector \
  uv --directory $PWD run python -m vacant.cli.mcp_serve_test_runner alice
```

同樣三個工具。Inspector 讓你手動丟 `tools/call`，debug 簽章
失敗時非常好用。

---

## 3 · `ClientInheritedSubstrate` — 借用 client 的 LLM

這是「把 vacant 嫁接到你的 client」這個論點最 load-bearing 的一塊：
**部署的 vacant 完全不用自己帶 API key**。當 client 呼叫一個需要
推理的 vacant 工具時，vacant 反過來透過標準 MCP `sampling/createMessage`
請 client 替它做這次推理。

### 為什麼這樣設計

* 沒有秘密外洩風險。Vacant 在硬碟上的狀態只有 Ed25519 keypair +
  logbook；完全沒有 LLM 存取相關的東西。
* 不綁特定供應商。Client 用什麼 LLM，那一次呼叫 vacant 就用什麼。
* Reputation per-substrate 仍可審計。Substrate 身分記成
  `client-inherited:<caller_vacant_id>:<model_hint>`，借用完整可追蹤。
  細節見 ADR
  [`D017_client_inherited_substrate.md`](../architecture/decisions/D017_client_inherited_substrate.md)。

### 線協議流程

```
Client（Claude Desktop）           Vacant（你的 serve 子程序）
       │                                              │
       │── tools/call vacant_call_with_sampling ──────▶│
       │     { user_prompt, system_prompt,            │
       │       model_hint, caller_vacant_id_hex }     │
       │                                              │
       │                         ┌────────────────────┤
       │                         │ 構造               │
       │                         │ ClientInherited    │
       │                         │ Substrate(cb=...)  │
       │                         └────────────────────┤
       │                                              │
       │◀──── sampling/createMessage(messages, …) ────│
       │                                              │
       │── createMessage 結果（你的 LLM 跑出來）─────▶│
       │                                              │
       │                         ┌────────────────────┤
       │                         │ 包成               │
       │                         │ SubstrateResponse  │
       │                         │（substrate name +  │
       │                         │  proof）           │
       │                         └────────────────────┤
       │                                              │
       │◀── tools/call result { text, substrate, …} ──│
```

Vacant 在 logbook 寫的那條 entry 會帶 substrate name
（`client-inherited:<caller>:<model>`）— 借用這件事完全可被任何讀
chain 的人事後審計。

### 用 `mcp` Python SDK 呼叫

這是標準寫法，也正是
[`tests/integration/test_mcp_sampling.py`](../tests/integration/test_mcp_sampling.py)
在驗證的：

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import (
    CreateMessageRequestParams, CreateMessageResult,
    SamplingCapability, TextContent,
)

async def my_sampling_cb(ctx, params: CreateMessageRequestParams) -> CreateMessageResult:
    user_text = next(
        m.content.text for m in params.messages
        if isinstance(m.content, TextContent)
    )
    # 換成你真的 LLM call。
    answer = await my_llm.complete(system=params.systemPrompt, user=user_text)
    return CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text=answer),
        model="claude-sonnet-4-6",
        stopReason="endTurn",
    )

params = StdioServerParameters(
    command="uv",
    args=["--directory", PROJECT_ROOT, "run", "python",
          "-m", "vacant.cli.mcp_serve_test_runner", "alice"],
)
async with stdio_client(params) as (r, w):
    async with ClientSession(
        r, w,
        sampling_callback=my_sampling_cb,
        sampling_capabilities=SamplingCapability(),
    ) as session:
        await session.initialize()
        result = await session.call_tool(
            "vacant_call_with_sampling",
            arguments={
                "user_prompt": "2 加 2 是多少？",
                "system_prompt": "簡短回答。",
                "model_hint": "claude-sonnet-4-6",
                "caller_vacant_id_hex": MY_CALLER_VID_HEX,
            },
        )
```

`result.content[0].text` 是一個 JSON 字串，裡面有 `text`（LLM
回的內容）、`substrate`（可審計的身分字串）、`proof`（借用的
metadata）。

### Reputation 怎麼算

借來的 substrate 跑出來的這次推理在貢獻 reputation 更新時，會
進到 `client-inherited:*` bucket — **不會** 算到 vacant 自己內建
substrate 的分數上。所以一個一直跑在 Claude 之上的 vacant，它的
紀錄被歸成「借 Claude 跑」，之後改用 Mistral 來借時，比較仍然
有意義。

---

## 4 · 兩台 vacant 互呼（真實網路）

只想接 MCP 的話可以跳過這節。這是 live A2A path 的示範。

```bash
# Terminal 1
uv run vacant init alice
uv run vacant serve --name alice --port 8443 \
  --endpoint http://127.0.0.1:8443/a2a/message/send

# Terminal 2
uv run vacant init bob
# 用 vacant.cli.server.build_serve_app 拿到 bob 的 signing key，
# 或透過 dispatch helper 跟 alice 講話：

uv run python <<'PY'
import asyncio, httpx
from vacant.cli.server import build_serve_app
from vacant.protocol import (
    A2AMessage, A2APart, call_local, make_httpx_transport,
)
from vacant.protocol.capability_card import deserialize as deserialize_card

async def main():
    bob = build_serve_app("bob")  # bob 在這裡沒在跑 server，
                                  # 我們只是要拿 bob 的 keypair。
    async with httpx.AsyncClient() as c:
        r = await c.get("http://127.0.0.1:8443/card")
    alice_card = deserialize_card(bytes.fromhex(r.json()["capability_card_blob_hex"]))
    transport = make_httpx_transport(timeout=5.0)
    result = await call_local(
        target_card=alice_card,
        requester=bob.form,
        requester_signing_key=bob.signing_key,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="嗨 alice")]),
        transport=transport,
    )
    print("response:", result.response_envelope.payload.parts[0].text)
    print("通過 alice 公鑰驗證:",
          result.response_envelope.verify(alice_card.vacant_id.verify_key()))

asyncio.run(main())
PY
```

真的簽過名的 envelope round-trip；alice 的回應通過她硬碟上的
Ed25519 公鑰驗證。這就是
[`tests/integration/test_live_two_vacants.py`](../tests/integration/test_live_two_vacants.py)
裡那條 live-network 測試濃縮成你能手動跑的 script。

---

## 5 · Troubleshooting

### `--port 8443` 上 `address already in use`

```bash
# 找出占用 port 的 process
lsof -i :8443
# 或乾脆換一個 port
uv run vacant serve --name alice --port 8444
```

### MCP client 看不到 `vacant_call_with_sampling`

要嘛 client 沒宣告 sampling capability，要嘛它默默把 schema
裡參考 `Context` 的工具濾掉了。

* **Claude Desktop**：確認版本夠新；舊版本不會 pass-through
  `sampling/createMessage`。
* **MCP Inspector**：開箱即用。
* **Cursor / Zed**：看 release notes — sampling 支援是逐步上線中。

### `EnvelopeSignatureError: response envelope did not verify`

對方 vacant 的回應不是用你預期那把 key 簽的。常見原因：

1. 你拿到的 card 過時了 — 重新 fetch `/card`。
2. 對方 vacant rotate 了 key 但沒更新 card。
3. 你呼到錯的 endpoint（例如 proxy 把 metadata block 砍掉了）。

對 `/card` 裡的 `vacant_id` 跟 response envelope 裡的
`from_vacant_id` — 必須一致。

### `the greenlet library is required`

我們有 explicit pin `greenlet`。看到這個錯代表你的 `uv sync` 跑在
舊 lockfile 上。pull 後跑 `uv sync --all-extras`。

### `vacant init <name>` 說 "already exists"

每個 name 對應 `~/.vacant/` 底下一個資料夾。換個 name 或者
`rm -rf ~/.vacant/<name>`（這會把 keypair 砍掉，不可逆）。

### Sampling callback 有打到，但工具回傳 text 是空的

確認你的 callback 回的 `CreateMessageResult` 的 `content` 是
`TextContent`（不是 `ImageContent` 或 `ResourceLinkContent`）。
Vacant 只知道怎麼從 sampling 回應裡讀 text。

### MCP server 啟動時看似卡住

Vacant 的 stdio MCP server 在 client 還沒 initialize 之前不會
emit 任何輸出。檢查：

* Client 真的有送 `initialize`（Inspector 有 "Reconnect" 按鈕）。
* 如果你跑在 `~/.vacant` 之外，記得設 `VACANT_HOME`。
* 那個名字的 vacant 真的存在（`vacant status`）。

---

## 接下來

* [`docs/RUNBOOK.md`](RUNBOOK.md) — 跑 scenarios 跟 dashboard
* [`docs/DEMO_SCRIPT.md`](DEMO_SCRIPT.md) — 答辯 / talk 用的 5 分鐘走法
* [`architecture/THEORY_V5.md`](../architecture/THEORY_V5.md) — 完整理論
* [`architecture/decisions/D017_client_inherited_substrate.md`](../architecture/decisions/D017_client_inherited_substrate.md)
  — 借用 substrate 的安全模型

做了什麼東西的話歡迎開 issue 或 PR — 各種範例跟 client 專屬
recipe 都歡迎進來。
