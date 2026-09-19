# 通用 agent 相容性矩陣（`vacant run` V0 實測，2026-09-18；**OpenCode／Claude Code／Codex(API key) 真模型 2026-09-19**；**§11 第二輪、§12 Hermes 2026-09-19**）

> 一句話：五個 agent，**五個都接通了、五個都有真模型證據**
> （Claude Code／Codex／OpenCode／pi／**Hermes**，§8–§10 與 **§12**；pi 靠 R535）。
> **矩陣裡不再有「完全沒量過」的 agent。**
> 仍然空著的是**同一個 agent 的另一條路**，不是另一個 agent：
> Codex 的 `codex login`（模型通道是寫死的 `wss://`，HTTP 反向代理在那條路上
> 不存在）與 Codex 的 `wire_api=chat`（§11.1，0.147.0 在設定層就退件）。
>
> ⚠ **§8–§12 那五格是分批、分機器、分時間量的，不是一張同條件的矩陣。**
> 要一起引用的話用 **§13**：同一台機器、同一個模型、同一題、同一天，
> 五個 agent × 兩格 × **兩次** ＝ 20 格全過，落盤進了 repo
> （[`runs/v1_five_agent_matrix_20260919/`](../runs/v1_five_agent_matrix_20260919/)）。
> §13.1 記了它**證偽**本文哪一句話。

## 證據等級（**不可混講**，`.claude/commands/goal.md` 的同一張表）

| 級 | 意思 | 誰 |
|---|---|---|
| **L-real** | **真模型**真跑，拒交格與交付格都過，收據可重驗 | **pi**（R535）、**OpenCode**（§8）、**Claude Code**（§9）、**Codex（API key／自訂 provider）**（§10）、**Hermes**（§12）——五個都是 2026-09-19；**五個在同一台機器上各複製兩次＝§13** |
| **L-fake** | 假上游（`mockup.py`）只驗通道與閘門 | （目前沒有只停在這一級的 agent；§1–§6 的假上游格仍然只算這一級） |
| **L-none** | 沒量 | **Codex（`codex login`／ChatGPT 帳號）** ／ **Codex × chat/completions wire**（§11.1：0.147.0 設定層退件，`requests_seen=0`） |

⚠ **L-fake 不能寫成「這個 agent 可以用 Vacant」。** 假上游碰不到 SSE 分塊、
工具呼叫格式、逾時、上下文長度。§1 的矩陣量的是**通道與閘門**；
真模型只在 §8（OpenCode）、§9（Claude Code）、§10（Codex API key）、
§12（Hermes）四節，其餘各格仍然是假上游。

⚠ **Hermes 從 L-none 直接跳到 L-real，中間沒有經過 L-fake**——它從來沒被假上游
量過，這一格的證據**全部**是真模型。所以引用 §1–§6 講 Hermes 時要小心：
那幾節的假上游結論**不涵蓋它**。

量具與判準：[`vacant_network/vrun/`](../vacant_network/vrun/)（V0，見
[`docs/VACANT_RUN.md`](VACANT_RUN.md)）。
名單的單一真相：[`vacant_network/vrun/envmap.py`](../vacant_network/vrun/envmap.py)。

> ⚠ **本文的實測是在搬家之前跑的**（判斷層當時住在 `ops/vacantrun/`）。
> 判準一個字沒動、`ops.vacantrun.launcher` 是同一個 module 物件，所以下面的
> `requests_seen` 與退出碼照樣成立；但 `envmap` **沒有**留 re-export，
> 名單只住在 `vacant_network/vrun/envmap.py` 一個地方。

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
| **Codex CLI** 0.153.2（假上游）／**0.147.0**（真模型，vacant-dev）（API key／自訂 provider） | `POST /v1/responses`（Responses API，SSE）<br>⚠ **chat/completions 那條在 0.147.0 上打不開**：`wire_api="chat"` 在設定層被退件、`requests_seen=0` ⇒ **L-none**（§11.1）。0.153.2 沒試過 | **設定**：`model_providers.<新 id>.base_url`（`-c` 旗標或 `config.toml`／`wrap_agent.sh codex`）。**不吃 `OPENAI_BASE_URL`** | 假上游 **1**（拒交格）／**2**（交付格）<br>**真模型：4 ／ 5**（§10） | ✅ **exit 20** ／ ✅ **exit 0**<br>**真模型：✅ exit 20 ／ ✅ exit 0（L-real，§10）** |
| **Codex CLI** 0.153.2（`codex login`／ChatGPT 帳號，**L-none**） | `wss://chatgpt.com/backend-api/codex/responses`（**WebSocket**） | ❌ **沒有辦法**。`chatgpt_base_url` 只搬得動外掛／遙測／設定那幾條 | **0**（模型那一條完全沒經過 proxy） | ⚠ 閘門**照跑**（觸發點在行程結束不在 wire 上），但**逐字落盤在那條路上不成立** |
| **OpenCode** 1.18.31 | (a) `POST /v1/responses`（內建 `openai` provider）<br>(b) `POST /v1/chat/completions`（自訂 openai-compatible provider） | (a) **環境變數** `OPENAI_BASE_URL`（launcher 已內建，**零接線**——但**只在模型 id 是 models.dev 註冊表裡的那些**時成立，見 §2.3 ⚠）<br>(b) 設定 `OPENCODE_CONFIG_CONTENT`／`wrap_agent.sh opencode`。**真模型走這條** | (a) **2**（假上游）／ (b) **2**（拒交格）、**3**（交付格）<br>**真模型：5 ／ 5**（§8） | ✅ 兩條路都 **exit 20**；(b) 另有 ✅ **exit 0**<br>**真模型 (b)：✅ exit 20 ／ ✅ exit 0（L-real，§8）** |
| **pi** 0.85.1 | `POST /v1/chat/completions`（OpenAI Chat Completions，SSE，`store:false`） | **設定**：`PI_CODING_AGENT_DIR` 指到一個暫時目錄＋寫 `models.json`。**不吃 `OPENAI_BASE_URL`**（實測反例見 §3） | **1**（拒交格）／**2**（交付格） | ✅ **exit 20** ／ ✅ **exit 0** |
| **Hermes Agent** 0.19.0（Nous Research，PyPI `hermes-agent`） | `POST /v1/chat/completions`（OpenAI Chat Completions，SSE，`stream:true`）<br>**另有**每跑 2 通 `GET /api/v1/models` 探測（§12.4） | **設定**：`HERMES_HOME` ＋ `config.yaml` 的 `model.provider: custom` **＋** `model.base_url`。<br>`CUSTOM_BASE_URL`（launcher 已內建）**蓋得過 base_url，但蓋不掉 provider** ⇒ **不是零接線**，最小接線＝一個 `--provider custom`（§12.2） | **真模型：6 ／ 6**（§12）<br>⚠ 這 6 通裡 **2 通是 models 探測**，模型通道是 4 通 | ✅ **exit 20** `visible_fail`（`visible 1/2`）／ ✅ **exit 0** `visible_pass`（`visible 2/2`）<br>**（L-real，§12）** |

⚠ **Claude Code 那一格的「零接線」有一個不在 `vacant run` 裡的前提**：
**上游必須自己會講 Anthropic Messages（`POST /v1/messages`）**。
`vacant_network/vrun/wireproxy.py` 是**反向代理不是協定轉換器**——它照 path 路由，
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
**2026-09-19 加上第五段 `hermes`**（§12），每段都在 runtime 讀
`$VACANT_RUN_PROXY`：

```bash
python3 ops/vacantrun/launcher.py --suite ../tests_visible --run-dir ~/.vacant-run/x -- \
    "$PWD/ops/vacantrun/wrap_agent.sh" pi "把 solution.py 寫完"
#                                      ^^^^ pi | codex | opencode | claude | hermes
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

第五段是後來加的，而且**沒有假上游那一輪**——它的證據直接是真模型（§12）：

| | `requests_seen` | proxy 收到的 path | 裁決 |
|---|---|---|---|
| `wrap_agent.sh hermes`（**真模型**，2026-09-19） | 6 | `POST /v1/chat/completions` ×4 ＋ `GET /api/v1/models` ×2 | `visible_pass`、**exit 0**（交付格）／`visible_fail`、**exit 20**（拒交格） |

模型用 `VACANT_AGENT_MODEL` 換；Hermes 的上下文用 `VACANT_HERMES_CONTEXT`
（預設 65536——Hermes 自己要求 ≥64,000）、執行檔用 `VACANT_HERMES_BIN`
（裝在 venv 裡沒進 PATH 時用）；Codex 的 wire 用 `VACANT_CODEX_WIRE`
（`responses`｜`chat`）換；Codex 另有一個**預設不設**的
`VACANT_CODEX_REASONING_EFFORT`（為什麼要有它：§10.7 的 runaway）。
下面幾節是同樣的東西攤開來，要自己改的時候看。

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

> ⚠ **本節是 2026-09-18 的假上游那一輪。** API key／自訂 provider 那條
> **2026-09-19 已經升到 L-real**（真模型兩格，§10）；ChatGPT 登入那條
> **一個字都沒動**，§4.2／§4.3 仍然逐字成立。

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

1. ✅ **改用自訂 provider ＋ API key**（§2.2）——這是目前唯一**證明有效**的繞法，
   **2026-09-19 已經在真模型上把兩格跑完**（§10）。
   代價：不能用 ChatGPT 訂閱額度，要另外付 API 費用（或像 §10 那樣指到本地端點）。
2. ⚠ **出網封鎖**（`block_egress.sh`，V3，要 root）——封鎖之後那條路會
   **連不上**而不是**偷偷連上**。~~沒量過。~~ **2026-09-19 量了**（量過了：[`decisions/DECISION_20260919_BLOCK_EGRESS_V3.md`](../decisions/DECISION_20260919_BLOCK_EGRESS_V3.md)、[`docs/VACANT_RUN.md`](VACANT_RUN.md) §5.1）：
   對外 TCP／TLS／直打外部 DNS 的 UDP／ICMP 都確實擋得住（有負向控制），
   ⚠ **但「看得見的失敗」只對讀 agent 輸出的人成立，對收據不成立**——
   洩漏格與被擋格的 `run_*.json` **26 個判斷欄位逐字相同**。
   ⚠ **而且這一條對 Codex 的 `wss://` 那條路仍然沒量**（只量了 Hermes）。
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

## 5. Hermes：~~沒量到，寫沒量到~~ → **2026-09-19 量掉了，見 §12**

> **這一節保留 2026-09-18 當天的原文**，因為它本身是一筆有用的紀錄：
> 「沒量到」跟「量到 0」不是同一件事，而且下面那段**反推**後來被實測改了兩處
> （見 §12.2）。原文不回頭改寫，改的話就看不出反推錯在哪。
>
> **一句話結論（2026-09-19）**：Hermes **裝得起來**（`pip install hermes-agent`，
> 0.19.0，208 MB venv，不需要官方的 `curl | bash` 安裝器），
> 而且真模型兩格都拿到了（exit 20 ／ exit 0，`requests_seen` 6 ／ 6）。
> 它是**設定路線**，不是零接線。

### 5.0 原文（2026-09-18）

- Mac：`hermes` 不在 PATH，`~/hermes-agent` 不存在。
- vacant-dev（100.124.254.83）：同上。
- vacant-clean1（100.77.224.99）：同上。

repo 裡的兩支相關程式碼**還在**、也還說得通，但它們是**呼叫端**不是證據：

- [`vacant_network/hermes_substrate.py`](../vacant_network/hermes_substrate.py)：spawn
  `hermes -z`、綁 `HERMES_HOME`、寫 `config.yaml`
  （`model.provider: vllm` ＋ `model.base_url: <...>/v1`）、
  另外設 `CUSTOM_BASE_URL` 環境變數。
- [`vacant_network/brains.py::HermesBrain`](../vacant_network/brains.py)：同樣用 `CUSTOM_BASE_URL`。
- [`vacant_network/mcp_trace.py`](../vacant_network/mcp_trace.py)：**stdio tee-proxy**，
  原本就是為 Hermes 寫的——它 tee 的是 **MCP JSON-RPC**（Hermes ↔ vacant MCP
  server），**不是模型通道**。兩者不可互相替代：`mcp_trace` 證明的是
  「Hermes 有沒有呼叫 vacant、問了什麼」，`wireproxy` 證明的是
  「模型通道上跑了哪些 bytes」。

⇒ 依上面反推，Hermes 應該落在「設定檔框架，但有 `CUSTOM_BASE_URL` 環境變數」
這一類。`CUSTOM_BASE_URL` 已經加進 `envmap.REDIRECT_VARS`，**標記為未實測**：
名單多一個變數只是多設一個環境變數（無害），漏一個才會靜靜地沒被中介。
**要裝了 Hermes 才能把這一格填掉，在那之前它是「未測」不是「可用」。**

### 5.1 那段反推後來錯在哪（2026-09-19 回填）

「設定檔框架 ＋ 有 `CUSTOM_BASE_URL`」這個**大方向對了**，但兩個細節是錯的，
而且錯的方向剛好相反——**這就是為什麼靜態反推要標「未實測」**：

