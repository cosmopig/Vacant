# 公開題庫上的 `vacant run` 閘門 —— **換後端**第三輪（LCB v2 ×10 題 × 3 個 agent × **1004** ＝ 30 格）

> **一句話（驗得到什麼、驗不到什麼）**
> 驗得到：把 [`runs/pbgate2_agents_lcb2_20260920/`](../pbgate2_agents_lcb2_20260920/) 那 30 格
> **逐格重跑一次、唯一被變的東西是後端**（1003 thinking → 1004 非 thinking），
> 結果 **24 交付 ∶ 6 拒交**、30 格全部真的被中介、30 條收據鏈都驗得過，
> 而且 **`finish_reason="length"` 在這 30 格出現 0 次**——pi 那個
> `max_completion_tokens=16384` 的接線參數**一個字沒改、逐格仍在 request body 裡**，
> 在這台後端上**沒有咬到任何一格**。
> **驗不到**：這不是效果量，也不是框架能力排名。每格 n=1、10 題、一個模型、一台後端。
> **非預註冊** ⇒ 跨批只能**逐格列一樣／不一樣**，**不准相減**。

這一批補的是 `pbgate2` 誠實邊界的**第 9 條**：

> 9. **跨 agent 的結果與後端綁在一起。** 本輪三個 agent 全部只在 1003 跑過，
>    **沒量** 1004 上的 Claude Code／OpenCode ⇒ 拆不開「框架差異」還是「框架×thinking 差異」。

## 零、設計：**唯一變因是後端**

| 項 | 值 | 與 `pbgate2` 相同？ |
|---|---|---|
| 題庫 | LCB v2，`ops/gain/data/lcb_bank_v2.jsonl`，sha256 `b98f0272…`（執行端實測） | ✅ 同 |
| 10 題 | R534 **B 層全取**：`lcb_3522` `lcb_3583` `lcb_3584` `lcb_3637` `lcb_3654` `lcb_3681` `lcb_3686` `lcb_3700` `lcb_3764` `lcb_3794` | ✅ 同（一字不改） |
| 臂 | V | ✅ 同 |
| agent | pi **0.85.1** · Claude Code **2.1.278** · OpenCode **1.18.31**（發射前逐個 `--version` 實測） | ✅ 同版本 |
| 旗標 | `--sandbox none --test-timeout 120 --timeout 900 --retry none --json`，外層 `timeout 1200` | ✅ 同 |
| prompt | `Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.` | ✅ 逐字同 |
| 接線 | `ops/vacantrun/wrap_agent.sh`，**含 pi 段那個 `"maxTokens":16384`** | ✅ **一個字沒動** |
| repo 子集 | commit `b5654eac`（**刻意用與 pbgate2 同一個，不是本分支 HEAD**） | ✅ 同 |
| 併發 | 三條 lane 同時跑 | ✅ 同 |
| **後端** | 🔴 **1004** `http://100.86.226.21:1234`，`gemma-4-12b-it-qat` | ❌ **這一項，只有這一項** |

**為什麼不改那個 16384**：pbgate2 §五 量到的機制是「**我們自己設的** 16384 × **thinking 後端**」的
交互作用。要驗這條假說，就必須**保住 16384**，只換後端。改掉它等於同時動兩個東西，什麼都驗不了。

**為什麼 repo 子集用舊 commit**：`ae9cd4b4` 之後 `vacant_network/vrun/{launcher,wireproxy,verify_receipts,proxyd,sandbox}.py`
都改了（加了 attestation 維度）。用新的等於同時動後端與 harness。
`ops/vacantrun/wrap_agent.sh` 與 `ops/gain/r534/` 在兩個 commit 之間 `git diff --stat` **是空的**。

`diff pbgate2_cell.sh pbgate3_cell.sh` 只有四處：註解、`ROOT`、兩個上游 URL、`--task-id` 前綴。**沒有第五處。**

## 一、⚠ 紅線：非預註冊

**這一批沒有預註冊檔、沒有人類簽字。** 因此：

- 不做假說檢定（沒有 p 值、沒有效果量、沒有信賴區間當結論）
- 不與 R535／R530／R534／G 實驗的任何數字合併、平均或對照
- **也不與 `pbgate2`／`pbgate` 相減當效果量**——三批都是非預註冊，
  兩個描述性觀測相減不會變成檢定。第六節那張跨批表是**逐格列一樣／不一樣**，不是效果量
