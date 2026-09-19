# 公開題庫上的 `vacant run` 閘門 —— **跨 agent** 第二輪（LCB v2 ×10 題 × 3 個 agent × 1 次 ＝ 30 格）

> **一句話（驗得到什麼、驗不到什麼）**
> 驗得到：`vacant run` 的交付閘門在同一個**公開**題庫（LiveCodeBench v2，sha256 釘死、
> 在版控裡）、同一台後端、同一組旗標下，換成**三個既有的 agent 框架**各跑一次，
> **三個框架上兩個方向都會動**（19 格交付 exit 0／11 格拒交 exit 20），
> 30 格的模型通道全部真的被中介（`requests_seen` 4–14），30 條收據鏈外人可以自己重驗。
> **驗不到**：這不是效果量，也不是框架能力排名。沒有對照臂、每格 n=1、一個模型、
> 一台後端、10 題。**非預註冊** ⇒ 收官句只能是描述性的。

這一批擴大的是 [`runs/pbgate_lcb2_20260919/`](../pbgate_lcb2_20260919/)（commit `c606132d`）。
那一批自己列的「沒量到」清單裡有兩條：**其他 agent** 與 **1003（thinking）**。本輪兩條一起補。

## 零、為什麼選「換 agent」不是「加題數」也不是「換題庫」

| 方向 | 補的缺口 | 判斷 |
|---|---|---|
| (a) 同題庫加題數 | 樣本數 | ✗ 缺口不是樣本數。非預註冊本來就不做檢定，加題數不會讓一句描述性的話變成可檢定的話 |
| (b) 換另一個公開題庫 | 「只在一個題庫上成立」 | △ 真缺口，但**閘門本身跟題目無關**——它讀的是 `--suite` 渲染出來的驗收結果。換題庫主要換的是題目難度 |
| (c) **換另一個 agent** | 「只在一個 agent 上成立」 | ✓ **選這個**。閘門要成立必須先有「模型通道真的被中介」，而那一層**是逐框架的**：協定不同（Anthropic Messages vs OpenAI Chat Completions）、接線位置不同（環境變數 vs 設定檔）、失效模式不同。這是三條原則裡第一優先那條（「附身任何 agent」）直接要的東西 |

本輪三個 agent 涵蓋**兩條不同的 wire 協定**，所以它不只是「換一個 CLI」：

| agent | 版本 | wire | 接線 |
|---|---|---|---|
| **pi** | 0.85.1 | `POST /v1/chat/completions`（OpenAI，SSE） | `wrap_agent.sh` 換設定目錄 |
| **Claude Code** | 2.1.278 | `POST /v1/messages?beta=true`（**Anthropic Messages**，SSE） | **零接線**（`ANTHROPIC_BASE_URL` 在 launcher 裡） |
| **OpenCode** | 1.18.31 | `POST /v1/chat/completions`（OpenAI，SSE） | `wrap_agent.sh` 自訂 provider |

**沒有自造迴圈當 agent。** 三個都是既有框架，進入點都是 `ops/vacantrun/wrap_agent.sh`。

**沒跑 codex／hermes，理由寫在 `manifest.json` 的 `agents_not_run`**：codex-cli 0.147.0
在 1003 上有已知的 thinking runaway，唯一已驗的緩解會**把推理整個關掉** ⇒ 那 10 格
就不是與另外三個同一個推論條件；hermes 這台現在根本沒裝（**沒量到，不是量到 0**）。

## 一、⚠ 紅線：非預註冊

**這一批沒有預註冊檔、沒有人類簽字。** 因此：

- 不做假說檢定（沒有 p 值、沒有效果量、沒有信賴區間當結論）
- 不與 R535／R530／R534／G 實驗的任何數字合併、平均或對照
- **也不與 `runs/pbgate_lcb2_20260919` 合併或算差值**——那一批同樣非預註冊，
  兩批相減不會因為都是描述性就變成檢定。第六節的對照表是**逐格列出哪幾格一樣、
  哪幾格不一樣**，不是效果量
- 不准寫「複製」「效果消失」「顯著」「優於」
- 收官句只能是：**「在這 30 格上，閘門的判決逐格長這樣」**