1. **反推少寫了 `provider`。** 上面只講 `model.base_url`，而實測顯示
   **光有 base_url（或光有 `CUSTOM_BASE_URL`）是不夠的**：沒選 provider 的話
   Hermes 在送出任何請求之前就停在 `No LLM provider configured`
   ⇒ `requests_seen = 0`（§12.2 對照 A）。⇒ **反推漏掉的那一半正好是
   「會不會被中介到」的決定性那一半。**
2. **反推低估了 `CUSTOM_BASE_URL`。** 它不只是「另外也會讀」——它的優先序
   **高於** config 的 `base_url`（§12.2 smoke D 實測：config 指到死埠、
   環境變數指到真上游 ⇒ 走環境變數）。⇒ 對**已經設好自訂 provider** 的使用者，
   `vacant run` 確實是零接線。
3. 另外，`hermes_substrate.py` 寫的 `provider: vllm` 在 0.19.0 是 `custom` 的
   **別名**（`hermes_cli/auth.resolve_provider`），不是獨立 provider。

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
   **2026-09-19 補第五個**：Hermes 0.19.0 也一樣（沒有 `store`、
   `n_messages` 2→4→6→8 逐通重放，§12.5）。**五個五個都是。**

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
- **§5 的 Hermes「未測」已於 2026-09-19 失效**（→ §12），
  但那一節的原文保留著，因為它記的是「反推錯在哪」（§5.1）。
  ⚠ **Hermes 沒有假上游那一輪**：§1–§6 任何一句關於假上游的結論**不涵蓋它**。

---

## 8. OpenCode × 真模型（L-real，2026-09-19）

**這一節跟 §1–§6 的差別只有一個，但那一個就是全部：上游是真模型，不是 `mockup.py`。**

- 機器：vacant-dev（`100.124.254.83`）· OpenCode **1.18.31**
  （`npm i -g opencode-ai@1.18.31`，node v22.23.2）
- 上游：`http://100.119.113.56:1234/v1`（1003，載著 `gemma-4-12b-it-qat`）
- 接線：**設定路線**（`wrap_agent.sh opencode` ⇒ `OPENCODE_CONFIG_CONTENT`），
  不是零接線——理由見 §2.3 ⚠
- 題目：**現成的** `ops/gain/r535/bank/s1_01_addmul`（沒有為了這次新造題）
- 判斷層：`vacant_network/vrun/launcher.py`，`--suite` 指到**工作區外**的 bank 路徑

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
  python3 -m vacant_network.vrun.launcher \
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
$ python3 -m vacant_network.vrun.verify_receipts --selftest
selftest: PASS                                          ← 負控制：它抓得到壞鏈

$ python3 -m vacant_network.vrun.verify_receipts --glob <refuse-run-dir>
run 1　鏈 1　entries 2　驗過 2　失敗 0　壞鏈 0
run   RUN-ON   2   2   0   1   1   11889f630ac27ec4…  OK      總判：OK

$ python3 -m vacant_network.vrun.verify_receipts --glob <deliver-run-dir>
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
- 判斷層：`vacant_network/vrun/launcher.py` @ `8eec09a`，`--suite` 指到**工作區外**的 bank 路徑

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

⚠ **這一句的交付格那一半在 2026-09-19 傍晚被證偽了**（§13.1）：同一台機器
（1004）上重跑，Claude Code 的交付格兩次都寫了 docstring，`ws_end` 是
`14332382…` 而不是 `d1ed637b…`。**拒交格那一半（`39c19a7a…`）複製成功。**
本段原文不改（那是當時跑出來的東西），引用時要連機器一起講。

### 9.3 逐字落盤

```
指令（兩格只差工作區裡那一份 TASK.md）
  export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
  export VACANT_RUN_UPSTREAM_ANTHROPIC=http://100.119.113.56:1234
  export VACANT_AGENT_MODEL=gemma-4-12b-it-qat
  python3 -m vacant_network.vrun.launcher \
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
   **2026-09-19 量了**（量過了：[`decisions/DECISION_20260919_BLOCK_EGRESS_V3.md`](../decisions/DECISION_20260919_BLOCK_EGRESS_V3.md)、[`docs/VACANT_RUN.md`](VACANT_RUN.md) §5.1）：擋得住，**但收據上看不出差別**，
   而且它自己有五條擋不住的（迴圈上其他 uid 的 listener、unix socket、
   systemd-resolved 的 DNS、IPv6、已經送出去的位元組）。
   ⚠ **Claude Code 在封鎖之下會怎樣沒量**——那次只量了 Hermes。
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
   這是 V0 的邊界不是 bug，本次**沒有動 `vacant_network/vrun/` 一行**。

### 9.5 收據驗證（先負控制再驗該跑）

```
$ python3 -m vacant_network.vrun.verify_receipts --selftest
selftest: PASS                                          ← 負控制：它抓得到壞鏈

$ python3 -m vacant_network.vrun.verify_receipts --glob /var/tmp/vacant_cc/rd_refuse
run 1　鏈 1　entries 2　驗過 2　失敗 0　壞鏈 0
rd_refuse   RUN-ON   2   2   0   1   1   ca59a79e584b6a6c…  OK      總判：OK

$ python3 -m vacant_network.vrun.verify_receipts --glob /var/tmp/vacant_cc/rd_deliver
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

## 10. Codex CLI（API key／自訂 provider）× 真模型（L-real，2026-09-19）

**跟 §8／§9 同一個形狀：上游是真模型不是 `mockup.py`。這一節補的是第三條 wire——
`POST /v1/responses`（Responses API）。**

⚠ **只有 API key／自訂 provider 那一條。`codex login`（ChatGPT 帳號）那條沒有動**
——它的模型通道寫死 `wss://chatgpt.com/backend-api/codex/responses`，
HTTP 反向代理在那條路上不存在（§4.2），人類另外排。

- 機器：vacant-dev（`100.124.254.83`）· **codex-cli 0.147.0**
  （`/home/user1/.local/bin/codex`，**機器上本來就有的那一份，本次沒有安裝任何東西**）
  ⚠ 版本跟 §1 矩陣的 0.153.2 **不同**——那一格是 2026-09-18 在別處用假上游量的。
  引用時要連機器一起講。
- 上游：`http://100.119.113.56:1234/v1`（1003，載著 `gemma-4-12b-it-qat`）
- 接線：**設定路線**（`wrap_agent.sh codex` ⇒ `CODEX_HOME` ＋ `config.toml` 裡一個
  **新** provider id）。**不是零接線**——Codex 不吃 `OPENAI_BASE_URL`（§3 有否定證據）。
- 題目：**現成的** `ops/gain/r535/bank/s1_01_addmul`（沒有為了這次新造題）
- 判斷層：`vacant_network/vrun/launcher.py` @ `9eeb1d9`，`--suite` 指到**工作區外**的 bank 路徑
- 落盤：vacant-dev 的 `/var/tmp/vacant_codex/rd_*`（收據、`rows.jsonl`、
  `wire_RUN-ON/{index.jsonl,*.req.bin,*.resp.bin}`、`_frozen_RUN-ON/`，共 15 MB）。
  **`/var/tmp` 沒有備份、會被清**——下面抄的是關鍵欄位不是原始 bytes（同附錄 A 的規矩）。
  ⚠ **跑完之後那份工作樹已經移掉了**（vacant-dev 當時只剩 3.7 G，一份 checkout
  佔 788 MB）。要重驗收據的話先把它加回來——**用 worktree，不要 clone**：

  ```
  cd ~/vacant/Vacant && git worktree add --detach /var/tmp/vacant_codex/repo 9eeb1d9
  cd /var/tmp/vacant_codex/repo && python3 -m vacant_network.vrun.verify_receipts --selftest
  ```

### 10.0 先解決那個**以為會是障礙的障礙**：`/v1/responses` 上游支不支援

§9.0 的 Claude Code 那一格靠「LM Studio 原生吃 `/v1/messages`」才成立。
Codex 走的是第三條路，所以**先直測 1003 有沒有開 `/v1/responses`**
（不經 `vacant run`）：

```
$ curl -s -X POST http://100.119.113.56:1234/v1/responses \
    -H 'content-type: application/json' \
    -d '{"model":"gemma-4-12b-it-qat","input":"say hi"}'
{"id":"resp_7e9eba0c…","object":"response","status":"completed",
 "model":"gemma-4-12b-it-qat",
 "output":[{"type":"reasoning",…},{"type":"message","role":"assistant",
            "content":[{"type":"output_text","text":"Hi! How can I help you today?"}]}]}
```

SSE ＋ function tool 也直測過，`response.output_item.added` 會帶
`{"type":"function_call"}`、回應物件裡 `tool_choice:"auto"`、`parallel_tool_calls:true`。
⇒ **這一節的可搬運性到「上游會講 Responses API」為止。** `wireproxy.route()` 把
`/v1/responses` 歸到 `openai`（它不是 `/v1/messages` 也不是 `/v1/complete`）
照 path 轉送，**不改寫 body**。上游只有 chat/completions 的話這條路要嘛自備 shim、
要嘛改用 `VACANT_CODEX_WIRE=chat`——後者本節沒有量過，**§11.1 把它量了：
在 codex-cli 0.147.0 上那個設定值直接被退件（`requests_seen = 0`，等級 L-none）**。

### 10.1 `command -v` 說沒裝，是 PATH 的假象（第二次踩同一個坑）

`.claude/commands/goal.md` 寫「vacant-dev 上只裝了 pi」。§9.7 已經記過
Claude Code 的反例，**Codex 也一樣**：

```
$ ssh user1@vacant-dev 'command -v codex'          # 非互動 shell
（空）
$ ssh user1@vacant-dev 'bash -lic "command -v codex; codex --version"'
/home/user1/.local/bin/codex
codex-cli 0.147.0
```

⇒ `~/.local/bin` 不在 SSH 非互動 shell 的預設 PATH 上。**本次沒有安裝 Codex。**

### 10.2 模型 id：**Codex 是「放行＋警告」，跟 Claude Code 同向、跟 OpenCode 反向**

這是同一個位置的**第三個資料點**（§2.3 ＝ OpenCode 擋、§9.1 ＝ Claude Code 放行）：

```
warning: Model metadata for `gemma-4-12b-it-qat` not found.
Defaulting to fallback metadata; this can degrade performance and cause issues.
```

印完照送，六通全部 `200`。⇒ **三家在「不認得的模型 id」這一格是 2 放行 ∶ 1 擋。
仍然不准從任何一格推另一格**——那是三次實測，不是一條規則。

⚠ 「fallback metadata」具體退到什麼（上下文視窗、支不支援 reasoning summary）
**本節沒有量**。它跟 §9.1 的 `CLAUDE_CODE_MAX_CONTEXT_TOKENS` 是同型的洞：
長任務下它會改變送出去的 input，也就是改變「逐字落盤」的內容。
**§11.4／§11.5 把這一格量了**：body 的**形狀**量到（退到 binary 裡編死的那一套，
`instructions` 20,751 字元 vs 目錄那份 17,730 字元，`tools` 從頂層搬進 `input`），
**上下文視窗那個數字沒量到，只量到下界 ≥ 32,768**。

順帶兩行**不是致命但會嚇人**的輸出，都在 stderr：

```
WARNING: proceeding, even though we could not create PATH aliases:
  Refusing to create helper binaries under temporary dir "/tmp" (codex_home: …)
ERROR codex_core::tools::router: error=failed to parse function arguments:
  unknown variant `pending`,step:`, expected one of `pending`, `in_progress`, `completed`
```

第一行是 `wrap_agent.sh` 把 `CODEX_HOME` 放在 `mktemp -d` 底下的後果（**刻意的**：
設定是這一次 run 的產物不是使用者的狀態）；第二行是模型自己吐壞了 `update_plan`
的參數，Codex 記一筆繼續跑。**兩行都不影響裁決**，但看到它們不要當成接線壞了。

### 10.3 兩格怎麼分開的——沿用 §8.1／§9.2，**題目一個位元組都沒改**

| 格 | 工作區放的 TASK.md | 結果 |
|---|---|---|
| **拒交格** | `TASK.md`（散文只說 "sum"／"multiplying"） | 掉進 `meta.json` 寫好的 `trap`（套件要 `add`／`mul`） |
| **交付格** | `TASK_explicit.md`（多五行 `## Interface`） | 兩題都過 |

⚠ **兩格都是 Codex 自己跑出來的**——工作區進去時只有一個 `TASK.md`，
**沒有預放 `solution.py`**。落地的檔案逐字：

```python
# 拒交格 —— Codex 寫的（掉進命名陷阱，而且比另外兩家掉得更深）
def sum_numbers(a, b):
    return a + b

def multiply_numbers(a, b):
    return a * b
```
```python
# 交付格 —— Codex 寫的
def add(a, b):
    return a + b

def mul(a, b):
    return a * b
```

