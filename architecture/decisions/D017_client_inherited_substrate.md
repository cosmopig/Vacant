# D017 — `ClientInheritedSubstrate` 與 MCP `sampling/createMessage`

* Status: Accepted
* Date: 2026-05-06
* Related dispatch: `dispatch/Pfix2_codex_round2.md` Group D2
* Implements: `src/vacant/substrate/client_inherited.py`,
  `src/vacant/cli/mcp_server.py::vacant_call_with_sampling`

## Context

THEORY_V5 §3 將 substrate 視為 *資源*，與 vacant 的 *身分* 解耦。
README 的 "嫁接到客戶端" 主張更進一步：vacant 部署時 **完全不需要自帶 LLM**
（沒有 API key、沒有本地模型）。實際的 LLM 推理由呼叫端（MCP-aware client，
例如 Claude Desktop / Claude Code / OpenClaw）在呼叫的當下臨時提供。

A2/A3 落地後，vacant 已經能透過 MCP 被外部 client 呼叫。但要真的兌現
"沒有自帶 LLM 也能跑" 的承諾，還需要一條反向通道：vacant 在處理一次呼叫
的中途，向發起呼叫的 client 借用一次 LLM 推理。MCP 標準裡這條通道
就是 [`sampling/createMessage`](https://modelcontextprotocol.io/specification/server/sampling)
— server 反向請求 client 做一次模型推理。

D2 把這條通道接起來。

## Decision

### 1. `ClientInheritedSubstrate` 是一個 first-class `SubstrateBackend`

它和 `AnthropicSubstrate`、`OllamaSubstrate` 並列，但有兩個關鍵差異：

* **沒有自有狀態**：建構函數收一個 `SamplingCallback`
  （`async (sys_prompt, user_prompt) -> text`），由呼叫端的 serve 層
  在收到呼叫的當下動態組出來，Substrate 物件只活在這一次呼叫的生命週期內。
* **身分可審計**：substrate name 是 `client-inherited:<caller_vacant_id>:<model_hint>`，
  讓 reputation per-substrate 仍然能正確歸因 — 「這個 vacant 借用 Alice 的
  Claude 跑出來的這個結果」會被記在它的歷史裡。

### 2. Envelope 的可選擴充欄位

`SubstrateHandle` dataclass 攜帶三個欄位：
`substrate_kind` (default `"client-inherited"`)、`model_hint`、
`transport_callback_id`。它的設計目標是 *當 client 透過 A2A HTTP path 呼叫
vacant 時*，能在 envelope metadata 裡聲明 "我這個呼叫附帶一個可借用的
substrate"。本 PR 只落地 dataclass + substrate 物件本體；A2A envelope schema
擴充留給後續 PR (envelope 簽章 surface 的變動需要另一輪 review)。

MCP path 不需要這個欄位 — MCP 規範本身已經有 `sampling/createMessage`，
client 在 `ClientSession(... sampling_callback=cb)` 構造時就承諾了能借出。

### 3. MCP server 端的 `vacant_call_with_sampling` 工具

`build_fastmcp_server` 在 `vacant_describe` / `vacant_call` 之外多註冊
一個 `vacant_call_with_sampling` 工具：

* 接 `user_prompt` / `system_prompt` / `model_hint` / `caller_vacant_id_hex`
* 工具實作裡用 `Context.session.create_message(...)` 反向呼叫 client
  做 sampling
* 回傳的 dict 包含 `text`（推理結果）、`substrate`（`client-inherited:...`
  完整身分）、`proof`（borrowed_from / model_hint / substrate_kind 完整稽核
  payload）

呼叫端（client）在 open session 時用 `sampling_callback=` 傳入自己的 LLM
session — `tests/integration/test_mcp_sampling.py` 是這個流程的 happy-path。

## 安全模型

1. **借出端 (client) 的責任**：client 收到 `sampling/createMessage` 時可以
   拒絕、改寫、取樣後返回。MCP 規範就是要求 client 對被自己 LLM 跑出來的
   內容負責。
2. **借入端 (vacant) 的責任**：vacant 不能假設借來的回覆是 ground truth。
   它在 logbook 裡記下的條目仍然由自己簽署，但 substrate 身分明確標示為
   `client-inherited:<caller>:<model_hint>` — 這代表 *這條 reputation
   不應該回饋到 vacant 自己的 substrate-skill 分數*，而應該分到
   `client-inherited:*` bucket 去。
3. **Envelope chain 不變**：sampling 反向呼叫只發生在 vacant 處理工具
   呼叫的中途；對外可見的 envelope chain（HTTP path）/ tool result
   chain（MCP path）仍然是 vacant 自己簽出去的東西。借用 LLM 不會弱化
   replay protect 與簽章鏈。

## Consequences

* **正面**：
  * "嫁接到客戶端" 的論文主張現在有實際可演示的程式碼。
  * 部署 vacant 不需要 API key — `vacant serve --mcp` 跑起來，client 連上
    就能用 client 的腦。
  * Substrate diversity 自然延伸：未來加 `OpenAISubstrate`、`GeminiSubstrate`
    時，`ClientInheritedSubstrate` 仍然透過同一條 MCP sampling 反向通道，
    無需任何提供者特定程式碼。
* **負面**：
  * Vacant 對 client LLM 的可用性有強依賴 — client 拒絕 sampling 時
    `vacant_call_with_sampling` 會直接 raise (這是預期行為，
    `test_substrate_propagates_callback_exceptions` 守住)。
  * 反向通道的延遲翻倍（vacant 每次呼叫都會多一次 round-trip 回 client）。
    對需要長 system_prompt 的 vacant 來說，要把 prompt 留在 vacant 端而非
    每次都重傳 — 後續 PR 會在 sampling 請求上加 `caching_hint`。

## Alternatives Considered

1. **強制每個 vacant 自帶 substrate** — 這是 D015 之前的預設。問題：違背
   THEORY_V5 §3 的解耦原則，且部署門檻高。
2. **把 sampling 寫進 A2A envelope metadata，不用 MCP** — 技術上可行，
   但會分裂 client 端的接入路徑（本來只要 MCP-aware 就能用）。MCP
   sampling 已經是事實標準。
3. **用 OpenAI 的 function-calling 反向作為 sampling 通道** — 不通用，
   只能跟 OpenAI-compatible client 對接，違反 substrate diversity 目標。

## References

* MCP `sampling/createMessage` 規範：
  <https://modelcontextprotocol.io/specification/server/sampling>
* `dispatch/Pfix2_codex_round2.md` §"Group D — Substrate diversity" §D2
* `tests/integration/test_mcp_sampling.py` — 完整 happy-path
* `tests/unit/test_client_inherited.py` — substrate 契約覆蓋