同一段話在 `manifest.json` 的 `RED_LINE_not_preregistered` 與每一格的
`cells/<cell>/_NOT_PREREGISTERED.txt`。

## 二、判準（與上一輪逐字相同）

| 格 | 判準（三條**全部**要成立） |
|---|---|
| **交付格** | `accepted=true` ＋ `stop_reason=visible_pass` ＋ **exit 0** |
| **拒交格** | `accepted=false` ＋ `stop_reason=visible_fail` ＋ **exit 20** |

三個**不可省**的旁證，逐格都查了：

1. **`requests_seen > 0`** —— 唯一能證明中介真的發生的欄位。
   **本批 30 格的 `requests_seen` 全部 ≥ 4（4–14，合計 207 通），
   `wire_by_protocol` 全部非空 ⇒ 0 個假拒交格。**
2. **收據鏈**：`verify_receipts --selftest` **先 PASS**（負控制，證明它抓得到壞鏈），
   再驗這 30 格 ⇒ `run 30　鏈 30　entries 60　驗過 60　失敗 0　壞鏈 0`，
   `中介：有 30　零請求 0`（[`receipts_verify.txt`](receipts_verify.txt)）。
3. **證據等級 ＝ L-real**（真模型）。不與 L-fake 混講。

`infra_void` 0 格；`upstreams_defaulted` 全部空陣列（兩條上游都明講指到 1003）。
V/GT 分離掃描 **0 命中**（[`vgt_scan.txt`](vgt_scan.txt)）。

## 三、矩陣（30 格）

`rs`＝`requests_seen`／`rc`＝`agent_rc`／`vis`＝可見驗收通過數／
`hidden`＝**事後**隱藏測資計分（衍生物，見第七節）／`reas`＝reasoning tokens
（⚠ Anthropic 那條 wire **沒有這個欄位**，claude 那一組的 0 是「沒量到」不是「量到 0」，見第五節）。