**交付格的 `ws_end_sha256` ＝ `d1ed637b…`，與 §8 OpenCode、§9 Claude Code 的交付格
逐位元相同。** 三個 agent、三條 wire 協定（chat/completions、Messages、Responses）、
同一個模型、同一題，交付格落地的東西一樣。

⚠ **拒交格反而三家都不一樣**：OpenCode 與 Claude Code 都寫 `add`／`multiply`
（`39c19a7a…`），Codex 寫 `sum_numbers`／`multiply_numbers`（`b720ee87…`）。
⇒ 「陷阱是題目的性質」（§9.2）那句話**只在敘述寫死介面時**表現成同一份檔案；
敘述含糊時，**落地的錯法是會分岔的**。n=1，不是效果量。

⚠⚠ **「分岔」這件事本身也不穩定**：2026-09-19 傍晚在 1004 上重跑（§13），
Codex 的拒交格兩次都落在 `39c19a7a…`（`add`／`multiply`，`visible 1/2`），
**與另外四家同一個檔**。本節這一格是在 1003 上跑的，1003 是 thinking 模式、
1004 不是——**這條變因沒有被隔離**，不要把它讀成 thinking 造成的。

⚠ **§11.3 把這句話再收回一半**：同一題同一台同一個模型第三次跑，Codex 的拒交格
落地成 `add`／`multiply`（`39c19a7a…`）——**正好就是 §8 OpenCode／§9 Claude Code
那一個值**。⇒ 「Codex 的錯法與別家不同」**不是一條性質**，三次跑出三種錯法。

### 10.4 逐字落盤（**出廠接線**，零額外設定）

```
指令（兩格只差工作區裡那一份 TASK.md）
  export PATH=/home/user1/.local/bin:/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
  export VACANT_RUN_UPSTREAM_OPENAI=http://100.119.113.56:1234/v1
  export VACANT_AGENT_MODEL=gemma-4-12b-it-qat
  export VACANT_CODEX_WIRE=responses          # 也是預設值，寫出來只為了可讀
  python3 -m vacant_network.vrun.launcher \
      --workspace <ws> --run-dir <rd> \
      --suite <repo>/ops/gain/r535/bank/s1_01_addmul/tests_visible \
      --task-id codex_real_<cell> --sandbox none --test-timeout 30 \
      --timeout 1200 --json \
      -- <repo>/ops/vacantrun/wrap_agent.sh codex \
         "Read TASK.md and do what it says. Use your tools to write the file."
```

### `codex_real_asis`（拒交格，出廠接線）

```
task_id         = codex_real_asis
accepted        = false   refused = true   stop_reason = visible_fail
退出碼           = 20
requests_seen   = 4   wire_by_protocol = {'openai': 4}   wire_errors = 0
proxy paths     = {'POST /v1/responses -> 200 [openai]': 4}
upstream        = http://100.119.113.56:1234/v1/responses
upstreams_defaulted = ['anthropic']   ← **這一跑沒有任何一通走 anthropic**，見 §10.6
visible         = 0 / 2   （兩題都掛在 ImportError：`add`／`mul` 都不存在）
agent_rc        = 0       ← Codex 自己說成功了，閘門說沒有
agent_wall_s    = 145.116  run_wall_s = 145.540   retry = none   attempts_used = 1
ws_start_sha256 = 03aeefafe6f8bb75eee9006f14eb3f0eb436a03214ffac42bd28565e02228a61
ws_end_sha256   = b720ee87df4a27f00d85f57636d71663d3be5da0ab6cac2dc6e23c7b80a356fd
wire_digest     = e3aef31ba7cc6db26860a7796416d8649f1980117b15dfae9b62d4999a412157
verdict_sha256  = f6e1198af74dc07391a597aaa05eb032c95f4f8ca84c5fb7153ad8f2f88dc4f9
verdict_hash    = 28e8d32909f343f2163d8bb2706a016374a0730d9a08135b7efe4e0b396d2c5d
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

**`agent_rc = 0` 第三次出現。** §8（OpenCode）、§9（Claude Code）各一次，
現在 Codex 也一次：**三個不同 agent、三條不同 wire，拒交格全部是
「agent 宣告完成、退出碼 0，閘門在行程結束那一刻擋下來」。**
那不是某一個框架的怪癖。

### `codex_real_asis_deliver`（交付格，出廠接線）

```
task_id         = codex_real_asis_deliver
accepted        = true    refused = false   stop_reason = visible_pass
退出碼           = 0
requests_seen   = 5   wire_by_protocol = {'openai': 5}   wire_errors = 0
proxy paths     = {'POST /v1/responses -> 200 [openai]': 5}
upstream        = http://100.119.113.56:1234/v1/responses
visible         = 2 / 2
agent_rc        = 0   agent_wall_s = 155.164  run_wall_s = 155.320
retry = none   attempts_used = 1
ws_start_sha256 = 1407f6cb722df0ec646475116f735bc3c42a7cf8ff3937ca90219a8d9d9c4feb
ws_end_sha256   = d1ed637b7ae45b8f71ddc69e113d9f52a0a998cf8df3dd008bc0bc04c9488f18
wire_digest     = 60ddfd3198a14d5a681ea50942febe18fb0d8108a8fdcd78707f81bcfe3a2abd
verdict_sha256  = dcc800d011503c4dfb72c5664bf4798d0a3721070af9929e8b62b62517298271
verdict_hash    = ebaf2218e3d6ce7c37352059972b6c87a365cee046600099b20a22ee01f7c169
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

### 10.5 wire 逐字（拆 `*.req.bin`）——**鐵律 3 在 Responses 這條路上成立**

§4.1 用假上游量過「Codex 每通重放完整上文」。**真模型把它複驗了一次**：

```
codex_real_asis（拒交格）
  POST /v1/responses 200  req=44261  n_input=3   tools=10  store=false  previous_response_id=<不存在>
        input kinds: message ×3
  POST /v1/responses 200  req=45474  n_input=6   tools=10
        input kinds: message ×3, reasoning, function_call, function_call_output
  POST /v1/responses 200  req=46500  n_input=9   tools=10
  POST /v1/responses 200  req=47002  n_input=11  tools=10

codex_real_asis_deliver（交付格）
  POST /v1/responses 200  req=44277  n_input=3 → 7 → 9 → 12 → 14（tools=10 固定）
```

`store = false`、**沒有 `previous_response_id`**、`tools` 固定 10、
每一通把完整 input 陣列重放一次。⇒ **逐字落盤成立，鐵律 3 沒有破**
（與 §8 的 chat/completions、§9 的 Messages 同結論，**三條 wire 各驗過一次**）。

⚠ 那是**這個版本、這個 provider 設定**下的觀測。Codex 只要改用
`store: true` ＋ `previous_response_id`，對話狀態就會搬到伺服器端、proxy 只看得到
delta ——§4.1 原本預期的就是那個。**它現在沒發生，不等於它不會發生。**

### 10.6 `upstreams_defaulted` 看一眼：**這一格跟 Claude Code 不一樣**

§9.4 的 Claude Code 會探 `HEAD /api/hello`，被 `route()` 判成 openai、
落到公開 API 的預設上游、**真的出網**。**Codex 沒有這個行為**：

```
四跑的 proxy path 全表 = {'POST /v1/responses -> 200 [openai]': 4／5／6／6}
upstreams_seen         = ['http://100.119.113.56:1234/v1/responses']   ← 只有這一個
upstreams_defaulted    = ['anthropic']
```

`upstreams_defaulted` 仍然列著 `anthropic`，因為這一跑**沒有人指定**
`VACANT_RUN_UPSTREAM_ANTHROPIC`。**但 `wire_by_protocol` 裡沒有 anthropic 這一項**
——那條預設上游從頭到尾沒被用到。

⇒ **`upstreams_defaulted` 的讀法**：它說的是「這條路由沒人指定，**萬一**有流量會去
公開 API」，**不是**「已經出網了」。要判有沒有出網，看的是 `wire_by_protocol` 與
`wire_*/index.jsonl` 的 `upstream` 欄位。§9.4 那一格兩者都成立（列了 ＋ 真的有一通），
本節只成立前半。結構性補法仍然是 `block_egress.sh`（V3），~~沒量過~~
**2026-09-19 量了**（量過了：[`decisions/DECISION_20260919_BLOCK_EGRESS_V3.md`](../decisions/DECISION_20260919_BLOCK_EGRESS_V3.md)、[`docs/VACANT_RUN.md`](VACANT_RUN.md) §5.1）：它擋得住出網，
**但擋不住「收據看不出差別」**——那要另外把 REJECT 規則的封包計數器寫進收據。
⚠ **Codex 在封鎖之下沒量。**

### 10.7 一種**跑不完**的失敗：思考模式下的 runaway（`codex_real_smoke`）

**第一次冒煙就踩到，必須寫下來。** 同樣的指令、同樣的出廠接線，第 5 通：

```
POST /v1/responses   request_bytes = 47751
  status = 0   error = BrokenPipeError(32, 'Broken pipe')   elapsed_s = 713.67
  response_sha256 = null          ← infra_void 的那個洞，wire_digest 簽的就是含 null 的配對
  已經落盤的 resp.bin = 9,340,297 bytes
    response.reasoning_text.delta  = 94,776 個
    response.output_text.delta     = 0 個
    response.completed             = 0 個
```

模型在**推理裡繞圈**，一個 `output_text` 都沒吐、713 秒還沒收尾。
（`BrokenPipe` 是人為中止造成的，`agent_rc = -15`——**這一格不算兩格之一**，
它是一份故障紀錄。那一跑的閘門照樣動：`visible 1/2`、`exit 20`。）

**為什麼會這樣**：1003 的 LM Studio **預設開思考**，而 Codex 的
`/v1/responses` body 帶 `reasoning: {"summary": "auto"}`（**沒有 `effort`**）
⇒ 思考照開。`ops/gain/r535/run_r535.py` 對同一個端點的紀律是 **NOTHINK**
（送 `reasoning_effort: "none"`，2026-09-19 裁決），本節算是從另一條 wire 上
撞到同一件事。

⚠ **出廠接線本身沒壞**：同樣設定總共跑了三次拒交格，**兩次正常收工（145 秒／
145 秒），一次 runaway**。§10.4 那兩格就是正常的那批。**1 / 3，n 很小。**

**緩解（已驗，但是觀測不是保證）**：`wrap_agent.sh` 多了一個
**預設不設**的鉤子 `VACANT_CODEX_REASONING_EFFORT`。沒設的話產生的
`config.toml` 與之前**逐位元相同**；設 `none` 才多一行 `model_reasoning_effort`。

```
$ VACANT_CODEX_REASONING_EFFORT=none  …  wrap_agent.sh codex  （其餘與 §10.4 逐字相同）
```

```
codex_real_nt_refuse    accepted=false  visible_fail  exit 20  requests_seen=6  agent_rc=0
    visible 0/2   agent_wall_s=301.212  run_wall_s=301.473
    ws_end_sha256  = b71ff60edca5e852136303340de62b5338e6266bf5b3da8af728f38301dfba8d
    wire_digest    = 5391a12e5cc421abdbc678f6ec6f18f2a4149cc5759170daa14a31dc487265aa
    verdict_hash   = 9df146b93fc2a820bfd9d6b45634b52c67bf617b8fc8ba26315224c274ea2a24
    receipts       = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
codex_real_nt_deliver   accepted=true   visible_pass  exit 0   requests_seen=6  agent_rc=0
    visible 2/2   agent_wall_s=336.015  run_wall_s=336.252
    ws_end_sha256  = d1ed637b7ae45b8f71ddc69e113d9f52a0a998cf8df3dd008bc0bc04c9488f18
    wire_digest    = 478167c142af00aa8c4ce94c4978d847ed81c7a1c376f8c3749ed2e5b5c59a20
    verdict_hash   = 29035207d34f5d606ab98958f89e5b22e71e0942cccb3319654237d6d5d697bc
    receipts       = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

request body 變成 `reasoning: {"effort": "none", "summary": "auto"}`、
回應的 `output_tokens_details.reasoning_tokens = 0`、`reasoning_text.delta = 0`，
兩格都沒有 runaway。

⚠ **交付格的 `ws_end_sha256` 跟出廠接線那一格逐位元相同（`d1ed637b…`），
拒交格不同**（`b71ff60e…` 是 `sum`／`multiply`，`b720ee87…` 是
`sum_numbers`／`multiply_numbers`）。同一個接線、同一題、只差推理開關，
**錯法本來就會漂**——這正是 §10.3 那句話的第二個例子。

⚠ 這個鉤子**把推理整個關掉**。它換來的是「跑得完」，代價是別的題上可能答得更差。
**本節沒有量那個代價**，而且兩格各只跑一次。

### 10.8 收據驗證（先負控制再驗該跑）

```
$ python3 -m vacant_network.vrun.verify_receipts --selftest
selftest: PASS                                          ← 負控制：它抓得到壞鏈