- 不准寫「複製」「效果消失」「顯著」「優於」
- 收官句只能是：**「在這 30 格上，閘門的判決逐格長這樣」**

同一段話在 `manifest.json` 的 `RED_LINE_not_preregistered` 與每一格的 `cells/<cell>/_NOT_PREREGISTERED.txt`。

## 二、判準與旁證（與前兩輪逐字相同）

| 格 | 判準（三條**全部**要成立） |
|---|---|
| **交付格** | `accepted=true` ＋ `stop_reason=visible_pass` ＋ **exit 0** |
| **拒交格** | `accepted=false` ＋ `stop_reason=visible_fail` ＋ **exit 20** |

三個**不可省**的旁證，逐格都查了：

1. **`requests_seen` 全部 ≥ 5**（5–37，合計 **261**），`wire_by_protocol` 全部非空
   ⇒ **0 個假拒交格**。
2. `verify_receipts --selftest` **先 PASS**（負控制，證明它抓得到壞鏈），再驗這一批：
   `run 30　鏈 30　entries 60　驗過 60　失敗 0　壞鏈 0`、`中介：有 30　零請求 0`
   （[`receipts_verify.txt`](receipts_verify.txt)）。
3. **證據等級 ＝ L-real**（真模型）。不與 L-fake 混講。

`infra_void` **0 格**；`upstreams_defaulted` 30 格全部是空陣列，`upstreams` 30 格逐格寫
`env:VACANT_RUN_UPSTREAM_*` → `http://100.86.226.21:1234`（**沒有一格是預設值**）。
V/GT 分離掃描 **TOTAL_HITS = 0**（[`vgt_scan.txt`](vgt_scan.txt)）。

## 三、矩陣（30 格）

`rs`＝`requests_seen`／`rc`＝`agent_rc`／`vis`＝可見驗收通過數／
`hidden`＝**事後**隱藏測資計分（衍生物，見第七節）。
⚠ **reasoning tokens 這一欄本輪整批是 0，而且那是量到的 0**（見第五節），所以不另列一欄。

| task | agent | 難度 | exit | accepted | stop | rs | rc | vis | hidden(事後) | agent 牆鐘 s | 拒交形狀 |
|---|---|---|---:|---|---|---:|---:|---|---|---:|---|
| `lcb_3522` | pi | medium | 0 | true | visible_pass | 6 | 0 | 3/3 | 27/27 | 163.4 | — |
| `lcb_3583` | pi | hard | 0 | true | visible_pass | 7 | 0 | 3/3 | 27/27 | 164.3 | — |
| `lcb_3584` | pi | medium | 0 | true | visible_pass | 15 | 0 | 4/4 | 28/28 | 611.4 | — |
| `lcb_3637` | pi | hard | **20** | false | visible_fail | 17 | **-9** | 0/1 | *沒有 solution.py* | 900.0 | **`timeout_killed,no_delivery`** |
| `lcb_3654` | pi | medium | 0 | true | visible_pass | 13 | 0 | 2/2 | 26/26 | 241.4 | — |
| `lcb_3681` | pi | medium | 0 | true | visible_pass | 6 | 0 | 3/3 | 27/27 | 53.9 | — |
| `lcb_3686` | pi | medium | 0 | true | visible_pass | 8 | 0 | 2/2 | 26/26 | 159.3 | — |
| `lcb_3700` | pi | hard | **20** | false | visible_fail | 37 | **-9** | 0/1 | *沒有 solution.py* | 900.0 | **`timeout_killed,no_delivery`** |
| `lcb_3764` | pi | medium | 0 | true | visible_pass | 6 | 0 | 2/2 | 26/26 | 17.0 | — |
| `lcb_3794` | pi | medium | 0 | true | visible_pass | 7 | 0 | 3/3 | 27/27 | 52.3 | — |
| `lcb_3522` | claude | medium | 0 | true | visible_pass | 5 | 0 | 3/3 | 27/27 | 121.8 | — |
| `lcb_3583` | claude | hard | **20** | false | visible_fail | 5 | 0 | 0/1 | *import_error* | 102.9 | **`no_delivery`** |
| `lcb_3584` | claude | medium | **20** | false | visible_fail | 6 | 0 | 2/4 | 25/28 | 776.2 | **`true_refuse`** |
| `lcb_3637` | claude | hard | 0 | true | visible_pass | 7 | 0 | 3/3 | 27/27 | 235.6 | — |
| `lcb_3654` | claude | medium | 0 | true | visible_pass | 6 | 0 | 2/2 | 26/26 | 200.5 | — |
| `lcb_3681` | claude | medium | 0 | true | visible_pass | 5 | 0 | 3/3 | 27/27 | 101.0 | — |
| `lcb_3686` | claude | medium | 0 | true | visible_pass | 6 | 0 | 2/2 | 26/26 | 164.4 | — |
| `lcb_3700` | claude | hard | **20** | false | visible_fail | 9 | 0 | 2/3 | 18/27 | 467.6 | **`true_refuse`** |
| `lcb_3764` | claude | medium | 0 | true | visible_pass | 5 | 0 | 2/2 | 26/26 | 62.8 | — |
| `lcb_3794` | claude | medium | 0 | true | visible_pass | 6 | 0 | 3/3 | 27/27 | 298.1 | — |
| `lcb_3522` | opencode | medium | 0 | true | visible_pass | 7 | 0 | 3/3 | 27/27 | 98.3 | — |
| `lcb_3583` | opencode | hard | 0 | true | visible_pass | 9 | 0 | 3/3 | 27/27 | 182.9 | — |
| `lcb_3584` | opencode | medium | 0 | true | visible_pass | 8 | 0 | 4/4 | 28/28 | 188.3 | — |
| `lcb_3637` | opencode | hard | 0 | true | visible_pass | 7 | 0 | 3/3 | 27/27 | 94.8 | — |
| `lcb_3654` | opencode | medium | 0 | true | visible_pass | 7 | 0 | 2/2 | 26/26 | 53.0 | — |
| `lcb_3681` | opencode | medium | 0 | true | visible_pass | 5 | 0 | 3/3 | 27/27 | 39.9 | — |
| `lcb_3686` | opencode | medium | 0 | true | visible_pass | 8 | 0 | 2/2 | 26/26 | 36.4 | — |
| `lcb_3700` | opencode | hard | **20** | false | visible_fail | 7 | **-9** | 0/1 | *沒有 solution.py* | 900.0 | **`timeout_killed,no_delivery`** |
| `lcb_3764` | opencode | medium | 0 | true | visible_pass | 7 | 0 | 2/2 | 26/26 | 98.0 | — |
| `lcb_3794` | opencode | medium | 0 | true | visible_pass | 14 | 0 | 3/3 | 27/27 | 253.3 | — |