| task | agent | 難度 | exit | accepted | stop | rs | rc | vis | hidden(事後) | agent 牆鐘 s | reas | 拒交形狀 |
|---|---|---|---:|---|---|---:|---:|---|---|---:|---:|---|
| `lcb_3522` | pi | medium | **20** | false | visible_fail | 4 | 0 | 0/1 | *沒有 solution.py* | 708.2 | 84 | **`no_delivery`** |
| `lcb_3583` | pi | hard | 0 | true | visible_pass | 8 | 0 | 3/3 | 27/27 | 207.8 | 2,312 | — |
| `lcb_3584` | pi | medium | **20** | false | visible_fail | 4 | 0 | 0/1 | *沒有 solution.py* | 504.9 | 16,421 | **`no_delivery`** |
| `lcb_3637` | pi | hard | 0 | true | visible_pass | 7 | 0 | 3/3 | 27/27 | 432.8 | 9,211 | — |
| `lcb_3654` | pi | medium | 0 | true | visible_pass | 9 | 0 | 2/2 | 26/26 | 215.9 | 5,486 | — |
| `lcb_3681` | pi | medium | 0 | true | visible_pass | 7 | 0 | 3/3 | 27/27 | 69.2 | 1,262 | — |
| `lcb_3686` | pi | medium | **20** | false | visible_fail | 4 | 0 | 0/1 | *沒有 solution.py* | 321.0 | 16,406 | **`no_delivery`** |
| `lcb_3700` | pi | hard | **20** | false | visible_fail | 4 | 0 | 0/1 | *沒有 solution.py* | 283.9 | 16,421 | **`no_delivery`** |
| `lcb_3764` | pi | medium | 0 | true | visible_pass | 7 | 0 | 2/2 | 26/26 | 54.3 | 1,076 | — |
| `lcb_3794` | pi | medium | **20** | false | visible_fail | 4 | 0 | 0/1 | *沒有 solution.py* | 365.2 | 16,408 | **`no_delivery`** |
| `lcb_3522` | claude | medium | 0 | true | visible_pass | 5 | 0 | 3/3 | 27/27 | 27.6 | — | — |
| `lcb_3583` | claude | hard | **20** | false | visible_fail | 5 | 0 | 0/1 | *沒有 solution.py* | 50.3 | — | **`no_delivery`** |
| `lcb_3584` | claude | medium | 0 | true | visible_pass | 5 | 0 | 4/4 | 28/28 | 105.3 | — | — |
| `lcb_3637` | claude | hard | 0 | true | visible_pass | 6 | 0 | 3/3 | 27/27 | 115.0 | — | — |
| `lcb_3654` | claude | medium | **20** | false | visible_fail | 5 | 0 | 0/2 | 14/26 | 164.3 | — | **`true_refuse`** |
| `lcb_3681` | claude | medium | 0 | true | visible_pass | 5 | 0 | 3/3 | 27/27 | 52.4 | — | — |
| `lcb_3686` | claude | medium | 0 | true | visible_pass | 5 | 0 | 2/2 | 26/26 | 53.4 | — | — |
| `lcb_3700` | claude | hard | **20** | false | visible_fail | 10 | **-9** | 1/3 | 17/27 | 900.0 | — | `timeout_killed,true_refuse` |
| `lcb_3764` | claude | medium | 0 | true | visible_pass | 5 | 0 | 2/2 | 26/26 | 65.4 | — | — |
| `lcb_3794` | claude | medium | 0 | true | visible_pass | 6 | 0 | 3/3 | 27/27 | 310.8 | — | — |
| `lcb_3522` | opencode | medium | 0 | true | visible_pass | 14 | 0 | 3/3 | 27/27 | 149.8 | 1,037 | — |
| `lcb_3583` | opencode | hard | 0 | true | visible_pass | 9 | 0 | 3/3 | 27/27 | 225.6 | 2,194 | — |
| `lcb_3584` | opencode | medium | **20** | false | visible_fail | 7 | **-9** | 0/1 | *沒有 solution.py* | 900.0 | 679 | `timeout_killed,no_delivery` |
| `lcb_3637` | opencode | hard | 0 | true | visible_pass | 9 | 0 | 3/3 | 27/27 | 160.5 | 811 | — |
| `lcb_3654` | opencode | medium | **20** | false | visible_fail | 9 | 0 | 0/2 | 4/26 | 244.7 | 540 | **`true_refuse`** |
| `lcb_3681` | opencode | medium | 0 | true | visible_pass | 7 | 0 | 3/3 | 27/27 | 46.3 | 638 | — |
| `lcb_3686` | opencode | medium | 0 | true | visible_pass | 12 | 0 | 2/2 | 26/26 | 261.2 | 494 | — |
| `lcb_3700` | opencode | hard | **20** | false | visible_fail | 6 | 0 | 0/1 | *沒有 solution.py* | 615.0 | 488 | **`no_delivery`** |
| `lcb_3764` | opencode | medium | 0 | true | visible_pass | 9 | 0 | 2/2 | 26/26 | 82.1 | 470 | — |
| `lcb_3794` | opencode | medium | 0 | true | visible_pass | 10 | 0 | 3/3 | 27/27 | 272.5 | 657 | — |

**19 交付 ∶ 11 拒交**（pi 5∶5、Claude Code 7∶3、OpenCode 7∶3）。
每一格的判準三條都成立，沒有 `infra_void`。

⚠ **這三個比數不是框架能力排名。** 為什麼不是，第五節有量到的原因。

## 四、⚠ 主要發現：**閘門三個框架都會動，但「哪一格會動」是逐框架的**

| task | pi | Claude Code | OpenCode | 三家一致？ |
|---|---|---|---|---|
| `lcb_3522` | 拒交 `no_delivery` | 交付 | 交付 | **異** |
| `lcb_3583` | 交付 | 拒交 `no_delivery` | 交付 | **異** |
| `lcb_3584` | 拒交 `no_delivery` | 交付 | 拒交 `timeout,no_delivery` | **異** |
| `lcb_3637` | 交付 | 交付 | 交付 | 同（全交付） |
| `lcb_3654` | 交付 | 拒交 `true_refuse` | 拒交 `true_refuse` | **異** |
| `lcb_3681` | 交付 | 交付 | 交付 | 同（全交付） |
| `lcb_3686` | 拒交 `no_delivery` | 交付 | 交付 | **異** |
| `lcb_3700` | 拒交 `no_delivery` | 拒交 `timeout,true_refuse` | 拒交 `no_delivery` | 同（全拒交） |
| `lcb_3764` | 交付 | 交付 | 交付 | 同（全交付） |
| `lcb_3794` | 拒交 `no_delivery` | 交付 | 交付 | **異** |

