# 通用 agent 相容性矩陣（`vacant run` V0 實測，2026-09-18；**OpenCode 真模型 2026-09-19**；**Claude Code 真模型 2026-09-19**）

> 一句話：五個 agent，**四個接通了**（Claude Code／Codex／OpenCode／pi），
> 一個**沒量**（Hermes，三台機器上都沒裝）。Codex 有一條**設定也救不了的路**：
> ChatGPT 登入時模型通道是寫死的 `wss://`，HTTP 反向代理在那條路上不存在。

## 證據等級（**不可混講**，`.claude/commands/goal.md` 的同一張表）

| 級 | 意思 | 誰 |
|---|---|---|
| **L-real** | **真模型**真跑，拒交格與交付格都過，收據可重驗 | **pi**（R535）、**OpenCode**（2026-09-19，見 §8）、**Claude Code**（2026-09-19，見 §9） |
| **L-fake** | 假上游（`mockup.py`）只驗通道與閘門 | Codex（API key 那條） |
| **L-none** | 沒量 | Hermes |

⚠ **L-fake 不能寫成「這個 agent 可以用 Vacant」。** 假上游碰不到 SSE 分塊、
工具呼叫格式、逾時、上下文長度。§1 的矩陣量的是**通道與閘門**；
只有 §8（OpenCode）與 §9（Claude Code）那兩節是真模型。

量具與判準：[`vacant/vrun/`](../vacant/vrun/)（V0，見
[`docs/VACANT_RUN.md`](VACANT_RUN.md)）。
名單的單一真相：[`vacant/vrun/envmap.py`](../vacant/vrun/envmap.py)。

> ⚠ **本文的實測是在搬家之前跑的**（判斷層當時住在 `ops/vacantrun/`）。
> 判準一個字沒動、`ops.vacantrun.launcher` 是同一個 module 物件，所以下面的
> `requests_seen` 與退出碼照樣成立；但 `envmap` **沒有**留 re-export，
> 名單只住在 `vacant/vrun/envmap.py` 一個地方。

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
驗收套件一條 `check_add()`。每個 agent 量**兩格**：

- **拒交格**：假上游只回一句 `done`，不會動工作區 ⇒ `visible_fail`／**exit 20**。
  驗的是**閘門有牙齒**。
- **交付格**：假上游回一個寫檔的工具呼叫 ⇒ `visible_pass`／**exit 0**。
  驗的是**閘門不是永遠說不**（一個永遠拒交的閘門跟沒有閘門一樣沒用）。

兩格一起才算數。只有拒交格＝量不出「量具會不會永遠回同一個答案」。

⚠ **這裡量到的是通道與閘門，不是模型能力。** 假上游站在模型的位置上，
所以本文件任何一格都**不能**讀成「這個 agent 用 Vacant 做得好」。

---

## 1. 矩陣

| agent | ① wire 協定 | ② 怎麼指過來 | ③ `requests_seen` | ④ 閘門（拒交／交付） |
|---|---|---|---|---|
| **Claude Code** 2.1.276（假上游）／**2.1.278**（真模型） | `POST /v1/messages?beta=true`（Anthropic Messages，SSE） | **環境變數** `ANTHROPIC_BASE_URL`（launcher 已內建，**零接線**——**接本地模型也成立**，見 §9 與下面那一行 ⚠） | 假上游 **3**（拒交格）／**4**（交付格）<br>**真模型：5 ／ 4**（§9） | ✅ **exit 20** `visible_fail` ／ ✅ **exit 0** `visible_pass`<br>**真模型：✅ exit 20 ／ ✅ exit 0（L-real，§9）** |
| **Codex CLI** 0.153.2（API key／自訂 provider） | `POST /v1/responses`（Responses API，SSE） | **設定**：`model_providers.<新 id>.base_url`（`-c` 旗標或 `config.toml`）。**不吃 `OPENAI_BASE_URL`** | **1**（拒交格）／**2**（交付格） | ✅ **exit 20** ／ ✅ **exit 0** |
| **Codex CLI** 0.153.2（`codex login`／ChatGPT 帳號） | `wss://chatgpt.com/backend-api/codex/responses`（**WebSocket**） | ❌ **沒有辦法**。`chatgpt_base_url` 只搬得動外掛／遙測／設定那幾條 | **0**（模型那一條完全沒經過 proxy） | ⚠ 閘門**照跑**（觸發點在行程結束不在 wire 上），但**逐字落盤在那條路上不成立** |
| **OpenCode** 1.18.31 | (a) `POST /v1/responses`（內建 `openai` provider）<br>(b) `POST /v1/chat/completions`（自訂 openai-compatible provider） | (a) **環境變數** `OPENAI_BASE_URL`（launcher 已內建，**零接線**——但**只在模型 id 是 models.dev 註冊表裡的那些**時成立，見 §2.3 ⚠）<br>(b) 設定 `OPENCODE_CONFIG_CONTENT`／`wrap_agent.sh opencode`。**真模型走這條** | (a) **2**（假上游）／ (b) **2**（拒交格）、**3**（交付格）<br>**真模型：5 ／ 5**（§8） | ✅ 兩條路都 **exit 20**；(b) 另有 ✅ **exit 0**<br>**真模型 (b)：✅ exit 20 ／ ✅ exit 0（L-real，§8）** |
| **pi** 0.85.1 | `POST /v1/chat/completions`（OpenAI Chat Completions，SSE，`store:false`） | **設定**：`PI_CODING_AGENT_DIR` 指到一個暫時目錄＋寫 `models.json`。**不吃 `OPENAI_BASE_URL`**（實測反例見 §3） | **1**（拒交格）／**2**（交付格） | ✅ **exit 20** ／ ✅ **exit 0** |
| **Hermes** | **未測**（推論：OpenAI-compatible，`model.base_url`／`CUSTOM_BASE_URL`） | **未測** | **未測** | **未測** |

⚠ **Claude Code 那一格的「零接線」有一個不在 `vacant run` 裡的前提**：
**上游必須自己會講 Anthropic Messages（`POST /v1/messages`）**。
`vacant/vrun/wireproxy.py` 是**反向代理不是協定轉換器**——它照 path 路由，
不把 `/v1/messages` 改寫成 `/v1/chat/completions`。1003 的 LM Studio
**原生就吃 `/v1/messages`**（含 SSE 與 `tool_use`），所以這一格不需要 shim；
換一個只講 OpenAI 的上游（純 llama.cpp server、vLLM 預設）就**必須**自備轉換
（LiteLLM／claude-code-router 之類），而那一層**不是**本 repo 的東西。
逐字驗證見 §9.0。