**24 交付 ∶ 6 拒交**（pi **8∶2**、Claude Code **7∶3**、OpenCode **9∶1**）。
每一格判準三條都成立，沒有 `infra_void`。

⚠ **這三個比數不是框架能力排名**，理由與 pbgate2 §四同一條。

拒交形狀：`no_delivery` **4**、`true_refuse` **2**、`timeout_killed` **3**（都同時是 `no_delivery`）、
`fake_refuse` **0**。

⚠ **6 個拒交格裡有 3 格是被 `--timeout 900` 砍掉的**（pbgate2 是 11 個裡 2 格）。
**`--timeout 900` 也是我們自己的參數。** 見第五節末。

## 四、三家在 1004 上一致嗎

| task | pi | Claude Code | OpenCode | 三家一致？ |
|---|---|---|---|---|
| `lcb_3522` | 交付 | 交付 | 交付 | 同（全交付） |
| `lcb_3583` | 交付 | 拒交 `no_delivery` | 交付 | **異** |
| `lcb_3584` | 交付 | 拒交 `true_refuse` | 交付 | **異** |
| `lcb_3637` | 拒交 `timeout_killed,no_delivery` | 交付 | 交付 | **異** |
| `lcb_3654` | 交付 | 交付 | 交付 | 同（全交付） |
| `lcb_3681` | 交付 | 交付 | 交付 | 同（全交付） |
| `lcb_3686` | 交付 | 交付 | 交付 | 同（全交付） |
| `lcb_3700` | 拒交 `timeout_killed,no_delivery` | 拒交 `true_refuse` | 拒交 `timeout_killed,no_delivery` | 同（全拒交） |
| `lcb_3764` | 交付 | 交付 | 交付 | 同（全交付） |
| `lcb_3794` | 交付 | 交付 | 交付 | 同（全交付） |

**三家方向一致 7/10 題**（6 題全交付、1 題全拒交）；**1003 那批是 4/10**。