**三家方向一致只有 4/10 題**（3 題全交付、1 題全拒交），**6/10 題至少有一家不一樣**。

這句話該怎麼讀：

- ✅ **「閘門會動」是跨框架成立的**——三個框架各自都有交付格也有拒交格，
  三個框架的每一格都真的被中介（`requests_seen` 全部 ≥ 4），30 條收據都驗得過。
- ❌ **「閘門在第 N 題上會擋下來」不是跨框架成立的**。上一輪 20 格記下來的
  逐格判決，**換一個框架就有 6/10 題會變**。⇒ **任何「閘門擋下 X 格」的數字都是
  綁在那一個框架＋那一個後端上的，不可以搬到另一個框架上講。**

拒交形狀沿用上一輪那張表（判準全部只看落盤欄位）：

| 形狀 | 判準 | 本批 |
|---|---|---|
| `no_delivery` | `rs>0` 但工作區裡沒有 `solution.py`；失敗 case `kind`＝`import`／`nofile` | **8** |
| `true_refuse` | 失敗 case `kind`＝`assert`／`exception`（交了但不對） | **3** |
| `timeout_killed` | `agent_timed_out=true`、`agent_rc=-9` | **2**（都同時是上面某一種） |
| `fake_refuse` | `requests_seen==0` 且 `wire_by_protocol` 空 ⇒ 中介根本沒發生 | **0** |

⚠ **11 個拒交格裡只有 2 格（`lcb_3584_opencode`、`lcb_3700_claude`）是被 `--timeout 900`
砍掉的**，其餘 9 格 `agent_rc=0`、`agent_timed_out=false` ——**agent 自己宣告完成、
退出碼 0 走人，閘門在行程結束那一刻擋下來。** 這是上一輪 `/goal` §5 那條觀察
（「拒交格都是 `agent_rc=0`」）在**三個框架**上的同時出現。

## 五、⚠ 為什麼 5∶7∶7 不是能力排名：**輸出上限 × thinking 後端**

這是本輪最該被記住的一件事，而且它**只在 wire 上看得到**，`run_*.json` 的欄位裡沒有。

逐位元重算 30 格的 `*.resp.bin`（[`finish_reason_census.txt`](finish_reason_census.txt)）：

```
finish_reason = "length" 出現在 6 格：
    lcb_3522_pi   lcb_3584_pi   lcb_3686_pi   lcb_3700_pi   lcb_3794_pi   lcb_3700_opencode
    ⇒ 這 6 格**全部是拒交格**；19 個交付格**一格都沒有**
```

request body 裡的輸出上限（逐格從 `*.req.bin` 讀出來）：

| agent | 輸出上限 | 誰設的 |
|---|---:|---|
| **pi** | `max_completion_tokens = 16384` | **我們**——`ops/vacantrun/wrap_agent.sh` 的 pi 段 `"maxTokens":16384` |
| Claude Code | `max_tokens = 32000` | 框架自己的預設，我們沒設 |
| OpenCode | `max_tokens = 32000` | 框架自己的預設，我們沒設 |

pi 的 5 個拒交格逐格長一樣：**前 3 通 `tool_calls`、第 4 通 `length`，然後 pi 就收工了**
（`rs=4`、`agent_rc=0`、工作區沒有 `solution.py`）。其中 4 格的 reasoning tokens
是 16,406–16,421 ——**16,384 的輸出預算幾乎整份被思考吃掉，工具呼叫沒吐出來。**
（第 5 格 `lcb_3522_pi` 也撞 `length`，但 reasoning 只有 84 ⇒ 那一格是輸出本身太長，
**同一個上限、不同的吃法**，不可以併成一句話講。）

⇒ **這是「我們的接線參數 × thinking 後端」的交互作用，不是 pi 比較差。**
上一輪同一個 pi、同一個 `maxTokens: 16384`、同樣 10 題，跑在**非 thinking** 的 1004 上，
**一格都沒有撞到 `length`**。

