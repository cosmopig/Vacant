# v1 發布證據底稿：五個 agent × 兩格 × 兩次，**同一台機器、同一個模型、同一題、同一天**

> **一句話（驗得到什麼、驗不到什麼）**
> 驗得到：五個 agent 的模型通道**真的被中介**（每格 `requests_seen` 4–6 通，
> 逐通的 path／status／上游都落盤），而且交付閘門在兩個方向上都有作用
> （拒交 exit 20 ／ 交付 exit 0），20 條收據鏈外人可以在自己的機器上重驗。
> **驗不到**：這不是效果量——沒有對照臂、一題、一個模型、每格 n=2。
> 也不是「模型能力」：本輪量的是**通道與閘門**。

- 量測日期：**2026-09-19**（UTC **12:49:22 → 12:55:05**，20 格；負控制 12:57:44–45）
- 執行端：vacant-dev `user1@100.124.254.83`
- 上游：**1004** `http://100.86.226.21:1234`，`gemma-4-12b-it-qat`
- 判斷層：`vacant/vrun/launcher.py` @ commit `8ae0318b`
- 題目：`ops/gain/r535/bank/s1_01_addmul`，**一個位元組都沒改**
- 證據等級：**L-real**（真模型；五個 agent 的拒交格與交付格都過，收據可重驗）

## 一、為什麼要重跑一次已經量過的東西

五格證據（`docs/AGENT_COMPAT.md` §8–§12）是**分批、分機器、分時間**量出來的：
1003（thinking）與 1004（非 thinking）混用、日期不同、有些先用假上游量過。
**每一格單獨都成立，但它們不是一個可以一起引用的矩陣。** v1 的 README 要講
「五個 agent 實測接通」，那句話需要一張**同條件**的表。本目錄就是那張表。

## 二、量具與判準（照抄，不是這一輪自創）

| 格 | 判準（三條**全部**要成立） |
|---|---|
| **拒交格** | `accepted=false` ＋ `stop_reason=visible_fail` ＋ **exit 20** |
| **交付格** | `accepted=true` ＋ `stop_reason=visible_pass` ＋ **exit 0** |

三個**不可省**的旁證：

1. **`requests_seen > 0`** —— 唯一能證明中介發生的欄位。見第五節的負控制：
   **退出碼／`accepted`／`stop_reason`／`chain_ok` 四個欄位可以在零通模型呼叫下
   全部成立**，只有 `requests_seen` 分得出來。
2. `verify_receipts --selftest` **先 PASS**（負控制：它抓得到壞鏈）再驗該批。
3. 證據等級標明（本輪 = L-real；不與 L-fake 混講）。

拒交／交付兩格的差別**只有工作區裡那一份 `TASK.md`**：

| 格 | 放進工作區的檔 | 為什麼會是這個結果 |
|---|---|---|
| 拒交 | `TASK.md`（散文只說 "sum"／"multiplying"） | `meta.json` 的 `trap`：套件要的是 `add`／`mul` |
| 交付 | `TASK_explicit.md`（多五行 `## Interface`，把 `add(a,b)`／`mul(a,b)` 寫死） | 同一題的天花板臂 |

工作區進去時**只有一個 `TASK.md`，沒有預放 `solution.py`**；`--suite` 指到
工作區**外**的 bank 路徑。題目檔的 sha256：

```
8257ace297526128b6508eae7deec0b4d3b09e5ea2b9fc4361adb6d1ab6883a3  TASK.md
8a8e09baaa8f62653ad6cebcc1459174c7231e34c7b6be6f7f0a17d0604485e6  TASK_explicit.md
0162294aeae48a4b80aceefedaf42c3afa0d959a429ac92f9f26fbbefc1dc43b  tests_visible/test_visible.py
```

## 三、矩陣（20 格，全部通過判準）

`exit`／`accepted`／`stop`／`rs`＝`requests_seen`／`wire`＝`wire_by_protocol`／
`rc`＝`agent_rc`／`vis`＝可見驗收通過數。

