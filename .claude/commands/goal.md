---
description: 第一優先目標——Vacant 要能附身在任何 agent 上；查現況、報缺口、說下一步
---

# /goal — 附身任何 agent（2026-09-19 人類定為第一優先）

人類原話：

> **原則三最重要，無論 Vacant 的架構長怎樣，這邊都要改好，因為他就是附身進去的。**

這條**凌駕**其他工作。實驗（R535 等）不停，但**資源衝突時這條先**。

---

## 一、目標的可量測定義

「附身」不是「裝得起來」，是**兩格都成立**，而且**用真模型**：

| 格 | 判準 | 為什麼兩格都要 |
|---|---|---|
| **拒交格** | 驗收沒過 ⇒ `accepted=false`、`stop_reason=visible_fail`、**exit 20** | 驗閘門**有牙齒** |
| **交付格** | 驗收過 ⇒ `accepted=true`、`visible_pass`、**exit 0** | 驗閘門**不是永遠說不**（永遠拒交的閘門跟沒有一樣） |

外加三個**不可省**的旁證：

1. **`requests_seen > 0`** —— 唯一能證明中介真的發生了的欄位。
   「我設了環境變數」不是證據（`docs/VACANT_RUN.md` §4.5）。
2. **收據鏈驗得過** —— `verify_run_receipts --selftest` 先 PASS（負控制），再驗該跑。
3. **證據等級要標明** —— 見下。

### 證據等級（**不可混講**）

| 級 | 意思 | 現在有誰（2026-09-19 更新） |
|---|---|---|
| **L-real** | **真模型**真跑，兩格都過 | **pi ／ OpenCode ／ Claude Code ／ Codex (API key) ／ Hermes** |
| **L-fake** | 假上游（`mockup.py`）驗通道與閘門 | —— |
| **L-none** | 沒量 | Codex (ChatGPT 登入) ／ Codex (chat wire) |

**矩陣裡不再有「完全沒量過」的 agent。**
⚠ Hermes **沒有經過 L-fake**（從來沒被假上游量過）⇒ §1–§6 的假上游結論不涵蓋它。

⚠ **「零接線」三個字有陷阱，各家的成立條件不同**：
- **Claude Code**：真模型**零接線成立**，但那**整個建在「LM Studio 有開 `/v1/messages`」
  這一個功能上**。換純 llama.cpp server／vLLM 預設就斷，而那時要補的協定轉換層
  **不在本 repo 裡也沒被量過**。
- **OpenCode**：零接線**只對雲端模型成立**。內建 provider 只吃 models.dev 註冊表裡的
  模型 id，餵本地模型會在**送出任何請求之前**死在模型解析 ⇒ `requests_seen = 0`。
  接本地模型**必經設定路線**。
- **pi**：一直都是設定路線（`PI_CODING_AGENT_DIR` ＋ `models.json`）。
- **Codex (API key)**：設定路線（`CODEX_HOME` ＋ `config.toml` 裡一個**新** provider id，
  內建 `openai` 不准覆寫）。**不吃 `OPENAI_BASE_URL`**。
- **Hermes** 0.19.0（`hermes-agent`，⚠ 不是 `hermes`）：**「一個旗標」，介於零接線與設定路線之間**。
  全新環境只給 `CUSTOM_BASE_URL` 會死在 `No inference provider configured`，
  最小接線＝加一個 `--provider custom`（比寫設定檔輕）。
  **但對已經設好自訂 provider 的使用者是零接線**——`CUSTOM_BASE_URL` 優先序**高過**
  他自己的 `base_url`，不必動 `~/.hermes/config.yaml`。兩句話都要講。

⚠ **L-fake 不能寫成「這個 agent 可以用 Vacant」。** 假上游碰不到 SSE 分塊、
工具呼叫格式、逾時、上下文長度。這條界線在 `docs/AGENT_COMPAT.md` 開頭就寫著，
不准在對外文案裡模糊掉。

---

## 二、優先序（人類指定）

```
OpenCode ＝ pi ＞ Claude Code ＞ Codex(API key) ＞ Hermes
```

