# 通用 agent 相容性矩陣（`vacant run` V0 實測，2026-09-18）

> 一句話：五個 agent，**四個接通了**（Claude Code／Codex／OpenCode／pi），
> 一個**沒量**（Hermes，三台機器上都沒裝）。Codex 有一條**設定也救不了的路**：
> ChatGPT 登入時模型通道是寫死的 `wss://`，HTTP 反向代理在那條路上不存在。

量具與判準：[`ops/vacantrun/`](../ops/vacantrun/)（V0，見
[`docs/VACANT_RUN.md`](VACANT_RUN.md)）。
名單的單一真相：[`ops/vacantrun/envmap.py`](../ops/vacantrun/envmap.py)。

---

## 0. 怎麼量的（先講量具，因為結論只跟量具一樣可信）

**唯一算數的證據是 `requests_seen`**，不是「我設了環境變數」。這條是 V0
docstring 就寫死的（`envmap` 誠實邊界 1），這份文件只是把它跑出來。

兩層：

1. **假上游**（`mockup.py`，本次的臨時量具，未進 repo）——對
   `/v1/chat/completions`、`/v1/messages`、`/v1/responses` 三條 wire 都回一個
   最小合法回應（含 SSE）。用假上游是因為真模型會把「請求送出去了嗎」跟
   「模型答得好不好」綁在一起；假上游對任何請求都回成功，所以
   **「假上游 0 通」只有一種解釋：沒被中介到**。
2. **`vacant run`**（`ops/vacantrun/launcher.py`）——把 agent 包起來，
   `VACANT_RUN_UPSTREAM_OPENAI`／`_ANTHROPIC` 指到假上游，
   跑完看 `run_RUN-ON.json` 的 `requests_seen`、`wire_RUN-ON/index.jsonl`
   的 path、退出碼、以及收據。

任務固定：工作區一個 `README.md`（「寫出 `solution.py`，內含 `add(a,b)`」），
驗收套件一條 `check_add()`。**假上游只會回一句 `done`，不會動工作區**
⇒ 正常結果就是 `visible_fail`／exit 20。那正是要驗的東西：**閘門有牙齒**。
交付那一格（exit 0）另外用一個會回工具呼叫的假上游量過（見 §Codex）。

⚠ **這裡量到的是通道與閘門，不是模型能力。** 假上游站在模型的位置上，
所以本文件任何一格都**不能**讀成「這個 agent 用 Vacant 做得好」。

---

## 1. 矩陣

| agent | ① wire 協定 | ② 怎麼指過來 | ③ `requests_seen` | ④ 閘門 |
|---|---|---|---|---|
| **Claude Code** 2.1.276 | `POST /v1/messages?beta=true`（Anthropic Messages，SSE） | **環境變數** `ANTHROPIC_BASE_URL`（launcher 已內建） | **3**（anthropic 2 ＋ `HEAD /api/hello` 1） | ✅ `visible_fail`、**exit 20**、收據 2 筆驗過 |
| **Codex CLI** 0.153.2（API key／自訂 provider） | `POST /v1/responses`（Responses API，SSE） | **設定**：`model_providers.<新 id>.base_url`（`-c` 旗標或 `config.toml`）。**不吃 `OPENAI_BASE_URL`** | **1**（拒交格）／**2**（交付格） | ✅ 兩條路都走到：**exit 20** 與 **exit 0** |
| **Codex CLI** 0.153.2（`codex login`／ChatGPT 帳號） | `wss://chatgpt.com/backend-api/codex/responses`（**WebSocket**） | ❌ **沒有辦法**。`chatgpt_base_url` 只搬得動外掛／遙測／設定那幾條 | **0**（模型那一條完全沒經過 proxy） | ❌ 閘門仍會跑（行程結束就是交付點），但**逐字落盤在那條路上不成立** |
| **OpenCode** 1.18.31 | (a) `POST /v1/responses`（內建 `openai` provider）<br>(b) `POST /v1/chat/completions`（自訂 openai-compatible provider） | (a) **環境變數** `OPENAI_BASE_URL`（launcher 已內建，**零額外接線**）<br>(b) 設定 `OPENCODE_CONFIG_CONTENT` | **2**（兩條路各量一次都是 2） | ✅ 兩條路都 `visible_fail`、**exit 20** |
| **pi** 0.85.1 | `POST /v1/chat/completions`（OpenAI Chat Completions，SSE，`store:false`） | **設定**：`PI_CODING_AGENT_DIR` 指到一個暫時目錄＋寫 `models.json`。**不吃 `OPENAI_BASE_URL`**（實測反例見下） | **1** | ✅ `visible_fail`、**exit 20** |
| **Hermes** | **未測**（推論：OpenAI-compatible，`model.base_url`／`CUSTOM_BASE_URL`） | **未測** | **未測** | **未測** |