收據：本次所有 `vacant run`（**14 個 run 目錄**，見附錄 A）的 `receipts_RUN-ON.ndjson`
都是 `entries_n=2 / verified_n=2 / failed_n=0 / chain_ok=true`，
用的是既有那把尺 `ops/gain/replay/verify_run_receipts.py`（沒有另寫第二把）。

**「交付」那一格是怎麼量的**（不要讀成模型會寫程式）：假上游在**帶著工具清單
的那一通**回一個 `bash`／`Bash`／`exec_command` 工具呼叫，內容是
`printf 'def add(a, b):\n    return a + b\n' > solution.py`。四個框架的 shell 工具
都吃 `{"command": str}`（Codex 是 `{"cmd": str}`），所以同一招四個都適用。
⇒ 它證明的是**工具呼叫真的穿過 proxy 回到 agent、agent 真的改了工作區、
驗收真的在凍結快照上跑出 `visible_pass`**，**不是**模型能力。

踩到的一個坑值得記：**不能用「第一通」當判準**。OpenCode 的第一通是
**title generator**（沒有 `tools` 欄位），工具呼叫給了它等於掉進一個不會執行的
子代理裡，整格看起來像「接上了但沒動工」——那正是會被誤讀成「閘門壞了」的假象。
判準要是「這一通帶不帶 `tools`」。

---

## 2. 可複製貼上的接線

### 2.0 最短的那一條：`ops/vacantrun/wrap_agent.sh`

下面 §2.1–§2.4 那四段接線已經寫成一支
[`ops/vacantrun/wrap_agent.sh`](../ops/vacantrun/wrap_agent.sh)，
四個 agent 各一段，**每段都在 runtime 讀 `$VACANT_RUN_PROXY`**：

```bash
python3 ops/vacantrun/launcher.py --suite ../tests_visible --run-dir ~/.vacant-run/x -- \
    "$PWD/ops/vacantrun/wrap_agent.sh" pi "把 solution.py 寫完"
#                                      ^^^^ pi | codex | opencode | claude
```

⚠ **`--suite` 要指到工作區外**（上面寫 `../tests_visible` 的原因）。這條擋門是
V2 才加的，比本文的實測晚：`--suite` 落在工作區底下 ⇒ `SystemExit`，因為
**agent 改得到的驗收不是驗收**。本文 §3 的原始 argv 紀錄保留當時逐字的樣子，
沒有回頭改寫——那是跑過的東西，不是能照抄的指令。

⚠ **`--` 之後要給絕對路徑**：launcher 用 `cwd=<workspace>` spawn，相對路徑會
解析到工作區底下 ⇒ `agent_spawn_failed`／exit 22（實測過；那是 `infra_void`，
launcher **不判交付也不判拒交**，行為正確但訊息容易看漏）。

四段全部實測過（2026-09-18，假上游回寫檔工具呼叫）：

| | `requests_seen` | proxy 收到的 path | 裁決 |
|---|---|---|---|
| `wrap_agent.sh pi` | 2 | `POST /v1/chat/completions` ×2 | `visible_pass`、**exit 0** |
| `wrap_agent.sh codex` | 2 | `POST /v1/responses` ×2 | `visible_pass`、**exit 0** |
| `wrap_agent.sh opencode` | 3 | `POST /v1/chat/completions` ×3 | `visible_pass`、**exit 0** |
| `wrap_agent.sh claude` | 4 | `POST /v1/messages?beta=true` ×3 ＋ `HEAD /api/hello` | `visible_pass`、**exit 0** |

模型用 `VACANT_AGENT_MODEL` 換；Codex 的 wire 用 `VACANT_CODEX_WIRE`
（`responses`｜`chat`）換。下面幾節是同樣的東西攤開來，要自己改的時候看。

### 2.0.1 底層機制

共通前提：`$P` ＝ proxy 的 base url。在 `vacant run` 底下，launcher 會把它
注入成 **`$VACANT_RUN_PROXY`**，所以 wrapper 可以在 runtime 讀它現寫設定——
**不需要 `--port` 固定埠，也不需要動使用者自己的設定檔**。
（`--port` 仍然保留給「只能改使用者那一份設定」的情況。）

### 2.1 Claude Code —— 零接線

`ANTHROPIC_BASE_URL` 已經在 `envmap.REDIRECT_VARS` 裡，直接包起來就好：

```bash
python3 ops/vacantrun/launcher.py --suite ../tests_visible --run-dir ~/.vacant-run/cc -- \
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
python3 ops/vacantrun/launcher.py --suite ../tests_visible --run-dir ~/.vacant-run/cx -- \
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
python3 ops/vacantrun/launcher.py --suite ../tests_visible --run-dir ~/.vacant-run/oc -- \
    opencode run --pure --log-level ERROR -m openai/gpt-4o-mini "把 solution.py 寫完"
```

⚠ **「零接線」有一條 2026-09-19 才量到的邊界：模型 id 必須是 models.dev
註冊表裡認得的那些。** 內建 `openai` provider 拿到註冊表以外的 id（例如本地
LM Studio 的 `gemma-4-12b-it-qat`）會在**送出任何請求之前**就死在模型解析：

```
$ opencode run -m openai/gemma-4-12b-it-qat "say hi"
Error: {"name":"UnknownError","data":{"message":"Unexpected server error. …"}}
⇒ requests_seen = 0      （proxy 一通都沒看到——那是 infra_void 不是 0 分）
```

同一支指令換成 `-m openai/gpt-4o-mini` ⇒ `requests_seen = 9`、
`POST /v1/responses`。**所以「零接線」擋不掉的是：本地模型的 id 進不去。**
要指到本地模型就得走下面的設定路線（§8 的真模型兩格走的就是這條）。

> 順帶量到：LM Studio **不檢查** `model` 欄位——拿 `gpt-4o-mini` 去問，
> 回來的 body 裡 `"model": "gemma-4-12b-it-qat"`。所以零接線那條路
> *理論上*可以靠謊報模型名接到本地模型。**那條沒有量到兩格，不准當成可用**
> ——而且「為了接線而謊報模型名」會讓收據裡的 `model` 欄位失真，
> 跟本系統的可究責性口徑相衝。

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