| cell | exit | accepted | stop | rs | wire | rc | vis | `ws_end_sha256` | agent 牆鐘 s |
|---|---|---|---|---|---|---|---|---|---|
| pi_refuse_r1 | 20 | false | visible_fail | 4 | `{openai:4}` | 0 | 1/2 | `39c19a7a…` | 4.1 |
| pi_refuse_r2 | 20 | false | visible_fail | 4 | `{openai:4}` | 0 | 1/2 | `39c19a7a…` | 5.0 |
| pi_deliver_r1 | 0 | true | visible_pass | 4 | `{openai:4}` | 0 | 2/2 | `d1ed637b…` | 4.4 |
| pi_deliver_r2 | 0 | true | visible_pass | 4 | `{openai:4}` | 0 | 2/2 | `d1ed637b…` | 4.4 |
| opencode_refuse_r1 | 20 | false | visible_fail | 5 | `{openai:5}` | 0 | 1/2 | `39c19a7a…` | 12.1 |
| opencode_refuse_r2 | 20 | false | visible_fail | 5 | `{openai:5}` | 0 | 1/2 | `39c19a7a…` | 11.5 |
| opencode_deliver_r1 | 0 | true | visible_pass | 5 | `{openai:5}` | 0 | 2/2 | `d1ed637b…` | 18.6 |
| opencode_deliver_r2 | 0 | true | visible_pass | 5 | `{openai:5}` | 0 | 2/2 | `d1ed637b…` | 17.2 |
| claude_refuse_r1 | 20 | false | visible_fail | 5 | `{openai:1, anthropic:4}` | 0 | 1/2 | `39c19a7a…` | 51.6 |
| claude_refuse_r2 | 20 | false | visible_fail | 5 | `{openai:1, anthropic:4}` | 0 | 1/2 | `39c19a7a…` | 34.6 |
| claude_deliver_r1 | 0 | true | visible_pass | 5 | `{openai:1, anthropic:4}` | 0 | 2/2 | **`14332382…`** | 37.7 |
| claude_deliver_r2 | 0 | true | visible_pass | 5 | `{openai:1, anthropic:4}` | 0 | 2/2 | **`14332382…`** | 35.5 |
| codex_refuse_r1 | 20 | false | visible_fail | **5** | `{openai:5}` | 0 | 1/2 | `39c19a7a…` | 12.3 |
| codex_refuse_r2 | 20 | false | visible_fail | **6** | `{openai:6}` | 0 | 1/2 | `39c19a7a…` | 11.5 |
| codex_deliver_r1 | 0 | true | visible_pass | 5 | `{openai:5}` | 0 | 2/2 | `d1ed637b…` | 8.2 |
| codex_deliver_r2 | 0 | true | visible_pass | 5 | `{openai:5}` | 0 | 2/2 | `d1ed637b…` | 9.3 |
| hermes_refuse_r1 | 20 | false | visible_fail | 6 | `{openai:6}` | 0 | 1/2 | `64de4ddf…` | 17.2 |
| hermes_refuse_r2 | 20 | false | visible_fail | 6 | `{openai:6}` | 0 | 1/2 | `64de4ddf…` | 13.1 |
| hermes_deliver_r1 | 0 | true | visible_pass | 6 | `{openai:6}` | 0 | 2/2 | `d1ed637b…` | 12.7 |
| hermes_deliver_r2 | 0 | true | visible_pass | 6 | `{openai:6}` | 0 | 2/2 | `d1ed637b…` | 12.8 |

`wire_errors = 0`、`attempts_used = 1`、`retry = none`、`receipts entries_n = 2`
在 20 格全部相同。**`agent_rc = 0` 在 10 個拒交格全部出現**——
五個 agent 都宣告完成、退出碼 0，閘門在行程結束那一刻擋下來。

### 3.1 五個 agent 在拒交格的收尾原話（逐字，取自 `cells/*/agent_stdout.log`）

> **pi**：I have created `solution.py` with the required `add` and `multiply`
> functions as specified in `TASK.md`.
>
> **OpenCode**：I have created `solution.py` with the requested `add` and
> `multiply` functions as specified in `TASK.md`.
>
> **Claude Code**：I have completed the task as specified in `TASK.md`.
> I created a file named `solution.py` containing two functions: `add(a, b)`
> for summing two numbers and `multiply(a, b)` for multiplying them.
>
> **Codex**：I have created `solution.py` with the requested numeric helper functions.
>
> **Hermes**：I have read `TASK.md` and created the `solution.py` file with the
> required numeric helper functions (`add` and `multiply`).

**五句話逐字都是真的，五句話也都不足以交付**——套件要的是 `mul` 不是 `multiply`。
五個 agent 的退出碼都是 0，閘門的退出碼是 20。
⚠ 這證明的是**閘門在行程結束那一刻有作用**，**不是**「這五個 agent 比較不可靠」
（同一題、每格 n=2、無對照組）。

逐格的 proxy path（這是「中介真的發生」的逐通證據）：