收據：上表每一格 `vacant run` 的 `receipts_RUN-ON.ndjson` 都是
`entries_n=2 / verified_n=2 / failed_n=0 / chain_ok=true`，
用的是既有那把尺 `ops/gain/replay/verify_run_receipts.py`（沒有另寫第二把）。

---

## 2. 可複製貼上的接線

共通前提：`$P` ＝ proxy 的 base url。在 `vacant run` 底下，launcher 會把它
注入成 **`$VACANT_RUN_PROXY`**，所以 wrapper 可以在 runtime 讀它現寫設定——
**不需要 `--port` 固定埠，也不需要動使用者自己的設定檔**。
（`--port` 仍然保留給「只能改使用者那一份設定」的情況。）

### 2.1 Claude Code —— 零接線

`ANTHROPIC_BASE_URL` 已經在 `envmap.REDIRECT_VARS` 裡，直接包起來就好：

```bash
python3 ops/vacantrun/launcher.py --suite tests_visible --run-dir ~/.vacant-run/cc -- \
    claude -p "把 solution.py 寫完" --dangerously-skip-permissions
```

⚠ **測的時候一定要隔離**，否則會干擾正在跑的 session：

```bash
export CLAUDE_CONFIG_DIR=/tmp/cc-isolated       # 獨立設定目錄
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SESSION_ID \
      CLAUDE_CODE_CHILD_SESSION CLAUDE_CODE_MESSAGING_SOCKET \
      CLAUDE_CODE_MESSAGING_TOKEN CLAUDE_PID
unset CLAUDE_CODE_USE_OPENAI                    # 有設的話它會改走 OpenAI wire
```

**注意這台機器的現況**：目前的 shell 有 `CLAUDE_CODE_USE_OPENAI=1` 與
`OPENAI_BASE_URL=http://100.119.113.56:8765/v1`，也就是 Claude Code 在這裡
**走的是 OpenAI wire 不是 Anthropic wire**。兩條 launcher 都認得
（`OPENAI_BASE_URL` 與 `ANTHROPIC_BASE_URL` 都在名單裡），但
**收據上的 `by_wire` 會長得不一樣**，引用時不要混。

### 2.2 Codex —— 一串 `-c` 旗標（不寫檔）

```bash
python3 ops/vacantrun/launcher.py --suite tests_visible --run-dir ~/.vacant-run/cx -- \
  env CODEX_HOME=/tmp/codex-isolated \
  codex exec --skip-git-repo-check \
    -c "model_providers.vacantproxy.name=\"vacant proxy\"" \
    -c "model_providers.vacantproxy.base_url=\"$VACANT_RUN_PROXY/v1\"" \
    -c "model_providers.vacantproxy.env_key=\"OPENAI_API_KEY\"" \
    -c "model_providers.vacantproxy.wire_api=\"responses\"" \
    -c 'model_provider="vacantproxy"' \
    -c 'model="gpt-5.6-sol"' \
    -c 'approval_policy="never"' \
    -c 'sandbox_mode="danger-full-access"' \
    "把 solution.py 寫完"
```

⚠ `$VACANT_RUN_PROXY` 只有在 launcher 的**子行程**裡才有值，所以上面這串要
包在一支 wrapper script 裡（或用 `--port` 給固定埠後把它寫死）。
本次實測用的就是一支八行 wrapper。

**三個踩過的坑（都是實測，不是文件）**：

- `-c model_providers.openai.base_url=...` **會被拒絕**：
  > `Error loading config.toml: model_providers contains reserved built-in provider IDs: `openai`. Built-in providers cannot be overridden. Rename your custom provider (for example, `openai-custom`).`

  ⇒ 必須取一個新的 provider id。（這是 fail-closed，不是安靜跑錯，好事。）
- `wire_api` 可選 `"responses"` 或 `"chat"`。用 `"responses"` 時 path 是
  `/v1/responses`，`wireproxy.route()` 把它歸到 `openai` 那條轉送，**不需要改碼**。