- §1–§6 量的是**通道與閘門**，不是模型能力，也不是「用 Vacant 做得比較好」。
  假上游站在模型的位置上。
- ~~**沒有一格用真模型跑過。**~~ **2026-09-19 更正**：OpenCode 那一格已經用真模型
  （1003 的 `gemma-4-12b-it-qat`）跑出拒交／交付兩格，見 **§8**。
  **其餘三格仍然是假上游**（Claude Code、Codex、以及 OpenCode 的零接線那條路）。
  即使是 §8，量到的也只是**這一題**上的通道與閘門；
  「這個 agent 配 Vacant 在真任務上表現如何」是另一個實驗，這裡一個字都沒說。
- OpenCode 的**環境變數路線**（內建 `openai` provider，`/v1/responses`）
  只量到拒交格；交付格量的是**設定路線**（`/v1/chat/completions`）。
  原因是 Responses 那條的假上游工具呼叫寫的是 Codex 的 `exec_command` 工具名，
  OpenCode 沒有那個工具。**沒測到就是沒測到**，不要因為同一個 agent 另一條路
  過了就把這一格填綠。
- 版本綁死在上面那幾個號碼。上游改版這份表就會漂，
  **漂了的徵兆是 `requests_seen == 0`，不是這份文件變紅。**
- `vacant run` 單獨只有 L3：proxy **records，不 verifies**，也不阻止 agent
  自己開一條連線（`docs/VACANT_RUN.md` §4.1，逐字適用）。

---

## 8. OpenCode × 真模型（L-real，2026-09-19）

**這一節跟 §1–§6 的差別只有一個，但那一個就是全部：上游是真模型，不是 `mockup.py`。**

- 機器：vacant-dev（`100.124.254.83`）· OpenCode **1.18.31**
  （`npm i -g opencode-ai@1.18.31`，node v22.23.2）
- 上游：`http://100.119.113.56:1234/v1`（1003，載著 `gemma-4-12b-it-qat`）
- 接線：**設定路線**（`wrap_agent.sh opencode` ⇒ `OPENCODE_CONFIG_CONTENT`），
  不是零接線——理由見 §2.3 ⚠
- 題目：**現成的** `ops/gain/r535/bank/s1_01_addmul`（沒有為了這次新造題）
- 判斷層：`vacant/vrun/launcher.py`，`--suite` 指到**工作區外**的 bank 路徑

### 8.1 兩格怎麼分開的——**難度來自題庫本身，不是我們改了題**

R535 的題庫本來就備了兩份敘述，其餘位元組逐字相同（`meta.json` 的
`workspace_template` vs `workspace_template_pc`）：

| 格 | 工作區放的 TASK.md | 為什麼會是這個結果 |
|---|---|---|
| **拒交格** | `TASK.md`（散文只說 "sum"／"multiplying"） | `meta.json` 的 `trap`：**套件要的是 `add`／`mul`**。這一題的設計預期就是 `expected_first_attempt_visible_fail >= 0.8` |
| **交付格** | `TASK_explicit.md`（多五行 `## Interface`，把 `add(a,b)`／`mul(a,b)` 寫死） | 同一題的**天花板臂**（R535 的 PC 臂） |

⚠ **兩格都是 OpenCode 自己跑出來的**——工作區進去時只有一個 `TASK.md`，
**沒有預放 `solution.py`**。落地的檔案逐字如下：

```python
# 拒交格 —— OpenCode 寫的（掉進命名陷阱）
def add(a, b):
    return a + b

def multiply(a, b):        # ← 套件要的是 mul
    return a * b
```
```python
# 交付格 —— OpenCode 寫的
def add(a, b):
    return a + b

def mul(a, b):
    return a * b
```

**沒有動過 TASK 的難度**：兩份敘述都是 repo 裡本來就有的檔案，
一個位元組都沒改（`cp bank/s1_01_addmul/TASK.md` 與
`cp bank/s1_01_addmul/TASK_explicit.md`）。

### 8.2 逐字落盤

```
指令（兩格只差工作區裡那一份 TASK.md）
  export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
  export VACANT_RUN_UPSTREAM_OPENAI=http://100.119.113.56:1234/v1
  export VACANT_AGENT_MODEL=gemma-4-12b-it-qat
  python3 -m vacant.vrun.launcher \
      --workspace <ws> --run-dir <rd> \
      --suite <repo>/ops/gain/r535/bank/s1_01_addmul/tests_visible \
      --task-id opencode_real_<cell> --sandbox none --test-timeout 30 \
      --timeout 1200 --json \
      -- <repo>/ops/vacantrun/wrap_agent.sh opencode \
         "Read TASK.md and do what it says. Use your tools to write the file."
```

### `opencode-real-refuse`（拒交格）

```
task_id         = opencode_real_refuse
accepted        = false   refused = true   stop_reason = visible_fail
退出碼           = 20
requests_seen   = 5   wire_by_protocol = {'openai': 5}   wire_errors = 0
proxy paths     = {'POST /v1/chat/completions -> 200': 5}
upstream        = http://100.119.113.56:1234/v1/chat/completions
visible         = 1 / 2   （check_01_add 過；check_02_mul 掛在
                  ImportError: cannot import name 'mul' from 'solution'）
agent_rc        = 0       ← OpenCode 自己說成功了，閘門說沒有
agent_wall_s    = 20.908  run_wall_s = 21.31   retry = none   attempts_used = 1
ws_start_sha256 = 03aeefafe6f8bb75eee9006f14eb3f0eb436a03214ffac42bd28565e02228a61
ws_end_sha256   = 39c19a7a2c38d254ad5fdd2ce61d95ccec16260e05e8efb90310a957711474a3
wire_digest     = ab819bcb08e2c99ce3e2c31358017f37ef076f22bf538d4807d16a7fe80534c3
verdict_sha256  = e9cc2ddb0abde551f5dcd20ae766b1fdbb434af58d32d4a1ab72d359cf150da5
verdict_hash    = 11889f630ac27ec454a267ec3316f3b11db319ffc73932d9680f3535db9a9788
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

**這一格最值得看的是 `agent_rc = 0`。** OpenCode 的收尾原話是
「I have created `solution.py` with the requested `add` and `multiply` functions
as specified in `TASK.md`.」——**它宣告完成、退出碼 0、而且講得很有把握**。
閘門在行程結束那一刻跑驗收，拒交。這正是
`docs/VACANT_RUN.md` §1 那個洞察的真模型版本。

### `opencode-real-deliver`（交付格）

```
task_id         = opencode_real_deliver
accepted        = true    refused = false   stop_reason = visible_pass
退出碼           = 0
requests_seen   = 5   wire_by_protocol = {'openai': 5}   wire_errors = 1
proxy paths     = {'POST /v1/chat/completions -> 200': 4,
                   'POST /v1/chat/completions -> 0（BrokenPipe）': 1}