$ python3 -m vacant_network.vrun.verify_receipts --glob /var/tmp/vacant_codex/rd_asis
rd_asis          RUN-ON   2   2   0   1   1   28e8d32909f343f2…  OK      總判：OK
$ python3 -m vacant_network.vrun.verify_receipts --glob /var/tmp/vacant_codex/rd_asis_deliver
rd_asis_deliver  RUN-ON   2   2   0   1   1   ebaf2218e3d6ce7c…  OK      總判：OK
$ python3 -m vacant_network.vrun.verify_receipts --glob /var/tmp/vacant_codex/rd_nt_refuse
rd_nt_refuse     RUN-ON   2   2   0   1   1   9df146b93fc2a820…  OK      總判：OK
$ python3 -m vacant_network.vrun.verify_receipts --glob /var/tmp/vacant_codex/rd_nt_deliver
rd_nt_deliver    RUN-ON   2   2   0   1   1   29035207d34f5d60…  OK      總判：OK
```

### 10.9 這一節**沒有**說的事

1. **不是**「Codex 配 Vacant 寫程式比較好」。出廠接線的交付格跑 **1 次**、
   拒交格跑 **3 次**（兩次正常＋一次 runaway）；NOTHINK 那組各 1 次。
   沒有對照組、沒有換題、沒有換模型。**存在性證明，不是效果量。**
2. **不是**「Codex 可以用 Vacant」——只有 **API key／自訂 provider** 那一條。
   `codex login` 那條的模型通道是 `wss://`，**本次一個字都沒動**（§4.2 仍然成立）。
3. **不是**「零接線」。Codex 不吃 `OPENAI_BASE_URL`（§3 的否定證據），
   要寫 `CODEX_HOME/config.toml`。
4. **不是**「任何 OpenAI 相容端點都行」。前提是上游會講 **Responses API**（§10.0）。
   只有 chat/completions 的端點要改 `VACANT_CODEX_WIRE=chat`——**§11.1 量完了：
   那條在 0.147.0 上打不開（設定層退件），仍然是 L-none。**
5. **不是**「全部流量都留在本機」的保證。本節四跑**實際上**沒有一通出網
   （§10.6），但 `anthropic` 那條路由仍然是 `defaulted`。
6. **不是**「0.153.2 也是這樣」。本節量的是 **0.147.0**。
7. 沿用 §7 的所有邊界：proxy **records，不 verifies**；
   `vacant run` 單獨只有 L3。

### 10.10 踩到的坑

- **`command -v codex` 空白不等於沒裝**（§10.1）。**第二次**在同一台機器上
  用同一個方式量錯，先 `bash -lic`。
- **`CODEX_HOME` 放在 `/tmp` 會被 codex 抱怨**（拒絕在暫時目錄下造 helper binary），
  但它印完 `WARNING: proceeding` 就照跑。**不是錯誤。**
- **`~/.codex/auth.json` 在那台機器上是存在的**（人類自己的登入）。
  `wrap_agent.sh` 每次 `mktemp -d` 一個新的 `CODEX_HOME`，**本次沒有碰那一份**
  ——這也是為什麼走的一定是 API key 那條路：新的 `CODEX_HOME` 裡沒有 `auth.json`，
  provider 的 `env_key = "OPENAI_API_KEY"` 拿到的是 launcher 給的 sentinel。
- **`--json` 要讀 `<run-dir>/run_RUN-ON.json`**，不要讀 stdout：Codex 把整個
  對話逐格印在 stderr（`exec` ／ `succeeded in …`），終端上會混在一起。
- **兩格並行跑會互相拖慢**：`nt_*` 那組兩格同時跑是 301／336 秒，
  出廠接線那組分開跑是 145／155 秒，而且當時 1003 上還有**別的 session** 在用。
  **牆鐘時間不可以當成效能數字。**

---

## 11. 兩個空白格：`wire_api=chat` 與「fallback metadata 退到什麼」（2026-09-19 第二輪）

**這一節填的是 §10 自己列出來的兩個洞**（§10.0／§10.9-4 的
「`VACANT_CODEX_WIRE=chat` 那條沒量過」，與 §10.2／§10.9 的
「fallback metadata 退到什麼沒量」）。**一個填成了，一個填成「量不到」**：

1. **`VACANT_CODEX_WIRE=chat` ⇒ 仍然是 L-none（沒量到）。**
   codex-cli 0.147.0 在**載入 config 的那一步**就拒絕 `wire_api = "chat"`，
   `requests_seen = 0`、`agent_rc = 1`、一個 byte 都沒送出去。
   **中介從來沒發生 ⇒ 沒有拒交格也沒有交付格可言。**
   ⚠ **本節不會把它寫成 L-fake**：假上游那一級至少有通道與閘門的流量，
   這裡連流量都沒有。**「沒量到」≠「量到 0」**（鐵律 3 的 `infra_void`）。
2. **fallback metadata ⇒ 退到什麼「形狀」量到了，退到什麼「數字」沒量到。**
   形狀：binary 裡編死的那一套，**確實改變了送出去的 bytes**，而且在這個上游上
   **退化的那一版才是能用的那一版**（§11.4）。
   數字（context window）：**只量得到一個下界**，那個值本身讀不出來（§11.5）。

- 機器：vacant-dev（`100.124.254.83`）· **codex-cli 0.147.0**
  （`/home/user1/.local/bin/codex` → `~/.codex/packages/standalone/releases/`
  `0.147.0-x86_64-unknown-linux-musl`，**機器上本來就有的那一份，本次沒有安裝任何東西**）
- 上游：**1003**（`http://100.119.113.56:1234/v1`，LM Studio × `gemma-4-12b-it-qat`）
  ⚠ **1003 是 thinking 模式**，本輪四格全部帶 `VACANT_CODEX_REASONING_EFFORT=none`
  （理由見 §10.7；**那是觀測到的緩解不是保證**，而且它把推理整個關掉、代價沒量）。
  判準逐字：`POST /v1/chat/completions` 的 `choices[0].message.reasoning_content`
  在 1003 上**有內容**（`'The user said "say hi".\n…'`，100 字元）。
  ⚠ **不要拿頂層 `usage.reasoning_tokens` 當判準——那個欄位根本不在回應裡。**
  有的是巢狀的 `usage.completion_tokens_details.reasoning_tokens`（1003 這一通＝25）。
  兩個名字差一層，抄錯就會得到 `None` 然後把 thinking 模式判成不是。
- 判斷層：`vacant_network/vrun/launcher.py` @ `9eeb1d9`（與 §10 同一份）
- wrapper：`wrap_agent.sh` @ `feat/codex-real`（sha256
  `6cce391df9e56c62223997f4b9bfb42b2a7e1548ea1ac8bdf8dfd8f64cbca32d`），
  因為要用 §10.7 那個 `VACANT_CODEX_REASONING_EFFORT` 鉤子
- 題目：**現成的** `ops/gain/r535/bank/s1_01_addmul`（沒有為了這次新造題）
- 落盤：vacant-dev 的 `/var/tmp/vacant_codex_chat/{rd_*,ws_*}`。
  **`/var/tmp` 沒有備份、會被清**——下面抄的是關鍵欄位不是原始 bytes（同附錄 A 的規矩）。

### 11.1 空白格一：`requests_seen = 0`，所以這一格是 **L-none**

**先把等級釘死，因為退出碼會騙人。** 下面 §11.2 那兩格
`accepted=false`、`stop_reason=visible_fail`、`exit 20`——**看起來**像
「閘門有牙齒」。配上 `requests_seen = 0`、`wire_by_protocol = {}`、
`agent_rc = 1`、`ws_end` 與 `ws_start` 逐位元相同，它**不是**：

> **閘門擋下來的是一個從來沒產生過的東西。**
> `/goal` 把「`requests_seen > 0`」寫成拒交格的不可省旁證，就是為了擋這種
> **假的拒交格**。⇒ **Codex × chat wire ＝ L-none。**

**那接不通的原因是「我們接線接錯」還是「這個版本沒有這條路」？**
這兩個結論在文件裡完全不同，所以分開查。查得到的兩個開關都查了：

1. **設定值**——`wire_api` 這個 enum 現在只剩一個變體。serde 的錯誤訊息
   會把**所有**已知變體列出來，而它列出來的只有 `responses`（§11.1a 逐字）。
2. **feature flag**——`codex features list` 共 **104 個**旗標，
   `grep -iE "chat|wire|completion|legacy|responses"` 只撈到
   `responses_websockets`／`responses_websockets_v2`（兩個都 `removed`）與
   `use_legacy_landlock`（`deprecated`）。**沒有任何一個能把 chat 打開。**

3. **上游無關**——同一個 `wire_api = "chat"` 在**三個不同的 `base_url`** 上
   得到逐字相同的退件：`http://100.86.226.21:1234/v1`（1004）、
   `http://100.119.113.56:1234/v1`（1003）、`http://127.0.0.1:1/v1`（**根本連不上**）。
   ⇒ **失敗發生在 codex 讀 config 的那一步，網路那一側完全沒有參與。**
   換上游、換機器都不會變——所以**沒有在 1004 上重跑**（同一個 client 端 bug，
   重跑只會多一份一樣的紀錄；四個正式格全部留在 1003，同一台同一個推論條件）。

⇒ **在這個版本的兩個公開開關上都沒有 chat 這條路，而且那跟上游是誰無關。**
⚠ 但**這仍然不是「Codex 不支援 chat/completions」**——那是關於
**一個版本、兩個開關**的陳述。沒反編譯、沒試別的版本，
**0.153.2 會怎樣本節不知道**（§11.8-1）。
⚠ 也**不是**「`vacant run` 接不通 chat/completions」——**pi 與 OpenCode 的真模型格
走的就是 chat/completions**（§1、§8）。**接不通的是 Codex 這一家的這個版本。**

### 11.1a `wire_api = "chat"` 的逐字退件

**直測（不經 `vacant run`，四個值各試一次）**：

```
wire_api = "chat"              exit 1
  Error loading config.toml: `wire_api = "chat"` is no longer supported.
  How to fix: set `wire_api = "responses"` in your provider config.
  More info: https://github.com/openai/codex/discussions/7782
  in `model_providers.vacantprobe.wire_api`
wire_api = "chat_completions"  exit 1   unknown variant `chat_completions`, expected `responses`
wire_api = "completions"       exit 1   unknown variant `completions`, expected `responses`
wire_api = "responses"         exit 0   （正常啟動）
```

**`expected \`responses\`` ——那個 enum 現在只剩一個變體。** 這不是打錯字被擋：
serde 的 `unknown variant` 訊息會把所有已知變體列出來，而它只列了一個。
⚠ 精確的說法是「**0.147.0 的設定層只接受 `responses`**」，
**不是**「這支 binary 裡沒有 chat 的程式碼」——後者我們沒有查（沒反編譯）。

⇒ **`wrap_agent.sh` 的 `VACANT_CODEX_WIRE=chat` 在 0.147.0 上是一條死路**。
它不會安靜跑錯：config 載入就停（fail-visible），`requests_seen` 是 **0**。

### 11.2 那兩格實際跑出來的形狀（**兩格都 exit 20，但那不是拒交格**）

四格同一台、同一個模型、同一題、同一個 effort，只差 `VACANT_CODEX_WIRE`
與工作區裡那一份 TASK.md：

| 格 | wire | 退出碼 | `accepted` | `stop_reason` | `requests_seen` | `agent_rc` | `visible` | `agent_wall_s` |
|---|---|---|---|---|---|---|---|---|
| `codex_chat_refuse` | chat | **20** | false | `visible_fail` | **0** | **1** | 0 / 2 | 0.034 |
| `codex_chat_deliver` | chat | **20** | false | `visible_fail` | **0** | **1** | 0 / 2 | 0.033 |
| `codex_resp_refuse`（對照） | responses | **20** | false | `visible_fail` | **6** | **0** | 1 / 2 | 17.559 |
| `codex_resp_deliver`（對照） | responses | **0** | **true** | `visible_pass` | **6** | 0 | 2 / 2 | 18.012 |

```
codex_chat_refuse     ws_start = ws_end = 03aeefafe6f8bb75eee9006f14eb3f0eb436a03214ffac42bd28565e02228a61
                      wire_by_protocol = {}   verdict_sha256 = 34aa50d78acd8b9b…  verdict_hash = 2691d9488ebc3d17…
codex_chat_deliver    ws_start = ws_end = 1407f6cb722df0ec646475116f735bc3c42a7cf8ff3937ca90219a8d9d9c4feb
                      wire_by_protocol = {}   verdict_sha256 = 8779964b396f7177…  verdict_hash = df52af988c1c807b…
chat 兩格的 wire_digest 同一個值 = 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945
  ＝**空 wire 的 digest**（`sha256("[]")`）。兩格連簽的東西都一樣，因為兩格都沒有 wire。
codex_resp_refuse     ws_end = 39c19a7a2c38d254ad5fdd2ce61d95ccec16260e05e8efb90310a957711474a3
                      wire_digest = ea1e65caeda0c982…  verdict_hash = ffd503694a4f47b5…
                      proxy paths = {'POST /v1/responses -> 200 [openai]': 6}
codex_resp_deliver    ws_end = d1ed637b7ae45b8f71ddc69e113d9f52a0a998cf8df3dd008bc0bc04c9488f18
                      wire_digest = 88f6fbfb4b16482c…  verdict_hash = 9e7b5a66471a2769…
                      proxy paths = {'POST /v1/responses -> 200 [openai]': 6}
四格 upstreams = {"openai": env:VACANT_RUN_UPSTREAM_OPENAI → 1003, "anthropic": default（沒人指定）}
四格 upstreams_defaulted = ['anthropic']；**四格的 wire_by_protocol 裡都沒有 anthropic**（§10.6 的讀法）
```