- **OpenCode 與 pi 是「絕對一定要」**（人類 2026-09-19 原話）。
- **Codex 的 ChatGPT 登入路徑先放著**——人類說「到時候我跟你一起弄」。
  那不是設定問題：模型通道寫死 `wss://chatgpt.com/backend-api/codex/responses`，
  **HTTP 反向代理在那條路上不存在**。要另想辦法（攔 WebSocket 或換登入方式）。

---

## 三、被這個目標擋下來的已知問題

1. **vacant-dev 上只裝了 pi。** `opencode`、`claude` 都沒有 ⇒ 現有矩陣是在別處跑的，
   而且**沒有一格是真模型**（pi 除外，靠 R535）。
2. **`vacant run --help` 曾經印舊介面**（已修，PR `fix/run-help`）——
   外人照 help 讀找不到收件口，等於沒發。這類「功能在但構不到」要當成附身失敗。
3. **`envmap` 是單一真相**（`vacant/vrun/envmap.py`）。新增 agent 一律改那裡，
   不要在別處再開一張表。
4. **零接線 vs 要接線**：Claude Code／OpenCode 吃環境變數（launcher 內建 ⇒ 零接線）；
   Codex／pi 吃設定檔（要寫 `config.toml`／`models.json`）。
   **後者是附身品質較差的一種**，文件要講明白使用者得多做什麼。

---

## 四、你被叫到時要做什麼

1. **先查現況**，不要憑記憶：
   ```bash
   sed -n '1,60p' docs/AGENT_COMPAT.md          # 矩陣（含誠實邊界）
   cat vacant/vrun/envmap.py                     # 名單的單一真相
   ssh user1@100.124.254.83 'export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH; for a in pi opencode claude codex; do printf "%-10s " "$a"; command -v $a >/dev/null && $a --version 2>&1|head -1 || echo "沒裝"; done'
   ```
2. **報缺口**：哪個 agent 在哪一級、缺什麼才能升級。
3. **說下一步**，並指出資源衝突（1003 的吞吐 4 串封頂；R535 在跑時插進去會互搶）。

⚠ **報告用繁體中文**；口徑用「**可究責性**」不用「信任」。

---

## 五、完成的定義

**優先序前兩名（OpenCode、pi）都到 L-real，而且拒交格與交付格都留下可重驗的收據。**

### ✅ 已達成（2026-09-19）

pi、OpenCode **與 Claude Code** 三個都到 L-real，各自拒交格 exit 20 ／ 交付格 exit 0、
`requests_seen > 0`、收據 `--selftest` 先過再驗該跑。

⚠ **達成之後浮出來的新東西，不要當成結案**：

1. **三個 agent 的拒交格都是 `agent_rc = 0`** ——它們都宣告完成、退出碼 0、講得很有把握，
   閘門在行程結束那一刻擋下來。**那不是巧合，是這個設計要處理的那件事。**
2. **收據的 `model` 欄位不是證據**：LM Studio 不檢查 `model`，拿
   `claude-3-5-haiku` 去問 1003 照樣回 gemma 的內容；Claude Code 對不認得的 id
   **放行不擋**（OpenCode 是硬失敗，方向相反）⇒ **沒有任何一個環節會在
   「上游其實不是你以為的模型」時報錯。**
3. **`route()` 按 path 猜家族**，未命名的家族會落到公開 API 的預設上游。
   已讓它在收據上看得見（`upstreams_defaulted`），但**結構性補法是 `block_egress.sh`（V3）**。

### ✅ Codex (API key) 也到 L-real（2026-09-19）

`codex-cli 0.147.0`，拒交格 exit 20（`requests_seen=4`、`visible=0/2`）／
交付格 exit 0（`requests_seen=5`、`visible=2/2`），收據 `--selftest` 先過再驗四跑全 OK。
**沒有碰 `~/.codex/auth.json`**：每跑 `mktemp -d` 一個新 `CODEX_HOME`，裡面沒有
auth.json ⇒ 走的一定是 API key 那條。ChatGPT 登入那條一個字都沒動。
⚠ 版本與假上游那輪的 0.153.2 不同，引用時要連機器一起講。

**四個 agent 到 L-real 之後浮出來的東西**：

4. **`agent_rc = 0` 出現在全部四個拒交格。** 四個框架都宣告完成、退出碼 0、講得很有把握，
   閘門在行程結束那一刻擋下來。**不是單一框架的怪癖，是這個設計要處理的那件事。**