這條與 `docs/AGENT_COMPAT.md` §10.7（codex 在 1003 上的 thinking runaway）是**同一類**
失效：thinking 模式把輸出預算或牆鐘吃掉，agent 看起來「做完了」而其實什麼都沒交。
⚠ 但**不是同一個**：那邊是跑不完（713 秒沒有 `output_text`），這邊是撞上限收工。
兩個現象不要合寫成一句。

## 六、跟上一輪（`c606132d`）對得起來嗎

上一輪 20 格是 **pi 0.85.1 × 1004（非 thinking）× N/V 兩臂**。
本輪的 **pi 那 10 格**與它的 **V 臂 10 格**：同一個 agent、同一個版本、同一組題目、
同一個臂、同一組旗標、同一個 prompt、同一個 `maxTokens` ——**只差後端**。

| task | 舊：pi / 1004 / 非 thinking | 新：pi / 1003 / thinking | 方向 |
|---|---|---|---|
| `lcb_3522` | 交付 | 拒交 `no_delivery` | **翻** |
| `lcb_3583` | 拒交 `no_delivery` | 交付 | **翻** |
| `lcb_3584` | 拒交 `timeout,true_refuse` | 拒交 `no_delivery` | 同（形狀不同） |
| `lcb_3637` | 交付 | 交付 | 同 |
| `lcb_3654` | 交付 | 交付 | 同 |
| `lcb_3681` | 交付 | 交付 | 同 |
| `lcb_3686` | 交付 | 拒交 `no_delivery` | **翻** |
| `lcb_3700` | 拒交 `timeout,no_delivery` | 拒交 `no_delivery` | 同（形狀不同） |
| `lcb_3764` | 交付 | 交付 | 同 |
| `lcb_3794` | 交付 | 拒交 `no_delivery` | **翻** |

**方向相同 6/10，翻面 4/10**（舊 7 交付∶3 拒交 → 新 5∶5）。

**一致的部分**（這才是可以拿來講的）：

- 兩輪都是**兩個方向都會動**，兩輪的 `requests_seen` 都沒有一格是 0 ⇒ **0 個假拒交格**
- 兩輪的收據鏈都 100% 驗得過（上一輪 20/20，本輪 30/30）
- 兩輪的交付格**事後隱藏測資都全過**，而且兩輪的計分器負控制都 10/10 擋得住退化樁
- 兩輪都出現「`agent_rc=0`、工作區連 `solution.py` 都沒有、還是退出碼 0 走人」

**不一致的部分是「哪一格」**，而且**歸因分得開**：

- 這 4 格翻面**不是題庫差異**（同一個題庫、同一個 10 題、渲染檔 sha256 逐位元相同），
  也**不是 agent 差異**（同一個 pi 0.85.1、同一份 `wrap_agent.sh` 接線）。
- 剩下能變的只有**後端**（1004 非 thinking → 1003 thinking），而且第五節量到了機制：
  4 個翻成拒交的格裡有 3 格（`3686`／`3794`／`3522`）撞 `finish_reason=length`，
  上一輪一格都沒有。
- ⚠ **還有一個沒排除的變數：本輪三條 lane 同時跑、上一輪嚴格序列。**
  它會讓牆鐘變長。但翻面的那幾格 `agent_timed_out=false`、`agent_rc=0`、
  死因是 token 上限不是牆鐘 ⇒ **並行解釋不了這 4 格**。牆鐘的跨輪比較仍然不可用。

## 七、事後隱藏測資計分（**衍生物，不是被量的東西**）

跑完之後，用 `ops/gain/r534/hidden/<task_id>/test_hidden.py`（可見 ∪ 隱藏，26–28 條）
對每一格 frozen 下來的 `solution.py` 再算一次分。**零模型呼叫。**

**先講負控制**：[`hidden_scorer_negative_control.json`](hidden_scorer_negative_control.json)
——`def <entry_point>(*a, **k): return None` 這個退化樁，**10/10 題都被擋下來**。
沒有它，下面那句話不可信。

- **19 個交付格，隱藏測資 19/19 全過**（26/26、27/27 或 28/28）。
  ⇒ 在這 19 格上，「可見驗收過了」沒有出現**假通過**。