| agent | proxy 收到的 path | wire 協定 |
|---|---|---|
| pi | `POST /v1/chat/completions -> 200` ×4 | OpenAI Chat Completions |
| OpenCode | `POST /v1/chat/completions -> 200` ×5 | OpenAI Chat Completions |
| Claude Code | `POST /v1/messages?beta=true -> 200` ×4 ＋ `HEAD /api/hello -> 200` ×1 | Anthropic Messages |
| Codex | `POST /v1/responses -> 200` ×5（r2 拒交格 ×6） | OpenAI Responses |
| Hermes | `POST /v1/chat/completions -> 200` ×4 ＋ `GET /api/v1/models -> 200` ×2 | OpenAI Chat Completions |

**20 格的 `upstreams_defaulted` 全部是 `[]`**，`upstreams_seen` 全部只有
`http://100.86.226.21:1234/…`。本輪把 `VACANT_RUN_UPSTREAM_OPENAI` 與
`_ANTHROPIC` **兩條都釘到 1004**，所以 §9.4 那個 `HEAD /api/hello` 出網的洞
在這 20 格裡沒有發生（那一通落在 `http://100.86.226.21:1234/api/hello`）。
⚠ 這句話的範圍：**proxy 記錄得到的流量**都留在本機。proxy **records，不 verifies**
——繞過 proxy 的流量它看不到，本輪**沒有**跑網路層的 `ops/vacantrun/block_egress.sh`。

## 四、兩次之間一致嗎

| agent × 格 | 結論 |
|---|---|
| pi 拒交／交付 | **逐欄相同** |
| OpenCode 拒交／交付 | **逐欄相同** |
| Claude Code 拒交／交付 | **逐欄相同** |
| Codex 交付 | **逐欄相同** |
| Codex **拒交** | ⚠ **`requests_seen` 5 vs 6**（`POST /v1/responses` 多一通） |
| Hermes 拒交／交付 | **逐欄相同** |

比較的欄位：`exit_code`／`accepted`／`stop_reason`／`requests_seen`／
`wire_by_protocol`／`agent_rc`／`visible_passed`／`ws_end_sha256`／`proxy_paths`。
（`verdict_hash` 每跑都不同是**對的**：收據鏈綁 run 的身分與時間，不是只綁工作區。）

**Codex 拒交格那一格的可能原因**：agent 迴圈多轉了一圈才收工，
落地的檔案**逐位元相同**（`39c19a7a…`、`754afb96…` 的 `solution.py`），
`req_bytes` 一路 44289→47653（vs r1 的 44289→46958）＝多一輪完整上文重放。
⇒ 是**模型取樣造成的回合數差**，不是接線差異。

### 三個跨 agent 的不變量，與一個**不成立**的

1. 拒交格的 `ws_start_sha256` 20 格一致：
   `03aeefafe6f8bb75eee9006f14eb3f0eb436a03214ffac42bd28565e02228a61`
2. 交付格的 `ws_start_sha256`：
   `1407f6cb722df0ec646475116f735bc3c42a7cf8ff3937ca90219a8d9d9c4feb`
3. **拒交格四家落在同一個檔**（pi／OpenCode／Claude Code／Codex，`multiply` 而非 `mul`）：
   `39c19a7a2c38d254ad5fdd2ce61d95ccec16260e05e8efb90310a957711474a3`；
   Hermes 落在自己那一份（加了 type hints）：
   `64de4ddf8c6cb02c4698fa8f6e03d402d5a308f3fc17dcc430946f20d29f1fc7`

⚠ **不成立的那一個**：`docs/AGENT_COMPAT.md` §9.2／§12.4 寫過
「交付格的 `ws_end` 在四個 agent 上逐位元相同（`d1ed637b…`）」。
**本輪在同一台機器上重跑，那句話只對 4/5 成立**：

```
pi / OpenCode / Codex / Hermes  交付格 ws_end = d1ed637b7ae45b8f71ddc69e113d9f52a0a998cf8df3dd008bc0bc04c9488f18
Claude Code                     交付格 ws_end = 143323827343cfb79d6008ee9dca709cf8f5f424d65dace9c285b37e1572fd1a
```

差別是 Claude Code 這次替兩個函式各加了一行 docstring（兩次都加、逐位元相同）：

```python
def add(a, b):
    """Returns the sum of two numbers."""
    return a + b

def mul(a, b):
    """Returns the product of two numbers."""
    return a * b
```

⇒ **「四個 agent 落地的東西一樣」是一次觀察，不是性質。** 換機器（1003→1004）
就變了。引用那句話時要連機器一起講。