可以講的：在這 10 題上，換掉那個會咬人的後端之後，**三個框架的判決彼此靠得比較近**。
不可以講的：這**不是**「框架差異消失了」——`lcb_3583`／`lcb_3584`／`lcb_3637`
三題仍然至少有一家不一樣，而且每格 n=1。

## 五、⚠ 主要發現：**`finish_reason="length"` 在 1004 上 0 次，而那個 16384 一個字沒改**

這是本輪要回答的那一題。pbgate2 §四 的原話：

> pi 的 5 個拒交格逐格長一樣：前 3 通 `tool_calls`、第 4 通 `length`，pi 就收工了……
> 其中 4 格的 reasoning tokens 是 **16,406–16,421** ——**16,384 的輸出預算幾乎整份被思考吃掉**。

**本輪結果**（[`finish_reason_census.txt`](finish_reason_census.txt)，逐位元重算 264 通）：

```
finish_reason 在 30 格裡出現過的值只有兩個：
    "tool_calls"  172 次
    "stop"         27 次
    "length"        0 次   ←── 就是這個 0
req_cap 逐格仍然印得出來：pi 10 格全部 max_completion_tokens=16384（接線沒改）
                          claude／opencode 20 格全部 max_tokens=32000（框架預設）
```

### ⚠ 先證明這個 0 是量到的

**本輪最關鍵的數字是一個 0 ⇒ 必須先證明量具讀得到非 0**（memory「判成『0』之前先證明量得動」）。
**兩個互相獨立的量法，各自帶自己的正控制**：

| 量法 | 對本輪（1004） | 對必中的輸入 |
|---|---:|---|
| `census3.py` 的 SSE 解析器 | `length` **0 格** | 同一支解析器跑在 **pbgate2 歸檔的 1003 wire 位元組**上 ⇒ 讀出 **6 格**，與 pbgate2 自己記的 6 格**逐格相同** |
| 不靠解析器，直接對原始位元組 `LC_ALL=C grep '"finish_reason":"length"'` | 528 個 `*.bin` 命中 **0** | 對一個手造的必中輸入命中 **1** |

⇒ **這個 0 是量到的 0，不是量具壞掉。**

### pi 那 5 格怎麼了

| task | 1003（thinking） | 1004（非 thinking） |
|---|---|---|
| `lcb_3522` | 拒交，第 4 通 `length`，reasoning 84 | **交付**，6 通，`stop`＋`tool_calls` |
| `lcb_3584` | 拒交，第 4 通 `length`，reasoning 16,421 | **交付**，15 通 |
| `lcb_3686` | 拒交，第 4 通 `length`，reasoning 16,406 | **交付**，8 通 |
| `lcb_3794` | 拒交，第 4 通 `length`，reasoning 16,408 | **交付**，7 通 |
| `lcb_3700` | 拒交，第 4 通 `length`，reasoning 16,421 | **仍是拒交，但機制換了**：0 個 `length`，打了 **37 通** `tool_calls` 之後被 `--timeout 900` 砍掉（`agent_rc=-9`） |

**⇒ 假說成立的那一半**：pbgate2 那 5 格的**直接機制**（輸出預算被思考吃光）
在非 thinking 後端上**一格都沒有重現**。4 格變成交付，第 5 格改用完全不同的死法。
**那不是「pi 比較差」，是「我們的接線參數 × thinking 後端」。**

⚠ **假說沒有被驗到的那一半**：這**不等於**「pi 與另外兩家一樣好」。
本輪只證明了那一個特定機制不在，**沒有**證明其他差異不存在——那需要預註冊與樣本數。

### ⚠ 失效模式換了個地方咬人

pi 在 1004 上打的通數變多了（1003 那 10 格 `rs` 合計 **58**，本輪 **122**）——
思考不再吃掉輸出預算，工具呼叫迴圈就跑得更久。結果：

- `lcb_3637_pi`：1003 交付（432.8 s）→ 1004 **拒交**，17 通、900 s 被砍
- `lcb_3700_pi`：1003 拒交（`length`）→ 1004 拒交，**37 通**、900 s 被砍

⇒ **失效模式從「token 上限吃掉工具呼叫」換成「工具呼叫迴圈吃掉牆鐘」。
`--timeout 900` 與 `maxTokens 16384` 都是我們自己的參數，兩個都不是「agent 比較差」。**
這一條要跟第一條一起講，不可以只講前半。

## 六、跟 `pbgate2`（1003）的逐格對照

⚠ **這是逐格列一樣／不一樣，不是效果量、不是檢定、不准相減。**