5. **交付格的 `ws_end` 三家逐位元相同**（`d1ed637b…`），**拒交格反而分岔**
   （OpenCode／Claude Code＝`add`+`multiply`，Codex＝`sum_numbers`+`multiply_numbers`）。
   ⇒ 「陷阱是題目的性質」只在**敘述寫死介面時**表現成同一份檔案；**敘述含糊時錯法會分岔**。
6. **模型 id：2 放行 ∶ 1 擋。** Claude Code 與 Codex 對不認得的 id 放行（Codex 另印
   `warning: Model metadata ... not found. Defaulting to fallback metadata`），
   OpenCode 硬失敗（`requests_seen=0`）。**那是三次實測不是一條規則，第四家仍要自己量。**
   ⚠ 「fallback metadata 退到什麼」**沒量**——它會改變送出去的 input，也就是改變逐字落盤的內容。
7. **思考模式下的 runaway（1/3，n 很小）**：1003 預設開思考，而 Codex 的 body 帶
   `reasoning:{"summary":"auto"}` **沒有 `effort`** ⇒ 一通 713 秒、94,776 個
   `reasoning_text.delta`、`output_text.delta` 為 0、BrokenPipe、`response_sha256=null`
   （**infra_void 的洞，而 `wire_digest` 簽的就是含 null 的那個配對**）。
   `wrap_agent.sh` 多了**預設不設**的 `VACANT_CODEX_REASONING_EFFORT` 鉤子；
   ⚠ **那是觀測到的緩解不是保證**，而且它把推理整個關掉、代價沒量。
9. **⚠ 一個假拒交格與真拒交格在收據上只差一個欄位**（2026-09-19，Hermes 對照 C）。
   `CUSTOM_BASE_URL` 漏設時，Hermes **不報錯**，安靜走到解析鏈尾去打編死的
   `https://openrouter.ai/api/v1`：
   ```
   requests_seen = 0   wire_by_protocol = {}   agent_rc = 0   ← 0，不是 1
   stop_reason = visible_fail   退出碼 = 20   chain_ok = true
   ```
   **除了 `requests_seen` 以外，每一個欄位都跟一個合法的拒交格一樣**（連
   `agent_rc=0` 都一樣），而且**真的出網去了第三方**。
   ⇒ 這就是 `requests_seen > 0` 為什麼是**唯一**能證明中介發生的欄位，
   也是 `envmap` 誠實邊界 2「名單漏一個變數不會有任何錯誤訊息」的活體標本。

8. **`upstreams_defaulted` 的正確讀法**：它說的是「**這條路由沒人指定、萬一有流量會去公開
   API**」，**不是「已經出網了」**。要判有沒有真的出網看 `wire_by_protocol` 與
   `index.jsonl` 的 `upstream` 欄位。Claude Code 真的出過網（探 `/api/hello`）、
   **Codex 沒有**（`wire_by_protocol` 裡根本沒有 anthropic 這一項）。

### 下一個（優先序）

1. **`block_egress.sh`（V3）** —— `upstreams_defaulted` 只是讓那個洞**看得見**，沒補起來。
2. **`VACANT_CODEX_WIRE=chat`** —— Codex 走 chat/completions 那條**沒量過**，
   只有 chat/completions 的上游要靠它。
3. ~~Hermes~~ ✅ **2026-09-19 到 L-real**（拒交格 exit 20／交付格 exit 0，
   `requests_seen=6`，收據 `--selftest` 先過再驗）。
   ⚠ 只量到 `provider: custom`——**Nous Portal／OpenRouter／Anthropic OAuth／Copilot ACP
   那些要憑證的路一條都沒碰**。其中 **Copilot ACP 會 spawn 外部行程講 ACP**，
   跟 Codex 的 `wss://` 是同型的邊界嫌疑，**但沒量，不准寫成已知**。

**Codex 的 ChatGPT 登入那條：人類說「到時候我跟你一起弄」，不要自己動。**
那不是設定問題——模型通道寫死 `wss://chatgpt.com/backend-api/codex/responses`，
**HTTP 反向代理在那條路上不存在**。

⚠ 對外文案**仍然不准**寫「可以套用在各種 agent 上」——
只能寫「通道與閘門在 N 個 agent 上實測接通，其中 **4 個**有真模型證據」。