- Codex 的 model catalog 有 `prefer_websockets: true` 的 slug（例如 `gpt-5.6-sol`），
  但**自訂 provider ＋ `http://` base_url 之下它仍然走純 HTTP POST**（實測過，
  同一個 slug 兩種 provider 兩種行為）。

### 2.3 OpenCode —— 零接線（走內建 openai provider）

```bash
python3 ops/vacantrun/launcher.py --suite tests_visible --run-dir ~/.vacant-run/oc -- \
    opencode run --pure --log-level ERROR -m openai/gpt-4o-mini "把 solution.py 寫完"
```

要用自訂 provider（例如指到本地模型）時，整份設定可以用環境變數餵進去，
不必動 `~/.config/opencode/opencode.json`：

```bash
export OPENCODE_CONFIG_DIR=/tmp/oc-isolated
export OPENCODE_DISABLE_PROJECT_CONFIG=1
export OPENCODE_CONFIG_CONTENT='{"provider":{"vacantproxy":{"name":"vacant proxy",
  "npm":"@ai-sdk/openai-compatible",
  "options":{"baseURL":"'"$VACANT_RUN_PROXY"'/v1","apiKey":"'"$OPENAI_API_KEY"'"},
  "models":{"mock":{"name":"mock"}}}},
  "model":"vacantproxy/mock",
  "permission":{"edit":"allow","bash":"allow"}}'
opencode run --pure -m vacantproxy/mock "把 solution.py 寫完"
```

### 2.4 pi —— 換掉整個設定目錄

pi 的 `baseUrl` 在 `~/.pi/agent/models.json`，但 **`PI_CODING_AGENT_DIR`
可以把整個設定目錄搬走**，所以不必動使用者那一份，也不必固定埠：

```bash
export PI_CODING_AGENT_DIR=/tmp/pi-isolated
mkdir -p "$PI_CODING_AGENT_DIR"
cat > "$PI_CODING_AGENT_DIR/models.json" <<EOF
{"providers":{"vacantproxy":{
  "baseUrl":"$VACANT_RUN_PROXY/v1",
  "api":"openai-completions",
  "apiKey":"sk-whatever",
  "compat":{"supportsDeveloperRole":false,"supportsReasoningEffort":false},
  "models":[{"id":"gemma-4-12b-it-qat","name":"m","contextWindow":262144,"maxTokens":16384}]}}}
EOF
export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1
pi -p --provider vacantproxy --model m "把 solution.py 寫完" < /dev/null
```

⚠ **`pi -p` 不給 `< /dev/null` 會永久卡住**（V0 已實測；launcher 的
`--stdin devnull` 預設就是為了這個）。

---

## 3. 反面對照：「我設了環境變數」真的不是證據

這一節存在的理由：矩陣裡「不吃環境變數」那幾格，**如果只寫結論就等於憑文件**。
下面每一條都是同一個假上游、同一支量具跑出來的**否定證據**。

| 測 | 設了什麼 | 假上游收到 | 它實際上去了哪 |
|---|---|---|---|
| pi 0.85.1 ＋ 內建 `openai` provider | 只有 `OPENAI_BASE_URL` | **0 通** | `api.openai.com` — `OpenAI API error (401): Incorrect API key provided: sk-mock` |
| Codex 0.153.2 ＋ 無 auth.json | 只有 `OPENAI_BASE_URL` | **0 通** | `wss://api.openai.com/v1/responses` → 401 → 退回 `https://api.openai.com/v1/responses` → 401 |
| Codex 0.153.2 ＋ ChatGPT 登入 | `chatgpt_base_url` 指到假上游 | **16 通，但沒有一通是模型**（`/ps/plugins/*`、`/codex/analytics-events/events`、`/api/codex/settings/user`） | `wss://chatgpt.com/backend-api/codex/responses`（`RUST_LOG` trace：`transport="responses_websocket" wire_api=responses`） |

第三列特別要看：**它「看起來被中介了」——假上游收到 16 通**。
如果判準是「proxy 有沒有流量」而不是「模型通道有沒有流量」，這一格會被誤判成通過。
`requests_seen` 要配上 `wire_*/index.jsonl` 的 path 一起讀。

反過來也有一格打臉**靜態推論**：OpenCode 的 binary 裡 grep 不到
`OPENAI_BASE_URL`（grep 得到的只有 `OPENCODE_*`），照字串判會寫「不吃環境變數」——
**實測它吃**。原因是它的 provider 是 runtime 才載入的 `@ai-sdk/openai`，
讀變數的是那包 SDK。⇒ **掃 binary 不算量，wire log 才算。**