| task | agent | 1003（thinking） | 1004（非 thinking） | 方向 | 1003 那側撞 `length`？ |
|---|---|---|---|---|---|
| `lcb_3522` | pi | 拒交 `no_delivery` | 交付 | **翻** | **是** |
| `lcb_3583` | pi | 交付 | 交付 | 同 | 否 |
| `lcb_3584` | pi | 拒交 `no_delivery` | 交付 | **翻** | **是** |
| `lcb_3637` | pi | 交付 | 拒交 `timeout_killed,no_delivery` | **翻** | 否 |
| `lcb_3654` | pi | 交付 | 交付 | 同 | 否 |
| `lcb_3681` | pi | 交付 | 交付 | 同 | 否 |
| `lcb_3686` | pi | 拒交 `no_delivery` | 交付 | **翻** | **是** |
| `lcb_3700` | pi | 拒交 `no_delivery` | 拒交 `timeout_killed,no_delivery` | 同 | **是** |
| `lcb_3764` | pi | 交付 | 交付 | 同 | 否 |
| `lcb_3794` | pi | 拒交 `no_delivery` | 交付 | **翻** | **是** |
| `lcb_3522` | claude | 交付 | 交付 | 同 | 否 |
| `lcb_3583` | claude | 拒交 `no_delivery` | 拒交 `no_delivery` | 同 | 否 |
| `lcb_3584` | claude | 交付 | 拒交 `true_refuse` | **翻** | 否 |
| `lcb_3637` | claude | 交付 | 交付 | 同 | 否 |
| `lcb_3654` | claude | 拒交 `true_refuse` | 交付 | **翻** | 否 |
| `lcb_3681` | claude | 交付 | 交付 | 同 | 否 |
| `lcb_3686` | claude | 交付 | 交付 | 同 | 否 |
| `lcb_3700` | claude | 拒交 `timeout_killed,true_refuse` | 拒交 `true_refuse` | 同 | 否 |
| `lcb_3764` | claude | 交付 | 交付 | 同 | 否 |
| `lcb_3794` | claude | 交付 | 交付 | 同 | 否 |
| `lcb_3522` | opencode | 交付 | 交付 | 同 | 否 |
| `lcb_3583` | opencode | 交付 | 交付 | 同 | 否 |
| `lcb_3584` | opencode | 拒交 `timeout_killed,no_delivery` | 交付 | **翻** | 否 |
| `lcb_3637` | opencode | 交付 | 交付 | 同 | 否 |
| `lcb_3654` | opencode | 拒交 `true_refuse` | 交付 | **翻** | 否 |
| `lcb_3681` | opencode | 交付 | 交付 | 同 | 否 |
| `lcb_3686` | opencode | 交付 | 交付 | 同 | 否 |
| `lcb_3700` | opencode | 拒交 `no_delivery` | 拒交 `timeout_killed,no_delivery` | 同 | **是** |
| `lcb_3764` | opencode | 交付 | 交付 | 同 | 否 |
| `lcb_3794` | opencode | 交付 | 交付 | 同 | 否 |

**同 21 ∶ 翻 9**。逐 agent：

| agent | 1003（thinking） | 1004（非 thinking） | 翻面 |
|---|---|---|---:|
| pi 0.85.1 | 5 交付 ∶ 5 拒交 | **8 ∶ 2** | 5/10 |
| Claude Code 2.1.278 | 7 ∶ 3 | **7 ∶ 3** | 2/10 |
| OpenCode 1.18.31 | 7 ∶ 3 | **9 ∶ 1** | 2/10 |

**歸因分不分得開，逐條講**：

- ✅ **pi 那 4 格分得開**（`3522`／`3584`／`3686`／`3794`）：1003 那一側**全部**撞 `length`，
  1004 這一側 `length` 出現 0 次，而接線參數逐位元相同。**機制被量到了。**
- △ **`lcb_3637_pi` 與 `lcb_3700_pi` 分得一半**：死因確定是牆鐘（`agent_rc=-9`、
  `agent_timed_out=true`），確定**不是** token 上限。但「為什麼在 1004 上要打 17／37 通」
  只有一個觀測，**不可歸因**。
- ❌ **另外 4 格（`3584_claude`／`3654_claude`／`3584_opencode`／`3654_opencode`）分不開**：
  1003 那一側**都不是** `length` 格，本輪也沒有量到任何機制。n=1 ⇒ 它們可能是後端差異、
  可能是取樣雜訊。**寫成「後端造成的」是超譯。**
