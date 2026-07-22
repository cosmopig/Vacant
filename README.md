# Vacant

Vacant 是 AI agent 前面的信任與驗證層。它不再期待 agent 自己記得呼叫某個工具，
而是先取得經客觀檢查、互審、稽核與簽章的交付，再啟動 Hermes 或任何 CLI agent。

```text
user task
   |
   v
Vacant-first controller
   |-- reputation routing
   |-- generate -> objective check -> repair (up to 3 attempts)
   |-- signed peer reviews + deterministic audit
   |-- task/answer-bound signed receipt
   v
Hermes / Claude Code / Aider / any argv-based agent
```

這個順序由程式控制，不靠 system prompt：收據或客觀重驗有任何一項失敗，下游 agent
不會被啟動。

## 安裝

需要 Python 3.11 以上。

```bash
pip install git+https://github.com/cosmopig/Vacant.git
```

開發版本：

```bash
git clone https://github.com/cosmopig/Vacant.git
cd Vacant
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

## 三分鐘開始

先指向 LM Studio、vLLM 或任何 OpenAI-compatible 模型端點：

```bash
export VACANT_MCP_BASE=http://localhost:1234
export VACANT_MCP_MODEL=your-model
export VACANT_MCP_API=openai
```

reasoning 模型若使用 LM Studio `/api/v1/chat`，把 `VACANT_MCP_API` 改成
`responses`。需要 Bearer token 的遠端端點可另設：

```bash
export VACANT_API_KEY=your-token
```

先只取得 Vacant 的已驗證交付：

```bash
vacant run \
  "Write solve(nums), returning the sum of all even integers." \
  --test "assert solve([1, 2, 3, 4]) == 6" \
  --test "assert solve([]) == 0"
```

預設流程會：

1. 使用全良性的產品 resident roster，不載入 demo 的人工 saboteur。
2. 最多生成三次；前一版未過客觀 check 時才重作。
3. 由其他 resident 簽章互審，並由 deterministic auditor 重跑 check。
4. 產生完整綁定 task、check、risk、answer 與 trust card 的 Ed25519 receipt。
5. 在本機重新執行一次 check；全部成立才算 gate 通過。

## 強制接到 Hermes

```bash
vacant run \
  "Write solve(nums), returning the sum of all even integers." \
  --test "assert solve([1, 2, 3, 4]) == 6" \
  --test "assert solve([-2, -3, 4]) == 2" \
  --agent hermes
```

若 Hermes 不在 `PATH`：

```bash
vacant run \
  "Write solve(s) that reverses a string." \
  --test "assert solve('abc') == 'cba'" \
  --agent hermes \
  --hermes-bin "$HOME/hermes-agent/venv/bin/hermes"
```

Hermes 直到 gate 通過後才會被建立成子行程。啟動時已收到：

- 原始任務；
- Vacant 通過客觀檢查的交付；
- 本次 `task_id`；
- 簽章 receipt 與公開 context 路徑。

Hermes 不需要自行決定是否呼叫 Vacant，也不能在這條流程裡先寫答案再略過委派。

## 接到任何 CLI agent

`--agent-argv` 接受 JSON 字串陣列，不經 shell。以下例子把已驗證答案交給另一個
agent：

```bash
vacant run \
  "Return a JSON object with a non-empty name field." \
  --schema '{"type":"object","required":["name"],"properties":{"name":{"type":"string","minLength":1}}}' \
  --agent-argv '["my-agent","--prompt","Apply this verified delivery:\n{answer}\nReceipt: {receipt_path}"]'
```

大型內容可改傳公開 context 檔，避免把完整答案放進 process argv：

```bash
vacant run \
  --task-file task.md \
  --check-file check.json \
  --agent-argv '["my-agent","--context","{context_path}"]'