---

## 4. Codex 那一格（人類特別點名的）

### 4.1 原本的預期，跟量到的不一樣

預期是：Codex 走 Responses API ＋ `store:true` ＋ `previous_response_id`
⇒ 對話狀態在 OpenAI 伺服器上、proxy 只看得到 delta
⇒ 鐵律 3「逐字落盤」破功。

**量到的是**（自訂 provider ＋ API key，2026-09-18，codex-cli 0.153.2）：

```
POST /v1/responses   store=false   previous_response_id=<不存在>   stream=true
  第 1 通 input = 3 items（developer / user / user）
  第 2 通 input = 5 items（前 3 item ＋ function_call ＋ function_call_output）
```

也就是**每一通都把完整上文重放一次**。⇒ 在這條路上
**逐字落盤成立，鐵律 3 沒有破**。請求 body 逐位元落在
`wire_RUN-ON/<call_id>.req.bin`，`conversation_sha256` 算得出來。

### 4.2 真正破功的是另一條，而且更硬

**`codex login`（ChatGPT 帳號）那條路，模型通道是 WebSocket：**

```
2026-09-18T09:03:45Z INFO model_client.stream_responses_websocket{
    model=gpt-5.6-sol wire_api=responses transport="responses_websocket" ...}
… wss://chatgpt.com/backend-api/codex/responses
```

- `OPENAI_BASE_URL`：**無效**（該字串在 binary 裡只出現在 codex 自己的
  `network-proxy/src/mitm.rs`——那是 codex 注給**沙箱子行程**的，不是它自己讀的）。
- `chatgpt_base_url`：**只搬得動 HTTP 那幾條**（外掛清單、遙測、使用者設定），
  模型那一條不動。實測 16 通全部不是模型請求，而答案照樣回來了、
  `tokens used 14,595`——**它從別的地方拿到了模型**。
- ⇒ **`vacant run` 的 HTTP 反向代理在那條路上不存在。** 不是「還沒支援」。

**破功的是哪一條**：鐵律 3（全 I/O 逐字落盤）。
**為什麼**：沒有 HTTP wire 可以 tee；WebSocket 的 `Upgrade` 交握
`wireproxy._handle` 也不處理（它是 request/response 一來一回的模型）。
**有沒有繞法**：

1. ✅ **改用自訂 provider ＋ API key**（§2.2）——這是目前唯一**證明有效**的繞法。
   代價：不能用 ChatGPT 訂閱額度，要另外付 API 費用。
2. ⚠ **出網封鎖**（`block_egress.sh`，V3，要 root）——封鎖之後那條路會
   **連不上**而不是**偷偷連上**。它不能讓你看到 wire，但能讓
   「沒被中介到」變成一個**看得見的失敗**而不是一個沉默的洞。**沒量過。**
3. ❌ 在 proxy 加 WebSocket tee——技術上做得到，但那要 (a) 處理 `Upgrade`、
   (b) 解 WebSocket frame、(c) 而 `wss://chatgpt.com/...` 是寫死的網域，
   還是得靠 DNS／CA 層的透明攔截 ⇒ 撞到 V0 §4.10「不做透明 MITM」那條裁決。
   **不建議**，而且它不是一個 V0 級的改動。

### 4.3 一句話給誠實邊界

> Codex CLI 用 ChatGPT 登入時，模型通道是寫死的
> `wss://chatgpt.com/backend-api/codex/responses`。`vacant run` 在那條路上
> **什麼都看不到**，`requests_seen` 會是 0（或只有非模型流量），
> 而**閘門仍然會跑**——因為觸發點在行程結束不在 wire 上。
> 也就是說：**那一格的收據能證明「工作區最後長這樣、驗收過了沒」，
> 不能證明「模型通道上發生了什麼」。** 兩件事在收據裡不可以被讀成同一件。

---

## 5. Hermes：沒量到，寫沒量到

- Mac：`hermes` 不在 PATH，`~/hermes-agent` 不存在。
- vacant-dev（100.124.254.83）：同上。
- vacant-clean1（100.77.224.99）：同上。

repo 裡的兩支相關程式碼**還在**、也還說得通，但它們是**呼叫端**不是證據：

- [`vacant/hermes_substrate.py`](../vacant/hermes_substrate.py)：spawn
  `hermes -z`、綁 `HERMES_HOME`、寫 `config.yaml`
  （`model.provider: vllm` ＋ `model.base_url: <...>/v1`）、
  另外設 `CUSTOM_BASE_URL` 環境變數。