- ⚠ **一個沒排除的變數**：兩批都是三條 lane 並行（這一點是**對齊的**），
  但本輪 `timeout_killed` 比例較高（3/6 vs 2/11）。牆鐘型拒交的跨批解讀要帶這一句。

## 七、**「框架差異」與「框架×thinking 差異」現在拆開了嗎**

**拆開了一條，沒有全拆開。**

| 問題 | 答案 |
|---|---|
| pbgate2 的 `5∶7∶7` 裡，pi 那個 5 是不是「pi 比較差」？ | ❌ **不是**。它的直接機制是 `maxTokens 16384 × thinking`，本輪換後端之後那個機制 0 次出現、5 格裡 4 格翻成交付。**這一條拆開了。** |
| 三個框架在**同一台後端**上還剩多少差異？ | 1004 上 8∶2 ∶ 7∶3 ∶ 9∶1，三家方向一致 7/10。**有剩，但每格 n=1、非預註冊 ⇒ 不可量化、不可排名。** |
| 現在有 2 後端 × 3 框架的全格了嗎？ | ✅ **有**（pbgate2 的 30 格 ＋ 本輪的 30 格 ＝ 60 格），**但每格仍然只有 1 個觀測** ⇒ 拆得開的是「有沒有這個機制」，拆不開的是「差多少」。 |

**現在還拆不開的**（下一個該做的對照，本輪**沒做**）：
把 `wrap_agent.sh` 的 pi `maxTokens` 從 16384 改成 32000、**在 1003 上**重跑那 10 格。
若 `length` 消失 ⇒ 歸因直接落到那個常數；若還在 ⇒ 是 thinking 本身而不只是預算。
⚠ 改它要先決定「改了之後 r535／展件那批用 pi 的歸檔資料還比不比得起來」——
那不是本輪的授權範圍。

## 八、後端是量到的，不是宣稱的

- **1004** `http://100.86.226.21:1234`，`gemma-4-12b-it-qat`
- **同一份 gguf**：發射前 `/api/v0/models` 實測兩台都是 `quantization=Q4_0`、`arch=gemma4`、
  `loaded_context_length=262144`、`state=loaded`。
- **非 thinking**。判準：`choices[0].message.reasoning_content` 的字元數 ＋
  巢狀 `usage.completion_tokens_details.reasoning_tokens`。
  發射前探針 1004 ＝ **0 字元／0 tokens**。
- **正控制**：**同一支探針、同一次執行**對 1003 跑一次 ＝ **588 字元／267 tokens**
  ⇒ 這支量具讀得出差別，1004 的 0 是量到的 0。逐字在
  [`backend_probe_raw.json`](backend_probe_raw.json)。
- ⚠ **頂層 `usage.reasoning_tokens` 兩台都是 `None`**（不在回應裡）。**讀它永遠 None，
  不可以當判準。** 本輪第三次確認。
- **全批證據**：264 通逐位元重算，OpenAI 那條 wire 上 reasoning tokens 合計 **0**、
  `reasoning_content` 合計 **0 字元**（pbgate2 在 1003 上是 93,095／242,918）。
- **第二個獨立指標**：Anthropic 那條 wire 上的 `content_block_start(type=thinking)` 區塊數
  ＝ **0**（pbgate2 用同一支解析器在 1003 上數到 **11**）。
  ⚠ 它與 `reasoning_tokens` **不是同一個量**，不可相加、不可換算。
- 1004 **原生支援** `POST /v1/messages`（含 `tool_use`）——這是 Claude Code 零接線的前提，
  在 1004 上**也**成立（發射前直測 `stop_reason=tool_use`）。
- ⚠ **1004 的 LM Studio 版本本輪沒量到**（這台沒有可用的 SSH，HTTP 回應頭也沒有版本）。
  `runs/pbgate_lcb2_20260919/manifest.json` 在 2026-09-19 對同一台量到
  `0.4.17.0（FileVersion 0.4.17+4）`、`lms` CLI commit `6041ae0`——
  **那是前一批的量測，不是本輪的。**

## 九、事後隱藏測資計分（**衍生物，不是被量的東西**）

**先講負控制**：[`hidden_scorer_negative_control.json`](hidden_scorer_negative_control.json)
——退化樁 `def <entry_point>(*a, **k): return None`，**10/10 題都被擋下來**。
沒有它，下面那句話不可信。