upstream        = http://100.119.113.56:1234/v1/chat/completions
visible         = 2 / 2
agent_rc        = 0   agent_wall_s = 13.714  run_wall_s = 15.997
retry = none   attempts_used = 1
ws_start_sha256 = 1407f6cb722df0ec646475116f735bc3c42a7cf8ff3937ca90219a8d9d9c4feb
ws_end_sha256   = d1ed637b7ae45b8f71ddc69e113d9f52a0a998cf8df3dd008bc0bc04c9488f18
wire_digest     = cacc96253df04ef407045e8adb0a23479ebc0d2ecd2c82f6b557855bfd0a6b6e
verdict_sha256  = 62d253ad5ac06216bb3d564e909f6a2af7873d4e92873fc3c6edd94a50555077
verdict_hash    = 8ed10a3f3898e68306bc5c827ce365368782ed33e367d5ce5b5a268e80f719ff
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

**那一通 `BrokenPipeError`**（`elapsed_s = 13.5`、`request_bytes = 2521`）
**是 title generator，不是模型主通道**——拆 `*.req.bin` 逐通看就知道：

```
status=200  tools=10  n_msgs=2  model=gemma-4-12b-it-qat   "You are opencode, an interactive CLI tool…"
status=200  tools=10  n_msgs=4  model=gemma-4-12b-it-qat
status=200  tools=10  n_msgs=6  model=gemma-4-12b-it-qat
status=200  tools=10  n_msgs=8  model=gemma-4-12b-it-qat
status=0    tools=0   n_msgs=3  model=gemma-4-12b-it-qat   "You are a title generator. You output ONLY a thread title."
```

主對話先結束，OpenCode 就把還在跑的 title generator 連線收掉了。
**沒有影響裁決**（驗收跑的是凍結快照不是 wire），但它證明
`wire_errors > 0` **不等於接線壞了**，讀的時候要配 `index.jsonl` 的 `error`
欄位與 `*.req.bin` 一起看。

⚠ 同一份拆解也**重新踩到 §1 那個坑的反面**：這一跑的 title generator 是
**最後一通**不是第一通。判準仍然是「這一通帶不帶 `tools`」，不是通次。

順帶：上面 `n_msgs` 一路 2→4→6→8，**每一通都把完整上文重放一次**
（`tools=10` 固定、沒有 `previous_response_id`）。
⇒ 在 OpenCode 的 chat/completions 這條路上，**鐵律 3「逐字落盤」成立**。

### 8.3 收據驗證（先負控制再驗該跑）

```
$ python3 -m vacant.vrun.verify_receipts --selftest
selftest: PASS                                          ← 負控制：它抓得到壞鏈

$ python3 -m vacant.vrun.verify_receipts --glob <refuse-run-dir>
run 1　鏈 1　entries 2　驗過 2　失敗 0　壞鏈 0
run   RUN-ON   2   2   0   1   1   11889f630ac27ec4…  OK      總判：OK

$ python3 -m vacant.vrun.verify_receipts --glob <deliver-run-dir>
run 1　鏈 1　entries 2　驗過 2　失敗 0　壞鏈 0
run   RUN-ON   2   2   0   1   1   8ed10a3f3898e683…  OK      總判：OK
```

### 8.4 這一節**沒有**說的事

1. **不是**「OpenCode 配 Vacant 寫程式比較好」。兩格各跑 **1 次**，n=1，
   沒有對照組、沒有重複。它是**存在性證明**（通道與閘門在真模型上成立），
   不是效果量。
2. **不是**「零接線可用」。真模型這兩格走的是**設定路線**；
   零接線那條在本地模型 id 上會死在模型解析（§2.3 ⚠）。
3. **不是**「這一題有代表性」。`s1_01_addmul` 是 S1 層最簡單的一題，
   而且交付格用的是**天花板臂**的敘述。換題、換層、換模型都會漂。
4. 沿用 §7 的所有邊界：proxy **records，不 verifies**；
   `vacant run` 單獨只有 L3。

### 8.5 踩到的坑（會咬下一個人）

- **`--json` 的 stdout 會被 agent 自己的 stdout 汙染。** launcher 讓 agent 繼承
  stdout，所以 OpenCode 的收尾那句話會印在 summary JSON **前面**，
  直接 `json.load(stdout)` 會 `JSONDecodeError`。
  **要讀就讀 `<run-dir>/run_RUN-ON.json`**，那一份是乾淨的。
- **node 不在預設 PATH 上**（`/home/user1/.local/opt/node-v22.23.2-linux-x64/bin`）。
  不 export 的話 `opencode` 的 shebang 找不到 node——`pi` 當初也是栽在這個。
- **`--` 之後要絕對路徑**（launcher 用 `cwd=<workspace>` spawn）；
  `wrap_agent.sh` 也一樣。

---

## 9. Claude Code × 真模型（L-real，2026-09-19）

**跟 §8 同一個形狀：上游是真模型不是 `mockup.py`。差別在 wire 協定——
Claude Code 走的是 Anthropic Messages，不是 OpenAI Chat Completions。**

- 機器：vacant-dev（`100.124.254.83`）· Claude Code **2.1.278**
  （`npm i -g @anthropic-ai/claude-code`，node v22.23.2；
  ⚠ `claude` 不在 SSH 非互動 shell 的預設 PATH 上——`~/.local/bin` 與 node 的
  `bin` 都要自己 export，`.claude/commands/goal.md` 那句「vacant-dev 上只裝了 pi」
  是 PATH 的假象，機器上本來就有 `~/.local/share/claude/versions/2.1.233…2.1.259`）