⚠ 同一件事的第二個例子：`docs/AGENT_COMPAT.md` §10 的 Codex 拒交格在 1003 上是
`visible 0/2`、`ws_end = b720ee87…`；本輪在 1004 上是 `visible 1/2`、`39c19a7a…`。
**敘述含糊時「錯法」不可重現**——那不是 agent 之間的差異，也不是 1003／1004 的
效能差異，是同一個已知現象（§10.3）再出現一次。1003 是 thinking 模式、1004 不是，
這一條**沒有被隔離**，不要當成因果。

## 五、負控制：**一個假的格子跟真的格子只差一個欄位**

本輪自己做了兩個**零網路**的對照（`controls.sh`，agent 的位置放 `/bin/true`
與一行 `cp`，一通模型都沒打）：

| | exit | accepted | stop_reason | **`requests_seen`** | **`wire_by_protocol`** | `agent_rc` | `chain_ok` |
|---|---|---|---|---|---|---|---|
| `ctl_norequest_refuse` | **20** | false | `visible_fail` | **0** | **`{}`** | 0 | true |
| `ctl_norequest_deliver` | **0** | true | `visible_pass` | **0** | **`{}`** | 0 | true |
| （真的格子，例：`hermes_refuse_r1`） | 20 | false | `visible_fail` | **6** | **`{openai:6}`** | 0 | true |

⇒ **退出碼、`accepted`、`stop_reason`、`agent_rc`、`chain_ok` 五個欄位
在零通模型呼叫下全部成立。** 這正是 2026-09-19 兩條獨立的線各撞一次的那個陷阱
（Hermes 漏設 `CUSTOM_BASE_URL` 安靜去打 openrouter.ai：`rs=0`／`wire={}`／
`rc=0`／exit 20；Codex `wire_api=chat` 退件：`rs=0`／`wire={}`／`rc=1`／exit 20）。
**唯一分得出來的是 `requests_seen` 與 `wire_by_protocol`。**
本輪 20 格逐格檢查過這兩欄，最小值是 4。

⚠ 本輪的負控制**不出網**（`/bin/true` 與 `cp`）。Hermes 那個「安靜打第三方」的
活體標本**不是這一輪量的**，引用要指 `docs/AGENT_COMPAT.md` §12.2 對照 C。

## 六、收據驗證（先負控制再驗全批）

```
$ python3 -m vacant.vrun.verify_receipts --selftest
selftest: PASS                                   ← 負控制：它抓得到壞鏈

$ python3 -m vacant.vrun.verify_receipts --glob '/var/tmp/vacant_v1matrix/rd_*'
run 20　鏈 20　entries 40　驗過 40　失敗 0　壞鏈 0        總判：OK
```

逐字在 [`receipts_selftest.txt`](receipts_selftest.txt)／
[`receipts_verify.txt`](receipts_verify.txt)／
[`receipts_verify.json`](receipts_verify.json)；控制組在
[`controls_receipts_verify.txt`](controls_receipts_verify.txt)。

**本歸檔可以自己重驗**（不必連 vacant-dev），在 repo 根：

```
python3 -m vacant.vrun.verify_receipts --selftest
python3 -m vacant.vrun.verify_receipts --glob 'runs/v1_five_agent_matrix_20260919/cells/*'
```

檔案完整性：`shasum -a 256 -c SHA256SUMS`（在本目錄下跑）。

## 七、接線（五段都在 `ops/vacantrun/wrap_agent.sh`，本輪一行都沒改）

| agent | 版本 | 路線 |
|---|---|---|
| **pi** | 0.85.1 | 設定：`PI_CODING_AGENT_DIR` ＋ `models.json` |
| **OpenCode** | 1.18.31 | 設定：`OPENCODE_CONFIG_CONTENT`（自訂 provider；本地模型 id 走不了內建 provider） |
| **Claude Code** | 2.1.278 | **零接線**：`ANTHROPIC_BASE_URL` 在 `envmap.REDIRECT_VARS`，wrapper 只做行程隔離 |
| **Codex** | 0.147.0 | 設定：`CODEX_HOME` ＋ `config.toml` 新 provider id，`wire_api="responses"` |
| **Hermes** | 0.19.0 | `HERMES_HOME` ＋ `config.yaml`；**最小接線是 `provider: custom`**，只給 `CUSTOM_BASE_URL` 會死在 `No LLM provider configured` |

⚠ **憑證**：每一格的設定目錄都是 wrapper 自己 `mktemp -d` 出來的，
`~/.codex/auth.json`、`~/.pi`、`~/.config/opencode` **一個都沒動**。
金鑰類環境變數由 launcher 換成 sentinel（`envmap.SECRET_VARS`），
本輪父行程本來就沒有真鑰。