- **24 個交付格，隱藏測資 24/24 全過**（26/26、27/27 或 28/28）
  ⇒ 在這 24 格上，「可見驗收過了」沒有出現**假通過**。
- 拒交格：`lcb_3584_claude` 25/28、`lcb_3700_claude` 18/27、`lcb_3583_claude` import 不起來；
  其餘 3 個拒交格**沒有 `solution.py` 可以計分**。

⚠ **三條不准省的邊界**（逐字沿用前兩輪）：

1. **這是衍生物。** 它沒有在跑的時候影響任何一格，也沒有任何一個位元組回饋給模型。
   報表裡兩個數字（`vis` 與 `hidden`）必須分開講。
2. **`vacant_network/suitegauge.py` 的單邊保證一個字都沒鬆。** 「這 24 格沒有假通過」
   **不等於**「可見套件涵蓋了真需求」——只是這一批沒量到反例。n 很小，
   而且 LCB 的可見 case 只有 2–4 條。
3. **渲染出來的 `test_hidden.py` 比既有判準寬**（`vacant_network/checks.py` 的 AST 政策
   在這條路徑上沒有套用）⇒ **本輪的隱藏分與 r460／r532 的 `meets_demand` 不可互引。**

## 十、成本

| 項 | 值 |
|---|---|
| 格數 | 30（**3 條 lane 同時跑**，每條 lane 內部序列） |
| 發射窗（UTC） | **2026-09-19 22:18:31 → 23:13:22**（約 55 分鐘） |
| agent 牆鐘總和 | 7,739.0 s；最大 900.0 s（**3 格**撞上限） |
| 模型呼叫 | **261 通**（`requests_seen`，每格 5–37）；wire 上逐位元落盤 264 通 |
| prompt tokens | 4,074,830（**下界**） |
| completion tokens | 149,728（**下界**） |
| reasoning tokens | **0**（量到的 0，見第八節） |

⚠ **token 是下界**：264 通裡 **17 通沒有 `usage`**，其中 13 個 `*.resp.bin` 是 0 位元組
（10 個是 Claude Code 每格必打一次的 `HEAD /api/hello`，沒有 body；另 3 個是被中斷在飛的）。
⚠ `index.jsonl` 261 行 vs `*.resp.bin` 264 個 ⇒ **3 通在被 SIGKILL 的那一刻只寫得出檔案、
來不及寫索引**（對得上 3 個 `timeout_killed` 格）。**「沒量到」≠「量到 0」**（鐵律 3）。

## 十一、誠實邊界（**不准淡化**）

1. **不是效果量。** 每格 n=1、10 題、一個模型、一台後端。24∶6 與 1003 的 19∶11 **不可相減**。
2. **8∶7∶9 不是框架能力排名。**
3. **假說只被驗掉一條**：驗到的是「`length` 在非 thinking 後端上 0 次」，
   **不是**「pi 與另外兩家一樣好」。
4. **牆鐘型失效反而變多**（3/6 vs pbgate2 的 2/11），而 `--timeout 900` **也是我們的參數**。
5. **proxy records，不 verifies**；本輪**沒有出網封鎖**。
6. **中介的是模型通道不是 agent 的行為。**
7. **`--sandbox none`**：驗收沒有跑在沙箱裡。
8. **`--retry none`**：量的是閘門本身，不是 V1 重試迴圈的增益（30 格 `attempts_used` 全 1）。
9. **不是模型能力評測。**
10. **LCB v2 的 `contest_date` 是 2023-08-26 → 2025-04-05**，**不能**宣稱晚於訓練截止。
11. **1004 的 LM Studio 版本本輪沒量到。**
12. **沒量到 ≠ 量到 0**：沒量出網封鎖、codex（**刻意**，為了與 pbgate2 同組）、
    hermes（沒裝）、N 臂、重試迴圈、A 層 10 題、MBPP+／HumanEval+／LCB v1／v3、
    以及**「把 16384 改掉之後 1003 上會怎樣」**（第七節那個對照，本輪沒做）。

口徑用「**可究責性 / 讓依賴有根據**」，不用「信任」。

## 十二、怎麼自己重驗