- 上游：`http://100.119.113.56:1234`（1003，載著 `gemma-4-12b-it-qat`）
- 接線：**零接線**。`ANTHROPIC_BASE_URL` 在 `envmap.REDIRECT_VARS` 裡，
  launcher 自己就設好了；`wrap_agent.sh claude` 那一段**只做行程隔離**
  （清掉父 session 的 `CLAUDE_CODE_*`、換 `CLAUDE_CONFIG_DIR`），
  **沒有一行是在指 base url**。這是本矩陣裡**唯一一個真模型走零接線的 agent**
  ——pi／OpenCode 的真模型都走設定路線。
- 題目：**現成的** `ops/gain/r535/bank/s1_01_addmul`（沒有為了這次新造題）
- 判斷層：`vacant/vrun/launcher.py` @ `8eec09a`，`--suite` 指到**工作區外**的 bank 路徑

### 9.0 先解決那個**以為會是障礙的障礙**：協定轉換

Claude Code 講 `POST /v1/messages`（Anthropic Messages），1003 是 **OpenAI 相容**
端點——照理中間要有一層協定轉換。**實測結果是不用**：1003 的 LM Studio
**原生就開了 `/v1/messages`**，而且含 SSE 與 `tool_use`。逐字（不經 `vacant run` 的直測）：

```
$ curl -s -X POST http://100.119.113.56:1234/v1/messages \
    -H 'content-type: application/json' -H 'anthropic-version: 2023-06-01' \
    -d '{"model":"gemma-4-12b-it-qat","max_tokens":256,"stream":true,
         "tools":[{"name":"Bash","description":"Run a shell command",
                   "input_schema":{"type":"object",
                     "properties":{"command":{"type":"string"}},
                     "required":["command"]}}],
         "messages":[{"role":"user","content":"Use the Bash tool to run: echo hi"}]}'
event: message_start
data: {"type":"message_start","message":{"id":"msg_…","model":"gemma-4-12b-it-qat",…}}
event: content_block_start
data: {"type":"content_block_start","index":0,
       "content_block":{"type":"tool_use","id":"ywHGGjar…","name":"Bash","input":{}}}
event: content_block_delta
data: {"type":"content_block_delta","index":0,
       "delta":{"type":"input_json_delta","partial_json":"{\"command\":\"echo hi\\n\"}"}}
event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"tool_use",…}}
event: message_stop
```

⇒ **這一節的可搬運性只到「上游會講 Anthropic Messages」為止。**
`wireproxy.py` 的 `route()` 只做 path 路由（`/v1/messages`、`/v1/complete` → anthropic；
其餘 → openai），**它不改寫 body、不做協定翻譯**。上游不會講 Messages 的話，
要嘛自備一層 shim，要嘛這條路就是不通——那一層不在本 repo 裡，也不該偷偷算進矩陣。

### 9.1 模型 id：**Claude Code 只警告，不像 OpenCode 那樣擋**

§2.3 記過 OpenCode 的坑：內建 `openai` provider 把 `gemma-4-12b-it-qat`
解析不出來，**在送出任何請求之前**就死 ⇒ `requests_seen = 0`。
Claude Code 在**同一個位置做了相反的事**——它印一行警告然後照送：

```
"gemma-4-12b-it-qat" isn't described by this version's model catalog; update Claude Code,
or map it with behavesAs on a modelPicker row (or modelOverrides, if it is a provider id of
a model this version knows). Until then auto-compact keeps this session within 200k tokens
(the context window it assumes); if the model accepts more, append [1m] to the model name
for 1M, or set CLAUDE_CODE_MAX_CONTEXT_TOKENS to its real window;
CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1 restores the previous
wait-for-the-API behavior.
[claude-code:unrecognized_model] {"model":"gemma-4-12b-it-qat","query_source":"sdk"}
```

⇒ **「這個框架吃環境變數」跟模型 id 綁在一起**（`envmap` 誠實邊界 1 的那一條）
**在兩個方向上都被量到了**：OpenCode ＝擋、Claude Code ＝放行。
不准從其中一格推另一格。

⚠ 那行警告有一個會咬人的後果：**Claude Code 假設上下文 200k**，
本題只有四通、七萬 bytes，碰不到；**長任務要自己設 `CLAUDE_CODE_MAX_CONTEXT_TOKENS`**，
否則 auto-compact 會照 200k 動作，而那會改變送出去的 messages ——
也就是改變「逐字落盤」的內容。本節**沒有**量這一格。

### 9.2 兩格怎麼分開的——沿用 §8.1，**題目一個位元組都沒改**

| 格 | 工作區放的 TASK.md | 結果 |
|---|---|---|
| **拒交格** | `TASK.md`（散文只說 "sum"／"multiplying"） | 模型寫了 `multiply`，套件要 `mul` ⇒ 掉進 `meta.json` 寫好的 `trap` |
| **交付格** | `TASK_explicit.md`（多五行 `## Interface`，把 `add(a,b)`／`mul(a,b)` 寫死） | 兩題都過 |

⚠ **兩格都是 Claude Code 自己跑出來的**——工作區進去時只有一個 `TASK.md`，
**沒有預放 `solution.py`**。落地的檔案逐字：

```python
# 拒交格 —— Claude Code 寫的（掉進命名陷阱）
def add(a, b):
    return a + b

def multiply(a, b):        # ← 套件要的是 mul
    return a * b
```
```python
# 交付格 —— Claude Code 寫的
def add(a, b):
    return a + b

def mul(a, b):
    return a * b
```

**順手得到的一個交叉檢查**：這兩份檔案跟 §8 OpenCode 那兩份**位元組相同**——
`ws_end_sha256` 拒交格都是 `39c19a7a…`、交付格都是 `d1ed637b…`。
同一個模型（`gemma-4-12b-it-qat`）、同一題，透過兩個不同 agent、
兩條不同 wire 協定，落在工作區的東西一樣。⇒ **那個陷阱是題目的性質，
不是某一個 agent 的失誤。**（n=1，不是效果量。）

### 9.3 逐字落盤