⚠ **不准寫的一句話**（它單看退出碼是真的，但會讓讀者以為中介發生過）：

> ❌ 「Codex 的 chat wire 閘門正常運作，兩格都 exit 20。」

**要寫的是**：chat 那兩格是 **假的拒交格**，理由在 §11.1 —— `requests_seen = 0`、
`wire_by_protocol = {}`、`agent_rc = 1`、`ws_end` 與 `ws_start` 逐位元相同。
閘門說「沒交出東西」是對的，但它擋下來的是**一個沒跑的 agent**，
不是**一個跑完了卻沒過驗收的 agent**。兩者的退出碼一樣，
**分得開它們的只有 `requests_seen`**。
⇒ 這正是 §3「我設了環境變數不是證據」的鏡像：**退出碼也不是證據。**

**交付格在 chat 那條路上也拿不到**（agent 沒跑 ⇒ 不會有 `solution.py`
⇒ 永遠 `visible_fail`）。所以 §1 矩陣那一格是
**❌（0.147.0 的設定層不接受）＋ L-none**，不是空白、不是 ✅、也不是 L-fake。

**responses 那兩格是對照組，作用是「把失敗歸因給誰」**：同一支 wrapper、
同一個 launcher、同一台機器、同一題、同一個 effort，只換 `wire_api` 就兩格都拿到
（exit 20 ／ exit 0、`requests_seen` 6 ／ 6、`agent_rc` 0 ／ 0）。
⇒ **量具本身沒壞**，chat 的 0 通不是 launcher／wrapper／題目的問題。
至於 0 通的**原因**，不靠推論：codex 自己在 stderr 上講了（§11.1a），
而且 `vacant run` 底下收到的那四行與直測到的那四行**逐字相同**
（唯一差別是 provider id：直測叫 `vacantprobe`、`wrap_agent.sh` 叫 `vacantproxy`）。
沒有這組對照，`requests_seen = 0` 這個數字是解釋不了的——
**它跟「接線接錯」長得一模一樣。**

### 11.2a 本輪五個 run 的分類（**哪些是證據、哪些是故障紀錄**）

| run 目錄 | 是什麼 | 可以拿去引用嗎 |
|---|---|---|
| `rd_resp_refuse` | **證據**：責任格對照組，拒交格（`rs=6`、`rc=0`、`visible 1/2`、exit 20） | ✅ 但只證明**量具沒壞**，不是新的 Codex L-real（§10 才是） |
| `rd_resp_deliver` | **證據**：同上，交付格（`rs=6`、`rc=0`、`visible 2/2`、exit 0） | ✅ 同上 |
| `rd_chat_refuse` | **故障紀錄**：chat wire 接不通的形狀（`rs=0`、`rc=1`） | ⚠ 只能引用成 **L-none 的證據**，不可引用成拒交格 |
| `rd_chat_deliver` | **故障紀錄**：同上 | ⚠ 同上 |
| `rd_resp_refuse_catalogid` | **探針**：拿目錄模型 id（`gpt-5.6-sol`）只為了抓第一通 request body。`rs=1`、`rc=1`、上游 400 退件 | ⚠ **不是格子**。它的價值只在 §11.4 那張 body 對照表 |

（同 §10 處理 `codex_real_smoke` 的規矩：**跑不完的那些也要留下來、也要標成故障紀錄**，
但不准混進格子裡數。）

### 11.3 對照組順手複驗到的三件事（都跟 §10 的敘述有出入）

1. **`ws_end` 交付格又一次逐位元相同**：`d1ed637b…`，與 §8（OpenCode）、
   §9（Claude Code）、§10（Codex）的交付格**同一個值**。這是第四次。
2. **拒交格又漂到第三種寫法**。同一題、同一個模型、同一台機器，三輪的拒交格落地：

   | 來源 | 落地的函式名 | `ws_end_sha256` | `visible` |
   |---|---|---|---|
   | §10.4（出廠接線，思考開） | `sum_numbers`／`multiply_numbers` | `b720ee87…` | 0 / 2 |
   | §10.7（NOTHINK） | `sum`／`multiply` | `b71ff60e…` | 0 / 2 |
   | **§11.2（NOTHINK，本輪）** | **`add`／`multiply`** | **`39c19a7a…`** | **1 / 2** |

   ⚠ 第三列的 `39c19a7a…` **正好等於 §8 OpenCode 與 §9 Claude Code 的拒交格**。
   ⇒ **不要把「Codex 的錯法與別家不同」寫成一條性質**（§10.3 那句話要收回一半）：
   三次同設定跑出三種錯法，它是**會漂的**，n 各只有 1。
   **跨 agent 的宣稱一定要連 agent 與那一跑一起講。**

3. **牆鐘：17.6 ／ 18.0 秒**，而 §10.7 的同一組是 301 ／ 336 秒——**差 17–19 倍**。
   差別不在程式：**§10.7 那組兩格並行跑、而且當時 1003 上有別的 session**，
   本輪是 1003 剛收官、整台空的，四格循序跑。
   ⇒ §10.10 那條「牆鐘時間不可以當成效能數字」**這一輪把它量成 17–19 倍**。
   ⚠ 反過來也要小心：**不可以拿本輪的 17.6 秒去講「Codex 很快」**——
   它量到的是「當時那台機器沒有人在用」。

### 11.4 空白格二：fallback metadata 退到什麼

**先講結論**：`codex debug models` 這支子指令會把**模型目錄**原樣吐成 JSON，
`gemma-4-12b-it-qat` 不在裡面 ⇒ 走 fallback。fallback **不是「少一點設定」，
是換一整套 request body 的形狀**。逐項對照（同一題、同一台、同一個 effort，
比的是 `POST /v1/responses` 的**第一通** `*.req.bin`）：

| body 欄位 | **fallback**（`gemma-4-12b-it-qat`） | **目錄模型**（`gpt-5.6-sol`） |
|---|---|---|
| `instructions`（頂層） | **有**，20,751 字元，`sha256 ac8ae107a0d72fe3476b430afb161ea4e67da2e446d778aefc44828160559807`，開頭 `You are a coding agent running in the Codex CLI, …` | **沒有這個欄位** |
| `tools`（頂層） | **有**，10 個：`exec_command` `write_stdin` `update_plan` `request_user_input` `view_image` `multi_agent_v1` `get_goal` `create_goal` `update_goal` `web_search` | **沒有這個欄位**（改成 `input[0]` 的 `{"type":"additional_tools"}`） |
| `input` | 11 項（developer skills 區塊 3,252 字元＋user 環境＋user prompt＋function_call…） | 7 項，且 `input[1]` 是一段 **17,730 字元**的 developer 訊息（＝目錄裡那一份 `base_instructions`，`sha256 cbefa6b0bede0e332d957fca70ccacf9f12f4c0ecdf81b819e5cbe1a3b16e265`，開頭 `You are Codex, an agent based on GPT-5. …`） |
| `reasoning` | `{"effort":"none","summary":"auto"}` | `{"effort":"none","context":"all_turns"}` |
| `text` | **沒有** | `{"verbosity":"low"}` |
| 多代理區塊 | **沒有** | 多 2 段 developer 訊息：`You are /root, the primary agent…`（2,264 字元）＋`<multi_agent_mode>…`（271 字元） |
| 兩邊逐位元相同的欄位 | `include`、`parallel_tool_calls`、`store`、`stream`、`tool_choice` | 同左 |

**所以「退到什麼」的答案是：退到 binary 裡編死的那一套**
（`grep -ac 'You are a coding agent running in the Codex CLI' <codex binary>` ＝ 2），
而不是伺服器目錄那一套。兩份 prompt **不是同一份**（sha256 不同、長度差 3,021 字元）。

**而且方向跟警告文字暗示的相反**。那行警告說 `this can degrade performance and
cause issues`，但在**這個**上游上：

```
目錄模型（gpt-5.6-sol）的 body ⇒ LM Studio 直接退件
  ERROR: {"error":{"message":"Invalid type for 'input'.","type":"invalid_request_error",
                   "param":"input","code":"invalid_union"}}
  requests_seen = 1   agent_rc = 1   agent_wall_s = 0.318   （run: codex_resp_refuse_catalogid）
fallback（gemma-4-12b-it-qat）的 body ⇒ 六通全部 200，兩格都拿到
```

目錄模型的那一格帶著 `use_responses_lite: true`，body 走的是把工具與指示都塞進
`input` 的那個形狀。**最可能的原因**是 `input[0].type = "additional_tools"` 這個
項目型別——錯誤訊息指的 `param` 就是 `input`、`code` 是 `invalid_union`。
⚠ **那一句是推論不是量到的**：我們沒有逐欄二分過是哪一項讓它解不開。
**量到的只有**「這個 body 被退件、那個 body 沒有」。

⇒ **在這個自架上游這一側，fallback 是走得通的那條路，目錄那套不是。**
「fallback ＝ 比較差」**是那行警告文字的說法，不是我們量到的東西**。

⚠ **不要把這句話擴大**：量到的是「**1003 上那一份 LM Studio**（版本本輪沒記，
所以引用時不要寫版本號）退掉目錄模型的 body 形狀」，**不是**「responses-lite
是壞的」，也不是「所有 OpenAI 相容端點都這樣」。換一個會講 responses-lite
的上游，結論可能整個反過來。**n = 1 個上游、1 個模型 id、1 通請求。**

### 11.5 fallback 的**上下文視窗**：量到的是一個下界，不是那個數字

`vacant_network/vrun/envmap.py` 原本把這一格記成「跟 Claude Code 的 200k 假設同型的洞」。
同型的部分成立（它會改變送出去的 input），**但這一格量得到的東西比較少**：

**量得到的**——那個數字是**活的**，而且改它會改 bytes。`codex debug prompt-input`
把「模型看得到的輸入」原樣吐出來，拿 `-c model_context_window=N` 掃一遍
（同一台、同一份 config，只差那一個覆寫）：

```
            未覆寫（fallback）  items=2  total_chars=3675  skills_block=3332
            cw=1000000／400000／272000／262144／131072／65536／32768
                               items=2  total_chars=3675  skills_block=3332   ← 與未覆寫同長
            cw=30000           items=2  total_chars=3326  skills_block=2983
            cw=28672           items=2  total_chars=3326  skills_block=2983
            cw=26000           items=2  total_chars=3194  skills_block=2851
            cw=24576           items=2  total_chars=3078  skills_block=2735
            cw=22000           items=2  total_chars=2874  skills_block=2531
            cw=20480           items=2  total_chars=2750  skills_block=2407
            cw=18432           items=2  total_chars=2586  skills_block=2243
            cw=17408           items=2  total_chars=2506  skills_block=2163
            cw=16384           items=2  total_chars=2430  skills_block=2087
            cw=8192            items=2  total_chars=1776  skills_block=1433
            cw=4096            items=2  total_chars=1448  skills_block=1105
            cw=2048            items=2  total_chars=1265  skills_block= 922
```

視窗調小，`<skills_instructions>` 區塊就被砍短（codex 另外印一行
`warning: Skill descriptions were shortened to fit the skills context budget.`）。
⇒ **這個數字直接改變「逐字落盤」的內容，而且 `model_context_window` 這個覆寫鍵
是活的**（binary 裡 27 筆、`--strict-config` 也不退件）。

**量不到的，以及為什麼**——**fallback 實際用的那個數字，這裡讀不出來**：

1. **wire 上沒有它。** request body 裡沒有任何 context/max-tokens 欄位
   （上表逐欄比過）。proxy 只看得到 bytes，看不到 client 心裡的數字。
2. **`codex debug models` 只吐目錄**（8 個 slug，全部 `context_window: 272000`、
   `max_context_window: 272000`、`effective_context_window_percent: 95`、
   `truncation_policy: {"mode":"tokens","limit":10000}`）。
   **fallback 不在那份目錄裡**——它是 binary 裡的預設值，那支指令不吐它。
3. **`codex doctor --json` 沒有這個欄位**（掃過 `.checks.*`，只有
   `model = gemma-4-12b-it-qat`、`model provider = vacantprobe`）。
4. **`codex exec --json` 的事件流也沒有**（`thread.started`／`turn.started`／
   `item.completed`／`turn.completed` 四種事件，沒有任何 `context_window`／
   `token_count` 欄位）。