- 拒交格：`lcb_3700_claude` 17/27、`lcb_3654_claude` 14/26、`lcb_3654_opencode` 4/26；
  其餘 8 個拒交格**沒有 `solution.py` 可以計分**。

⚠ **三條不准省的邊界**（逐字沿用上一輪）：

1. **這是衍生物。** 它沒有在跑的時候影響任何一格，也沒有任何一個位元組回饋給模型。
   報表裡兩個數字（`vis` 與 `hidden`）必須分開講。
2. **`vacant_network/suitegauge.py` 的單邊保證一個字都沒鬆。** 「這 19 格沒有假通過」
   **不等於**「可見套件涵蓋了真需求」——它只是說在這一批上沒有量到反例。
   n 很小，而且 LCB 的可見 case 只有 2–4 條。
3. **渲染出來的 `test_hidden.py` 比既有判準寬**（`vacant_network/checks.py` 的 AST 政策
   在這條路徑上沒有套用）⇒ **本輪的隱藏分與 r460／r532 的 `meets_demand` 不可互引。**

## 八、後端（**量到的**，不是宣稱的）

- **1003** `http://100.119.113.56:1234`（w401-win），`gemma-4-12b-it-qat`
  （`/v1/models` 實測：這台上只有這一個）
- **LM Studio 0.4.24+1**（FileVersion；ProductVersion `0.4.24.0`），`lms` CLI commit `ff50809`；
  `lms ps` 實測 context 262144、parallel 4、**無 TTL**
- **是 thinking 模式。** 判準：`choices[0].message.reasoning_content` 非空
  ＋ 巢狀 `usage.completion_tokens_details.reasoning_tokens` > 0。
  發射前探針：1003 ＝ `reasoning_content` **523 字元**／nested **241 tokens**。
  **負控制**：同一支探針對 1004 跑一次 ＝ **0 字元／0 tokens**
  ⇒ 這支量具讀得出差別，1004 的 0 是量到的 0。逐字在 [`backend_probe_raw.json`](backend_probe_raw.json)。
  ⚠ **頂層 `usage.reasoning_tokens` 兩台都是 `None`**（不在回應裡）。**讀它永遠 None，
  不可以當判準。**
- **全批證據**：207 通逐位元重算，OpenAI 那條 wire 上 reasoning tokens 合計 **93,095**、
  `reasoning_content` 合計 **242,918 字元**。
- ⚠ **Claude Code 那 10 格的 `reasoning_tokens` 是 0，那是「這條 wire 沒有這個欄位」
  不是「思考是 0」。** 同一批 wire 上數得到 **11 個** `content_block_start(type=thinking)`
  區塊。**兩個數不可換算、不可相加。**
- 1003 **原生支援** `POST /v1/messages`（含 `tool_use`）——這是 Claude Code 零接線的前提。
  `wireproxy.py` 只路由 path，**不做協定轉換**；換一個只講 OpenAI 的上游，這一格就不成立。

## 九、成本

| 項 | 值 |
|---|---|
| 格數 | 30（**3 條 lane 同時跑**，每條 lane 內部序列） |
| 發射窗（UTC） | pi／claude lane **2026-09-19 18:19:56** 起、opencode lane **18:24:15** 起，全部收工於 **19:14:12** 之前（約 54 分鐘） |
| agent 牆鐘總和 | 7,965.4 s；最大 900.0 s（2 格撞上限） |
| 模型呼叫 | **207 通**（每格 4–14） |
| prompt tokens | 1,965,993 |
| completion tokens | 238,880 |
| reasoning tokens（OpenAI wire） | 93,095 |

⚠ **token 是下界**：207 通裡有 **11 通沒有 `usage`**——10 通是 Claude Code 每格必打一次的
`HEAD /api/hello`（沒有 body，所以也對應 10 個 `unparsed_chunks`），另 1 通是
`lcb_3584_opencode` 被 SIGKILL 時正在飛的那一通（對得上它的 `wire_errors=1`）。
**「沒量到」≠「量到 0」**（鐵律 3）。

## 十、誠實邊界（**不准淡化**）

1. **不是效果量。** 每格 n=1、10 題、一個模型、一台後端。
2. **5∶7∶7 不是框架能力排名**，第五節量到了為什麼（我們自己設的 `maxTokens: 16384`）。
3. **不是模型能力評測。** 量的是**通道與閘門**；`visible_passed` 是
   「過了我們渲染的那幾條」，不是「做對了幾成」。