```
指令（兩格只差工作區裡那一份 TASK.md）
  export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
  export VACANT_RUN_UPSTREAM_ANTHROPIC=http://100.119.113.56:1234
  export VACANT_AGENT_MODEL=gemma-4-12b-it-qat
  python3 -m vacant.vrun.launcher \
      --workspace <ws> --run-dir <rd> \
      --suite <repo>/ops/gain/r535/bank/s1_01_addmul/tests_visible \
      --task-id claudecode_real_<cell> --sandbox none --test-timeout 30 \
      --timeout 1200 --json \
      -- <repo>/ops/vacantrun/wrap_agent.sh claude \
         "Read TASK.md and do what it says. Use your tools to write the file."
```

（`repo` ＝ `/var/tmp/vacant_cc/repo`，`git worktree` detached @ `8eec09a`。）

落盤位置（**vacant-dev 上的 `/var/tmp`，沒有備份，會被清**）：
`/var/tmp/vacant_cc/rd_{refuse,deliver,noleak,smoke}/`
各含 `run_RUN-ON.json`、`receipts_RUN-ON.ndjson`、`rows.jsonl`、
`agent_stdout.log`、`wire_RUN-ON/{index.jsonl,*.req.bin,*.resp.bin}`、
`_frozen_RUN-ON/`。下面抄的是關鍵欄位**不是原始 bytes**，
`*.bin` 要的話得重跑（同附錄 A 的規矩）。
腳本：`/var/tmp/vacant_cc/run_cell.sh`（＋ `run_cell_noleak.sh`、`dump.py`、
`dissect.py`、`lastresp.py`），**未進 repo**——它們只是把上面那條指令包起來。

### `claudecode-real-refuse`（拒交格）

```
task_id         = claudecode_real_refuse
accepted        = false   refused = true   stop_reason = visible_fail
退出碼           = 20
requests_seen   = 5   wire_by_protocol = {'openai': 1, 'anthropic': 4}   wire_errors = 0
proxy paths     = {'POST /v1/messages?beta=true -> 200 [anthropic]': 4,
                   'HEAD /api/hello -> 404 [openai]': 1}
upstream        = http://100.119.113.56:1234/v1/messages?beta=true
visible         = 1 / 2   （check_01_add 過；check_02_mul 掛在
                  ImportError: cannot import name 'mul' from 'solution'）
agent_rc        = 0       ← Claude Code 自己說成功了，閘門說沒有
agent_wall_s    = 14.034  run_wall_s = 14.392   retry = none   attempts_used = 1
ws_start_sha256 = 03aeefafe6f8bb75eee9006f14eb3f0eb436a03214ffac42bd28565e02228a61
ws_end_sha256   = 39c19a7a2c38d254ad5fdd2ce61d95ccec16260e05e8efb90310a957711474a3
wire_digest     = 8b3356043cc0ca2cf6dd284f47b900127593536717f2ef59b36bf3369ee62a5c
verdict_sha256  = 2893815af415e8aeffed9426a4f87632862729404c572dc52455be916e931069
verdict_hash    = ca59a79e584b6a6c29cef8ca7cdf79881f382437a9333c2b02eda8fd6a93acec
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

收尾原話（從最後一通的 SSE `text_delta` 重組）：

> I have created the `solution.py` file with the requested `add` and `multiply`
> functions as specified in `TASK.md`.

**跟 §8 OpenCode 那一格同一個形狀**：宣告完成、退出碼 0、講得很有把握，
閘門在行程結束那一刻跑驗收，拒交。**兩個不同 agent 上各出現一次，
不是單一框架的怪癖。**

### `claudecode-real-deliver`（交付格）

```
task_id         = claudecode_real_deliver
accepted        = true    refused = false   stop_reason = visible_pass
退出碼           = 0
requests_seen   = 4   wire_by_protocol = {'openai': 1, 'anthropic': 3}   wire_errors = 0
proxy paths     = {'POST /v1/messages?beta=true -> 200 [anthropic]': 3,
                   'HEAD /api/hello -> 404 [openai]': 1}
upstream        = http://100.119.113.56:1234/v1/messages?beta=true
visible         = 2 / 2
agent_rc        = 0   agent_wall_s = 12.005  run_wall_s = 12.346
retry = none   attempts_used = 1
ws_start_sha256 = 1407f6cb722df0ec646475116f735bc3c42a7cf8ff3937ca90219a8d9d9c4feb
ws_end_sha256   = d1ed637b7ae45b8f71ddc69e113d9f52a0a998cf8df3dd008bc0bc04c9488f18
wire_digest     = b0bdc402072107d816e17411490f73c68b2c8a3b3f09bd654173c65bea737f06
verdict_sha256  = c59249dfda85110015370cef06d5c83f1e635ba650d293f0dcb615b78989fadf
verdict_hash    = 48a05fa5269fd1f129569305673d83d412e9d297bff6eb8bc3c6c03d897ab721
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### 9.4 wire 逐字（拆 `*.req.bin`）

```
拒交格
  HEAD /api/hello            status=404  bytes=0      → https://api.openai.com/api/hello
  POST /v1/messages?beta=true status=200 bytes=69940  model=gemma-4-12b-it-qat
        max_tokens=32000 stream=true tools=21 n_msgs=2
        system[0]='x-anthropic-billing-header: cc_version=2.1.278.09f; cc_entry…'
  POST /v1/messages?beta=true status=200 bytes=70616  tools=21 n_msgs=5
  POST /v1/messages?beta=true status=200 bytes=71434  tools=21 n_msgs=8
  POST /v1/messages?beta=true status=200 bytes=72026  tools=21 n_msgs=11

交付格
  HEAD /api/hello            status=404  bytes=0      → https://api.openai.com/api/hello
  POST /v1/messages?beta=true status=200 bytes=69942  tools=21 n_msgs=2
  POST /v1/messages?beta=true status=200 bytes=71060  tools=21 n_msgs=5
  POST /v1/messages?beta=true status=200 bytes=71649  tools=21 n_msgs=8
```

`n_msgs` 一路 2→5→8→11、`tools=21` 固定、每一通把完整上文重放一次
（沒有 `previous_response_id` 那類 server-side 續接）。
⇒ **在 Claude Code 的 Messages 這條路上，鐵律 3「逐字落盤」成立**
（跟 §8 OpenCode 的 chat/completions 同結論，兩條 wire 各驗過一次）。