- [`vacant/brains.py::HermesBrain`](../vacant/brains.py)：同樣用 `CUSTOM_BASE_URL`。
- [`vacant/mcp_trace.py`](../vacant/mcp_trace.py)：**stdio tee-proxy**，
  原本就是為 Hermes 寫的——它 tee 的是 **MCP JSON-RPC**（Hermes ↔ vacant MCP
  server），**不是模型通道**。兩者不可互相替代：`mcp_trace` 證明的是
  「Hermes 有沒有呼叫 vacant、問了什麼」，`wireproxy` 證明的是
  「模型通道上跑了哪些 bytes」。

⇒ 依上面反推，Hermes 應該落在「設定檔框架，但有 `CUSTOM_BASE_URL` 環境變數」
這一類。`CUSTOM_BASE_URL` 已經加進 `envmap.REDIRECT_VARS`，**標記為未實測**：
名單多一個變數只是多設一個環境變數（無害），漏一個才會靜靜地沒被中介。
**要裝了 Hermes 才能把這一格填掉，在那之前它是「未測」不是「可用」。**

---

## 6. 順手量到的三件小事

1. **Claude Code 會先打一發 `HEAD /api/hello`**（連線預檢）。
   `wireproxy.route()` 把它歸到 `openai` 那條上游（因為 path 不是 `/v1/messages`），
   假上游沒有 `do_HEAD` 所以回 501——Claude Code **不在意**，照樣繼續。
   對真上游無所謂（`api.anthropic.com` 認得這條），但**對一個會終止連線的
   假上游／離線展場來說，這一格值得記一筆**。
2. **`requests_seen` 會把非模型流量也算進去**（上面那發 `HEAD` 就是）。
   要下「模型通道被中介到了」這個結論，得看 `wire_*/index.jsonl` 的 `path`，
   不能只看計數。§3 第三列是這條的極端版本：16 通全部不是模型。
3. **四個接上的 agent 全部是 `store:false` 或沒有 `store` 欄位**，
   而且每一通都重放完整上文。`previous_response_id` 一次都沒出現過。
   ⇒ 「Responses API ⇒ 狀態在伺服器上」不是 API 的性質，是**客戶端選擇**的性質。

---

## 7. 這份文件的邊界

- 量的是**通道與閘門**，不是模型能力，也不是「用 Vacant 做得比較好」。
  假上游站在模型的位置上。
- 交付（exit 0）那一格**只在 Codex 上實測過**（用一個會回 `exec_command`
  工具呼叫的假上游，讓它真的寫出 `solution.py`）。其餘三個只實測到**拒交**。
  閘門那一段與 agent 無關（同一支 `ops/gain/r530/acceptance.py`），
  但**沒測到就是沒測到**。
- 版本綁死在上面那幾個號碼。上游改版這份表就會漂，
  **漂了的徵兆是 `requests_seen == 0`，不是這份文件變紅。**
- `vacant run` 單獨只有 L3：proxy **records，不 verifies**，也不阻止 agent
  自己開一條連線（`docs/VACANT_RUN.md` §4.1，逐字適用）。

---

## 附錄 A：原始落盤（逐字，2026-09-18）

⚠ **這一節存在的理由**：下面每一格的 `run_RUN-ON.json`／`wire_RUN-ON/*.bin`／
`receipts_RUN-ON.ndjson` 都落在 **session 的 scratchpad**
（`/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/`
`ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/lab/<label>/run/`），
那是一個**會被清掉**的位置。重跑一次很貴（Codex 與 Claude Code 尤其），
所以關鍵欄位逐字抄在這裡。**抄過來的是摘要，不是原始 bytes**——
`*.req.bin`／`*.resp.bin` 沒有備份，需要的話要重跑。

臨時量具（同樣只活在 scratchpad，未進 repo）：`mockup.py`（假上游，三條 wire）、
`probe.sh`（包 `vacant run` 跑一格）、`direct.sh`（不經 `vacant run` 的直測）、
`agent_{claude,codex,opencode,pi}.sh`（四支接線 wrapper，內容已逐字寫進 §2）。

### `claude-gate-refuse`