4. **proxy records，不 verifies。** 它證明這些 bytes 經過它，不證明上游照著跑，
   也不阻止 agent 自己開一條連線（`docs/VACANT_RUN.md` §4.1）。本輪**沒有出網封鎖**。
5. **中介的是模型通道不是 agent 的行為。** 框架自己發起的本機工具呼叫、內建重試
   不經過模型通道，proxy 看不到也擋不到。
6. **`--sandbox none`**：驗收沒有跑在沙箱裡。這會改變「驗收有多硬」。
7. **量的是閘門本身，不是 V1 重試迴圈的增益。** `--retry none`，每格一次 agent 行程。
8. **三條 lane 並行**（上一輪是序列）⇒ 逐格牆鐘不可跨輪比。判決欄位不受影響
   （9/11 個拒交格 `agent_timed_out=false`）。
9. **跨 agent 的結果與後端綁在一起。** 本輪三個 agent 全部只在 1003 跑過；
   **沒量** 1004 上的 Claude Code／OpenCode ⇒ 拆不開「這是框架差異還是框架×thinking 差異」。
10. **LCB v2 的 `contest_date` 落在 2023-08-26 → 2025-04-05**（本輪 10 題是
    2024-08-17 → 2025-03-22）；**不能**宣稱晚於任何模型的訓練截止。污染風險沒有排除。
11. **沒量到 ≠ 量到 0**：沒量出網封鎖、沒量 codex／hermes、沒量 N 臂、沒量重試迴圈、
    沒量 R534 的 A 層 10 題、沒量 MBPP+／HumanEval+／LCB v1／v3。

口徑用「**可究責性 / 讓依賴有根據**」，不用「信任」。

## 十一、題庫出處（**釘死**）

| 欄 | 值 |
|---|---|
| 題庫 | **LiveCodeBench v2**（公開），`ops/gain/data/lcb_bank_v2.jsonl`（**在版控裡**） |
| sha256 | `b98f027213e2469a0a41bed813d99f029d3d6e2fac64e0fa18887c42c865b9ba`（執行端實測，與 `runs/INDEX.md` §七釘值相同） |
| 題數 | 120（`eligible_n` ＝ **118**） |
| 已知壞題排除 | `lcb_3613`、`lcb_3763`（`ops/gain/check_bank_precision.py::KNOWN_BAD`） |
| 轉換器 | `ops/gain/r534/build_bank.py`（**既有的**） |
| bank manifest | `ops/gain/r534/bank_manifest.json`，sha256 `e92ac8b810081b32de253d886bc70b634d933d4c30a92f5778762aae204995b7` |
| 選題規則 sha256 | `231971f3bad306f6…` |

**本輪實際跑的 10 題**（R534 的 **B 層**全取，一題沒挑，與上一輪同一組）：
`lcb_3522`、`lcb_3583`、`lcb_3584`、`lcb_3637`、`lcb_3654`、
`lcb_3681`、`lcb_3686`、`lcb_3700`、`lcb_3764`、`lcb_3794`
（逐題難度／entry_point／case 數／contest_date／`prompt_sha256`／渲染檔 sha256
都在 `manifest.json` 的 `bank.tasks`）。

> ⚠ **渲染器漂了，資料沒漂。**
> `python3 ops/gain/r534/build_bank.py --check` 在現在的樹上會 **FAIL**。
> 原因是 commit `fb7f4bfb`（套件改名 `vacant` → `vacant_network`）的 sed 掃過
> `build_bank.py` 的樣板字串，把它**未來**會渲染出來的註解改成 `vacant_network/codebench.py`。
> 磁碟上 `templates/`＋`hidden/` 那 100 個檔仍然寫 `vacant/codebench.py`，
> 而且與 `bank_manifest.json` 的釘值、與上一輪 `runs/pbgate_lcb2_20260919/manifest.json`
> 記的 sha **逐位元相同**。
> **本輪用的是磁碟上那一份凍結的，沒有重新渲染。** 發射前在執行端實測：
> `files checked = 100  tasks = 20  verdict = OK`；負控制（改一個 byte）→ `FAIL` 且印出 MISMATCH。
> 這與 commit `c7feccb4` 記的「改名打破了兩樣凍結的東西」是同一件事，**本輪沒有動手修**。