⚠ **`HEAD /api/hello` 那一通是一個要講清楚的洞。** Claude Code 啟動時會對
`$ANTHROPIC_BASE_URL/api/hello` 探一次連通性。`wireproxy.route()` 只把
`/v1/messages`／`/v1/complete` 判給 anthropic，**其餘一律 openai**——所以這一通
被送去 `VACANT_RUN_UPSTREAM_OPENAI` 的預設值 `https://api.openai.com`，**出了網**。
它沒有 body（`request_bytes=0`）、金鑰欄位是 sentinel 不是真鑰（`SECRET_VARS`
在這一跑 `stripped` 是空的，父行程本來就沒有真鑰），但**它是一通真的對外請求**，
不能講成「全部流量都留在本機」。

兩個補法，第二個當場驗過：

1. `ops/vacantrun/block_egress.sh`（V3）——出網封鎖，漏掉的路會**連不上**而不是偷偷連上。
2. **把 openai 那條路也釘到本地**。同一個拒交格加一行
   `export VACANT_RUN_UPSTREAM_OPENAI=http://100.119.113.56:1234/v1` 重跑
   （`claudecode_real_noleak`）：

   ```
   HEAD /api/hello -> 200 [openai] http://100.119.113.56:1234/api/hello   ← 留在本機了
   POST /v1/messages?beta=true -> 200 [anthropic] ×4
   requests_seen = 5   wire_errors = 0   visible = 1/2   exit 20
   ws_end_sha256 = 39c19a7a…（與拒交格逐字相同）
   verdict_hash  = 43b9629e122fc7280c50930a8fe38f80aae49b87df60c60b367e086748018573
   receipts      = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
   ```

   ⇒ **`route()` 沒有壞，是「按 path 猜家族」本來就猜不到 `/api/hello` 屬於誰。**
   這是 V0 的邊界不是 bug，本次**沒有動 `vacant/vrun/` 一行**。

### 9.5 收據驗證（先負控制再驗該跑）

```
$ python3 -m vacant.vrun.verify_receipts --selftest
selftest: PASS                                          ← 負控制：它抓得到壞鏈

$ python3 -m vacant.vrun.verify_receipts --glob /var/tmp/vacant_cc/rd_refuse
run 1　鏈 1　entries 2　驗過 2　失敗 0　壞鏈 0
rd_refuse   RUN-ON   2   2   0   1   1   ca59a79e584b6a6c…  OK      總判：OK

$ python3 -m vacant.vrun.verify_receipts --glob /var/tmp/vacant_cc/rd_deliver
run 1　鏈 1　entries 2　驗過 2　失敗 0　壞鏈 0
rd_deliver  RUN-ON   2   2   0   1   1   48a05fa5269fd1f1…  OK      總判：OK
```

### 9.6 這一節**沒有**說的事

1. **不是**「Claude Code 配 Vacant 寫程式比較好」。交付格跑 **1 次**，
   拒交格連同冒煙與 `noleak` 一共跑 **3 次**（`rd_smoke`／`rd_refuse`／`rd_noleak`，
   三次的 `ws_end_sha256` 都是 `39c19a7a…`、都 exit 20）。
   那是**穩定性**不是效果量：沒有對照組、沒有換題、沒有換模型。
2. **不是**「任何 OpenAI 相容端點都能接 Claude Code」。成立的前提是
   **上游自己會講 `/v1/messages`**（§9.0）。純 OpenAI 端點要自備協定轉換，
   那一層不在本 repo 裡，也**沒有**被量過。
3. **不是**「模型 id 隨便填都行」。Claude Code 放行但會按 200k 假設做
   auto-compact（§9.1）；長任務沒設 `CLAUDE_CODE_MAX_CONTEXT_TOKENS`
   會改變送出去的 messages。**本節沒量長任務。**
4. **不是**「流量全留本機」。預設設定下 `/api/hello` 會出網（§9.4）。
5. 沿用 §7 的所有邊界：proxy **records，不 verifies**；
   `vacant run` 單獨只有 L3。

### 9.7 踩到的坑

- **`claude` 不在 SSH 非互動 shell 的 PATH 上。** `~/.local/bin`（原生安裝）與
  node 的 `bin`（npm 安裝）兩個都不在。`command -v claude` 空白**不等於沒裝**。
- **vacant-dev 上現在有兩份 Claude Code，跑到哪一份看 PATH 順序**：
  `bash -lic 'claude --version'` → `~/.local/bin/claude` **2.1.259**（原生安裝，
  人類平常用的那份，本次沒動它）；把 node 的 `bin` 前置 → **2.1.278**（本次 npm 裝的，
  §9 兩格跑的是這一份）。**引用版本號時要連 PATH 一起講**，不然兩個人會量到兩個東西。
- **本次用 `npm i -g @anthropic-ai/claude-code` 裝 2.1.278**，它是一個 wrapper
  （`cli-wrapper.cjs`）＋平台原生 binary
  （`node_modules/@anthropic-ai/claude-code-linux-x64/claude`，234 MB）。
  npm 套件目錄下的 `.js`／`.cjs` **不含**模型通道的碼，掃那幾個檔會全 0。
- **一個自己踩到的量錯**（值得留著，因為它跟 `envmap` 誠實邊界 1 同型）：
  第一次用 `strings -a <binary> | grep -c …` 掃環境變數，**十三個全是 0**，
  差點寫成「Claude Code 不吃 `ANTHROPIC_BASE_URL`」。真因是
  **vacant-dev 上沒有 `strings`**（`command -v strings` → 空），
  管線前段失敗、後段照樣印 0。改用 `grep -a` 直接掃 binary：

  ```
  ANTHROPIC_BASE_URL               54
  CLAUDE_CODE_MAX_CONTEXT_TOKENS    5
  unrecognized_model                5
  api/hello                        10
  CLAUDE_CODE_USE_OPENAI            0
  ```

  ⇒ **靜態掃字串不算證據**（`envmap` 邊界 1 的 OpenCode 反例），
  而且**掃出 0 還要先確認掃得動**。本節的結論一格都不靠這張表，
  靠的是 `requests_seen` 與 `wire_*/index.jsonl`。