```
argv            = bash /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/agent_claude.sh read README.md and do what it says
requests_seen   = 3   wire_by_protocol = {'openai': 1, 'anthropic': 2}   wire_errors = 0
proxy paths     = {'HEAD /api/hello -> 501': 1, 'POST /v1/messages?beta=true -> 200': 2}
stop_reason     = visible_fail   accepted = False   refused = True
agent_rc        = 0   agent_wall_s = 0.667
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
wire_digest     = 21b60e2d0bf0b18f25748774b9b1f5912bd69ce5538cda106027285c32843092
verdict_hash    = 4ef142cc0ef7c5f2f472998e34c49e25709f7627de957950eed45dd5076608e4
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### `codex-gate-accept`

```
argv            = bash /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/agent_codex.sh read README.md and do what it says
requests_seen   = 2   wire_by_protocol = {'openai': 2}   wire_errors = 0
proxy paths     = {'POST /v1/responses -> 200': 2}
stop_reason     = visible_pass   accepted = True   refused = False
agent_rc        = 0   agent_wall_s = 1.167
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = e9cd0206d7eac65515768bf6d3fd50566311056dba236753253b3bea96562961
wire_digest     = 504149d554b0b0867ab34a96dfd49d2bca6c8aa5f50af30315cec5c848bcff4e
verdict_hash    = b825f35c1f2828a99d0f06c100203244a8a4777f04ccc4ed718f66b2d852bce2
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### `codex-gate-refuse`

```
argv            = bash /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/agent_codex.sh read README.md and do what it says
requests_seen   = 1   wire_by_protocol = {'openai': 1}   wire_errors = 0
proxy paths     = {'POST /v1/responses -> 200': 1}
stop_reason     = visible_fail   accepted = False   refused = True
agent_rc        = 0   agent_wall_s = 1.27
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
wire_digest     = 0fed669d455b0e5fb7887360a563956824b9a58f89bcfa360bcd10037494a52b
verdict_hash    = 2753cb024b9d271db90bf8e287d5e9468ff50cc3018dd379fd7be4c6c862bcef
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### `harness-selfcheck`

```
argv            = python3 /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/fakeagent.py
requests_seen   = 1   wire_by_protocol = {'openai': 1}   wire_errors = 0
proxy paths     = {'POST /v1/chat/completions -> 200': 1}
stop_reason     = visible_pass   accepted = True   refused = False
agent_rc        = 0   agent_wall_s = 0.227
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = 1c5051b70e9c8d3ab52012550c6ab26288d182e1011bff8bdc0013bb42251294
wire_digest     = a686dcfe2e8af2814e87c7a43b582f0d550dd6019f263a36b9d0a7ff40c54963
verdict_hash    = 3dbb1bc88dab6bab9b7b5eacb81577227b5eee2e1f5e9e28e5d34486590f4ef8
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### `opencode-env-gate`

```
argv            = bash /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/agent_opencode_env.sh read README.md and do what it says
requests_seen   = 2   wire_by_protocol = {'openai': 2}   wire_errors = 0
proxy paths     = {'POST /v1/responses -> 200': 2}
stop_reason     = visible_fail   accepted = False   refused = True
agent_rc        = 0   agent_wall_s = 6.792
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
wire_digest     = 0fc1e7568b2de9767d632e9ecdfea3f65ed65932cbd20fa832ba4e2629af0cea
verdict_hash    = 2a37f52d69a47a20a5be4ba89a713f596f8c45e1782700d9d97a8604af6afa60
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### `opencode-gate-refuse`

```
argv            = bash /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/agent_opencode.sh read README.md and do what it says
requests_seen   = 2   wire_by_protocol = {'openai': 2}   wire_errors = 0
proxy paths     = {'POST /v1/chat/completions -> 200': 2}
stop_reason     = visible_fail   accepted = False   refused = True
agent_rc        = 0   agent_wall_s = 5.065
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
wire_digest     = dbb48c170adf7f31a2c468e548be09cb54d2048150393af247dd20c557e9aec2
verdict_hash    = d3fe10adb965f48421de3aa60f00dceadd042aaf10bd838b34b92216c4156f4a
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### `pi-gate-refuse`

```
argv            = bash /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/agent_pi.sh read README.md and do what it says
requests_seen   = 1   wire_by_protocol = {'openai': 1}   wire_errors = 0
proxy paths     = {'POST /v1/chat/completions -> 200': 1}
stop_reason     = visible_fail   accepted = False   refused = True
agent_rc        = 0   agent_wall_s = 0.801
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
wire_digest     = ab10b00f19c531e3a94e0d9bcaad15eb3e98fac41286e3f215e188ffa58116f8
verdict_hash    = 7946881fc1a4e62ede51078566318ab14b4b098850546a98fcb296a78edf2f8d
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