5. 上面那支量具**會飽和**：`skills_block` 在 **32,768 以上就固定在 3,332**，
   而未覆寫的 fallback 也是 3,332。⇒ 只推得出 **fallback ≥ 32,768**（下界），
   **推不出上界**，更推不出那個數字本身。
   ⚠ 而且那個下界**帶一個假設**：量的其實是「skills 預算」不是視窗本身，
   要它等價於視窗得假設預算對視窗單調。上表在 2,048–32,768 這段**實測是單調的**
   （922 → 3,332 一路不回頭），但**單調性只在量過的那一段成立**。

⇒ 照鐵律 3 的 `infra_void` 規矩寫死：**「fallback 的 context window ≥ 32,768」
是量到的（帶上面那個單調性假設）；「fallback ＝ 128k／200k／272k」都沒量到，不准寫。**
要拿掉這個不確定性有一個**不必知道那個數字**的辦法：
**`-c model_context_window=<你自己上游的真視窗>` 自己釘死**，
就跟 Claude Code 那格要自己設 `CLAUDE_CODE_MAX_CONTEXT_TOKENS` 一樣。
⚠ **本節沒有量那個釘法在長任務上的效果**——本輪每格只有 **6 通**、
第一通 46,558 bytes（fallback 那格），**離任何一個視窗都很遠，
`shortened`／壓縮在四個正式格裡從頭到尾沒有觸發過**
（那行 `shortened` 警告只在 `-c model_context_window` 刻意調小的探針上出現）。

### 11.6 收據驗證（先負控制再驗該跑）

```
$ python3 -m vacant_network.vrun.verify_receipts --selftest
selftest: PASS                                   ← 負控制：它抓得到壞鏈

$ python3 -m vacant_network.vrun.verify_receipts --glob /var/tmp/vacant_codex_chat/rd_chat_refuse
rd_chat_refuse            RUN-ON  2  2  0  1  1  2691d9488ebc3d17…  OK   總判：OK
$ … rd_chat_deliver       RUN-ON  2  2  0  1  1  df52af988c1c807b…  OK   總判：OK
$ … rd_resp_refuse        RUN-ON  2  2  0  1  1  ffd503694a4f47b5…  OK   總判：OK
$ … rd_resp_deliver       RUN-ON  2  2  0  1  1  9e7b5a66471a2769…  OK   總判：OK
$ … rd_resp_refuse_catalogid RUN-ON 2 2 0 1 1  1d5b6634350f191f…  OK   總判：OK
```

**五個 run 全部 `entries_n=2 / verified_n=2 / failed_n=0 / chain_ok=true`。**
⚠ 連**沒送出任何請求**的那兩格也有完整收據鏈——
**收據鏈驗得過不代表 agent 跑過**，那是兩件事。

### 11.7 逐字落盤（可複製貼上）

```
# 共同環境（四格只差 VACANT_CODEX_WIRE 與工作區裡那份 TASK.md）
export PATH=/home/user1/.local/bin:/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
export VACANT_RUN_UPSTREAM_OPENAI=http://100.119.113.56:1234/v1     # 1003
export VACANT_AGENT_MODEL=gemma-4-12b-it-qat
export VACANT_CODEX_REASONING_EFFORT=none                            # 1003 是 thinking 模式
VACANT_CODEX_WIRE=chat|responses python3 -m vacant_network.vrun.launcher \
    --workspace <ws> --run-dir <rd> \
    --suite <repo>/ops/gain/r535/bank/s1_01_addmul/tests_visible \
    --task-id codex_<cell> --sandbox none --test-timeout 30 \
    --timeout 300|1200 --json \
    -- <wrap_agent.sh> codex "Read TASK.md and do what it says. Use your tools to write the file."

# fallback 那一格（不碰真模型，端點指到 127.0.0.1:1 就夠）
CODEX_HOME=<新的 mktemp -d> codex debug models                       # 目錄，JSON
CODEX_HOME=<同上>           codex debug prompt-input                 # 模型看得到的輸入
CODEX_HOME=<同上>           codex debug prompt-input -c model_context_window=16384
```

⚠ **工作樹是 `git worktree add --detach` 加的，跑完就 `git worktree remove` 了**
（vacant-dev 當時只剩 3.6 G，一份 clone 788 MB；移掉之後回到 4.9 G）。
收據還在（`/var/tmp/vacant_codex_chat/{rd_*,ws_*}` 共 2.5 MB），**但要重驗得先把碼加回來**：

```
cd ~/vacant/Vacant && git worktree add --detach /var/tmp/vacant_codex_chat/repo 9eeb1d9
cd /var/tmp/vacant_codex_chat/repo && python3 -m vacant_network.vrun.verify_receipts --selftest
python3 -m vacant_network.vrun.verify_receipts --glob /var/tmp/vacant_codex_chat/rd_resp_deliver
```

⚠ **`/var/tmp` 沒有備份、會被清。** 上面抄的是關鍵欄位不是原始 bytes（同附錄 A 的規矩）。

### 11.8 這一節**沒有**說的事

0. **最重要的那一條**：chat 那兩格 **不是拒交格／交付格**。
   `requests_seen = 0` ⇒ **中介沒發生** ⇒ 等級是 **L-none**。
   **不准寫成「兩格都 exit 20 所以閘門有牙齒」**（§11.1／§11.2）。
   這一輪**沒有**讓 Codex 多拿到任何一格——`/goal` 的四家 L-real 名單**不變**。
1. **不是**「Codex 不支援 chat/completions」——量到的是
   **`codex-cli 0.147.0` 的設定層只接受 `wire_api = "responses"`**，
   而且 `codex features list` 那 104 個旗標裡沒有能打開它的。
   **沒有反編譯**，所以「binary 裡還有沒有那條程式碼」不知道。
   §1 矩陣那一格寫的是 0.153.2（2026-09-18、別台、假上游），
   **那一輪沒有試過 `wire_api="chat"`**，所以**不知道** 0.153.2 是不是一樣。
   **兩個版本號不可以混寫成一個。**
1a. **也不是**「`vacant run` 接不通 chat/completions」——pi 與 OpenCode 的格子
   走的就是那條 wire（§1、§8）。接不通的是 **Codex 這一家的這個版本**。
2. **不是**「fallback 比較好」。量到的是**在 LM Studio 這個上游上**，
   目錄模型的 body 被退件而 fallback 的沒有。換上游可能反過來。
3. **不是**「fallback 的 context window 是某某數字」。量到的只有 **≥ 32,768**。
4. **不是**「effort=none 沒有代價」。本輪四格全帶著它跑（1003 是 thinking 模式），
   **代價沒有量**，而且每格只跑 1 次。
5. **不是** effect size。每一格 n=1，沒有對照組、沒有換題、沒有換模型。
6. **跨 agent 的話一句都不要說**：本節只量了 Codex。§11.3 那個
   `39c19a7a…` 撞號是**同一題同一個上游的巧合**，不是「三家會寫一樣的錯」。
7. 沿用 §7 的所有邊界：proxy **records，不 verifies**；
   `vacant run` 單獨只有 L3。
8. **收據鏈驗得過不代表跑過**：chat 那兩格的收據一樣是
   `verified_n=2 / chain_ok=true`（§11.6）。**收據證明的是「這份紀錄沒被改過」，
   不是「裡面記的事情發生過」。** 要判有沒有發生，看 `requests_seen`。

---

## 12. Hermes Agent × 真模型（L-none → **L-real**，2026-09-19）

**矩陣最後一個完全沒量過的 agent。** 跟 §8／§9／§10 同一個形狀（同一題、
同一個判斷層、同一把驗章尺），差別在三處：**(a) 它從來沒被假上游量過**，
所以這一節是它唯一的證據；**(b) 上游是 1004 不是 1003**；
**(c) 它在這台機器上本來不存在，是本次裝的。**

- 機器：vacant-dev（`100.124.254.83`）· **Hermes Agent 0.19.0**（`2026.7.20` build）
  **本次安裝**：`python3 -m venv --without-pip` ＋ `get-pip.py` ＋
  `pip install hermes-agent`（**沒有**用官方的 `curl … install.sh | bash`，
  那支會另外裝 uv／Python 3.11／Node.js／ripgrep／ffmpeg）。
  裝在 `/var/tmp/vacant_hermes/hv`，**208 MB**，零編譯、無 GPU 依賴
  （`hermes-agent` 的 120 條 `requires_dist` 幾乎全是 extras，base 只有
  openai／httpx／pydantic／rich 那一類）。
  ⚠ vacant-dev 的 `python3 -m venv` **會失敗**（沒裝 `python3-venv`／ensurepip），
  `--without-pip` ＋ `get-pip.py` 是繞過它的無 sudo 解。
- 上游：`http://100.86.226.21:1234/v1`（**1004**，載著 `gemma-4-12b-it-qat`）。
  用 1004 不用 1003 是因為 **1003 當時 4 串滿載**（r530vrun）。
  ⚠ **1004 不是 thinking 模式**（1003 是）——判準是回應裡有沒有
  `choices[0].message.reasoning_content`，**不是** `usage.reasoning_tokens`
  （兩台都回 `None`，那個欄位是壞的）。所以 §10.7 那種 reasoning runaway
  在這一節**不可能觀察到**，這裡沒遇到不算證據。
- 接線：**設定路線**（`wrap_agent.sh hermes` ⇒ `HERMES_HOME` ＋ `config.yaml`）。
  **不是零接線**，理由見 §12.2。
- 題目：**現成的** `ops/gain/r535/bank/s1_01_addmul`（沒有為了這次新造題）
- 判斷層：`vacant_network/vrun/launcher.py`，`--suite` 指到**工作區外**的 bank 路徑
- 落盤：vacant-dev 的 `/var/tmp/vacant_hermes/rd_*`（收據、`rows.jsonl`、
  `wire_RUN-ON/{index.jsonl,*.req.bin,*.resp.bin}`、`_frozen_RUN-ON/`）。
  **`/var/tmp` 沒有備份、會被清**——下面抄的是關鍵欄位不是原始 bytes（同附錄 A 的規矩）。
  repo 也不是完整 checkout：只 `git archive` 了 `vacant_network/` ＋ `ops/vacantrun/` ＋
  那一題的 bank（**1.4 MB**），因為 vacant-dev 當時只剩 4.9 G，
  **一份 worktree 要 789 MB**。

### 12.0 先解決那個**以為會是障礙的障礙**：上游要會講什麼

§9 的 Claude Code 靠「LM Studio 原生吃 `/v1/messages`」，§10 的 Codex 靠
「LM Studio 有開 `/v1/responses`」。Hermes 走的是**最普通的那一條**——
`POST /v1/chat/completions`——所以這一格的可搬運性是三者裡最高的：
任何 OpenAI 相容端點都講這條。

**但它多要了一樣東西**，而且是 Hermes 自己的硬條件：

> Hermes Agent 對 agent 用途**要求至少 64,000 tokens 的上下文**，
> 小於就在啟動時拒絕（官方 providers 文件寫在 Ollama 那一段）。

1004 的 `gemma-4-12b-it-qat` 是 `context_length: 262144` ÷ 4 槽 ＝ 每槽 65,536，
剛好過線。`wrap_agent.sh` 寫進 config 的 `context_length: 65536` 就是這個數字，
可用 `VACANT_HERMES_CONTEXT` 改。
⚠ **「過線」是本次這個配置過線**，不是「Hermes 配任何本地模型都過線」。

### 12.1 `command -v` 說沒裝——這次是真的沒裝（第三次量同一件事，結論相反）

§9.7（Claude Code）與 §10.1（Codex）都記過「`command -v` 空白只是 PATH 假象」。
這一格**先按那個教訓查了，然後結論仍然是沒裝**：

```
$ ssh user1@vacant-dev 'bash -lic "command -v hermes; ls -d ~/hermes-agent"'
（空）
ls: cannot access '/home/user1/hermes-agent': No such file or directory
$ ls ~/.local/bin
chrome-headless-shell
claude
codex
```

⇒ **「沒量到」與「量到 0」的差別在這裡具體化**：前兩次用錯方法得到的「沒裝」
是假的，這一次用對方法得到的「沒裝」是真的。**方法對了才有資格說沒有。**
然後才有下一步——**裝它**，因為「裝不裝得起來」本身就是相容性矩陣要回答的問題。

### 12.2 **這一節最重要的一段**：Hermes 是「一個旗標」而不是「零接線」

`CUSTOM_BASE_URL` 2026-09-18 就在 `envmap.REDIRECT_VARS` 裡了（標記未實測）。
問題是：**它一個人夠不夠？** 四格實測，答案是**不夠，但只差一點點**。

Hermes 0.19.0 解 base_url 的順序（`hermes_cli/runtime_provider.py`，
`hermes_constants.py:1259`）：

```
--base-url → CUSTOM_BASE_URL → config.yaml 的 model.base_url
           → OPENROUTER_BASE_URL → 編死的 https://openrouter.ai/api/v1
```

**但在這條鏈之前還有一道閘：有沒有選 provider。** 四格：