## 八、還不能說的話

1. **這是存在性證明，不是效果量。** 沒有對照臂、**一題**、**一個模型**、
   每格 **n=2**。不可以說「某個 agent 配 Vacant 寫程式比較好」，
   也不可以從本表推任何比率。
2. **量的是通道與閘門，不是模型能力。** 交付格用的是同一題的**天花板臂**敘述
   （把介面寫死），拒交格用的是**設計上就預期會失敗**的敘述
   （`meta.json`：`expected_first_attempt_visible_fail >= 0.8`，
   而且該欄自己標了 `expected_is_design_intent_not_measurement: true`）。
3. **`s1_01_addmul` 沒有代表性。** S1 層最簡單的一題。換題、換層、換模型都會漂。
4. **只跑了可見套件（2 題）。** 本題另有 7 題隱藏測試，本輪**沒有**跑，
   所以「交付格通過」只到 `visible_pass`，**不是** R535 那個
   `M1 ≡ accepted ∧ hidden 全過`。
5. **Claude Code 那一格的前提沒被搬運性驗證。** 它成立是因為 1004 的 LM Studio
   **原生會講 `/v1/messages`**；`wireproxy.py` 是反向代理**不是協定轉換器**。
   換一個只講 OpenAI 的上游就必須自備 shim，**那一層不在本 repo 裡也沒被量過**。
6. **Codex 只量了 API key／自訂 provider 那一條。** `codex login`（ChatGPT 帳號）
   的模型通道是寫死的 `wss://`，設定搬不動——**那條路本輪一樣沒有辦法**。
7. **Hermes 只量了 `custom` provider。** 要憑證的 provider 一條都沒碰。
8. **驗收套件是單邊保證。** 擋得住已知壞解 ≠ 涵蓋真需求
   （`vacant/suitegauge.py` docstring、本題 `meta.json` 的 `honesty` 欄）。
   收據證明的是「跑完之後沒有人改過紀錄」，**不是**「驗收問對了問題」。
9. **牆鐘不是效能數字。** 量測期間 vacant-dev 同時在跑 r530vrun 的四串，
   1004 的負載也沒有控制。表裡的秒數只用來說明「跑得完」。
10. **`--sandbox none`。** 本輪驗收沒有走沙箱後端，所以本輪**沒有**量到
    沙箱相關的任何行為。
11. **「沒量到」≠「量到 0」**（鐵律 3）。本輪沒有量的東西：網路層出網封鎖、
    長任務下的 auto-compact、`CLAUDE_CODE_USE_OPENAI` 那條路、
    Hermes 的 fail-open 到 openrouter（那是 §12.2 的紀錄不是本輪的）。
12. 口徑：本輪講的是**可究責性**（讓依賴有根據），不是「信任」。

## 九、目錄長什麼樣

```
matrix.json                 20 格的欄位彙整（機器讀；含每格的 solution.py 原文與 sha256）
MATRIX.log                  驅動腳本的完整輸出（逐格 BEGIN/END 帶 UTC 時戳）
matrix.sh                   ⭐ 跑出這 20 格的那一支腳本，逐字
collect.py                  matrix.json 的產生器
controls.sh                 第五節兩個零網路負控制的腳本，逐字
controls/<cell>/            兩個負控制的落盤（同 cells/ 的結構）
controls_receipts_verify.txt
receipts_selftest.txt       負控制：驗章器自己抓得到壞鏈
receipts_verify.{txt,json}  20 條收據鏈的驗證輸出
cells/<cell>/
    run_RUN-ON.json         裁決摘要（判準的所有欄位都在這裡）
    receipts_RUN-ON.ndjson  ed25519 收據鏈（2 筆／run）
    receipts_RUN-ON.pub.json 公鑰
    rows.jsonl              逐列紀錄
    visible_RUN-ON.json     可見驗收逐題結果（含失敗原文）
    agent_stdout.log        agent 自己的輸出（**它宣告完成的那句話在這裡**）
    _launcher_exit_code.txt 退出碼（本輪自己補記的，不是 launcher 產的）
    wire/index.jsonl        逐通的 method／path／status／bytes／elapsed／upstream
    frozen/                 驗收跑的那一份凍結快照（TASK.md ＋ solution.py）
wire.tar.gz                 20 格的 wire 原始位元組（*.req.bin／*.resp.bin，6.2 MB 未壓）
SHA256SUMS
NOT_IN_REPO.json            沒有進 repo 的東西在哪、為什麼不帶
```