## 十二、怎麼自己重驗

```bash
# 1) 負控制先跑：證明驗章器抓得到壞鏈
.venv/bin/python -m vacant_network.vrun.verify_receipts --selftest

# 2) 驗這 30 條鏈
.venv/bin/python -m vacant_network.vrun.verify_receipts \
    --glob 'runs/pbgate2_agents_lcb2_20260920/cells/*'

# 3) 題庫樹沒漂（比對 100 個檔與 bank_manifest 的釘值；**不要**用 build_bank.py --check，
#    那支現在會因為渲染器漂了而 FAIL，見第十一節）
python3 runs/pbgate2_agents_lcb2_20260920/verify_bank_tree.py .

# 4) 事後隱藏計分與它的負控制（零模型呼叫）
cat runs/pbgate2_agents_lcb2_20260920/hidden_scorer_negative_control.json

# 5) 收尾原因普查（需要 wire 原始位元組；先解開 wire.tar.gz）
cat runs/pbgate2_agents_lcb2_20260920/finish_reason_census.txt

# 6) 落盤完整性
cd runs/pbgate2_agents_lcb2_20260920 && shasum -a 256 -c SHA256SUMS
```

## 十三、檔案

| 檔 | 是什麼 |
|---|---|
| `manifest.json` | **所有參數**：題庫出處＋逐題 id、三個 agent 的版本／wire／接線／輸出上限、後端、旗標、發射窗、紅線、誠實邊界 |
| `matrix.json` | 30 格逐格的完整欄位＋`solution_text`＋`wire_usage`（逐 wire 分開）＋`refusal_shape`＋事後隱藏分 |
| `SUMMARY.txt` | 一行一格的摘要表 |
| `MATRIX.log` | 三條 lane 的發射全程逐字（每格 BEGIN/END、退出碼、關鍵欄位） |
| `finish_reason_census.txt` | 30 格的收尾原因普查（第五節的來源）；產生器 `census.py` |
| `cells/<cell>/` | `run_RUN-ON.json`／收據鏈＋公鑰／`rows.jsonl`／`visible_RUN-ON.json`／`agent_stdout.log`／`wire/index.jsonl`／`argv.txt`／frozen 的 `solution.py`／`_NOT_PREREGISTERED.txt` |
| `wire.tar.gz` | 30 格 wire 的**原始位元組**（`*.req.bin`／`*.resp.bin`，414 檔、未壓 65.3 MB）——收據的 `wire_digest` 簽的就是這些 |
| `receipts_verify.txt` | selftest（負控制）＋ 30 條鏈的驗證輸出（**在執行端跑的那一份**，路徑是 `/var/tmp/...`） |
| `receipts_verify_archived_copy.txt` | 同樣兩步，但跑在**本目錄這份歸檔副本**上（路徑是 `runs/.../cells/*`）⇒ 外人 clone 下來照第十二節第 2 步就能重現同一行 |
| `vgt_scan.txt` | V/GT 分離掃描：30 格 wire ＋ 工作區，**0 命中** |
| `hidden_scorer_negative_control.json` | 事後計分器的退化樁負控制（10/10 擋住） |
| `backend_probe_raw.json` | 發射前對 **1003 與 1004** 的逐字探針（1004 是負控制） |
| `smoke_prelaunch.txt` | 發射前三格冒煙的摘要（`lcb_3534`，A 層，**不在被量的 10 題裡**，不進 `cells/`） |
| `pbgate2_cell.sh`／`pbgate2_matrix.sh`／`collect2.py`／`census.py`／`vgt_scan2.sh`／`verify_bank_tree.py`／`probe.py` | 這一輪實際跑的那幾支 |
| `NOT_IN_REPO.json` | 沒進 repo 的東西：在哪、多大、為什麼不帶、怎麼重建 |

裁決：[`decisions/DECISION_20260920_PUBLIC_BENCH_GATE_CROSSAGENT.md`](../../decisions/DECISION_20260920_PUBLIC_BENCH_GATE_CROSSAGENT.md)