| 格 | 設定 | 結果 |
|---|---|---|
| **A**（直測，無 proxy） | 全新 `HERMES_HOME`，只有 `CUSTOM_BASE_URL`，`-m <模型>` | ❌ `hermes -z: agent failed: No inference provider configured. Run 'hermes model' to choose a provider, or set an API key (OPENROUTER_API_KEY, OPENAI_API_KEY, etc.) in ~/.hermes/.env.` |
| **B**（直測） | ＋ `--provider custom`，**不寫 config.yaml** | ✅ `PONG` |
| **C**（直測） | config 只有 `provider: custom`（**沒有 base_url**）＋ `CUSTOM_BASE_URL` | ✅ `PONG` |
| **D**（直測） | config `provider: custom` ＋ `base_url: http://127.0.0.1:9/v1`（**死埠**）＋ `CUSTOM_BASE_URL` 指真上游 | ✅ `PONG` ⇒ **環境變數蓋過 config** |

⇒ 兩句話都要講，**只講一句就會誤導**：

1. **對全新環境：不是零接線。** 少了 provider 就 `requests_seen = 0`。
   最小接線是**一個 CLI 旗標** `--provider custom`（B 格），比 pi／Codex／
   OpenCode 的「寫一份設定檔」都輕，但**不是零**。
2. **對已經設好自訂 provider 的使用者：是零接線。** `CUSTOM_BASE_URL`
   優先序高於他自己 config 裡的 `base_url`（D 格），`vacant run` 包上去就轉向了，
   **不必動他的 `~/.hermes/config.yaml`**。

#### 對照 A（經 proxy）：**假拒交格長什麼樣**

把 A 格放進 `vacant run` 跑一次，因為這正是今天另一條線在 Codex chat wire 上
踩到的那個坑：

```
task_id         = hermes_ctl_noprovider
accepted        = false   stop_reason = visible_fail   退出碼 = 20
requests_seen   = 0       wire_by_protocol = {}        agent_rc = 1
agent_wall_s    = 0.721   visible = 0 / 2
agent stderr    = hermes -z: agent failed: No LLM provider configured.
                  Run `hermes model` to select a provider, or run `hermes setup`
                  for first-time configuration.
```

`visible_fail` ＋ exit 20 **看起來**像閘門有牙齒，但 `requests_seen = 0`
＋ `agent_rc = 1` ⇒ **中介從來沒發生，閘門擋的是一個從來沒產生過的東西**。
**等級是 L-none 不是 L-fake。**

#### 對照 C（經 proxy）：**fail-open 才是真正嚇人的那一格**

把 `CUSTOM_BASE_URL` 拿掉、config 也不寫 base_url，只留 `--provider custom`：

```
task_id         = hermes_ctl_nocustom
accepted        = false   stop_reason = visible_fail   退出碼 = 20
requests_seen   = 0       wire_by_protocol = {}        agent_rc = 0    ← **0**
agent_wall_s    = 2.435   visible = 0 / 2
agent stdout    = HTTP 401: Missing Authentication header
```

⇒ Hermes **沒有報錯**，它安靜地走到鏈尾、去打編死的
`https://openrouter.ai/api/v1`，拿了一個 401 回來。
**這一格跟一個真的拒交格在收據上只差 `requests_seen` 一個欄位**
（連 `agent_rc` 都是 0，跟 §8–§10 三個真拒交格一樣）。
⇒ **`envmap` 誠實邊界 2「名單漏一個變數不會有任何錯誤訊息」的活體標本。**
結構性補法仍然是 `block_egress.sh`（V3），~~沒量過~~
**2026-09-19 就是拿這一格去量的**（量過了：[`decisions/DECISION_20260919_BLOCK_EGRESS_V3.md`](../decisions/DECISION_20260919_BLOCK_EGRESS_V3.md)、[`docs/VACANT_RUN.md`](VACANT_RUN.md) §5.1）：
同一支 wrapper、同一個模型，封鎖之後 agent stdout 從 openrouter 回的
`HTTP 401: Missing Authentication header` 變成 `API call failed after 3 retries:
Connection error.` ⇒ **這條洩漏路徑被擋住了**。
⚠ **但收據沒變**：兩格的 `run_*.json` 26 個判斷欄位（含 `accepted`／`stop_reason`／
`requests_seen`／`agent_rc`／`ws_end_sha256`）**逐字相同**，
差別只在 `agent_stdout.log` 與耗時。**V3 改變的是世界，不是收據。**

**金鑰有沒有跟著漏出去？** 把 `OPENROUTER_BASE_URL` 指到一個本機 sink
（不出網）重跑，逐字收到 **21 通**，每一通的標頭都是：

```
authorization: Bearer no-key-required
```

launcher 的 sentinel（`vacant-run-<uuid>`）**一次都沒出現**。
⚠ **但那是 Hermes 自己的 host-gate 做的**（`base_url_host_matches`，
GHSA-76xc-57q6-vm5m／#28660：迴圈位址與 IP 不給任何廠商金鑰），
**不是 Vacant 給的保證**。上游換成一個 hostname 像 `openai.com` 的位址時，
同一段程式碼**會**把 `OPENAI_API_KEY` 送出去——那一格**沒量**。

那 21 通同時揭露一件 §12.4 會用到的事：Hermes 在第一通模型請求之前會
**嗅探上游是哪一種 server**——`/api/v1/models`、`/api/api/tags`（Ollama）、
`/api/v1/props`＋`/api/props`（llama.cpp）、`/api/version`、`/api/api/show`，
用三種 HTTP client（`httpx`、`requests`、`OpenAI/Python`）。
sink 每通都回 401 所以它重試了三輪；**真上游答得出來就只剩 2 通**（§12.4）。

### 12.3 模型 id：**第四個資料點，也是放行——而且連警告都沒有**

§2.3＝OpenCode 擋、§9.1＝Claude Code 印警告後放行、§10.2＝Codex 印警告後放行。
Hermes 是第四個：

- `gemma-4-12b-it-qat` 原樣出現在 wire 的 `model` 欄位（§12.5 逐字），
- **沒有任何警告**，六通全部 200。

⇒ 四家在這一格是 **3 放行 ∶ 1 擋**。
⚠ **但這不是同一個位置的同一個問題，不可以直接加總。** OpenCode 擋的是
**內建 provider**（models.dev 註冊表）配上不在表裡的 id；Hermes 這一格走的是
**自訂 provider，本來就沒有註冊表可查**，所以「放行」幾乎是定義使然。
「Hermes 對內建 provider（openrouter／nous portal）餵陌生 id 會怎樣」**沒量**
——那條路要憑證，本次一律不碰。
**仍然是四次實測，不是一條規則；第五家還是要自己量。**

### 12.4 出廠接線與逐字落盤

```
指令（兩格只差工作區裡那一份 TASK.md）
  export PATH=/var/tmp/vacant_hermes/hv/bin:$PATH
  export VACANT_RUN_UPSTREAM_OPENAI=http://100.86.226.21:1234/v1
  export VACANT_AGENT_MODEL=gemma-4-12b-it-qat
  python3 -m vacant_network.vrun.launcher \
      --workspace <ws> --run-dir <rd> \
      --suite <repo>/ops/gain/r535/bank/s1_01_addmul/tests_visible \
      --task-id hermes_real_<cell> --sandbox none --test-timeout 30 \
      --timeout 1200 --json \
      -- <repo>/ops/vacantrun/wrap_agent.sh hermes \
         "Read TASK.md and do what it says. Use your tools to write the file."
```

#### `hermes_real_asis`（拒交格）

```
task_id         = hermes_real_asis
accepted        = false   refused = true   stop_reason = visible_fail
退出碼           = 20
requests_seen   = 6   wire_by_protocol = {'openai': 6}   wire_errors = 0
proxy paths     = {'GET /api/v1/models -> 200 [openai]': 2,
                   'POST /v1/chat/completions -> 200 [openai]': 4}
upstreams_seen  = ['http://100.86.226.21:1234/api/v1/models',
                   'http://100.86.226.21:1234/v1/chat/completions']
upstreams_defaulted = ['anthropic']   ← **這一跑沒有任何一通走 anthropic**（同 §10.6）
visible         = 1 / 2   ← **不是 0/2**，見下
agent_rc        = 0       ← Hermes 自己說成功了，閘門說沒有
agent_wall_s    = 13.334  run_wall_s = 13.659   retry = none   attempts_used = 1
ws_start_sha256 = 03aeefafe6f8bb75eee9006f14eb3f0eb436a03214ffac42bd28565e02228a61
ws_end_sha256   = 64de4ddf8c6cb02c4698fa8f6e03d402d5a308f3fc17dcc430946f20d29f1fc7
wire_digest     = d7d609d8caee2a58360224163717c454d9fda501876702704dc5339e10c81215
verdict_sha256  = 4574954a58cd23f6218a5eb259a5537f906ae3e466a7614326024a4512ae4ebf
verdict_hash    = 2e89b17f1d22214b93c89515bdd7582be64b45485122382b9e70acfc8eb50045
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
failures        = test_visible.py::check_02_mul — exception: ImportError:
                  cannot import name 'mul' from 'solution'
```

落地的檔案逐字（Hermes 自己寫的，工作區進去時只有 `TASK.md`）：

```python
def add(a: float, b: float) -> float:
    return a + b

def multiply(a: float, b: float) -> float:
    return a * b
```

**`agent_rc = 0` 第四次出現。** §8（OpenCode）、§9（Claude Code）、§10（Codex）
各一次，現在 Hermes 也一次：**四個不同 agent、三條不同 wire，拒交格全部是
「agent 宣告完成、退出碼 0，閘門在行程結束那一刻擋下來」。**

⚠ **這一格是四個裡唯一的「半對」**：`add` 對了、`mul` 寫成 `multiply`
⇒ `visible 1/2`。另外三家都是 0/2。
⇒ §10.3 那句「敘述含糊時錯法會分岔」再加一個例子，而且分岔到**部分通過**
這個新的形狀。**n=1，不是效果量。**

#### `hermes_real_deliver`（交付格）

```
task_id         = hermes_real_deliver
accepted        = true    refused = false   stop_reason = visible_pass
退出碼           = 0
requests_seen   = 6   wire_by_protocol = {'openai': 6}   wire_errors = 0
proxy paths     = {'GET /api/v1/models -> 200 [openai]': 2,
                   'POST /v1/chat/completions -> 200 [openai]': 4}
visible         = 2 / 2
agent_rc        = 0   agent_wall_s = 12.787  run_wall_s = 12.986
retry = none   attempts_used = 1
ws_start_sha256 = 1407f6cb722df0ec646475116f735bc3c42a7cf8ff3937ca90219a8d9d9c4feb
ws_end_sha256   = d1ed637b7ae45b8f71ddc69e113d9f52a0a998cf8df3dd008bc0bc04c9488f18
wire_digest     = aa79b4db2a7c6eca1cf7c1c56dc75224d7463ea842076e1b15e2f32c7efd67e0
verdict_sha256  = 29402d2f81445b7af2fd81e38ad624b635bcb95ea41c83b2e5bcf2e1ececbd78
verdict_hash    = aad3f72a08bdc1c70cc636710525e4e663629762f5beea1540591700a0cd2d97
receipts        = entries_n=2 verified_n=2 failed_n=0 chain_ok=true
```

**交付格的 `ws_end_sha256` ＝ `d1ed637b…`，與 §8 OpenCode、§9 Claude Code、
§10 Codex 的交付格逐位元相同。** 四個 agent、三條 wire 協定、兩台不同的
LM Studio 機器（1003／1004）、同一個模型、同一題——交付格落地的東西一樣。

⚠ **「四個 agent」這個數字在 2026-09-19 傍晚的同條件複製裡變成 4/5**（§13.1）：
在 1004 上重跑五個 agent，pi／OpenCode／Codex／Hermes 都是 `d1ed637b…`，
**Claude Code 兩次都是 `14332382…`**（多了兩行 docstring）。
本段原文不改，但**不要把它引用成一條性質**——它是一次觀察。

#### 對照 B（經 proxy）：**環境變數那條路也通**

`--provider custom` ＋ launcher 設的 `CUSTOM_BASE_URL`，**完全不寫 config.yaml**：

```
task_id         = hermes_ctl_envonly
accepted        = true   stop_reason = visible_pass   退出碼 = 0
requests_seen   = 6   wire_by_protocol = {'openai': 6}   agent_rc = 0
visible         = 2 / 2   agent_wall_s = 12.576
ws_end_sha256   = d1ed637b7ae45b8f71ddc69e113d9f52a0a998cf8df3dd008bc0bc04c9488f18
verdict_hash    = 8d739fb00853d89572a8dd825031edfaee18e8db86bade3a94af3cf3072e821c
```

⇒ **`envmap.REDIRECT_VARS` 裡那個 `CUSTOM_BASE_URL` 是真的有用的**，
這是它從 2026-09-18 加進去以來的第一個 wire 證據。

#### 複製一次：**用最後 commit 的那一份 wrapper 重跑**

上面兩格是用還沒定稿的 `wrap_agent.sh` 跑的（可執行的幾行相同，註解不同）。
**「文件裡的數字是用 repo 裡那一份跑出來的」不能靠讀 diff 保證**，所以定稿之後
原封不動再跑一次：