```

允許的 placeholder：

| Placeholder | 內容 |
|---|---|
| `{task}` | 原始任務 |
| `{answer}` | Vacant 已驗證交付 |
| `{task_id}` | task 與 check 的識別碼 |
| `{receipt_path}` | 本次簽章 receipt |
| `{context_path}` | 不含 hidden check 的公開 context |

為了避免 shell injection：

- command 必須是 JSON argv，不接受 shell command string；
- `argv[0]` 不允許 placeholder；
- command 必須接收 `{answer}` 或 `{context_path}`；
- controller 固定以 `shell=False` 啟動。

自訂 agent executable 本身仍是信任設定；若它其實是會再次呼叫 shell 的 wrapper，仍會
重新引入 command injection。Vacant 會拒絕常見 shell、`env` 與 `python -c` 等直接入口，
但無法判斷任意自製 binary 的內部行為。

## 客觀 Check

`vacant run` 提供常見縮寫：

```bash
# Python 程式碼：可重複 --test
vacant run "Write solve(x)." --test "assert solve(2) == 4"

# 精確答案
vacant run "Return the token READY." --expect READY

# 子字串／正則
vacant run "Include build status." --contains success
vacant run "Return a four-digit code." --regex '^[0-9]{4}$'

# 完整 check-spec
vacant run --task-file task.md --check-json \
  '{"type":"json_schema","schema":{"type":"object","required":["name"]}}'
vacant run --task-file task.md --check-file check.json
```

完整 check-spec 支援：

```jsonc
{"type":"equals","value":"READY"}
{"type":"contains","value":"success","ignore_case":true}
{"type":"regex","pattern":"^[0-9]{4}$"}
{"type":"json_schema","schema":{"type":"object","required":["name"]}}
{"type":"run_python","code":"assert solve('ab') == 'ba'"}
```

要啟動下游 agent，gate 只接受 `equals`、`json_schema`、`run_python` 三種強 check。
`contains` 與 `regex` 適合探索或格式提示，但不足以證明整份交付安全，因此只能取得
Vacant 回答，不能授權 agent launch。

Vacant 傳給 agent 的不是模型原始訊息，而是 verifier 實際檢查的投影：Python 只傳
抽出的 code，JSON 只傳解析後的 canonical JSON，equals 只傳正規化後的精確值。未經
檢查的 fence 外文字或 JSON 前後說明不會進 receipt，也不會進 agent context。

`run_python` 在獨立 `python -I` 行程、暫存 cwd、CPU limit 與 timeout 下執行。
hidden tests 留在 verifier，候選碼在另一個 worker，函式參數與回值透過 literal-only
RPC 傳遞，因此參數與回值需能由 `ast.literal_eval` 還原。它能擋提前 `exit(0)`、直接
讀同檔 hidden tests 與常見 process/file API，但仍不是完整的惡意程式安全邊界；不可信
程式應放進 container、gVisor 或獨立 VM。

嚴格模式預設禁止 candidate import。確定需要標準函式庫時可在完整 check-spec 顯式加入
`"allowed_imports":["hashlib"]`；這會擴大 worker 的攻擊面，高風險任務應改用 container
verifier，而不是持續放寬 allowlist。

## Python API

```python
from vacant import ArgvTemplate, GatePolicy, VacantFirstController

controller = VacantFirstController.from_endpoint(
    "http://localhost:1234",
    "your-model",
    api="openai",
    policy=GatePolicy(max_attempts=3, min_reviews=1),
)

result = controller.delegate_then_run(
    task="Write solve(s) that reverses a string.",
    tests={
        "type": "run_python",
        "code": "assert solve('abc') == 'cba'",
    },
    launch=ArgvTemplate((
        "my-agent",
        "--context",
        "{context_path}",
    )),
)

print(result.stdout)
print(result.receipt_path)
```

省略 `launch` 時只取得已驗證答案與 receipt，不啟動其他 agent。

## Gate 到底驗什麼

每次 `vacant run` 都產生新的 `request_id`。產品 receipt 以交付 resident 的 Ed25519
key 簽署，並完整綁定：

- `request_id` 與 risk；
- task 的 SHA-256；
- check-spec canonical SHA-256；
- answer SHA-256；
- 完整 trust card SHA-256；
- 完整 resident identity、stream ID 與 chain head；
- verify 結果、audit 結果、review 數與嘗試次數。

controller 會用目前 registry 中的公鑰驗 receipt 和 trust card，而不是信任 receipt
自己攜帶的公鑰。之後再次執行 objective check，最後才以原子 `launch.claim` 消耗本次
receipt 並啟動 agent。

產物預設位於：

```text
~/.vacant-mcp/
  receipts/<request_id>.json
  controller/
    events.jsonl
    runs/<request_id>/
      receipt.json
      trust_card.json
      context.json
      launch.claim
      agent_result.json