```bash
# 1) 負控制先跑：證明驗章器抓得到壞鏈
.venv/bin/python -m vacant_network.vrun.verify_receipts --selftest

# 2) 驗這 30 條鏈
.venv/bin/python -m vacant_network.vrun.verify_receipts \
    --glob 'runs/pbgate3_backend_lcb2_20260920/cells/*'

# 3) 題庫樹沒漂（比對 100 個檔與 bank_manifest 的釘值；**不要**用 build_bank.py --check，
#    那支現在會因為渲染器漂了而 FAIL，見 pbgate2 README §十一）
python3 runs/pbgate3_backend_lcb2_20260920/verify_bank_tree.py .

# 4) 事後隱藏計分與它的負控制（零模型呼叫）
cat runs/pbgate3_backend_lcb2_20260920/hidden_scorer_negative_control.json

# 5) 收尾原因普查（本輪的 0；需要 wire 原始位元組，先解開 wire.tar.gz）
cat runs/pbgate3_backend_lcb2_20260920/finish_reason_census.txt

# 6) 那個 0 的正控制：同一支解析器跑在 pbgate2（1003）的歸檔 wire 上，應該讀出 6 格 length
mkdir -p /tmp/w2 && tar xzf runs/pbgate2_agents_lcb2_20260920/wire.tar.gz -C /tmp/w2
sed 's#pathlib.Path("/var/tmp/vacant_pbgate3")#pathlib.Path(__import__("sys").argv[1])#' \
    runs/pbgate3_backend_lcb2_20260920/census3.py > /tmp/census_probe.py
python3 /tmp/census_probe.py /tmp/w2 | grep -c length    # 應該是 6

# 7) 落盤完整性
cd runs/pbgate3_backend_lcb2_20260920 && shasum -a 256 -c SHA256SUMS
```

## 十三、檔案

| 檔 | 是什麼 |
|---|---|
| `manifest.json` | **所有參數**：題庫出處＋逐題 id、三個 agent 的版本／wire／接線／輸出上限、後端、旗標、發射窗、量具與控制、紅線、誠實邊界、wire 對帳 |
| `matrix.json` | 30 格逐格的完整欄位＋`solution_text`＋`wire_usage`（逐 wire 分開）＋`refusal_shape`＋事後隱藏分 |
| `SUMMARY.txt` | 一行一格的摘要表 |
| `MATRIX.log` | 三條 lane 的發射全程逐字（每格 BEGIN/END、退出碼、關鍵欄位、`upstreams_seen`） |
| `finish_reason_census.txt` | 30 格的收尾原因普查（第五節那個 **0** 的來源）；產生器 `census3.py` |
| `cells/<cell>/` | `run_RUN-ON.json`／收據鏈＋公鑰／`rows.jsonl`／`visible_RUN-ON.json`／`agent_stdout.log`／`wire/index.jsonl`／`argv.txt`／frozen 的 `solution.py`／`_NOT_PREREGISTERED.txt` |
| `wire.tar.gz` | 30 格 wire 的**原始位元組**（`*.req.bin`／`*.resp.bin`，528 檔、未壓 17 MB）——收據的 `wire_digest` 簽的就是這些 |
| `receipts_verify.txt` | selftest（負控制）＋ 30 條鏈的驗證輸出（**在執行端跑的那一份**） |
| `receipts_verify_archived_copy.txt` | 同樣兩步，但跑在**本目錄這份歸檔副本**上 ⇒ 外人 clone 下來照第十二節第 2 步就能重現同一行 |
| `vgt_scan.txt` | V/GT 分離掃描：30 格 wire ＋ 工作區，**TOTAL_HITS = 0** |
| `hidden_scorer_negative_control.json` | 事後計分器的退化樁負控制（10/10 擋住） |
| `backend_probe_raw.json` | 發射前對 **1004 與 1003** 的逐字探針（**1003 是正控制**，證明量具讀得出非 0） |
| `length_census_controls.txt` | 第五節那個 **0** 的兩個正控制的逐字輸出 |
| `smoke_prelaunch.txt` | 發射前三格冒煙的摘要（`lcb_3534`，A 層，**不在被量的 10 題裡**，不進 `cells/`） |
| `pbgate3_cell.sh`／`pbgate3_matrix.sh`／`collect3.py`／`census3.py`／`vgt_scan3.sh`／`verify_bank_tree.py`／`probe.py` | 這一輪實際跑的那幾支 |
| `NOT_IN_REPO.json` | 沒進 repo 的東西：在哪、多大、為什麼不帶、怎麼重建 |

裁決：[`decisions/DECISION_20260920_PUBLIC_BENCH_GATE_BACKEND.md`](../../decisions/DECISION_20260920_PUBLIC_BENCH_GATE_BACKEND.md)