| | 第一跑 | 第二跑（定稿版） |
|---|---|---|
| 拒交格 `ws_end_sha256` | `64de4ddf…` | **`64de4ddf…`（逐位元相同）** |
| 拒交格 | exit 20 · `rs=6` · `agent_rc=0` · `visible 1/2` | exit 20 · `rs=6` · `agent_rc=0` · `visible 1/2` |
| 交付格 `ws_end_sha256` | `d1ed637b…` | **`d1ed637b…`（逐位元相同）** |
| 交付格 | exit 0 · `rs=6` · `agent_rc=0` · `visible 2/2` | exit 0 · `rs=6` · `agent_rc=0` · `visible 2/2` |
| 牆鐘 | 13.334 ／ 12.787 s | 21.787 ／ 13.116 s |
| 收據 | `--selftest` PASS，兩跑 `chain_ok` | `--selftest` PASS，兩跑 `chain_ok` |

第二跑的 `verdict_hash` 不同（`6886fa72…`／`c0ddfec9…`）——**那是對的**：
收據鏈綁 run 的身分與時間，不是只綁工作區。
⚠ **牆鐘差 8 秒不是效能數字**（1004 上當時還有別的東西）。
⚠ **n=2 仍然是 n=2。** 落地檔案兩次相同不代表這個模型在這題上是決定性的。

### 12.5 wire 逐字（拆 `*.req.bin`）——**鐵律 3 在第三條 chat/completions 上成立**

```
hermes_real_asis（拒交格）
  GET  /api/v1/models      200  req=0      resp=2949   0.0065s
  POST /v1/chat/completions 200  req=48496  resp=1318   5.979s
        model='gemma-4-12b-it-qat' stream=True n_messages=2 (system=1) tools=17
        other={'max_tokens': 65536, 'stream_options': dict}
  GET  /api/v1/models      200  req=0      resp=2949   0.0073s
  POST /v1/chat/completions 200  req=48804  resp=2342   0.773s   n_messages=4
  POST /v1/chat/completions 200  req=49646  resp=2490   1.554s   n_messages=6
  POST /v1/chat/completions 200  req=50315  resp=29376  2.211s   n_messages=8

hermes_real_deliver（交付格）
  同樣的形狀：GET ×2 ＋ POST ×4，n_messages = 2 → 4 → 6 → 8，tools 固定 17
```

- **每一通重放完整 `messages` 陣列**（2→4→6→8，`system` 恆為 1），
  **沒有** `store`、**沒有**任何伺服器端 session id
  ⇒ **逐字落盤成立，鐵律 3 沒有破**（與 §8 chat/completions、§9 Messages、
  §10 Responses 同結論；chat/completions 這條**第二個 agent** 也驗過了）。
- `tools` 固定 17 個：`clarify, delegate_task, execute_code, memory, patch,
  process, read_file, search_files, session_search, skill_manage, skill_view,
  skills_list, terminal, text_to_speech, todo, vision_analyze, write_file`。
  **寫檔走的是 `write_file`，不是 shell**——這跟 §1 那句「四個框架的 shell 工具
  都吃 `{"command": str}`」是不同的路，Hermes 是第五個而且**不走 shell**。
- `max_tokens: 65536` 每通都帶（來自 config 的 `context_length`）。
  ⚠ 那是**要求上游一次最多吐 65,536 token**，對小一點的 server 可能被退件；
  本節沒量過那種上游。

#### `GET /api/v1/models` 那兩通：**一個看得見但沒踩到的洞**

base_url 是 `<proxy>/v1`，但探測打的是 **`<proxy>/api/v1/models`**
——**不在設定的 base 底下**。它在 LM Studio 上回 200，是因為 LM Studio 自己
另有一套 `/api/v1` REST API（回的是 `{"models":[{"key":…,"max_context_length":…}]}`，
**跟 `/v1/models` 的 `{"data":[{"id":…}]}` 是兩種 schema**）。

⇒ 三件事要分開講：

1. **這一跑沒出網**：`upstreams_seen` 只有 1004 那一台，`wire_by_protocol`
   裡沒有 anthropic。跟 §10.6 一樣，`upstreams_defaulted = ['anthropic']`
   說的是「那條路沒人指定」，**不是**「已經出網了」。
2. **`requests_seen = 6` 裡有 2 通不是模型通道**（§6.2 那條規則的第四個例子）。
   要下「模型通道被中介到了」的結論看的是 `path`，不是計數。
3. **換一個嚴格的 OpenAI 相容上游，那兩通會 404**。會不會因此壞掉
   **本節沒量**——這一格跟 §6.1 的 `HEAD /api/hello` 是同一型的未知。

### 12.6 收據驗證（先負控制再驗該跑）

```
$ python3 -m vacant_network.vrun.verify_receipts --selftest
selftest: PASS                                          ← 負控制：它抓得到壞鏈

$ python3 -m vacant_network.vrun.verify_receipts --glob /var/tmp/vacant_hermes/rd_hermes_real_asis
rd_hermes_real_asis      RUN-ON   2   2   0   1   1   2e89b17f1d22214b…  OK   總判：OK
$ python3 -m vacant_network.vrun.verify_receipts --glob /var/tmp/vacant_hermes/rd_hermes_real_deliver
rd_hermes_real_deliver   RUN-ON   2   2   0   1   1   aad3f72a08bdc1c7…  OK   總判：OK
```

### 12.7 這一節**沒有**說的事

1. **不是**「Hermes 配 Vacant 寫程式比較好」。兩格各跑 **2 次**（定稿前後各一，
   落地檔案逐位元相同），沒有對照組、沒有換題、沒有換模型。
   **存在性證明，不是效果量。**
2. **不是**「零接線」。最小接線是 `--provider custom`（§12.2）。
   **只有在使用者已經設好自訂 provider 的前提下**才是零接線。
3. **不是**「Hermes 的所有 provider 都行」。量到的只有 `provider: custom`。
   Nous Portal、OpenRouter、Anthropic OAuth、Copilot 那些**要憑證的路一條都沒碰**
   （紅線：不動任何人的登入憑證）。其中 **Copilot ACP** 那條特別值得警告——
   它 spawn 一個外部行程講 ACP，**跟 Codex 的 `wss://` 是同一型的邊界嫌疑**，
   但**沒量，不准寫成已知**。
4. **不是**「全部流量都留在本機」的保證。本節兩格**實際上**沒有一通出網，
   但 §12.2 的對照 C 證明**漏一個變數就會出網而且沒有錯誤訊息**。
5. **不是**「Hermes 只打模型通道」。它會探 `/api/v1/models`（§12.5），
   而且 `hermes postinstall` 會去抓 node／browser／ripgrep／ffmpeg
   ——**本次沒跑那支**，預設工具集不需要它。
   **「Hermes 在 `vacant run` 底下有沒有開 proxy 看不到的第二條連線」沒量**。
   ⚠ 2026-09-19 的 V3 量測（量過了：[`decisions/DECISION_20260919_BLOCK_EGRESS_V3.md`](../decisions/DECISION_20260919_BLOCK_EGRESS_V3.md)、[`docs/VACANT_RUN.md`](VACANT_RUN.md) §5.1）**也沒有回答這一題**：
   它量的是「封鎖之後出不出得去」，不是「封鎖之前開了幾條連線」。
   其餘四個 agent 在封鎖之下**一律沒量**。
6. **不是**「0.16.0 也是這樣」。`examples/run_hermes.py` 印的是
   `Hermes Agent v0.16.0`，本節量的是 **0.19.0**。
   `vacant_network/hermes_substrate.py` 的 `provider: vllm` 在 0.19.0 是 `custom` 的別名。
7. **1004 不是 thinking 模式** ⇒ §10.7 那種 reasoning runaway 在這一節
   **不可能被觀察到**。「Hermes 在 1003 上會不會 runaway」**沒量**。
8. 沿用 §7 的所有邊界：proxy **records，不 verifies**；
   `vacant run` 單獨只有 L3。

### 12.8 踩到的坑

- **`command -v` 空白這次是真的**（§12.1）——但**要先用 `bash -lic` 才有資格說**。
- **vacant-dev 的 `python3 -m venv` 是壞的**（缺 `python3-venv`）：
  `Error: Command '[…/hv/bin/python3', '-Im', 'ensurepip', …]' returned non-zero`。
  無 sudo 解＝`--without-pip` ＋ `get-pip.py`。
- **`hermes -z` 的退出碼不可信**：對照 A／C 兩格 agent 都失敗了，
  一格 `rc=1`、另一格 **`rc=0`**。⇒ **判交付要看閘門與 `requests_seen`，
  不是 agent 自己的退出碼**（這也是 §12.4 `agent_rc=0` 那一段的另一面）。
- **管線會吃掉退出碼**：`hermes … | tail` 之後 `$?` 是 `tail` 的。
  第一次量 A 格時就這樣印出 `RC_A=0`，差點把「失敗」讀成「成功」。
- **遠端 shell 的 OSC 跳脫序列會混進 stdout**（`]7;ssh://…`）。
  本節所有數字都是從 `run_RUN-ON.json`／`rows.jsonl` 用 Python 讀的，
  不是從終端文字剖出來的。
- **`~/.hermes` 從頭到尾沒有被建立**：`wrap_agent.sh` 每跑 `mktemp -d` 一個新的
  `HERMES_HOME`。使用者自己的 Hermes 狀態（sessions／skills／`.env` 憑證）
  **一個 byte 都沒碰到**，這也是為什麼走的一定是 config 裡那個 `custom` provider。

---

## 13. 同條件複製：五個 agent × 兩格 × 兩次（2026-09-19 傍晚）

**§8–§12 的五格是分批、分機器、分時間量出來的**（1003 thinking 與 1004 非
thinking 混用、日期不同、有幾格先用假上游量過）。每一格單獨都成立，
**但它們不是一個可以一起引用的矩陣**。本節把那個缺口補掉。

- **同一台機器**（上游 1004 `http://100.86.226.21:1234`）、**同一個模型**
  （`gemma-4-12b-it-qat`）、**同一題**（`s1_01_addmul`，未改）、**同一天**
  （2026-09-19 UTC 12:49–12:58）
- **五個 agent × 兩格 × 兩次 ＝ 20 格，全部通過判準**
  （拒交 `accepted=false`／`visible_fail`／exit 20；交付 `accepted=true`／
  `visible_pass`／exit 0），`requests_seen` 4–6，`wire_errors` 全 0，
  20 條收據鏈 `--selftest` PASS 之後全部 `chain_ok`
- 逐格落盤（**進了 repo，不會被 `/var/tmp` 清掉**）：
  [`runs/v1_five_agent_matrix_20260919/`](../runs/v1_five_agent_matrix_20260919/)
- 裁決：[`decisions/DECISION_20260919_FIVE_AGENT_MATRIX.md`](../decisions/DECISION_20260919_FIVE_AGENT_MATRIX.md)

### 13.1 ⚠ 它**證偽**了本文兩處的一句話

§9.2 與 §12.4 寫過「交付格的 `ws_end` 在四個 agent 上逐位元相同（`d1ed637b…`）」。
在 1004 上重跑，**那句話只對 4/5 成立**：Claude Code 兩次都多寫了 docstring，
交付格 `ws_end = 143323827343cfb79d6008ee9dca709cf8f5f424d65dace9c285b37e1572fd1a`。

⇒ **「四個 agent 落地的東西一樣」是一次觀察，不是性質。** 換機器就變了。
§9.2／§12.4 的原文**沒有回頭改寫**（那是當時跑出來的東西），
但引用那句話時要連機器一起講。

同型的第二例：§10 的 Codex 拒交格在 1003 上是 `visible 0/2`／`ws_end = b720ee87…`；
在 1004 上是 `visible 1/2`／`39c19a7a…`（與另外三家同一個檔）。
**敘述含糊時「錯法」不可重現**（§10.3 已經寫過）；1003 是 thinking、1004 不是，
**這一條沒有被隔離，不要當成因果**。

### 13.2 本輪自己做了負控制（零網路）

`/bin/true` 與一行 `cp` 放在 agent 的位置，**一通模型都不打**：

| | exit | accepted | stop_reason | **rs** | **wire** | `agent_rc` | `chain_ok` |
|---|---|---|---|---|---|---|---|
| `ctl_norequest_refuse` | **20** | false | `visible_fail` | **0** | **`{}`** | 0 | true |
| `ctl_norequest_deliver` | **0** | true | `visible_pass` | **0** | **`{}`** | 0 | true |

⇒ **退出碼、`accepted`、`stop_reason`、`agent_rc`、`chain_ok` 五個欄位在
零通模型呼叫下全部成立。唯一分得出來的是 `requests_seen` 與 `wire_by_protocol`。**
這是 `envmap` 誠實邊界 1 的可執行版本，也是 §12.2 對照 C 那個陷阱的通用形狀。

### 13.3 這一節沒有說的事

存在性證明不是效果量（無對照臂、一題、一模型、每格 n=2）；只跑可見套件（2 題）
不含隱藏 7 題；`--sandbox none`；沒跑網路層出網封鎖。完整清單見裁決檔第七節。

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