- **`wrap_agent.sh claude` 那一段的註解有一句沒有證據**：
  「有設 `CLAUDE_CODE_USE_OPENAI` 的話它會改走 OpenAI wire」。
  上面那張表裡它是**唯一的 0**（其他四個都掃得到，所以這個 0 是真的 0），
  而且本次**沒有**量過那條路。那一行 `unset` 無害（清一個不存在的變數），
  但**不要當成已知功能引用**。
- `--json` 的 stdout 汙染已經在 `88dbc00` 修掉了（agent 的 stdout 另外落在
  `<run-dir>/agent_stdout.log`），但 Claude Code 的 `unrecognized_model` 警告
  走 stderr，還是會混在終端輸出裡。**要讀就讀 `run_RUN-ON.json`。**

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

### `claude-gate-accept`

```
argv            = bash /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/agent_claude.sh read README.md and do what it says
requests_seen   = 4   wire_by_protocol = {'openai': 1, 'anthropic': 3}   wire_errors = 0
proxy paths     = {'HEAD /api/hello -> 501': 1, 'POST /v1/messages?beta=true -> 200': 3}
stop_reason     = visible_pass   accepted = True   refused = False
agent_rc        = 0   agent_wall_s = 2.119
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = e9cd0206d7eac65515768bf6d3fd50566311056dba236753253b3bea96562961
wire_digest     = f12a4841339ddfee81a3cd11bda805dd1d37cfe90e5a7af7450a64e0212899fa
verdict_hash    = d4f611cb15ce10a6d2eb65092f054e503d085f02ec1efe4c779125d87c039828
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

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

### `opencode-gate-accept`

```
argv            = bash /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/agent_opencode.sh read README.md and do what it says
requests_seen   = 3   wire_by_protocol = {'openai': 3}   wire_errors = 0
proxy paths     = {'POST /v1/chat/completions -> 200': 3}
stop_reason     = visible_pass   accepted = True   refused = False
agent_rc        = 0   agent_wall_s = 6.151
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = e9cd0206d7eac65515768bf6d3fd50566311056dba236753253b3bea96562961
wire_digest     = ba06d6f82bf59317eed5c4c33c9250edb0e275e7fa17991e63e14d13e06f8d8b
verdict_hash    = 8ad83cdbd640893c34472c43a524e2eea627c50ffad5dca852787d0685fe9cf5
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

### `pi-gate-accept`

```
argv            = bash /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/agent_pi.sh read README.md and do what it says
requests_seen   = 2   wire_by_protocol = {'openai': 2}   wire_errors = 0
proxy paths     = {'POST /v1/chat/completions -> 200': 2}
stop_reason     = visible_pass   accepted = True   refused = False
agent_rc        = 0   agent_wall_s = 0.92
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = e9cd0206d7eac65515768bf6d3fd50566311056dba236753253b3bea96562961
wire_digest     = 9e2aa30129fef944b73474dbbe5f882c0b47f343084763136a3f029c2a158c56
verdict_hash    = 6261cbf43d68481a5fa987b045dd3e4e728a3c20d5c932840d7cba46eb6bdf07
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

### `wrap-claude`

```
argv            = /Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/agent-a1025f660b68d0e85/ops/vacantrun/wrap_agent.sh claude read README.md and do what it says
requests_seen   = 4   wire_by_protocol = {'openai': 1, 'anthropic': 3}   wire_errors = 0
proxy paths     = {'HEAD /api/hello -> 501': 1, 'POST /v1/messages?beta=true -> 200': 3}
stop_reason     = visible_pass   accepted = True   refused = False
agent_rc        = 0   agent_wall_s = 2.112
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = e9cd0206d7eac65515768bf6d3fd50566311056dba236753253b3bea96562961
wire_digest     = b81cfa95098c2aaffd19edbfe97e2db6f65716b0b792336bc310ae1321fae214
verdict_hash    = 37ff74a0559d7f8115ad7fb4b427443e23bf84480b7a3e830971cbc3cd993206
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### `wrap-codex`

```
argv            = /Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/agent-a1025f660b68d0e85/ops/vacantrun/wrap_agent.sh codex read README.md and do what it says
requests_seen   = 2   wire_by_protocol = {'openai': 2}   wire_errors = 0
proxy paths     = {'POST /v1/responses -> 200': 2}
stop_reason     = visible_pass   accepted = True   refused = False
agent_rc        = 0   agent_wall_s = 1.059
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = e9cd0206d7eac65515768bf6d3fd50566311056dba236753253b3bea96562961
wire_digest     = 42232cab63d2ff023abe40acb3971b0e55e76eeafb3598a05ef0371b4f62e9a8
verdict_hash    = 5ac4a4e1d9afe5f29fea8be6f7af0af312d80a23919fef37a6715852f77e1232
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### `wrap-opencode`

```
argv            = /Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/agent-a1025f660b68d0e85/ops/vacantrun/wrap_agent.sh opencode read README.md and do what it says
requests_seen   = 3   wire_by_protocol = {'openai': 3}   wire_errors = 0
proxy paths     = {'POST /v1/chat/completions -> 200': 3}
stop_reason     = visible_pass   accepted = True   refused = False
agent_rc        = 0   agent_wall_s = 6.979
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = e9cd0206d7eac65515768bf6d3fd50566311056dba236753253b3bea96562961
wire_digest     = 12926d0e304d395b737afd13c622385e16961df16718c6d64c85772c3300f1f6
verdict_hash    = 664afd2199cc2ee989b653543a26da0eac5e6b7627c6e4699e235acf8c92c734
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### `wrap-pi`

```
argv            = /Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/agent-a1025f660b68d0e85/ops/vacantrun/wrap_agent.sh pi read README.md and do what it says
requests_seen   = 2   wire_by_protocol = {'openai': 2}   wire_errors = 0
proxy paths     = {'POST /v1/chat/completions -> 200': 2}
stop_reason     = visible_pass   accepted = True   refused = False
agent_rc        = 0   agent_wall_s = 1.023
ws_start_sha256 = 95264f3cd640714ff7a2fbb971d1e7639d516839d752ae1644d708bc817d310e
ws_end_sha256   = e9cd0206d7eac65515768bf6d3fd50566311056dba236753253b3bea96562961
wire_digest     = d6237e11c889f291c81afeff0fc066a7c0e00b9e0689a1c68f32838f9171418c
verdict_hash    = ca4726b4966735ab5c3467652c405c9f6b59ed4e860aeb6a7e54da76471dcd65
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