```

## MCP：相容模式，不是強制模式

Vacant 仍可作為 MCP server 掛進任何 client：

```json
{
  "mcpServers": {
    "vacant": {
      "command": "python",
      "args": ["-m", "vacant.mcp_server"],
      "env": {
        "VACANT_MCP_BASE": "http://localhost:1234",
        "VACANT_MCP_MODEL": "your-model",
        "VACANT_MCP_API": "openai"
      }
    }
  }
}
```

工具包含 `delegate`、`trust_card`、`receipt`、`residents`、`report`、`scoreboard` 與
`verify_fix`。MCP `delegate` 也使用產品 roster、最多三次 verify-fix，並回傳 signed
receipt ID；`receipt(request_id)` 會一起回傳該次 receipt 與其精確對應、不可變的
trust card，不受後續同題委派覆寫影響。

但 MCP 的 tool choice 最終仍由 agent 決定。若要求「每次都先經 Vacant」，請使用
`vacant run`；它由 controller 直接呼叫 Vacant，而不是請 agent 自願呼叫 MCP。

## 誠實邊界

- **可檢查任務才有客觀品質 gate。** 程式測試、格式、schema、精確約束最適合；主觀
  寫作或美感判斷沒有免費 oracle，Vacant 不宣稱能自動證明更好。
- **它改善可修復錯誤，不會創造模型沒有的能力。** 三次都未通過時 fail-closed，外部
  agent 不啟動。
- **receipt 證明本次交付與流程，不能讀心。** 下游 agent 收到答案後仍可能修改它；
  repository-level integration tests 仍應由 agent 或 CI 執行。
- **軟體 gate 只涵蓋透過 controller 啟動的行程。** 使用者若直接執行 `hermes`，當然能
  繞過 `vacant run`。要把 Vacant 做成機器唯一出口，需再用容器 entrypoint、ACL 或
  egress policy 強制。
- **key custody 是部署假設。** 同一 OS 使用者或 root 可讀 resident 私鑰時，軟體層無法
  prevents 偽造；production 應把信任庫放在獨立服務帳號、HSM 或 TEE。
- **同源／Sybil 防護是 raises-cost，不是 prevents。** 行為相關降權、probation 與 slash
  會提高洗白成本，但公開門檻仍可被針對。

## 產品與 Demo 隔離

`vacant run`、MCP server 與一般 `vacant up` 使用三個全良性 product residents。
研究用的 `Ecosystem()` 預設仍保留人工 `saboteur`，用來展示路由、slash 與信譽
收斂。需要 dashboard 展示該 roster 時必須顯式使用另一個 root：

```bash
vacant up --demo-roster --root ~/.vacant-demo
```

產品入口遇到含 demo residents 或舊版 `artifacts.jsonl`（曾明文保存 checks）的 root 會
fail-closed；請改用乾淨的 `--root`，不要把研究資料搬進產品信任庫。

常用維運命令：

```bash
vacant status
vacant scoreboard
vacant resident inspect resident_1
vacant verify resident_1
vacant ledger tail -n 20
```

## 開發與驗證

```bash
.venv/bin/python -m pytest tests/ -q
vacant selftest
```

重要模組：

| 模組 | 職責 |
|---|---|
| `controller.py` | 強制順序、receipt gate、shell-free agent launcher |
| `receipt.py` | 完整 task/check/answer/card 綁定與獨立驗章 |
| `ecosystem.py` | 信譽路由、verify-fix、互審、稽核、記憶與 trust card |
| `checks.py` | 可序列化 objective check 與 Python sandbox |
| `trustcard.py` | 交付者、review、audit、風險欄與簽章 |
| `registry.py` | 身分綁定、信譽、probation、同源降權 |
| `mcp_server.py` | 任意 MCP client 的相容工具面 |

研究 runner、預註冊與 X1/B-layer 基建仍保留在 `examples/`、`docs/` 與對應模組中，
但不再是使用 Vacant 的前提。研究紀律與目前完成度見 `CLAUDE.md`。
