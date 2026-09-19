# DECISION 2026-09-20 — 公開題庫上的閘門，**換後端**再跑一次（拆開 pbgate2 拆不開的那一條）

> **狀態：非預註冊。** 這一份記的是一批**描述性**觀測，不是假說檢定。
> 不准與 R535／R530／R534／G 實驗的任何數字合併、平均或對照；
> **也不准與 `runs/pbgate2_agents_lcb2_20260920` 或 `runs/pbgate_lcb2_20260919` 相減當效果量**
> ——三批都是非預註冊，兩個描述性觀測相減不會變成檢定。
> 不准寫「複製」「效果消失」「顯著」「優於」。

- run：[`runs/pbgate3_backend_lcb2_20260920/`](../runs/pbgate3_backend_lcb2_20260920/)
- 發射窗（UTC）：**2026-09-19 22:18:31 → 23:13:22**（約 55 分鐘，**3 條 lane 並行**）
- 執行端：vacant-dev `user1@100.124.254.83`；repo 子集 commit `b5654eac`（**與 pbgate2 同一個**）
- 後端：**1004** `http://100.86.226.21:1234`，`gemma-4-12b-it-qat`，**非 thinking**（量過，見 §五）
- 證據等級：**L-real**（真模型）

## 一、為什麼開這一批：把 `ae9cd4b4` 自己點名的混淆拆開

`runs/pbgate2_agents_lcb2_20260920` 誠實邊界第 9 條：

> **跨 agent 的結果與後端綁在一起。** 本輪三個 agent 全部只在 1003 跑過，
> **沒量** 1004 上的 Claude Code／OpenCode ⇒ 拆不開「框架差異」還是「框架×thinking 差異」。

**本輪只補這一條，範圍沒有擴大。** 30 格逐格重跑，**唯一被變的東西是後端**：

| 項 | 與 pbgate2 |
|---|---|
| 10 題（R534 B 層全取）／臂 V／prompt／旗標 | ✅ 一字不改 |
| pi 0.85.1・Claude Code 2.1.278・OpenCode 1.18.31 | ✅ 同版本（發射前逐個 `--version` 實測） |
| `ops/vacantrun/wrap_agent.sh`，**含 pi 段那個 `"maxTokens":16384`** | ✅ **一個字沒動** |
| repo 子集 commit | ✅ `b5654eac`，**刻意不用本分支 HEAD** |
| 併發（3 條 lane） | ✅ 同 |
| **後端** | ❌ **1003（thinking）→ 1004（非 thinking）** |

**為什麼不改那個 16384**：pbgate2 §四 量到的機制是「**我們自己設的** 16384 × **thinking 後端**」的
交互作用。**保住它才驗得到那條假說。** 改掉它等於同時動兩個東西。

**為什麼 repo 子集用舊 commit**：`ae9cd4b4` 之後 `vacant_network/vrun/{launcher,wireproxy,verify_receipts,proxyd,sandbox}.py`
都改了（加了 attestation 維度）。用新的等於同時動後端與 harness。
`ops/vacantrun/wrap_agent.sh` 與 `ops/gain/r534/` 在兩個 commit 之間 `git diff --stat` **是空的**。

`diff pbgate2_cell.sh pbgate3_cell.sh` 只有四處：註解、`ROOT`、兩個上游 URL、`--task-id` 前綴。

**沒跑 codex／hermes**：codex 是**刻意不跑**（pbgate2 為避開 1003 的 thinking runaway 沒跑它，
本輪要逐格可對照所以也不跑；⚠ 這**不代表** codex 在 1004 上跑不動，**本輪沒量**）。
hermes vacant-dev 上**沒裝**（發射前實測 `command -v hermes` 是 MISSING）——**沒量到，不是量到 0**。

## 二、判決：30 格，24 交付 ∶ 6 拒交

| agent | 1003（pbgate2） | **1004（本輪）** | 翻面 |
|---|---|---|---:|
| pi 0.85.1 | 5 ∶ 5 | **8 ∶ 2** | 5/10 |
| Claude Code 2.1.278 | 7 ∶ 3 | **7 ∶ 3** | 2/10 |
| OpenCode 1.18.31 | 7 ∶ 3 | **9 ∶ 1** | 2/10 |

判準三條（`accepted` ＋ `stop_reason` ＋ 退出碼）逐格都成立。三個不可省的旁證：

1. **`requests_seen` 全部 ≥ 5**（5–37，合計 **261**），`wire_by_protocol` 全部非空
   ⇒ **0 個假拒交格**。
2. `verify_receipts --selftest` **先 PASS**（負控制）再驗這一批：
   `run 30　鏈 30　entries 60　驗過 60　失敗 0　壞鏈 0`、`中介：有 30　零請求 0`。
   歸檔副本上再驗一次，同一行。
3. V/GT 分離掃描 **0 命中**；`infra_void` 0 格；`upstreams_defaulted` 30 格全空，
   `upstreams` 30 格逐格寫 `env:…` → `http://100.86.226.21:1234`（沒有一格用預設值）。

事後隱藏測資計分（衍生物、零模型呼叫）：**24 個交付格 24/24 全過**，
**而且退化樁負控制 10/10 擋得住**——沒有那條負控制，前半句不可信。

## 三、⚠ 主要發現：**`finish_reason="length"` 在 1004 上 0 次，而那個 16384 一個字沒改**

逐位元重算 30 格 264 通的 `*.resp.bin`：

```
finish_reason 在 30 格裡出現過的值只有兩個：
    "tool_calls"  172 次
    "stop"         27 次
    "length"        0 次   ←── 就是這個 0
req_cap 逐格仍然印得出來：pi 10 格全部 max_completion_tokens=16384（接線沒改）
```

### 先證明這個 0 是量到的

**本輪最關鍵的數字是一個 0 ⇒ 先證明量具讀得到非 0**（memory「判成『0』之前先證明量得動」）。
**兩個互相獨立的量法，各自帶自己的正控制**：

| 量法 | 對本輪（1004） | 對必中的輸入 |
|---|---:|---|
| `census3.py` 的 SSE 解析器 | `length` **0 格** | 同一支解析器跑在 **pbgate2 歸檔的 1003 wire 位元組**上 ⇒ **6 格**，與 pbgate2 自己記的逐格相同 |
| 直接對原始位元組 `LC_ALL=C grep` | 528 個 `*.bin` 命中 **0** | 手造的必中輸入命中 **1** |

⇒ **這個 0 是量到的 0。** 逐字在 `runs/pbgate3_backend_lcb2_20260920/length_census_controls.txt`。

### pi 那 5 格怎麼了

| task | 1003（thinking） | 1004（非 thinking） |
|---|---|---|
| `lcb_3522` | 拒交，第 4 通 `length`，reasoning 84 | **交付** |
| `lcb_3584` | 拒交，第 4 通 `length`，reasoning 16,421 | **交付** |
| `lcb_3686` | 拒交，第 4 通 `length`，reasoning 16,406 | **交付** |
| `lcb_3794` | 拒交，第 4 通 `length`，reasoning 16,408 | **交付** |
| `lcb_3700` | 拒交，第 4 通 `length`，reasoning 16,421 | **仍是拒交，但機制換了**：0 個 `length`，打了 **37 通** `tool_calls` 之後被 `--timeout 900` 砍掉 |

**⇒ 假說成立的那一半**：pbgate2 那 5 格的**直接機制**（輸出預算被思考吃光）
在非 thinking 後端上**一格都沒有重現**。
**pbgate2 §四 那句「不准讀成 pi 比較差」現在有第二個目擊者了。**

⚠ **假說沒有被驗到的那一半**：這**不等於**「pi 與另外兩家一樣好」。
本輪只證明那一個特定機制不在，**沒有**證明其他差異不存在。

## 四、⚠ 第二個發現：失效模式換了個地方咬人

pi 在 1004 上打的通數變多（1003 那 10 格 `rs` 合計 **58** → 本輪 **122**）——
思考不再吃掉輸出預算，工具呼叫迴圈就跑得更久：

- `lcb_3637_pi`：1003 **交付**（432.8 s）→ 1004 **拒交**，17 通、900 s 被砍
- `lcb_3700_pi`：1003 拒交（`length`）→ 1004 拒交，**37 通**、900 s 被砍

本輪 6 個拒交格裡 **3 格**是 `timeout_killed`（pbgate2 是 11 個裡 2 格）。

⇒ **失效模式從「token 上限吃掉工具呼叫」換成「工具呼叫迴圈吃掉牆鐘」。
`--timeout 900` 與 `maxTokens 16384` 都是我們自己的參數，兩個都不是「agent 比較差」。**
**這一條不可以只講前半。**

## 五、後端是量到的，不是宣稱的

- **同一份 gguf**：發射前 `/api/v0/models` 實測兩台都是 `quantization=Q4_0`、`arch=gemma4`、
  `loaded_context_length=262144`、`state=loaded`。
- **thinking 判準**：`choices[0].message.reasoning_content` 字元數 ＋ 巢狀
  `usage.completion_tokens_details.reasoning_tokens`。發射前探針 **1004 ＝ 0 字元／0 tokens**。
- **正控制**：**同一支探針、同一次執行**對 1003 ＝ **588 字元／267 tokens**
  ⇒ 量具讀得出差別，1004 的 0 是量到的 0。
- ⚠ **頂層 `usage.reasoning_tokens` 兩台都是 `None`**。**讀它永遠 None，不可以當判準。**
  （memory「兩張卡共 8 串」那條，**第三次**確認。）
- **全批證據**：264 通逐位元重算，OpenAI wire 上 reasoning tokens 合計 **0**、
  `reasoning_content` 合計 **0 字元**（pbgate2 在 1003 上是 93,095／242,918）。
- **第二個獨立指標**：Anthropic wire 上的 `content_block_start(type=thinking)` 區塊數 ＝ **0**
  （pbgate2 用同一支解析器在 1003 上數到 **11**）。⚠ 兩個數不可換算、不可相加。
- 1004 **原生支援** `POST /v1/messages`（含 `tool_use`）⇒ Claude Code 的零接線在 1004 上**也**成立。
- ⚠ **1004 的 LM Studio 版本本輪沒量到**（沒有可用的 SSH；本輪不去動金鑰，HTTP 頭也沒有版本）。
  引用 `0.4.17` 時要說那是 `runs/pbgate_lcb2_20260919` 在 2026-09-19 量的。

## 六、**「框架差異」與「框架×thinking 差異」拆開了嗎**

**拆開了一條，沒有全拆開。**

| 問題 | 答案 |
|---|---|
| pbgate2 的 `5∶7∶7` 裡，pi 那個 5 是不是「pi 比較差」？ | ❌ **不是**。直接機制是 `maxTokens 16384 × thinking`；換後端之後那個機制 0 次出現、5 格裡 4 格翻成交付。**這一條拆開了。** |
| 三個框架在**同一台後端**上還剩多少差異？ | 1004 上 8∶2 ∶ 7∶3 ∶ 9∶1，三家方向一致 **7/10**（1003 是 4/10）。**有剩，但每格 n=1、非預註冊 ⇒ 不可量化、不可排名。** |
| 現在有 2 後端 × 3 框架的全格了嗎？ | ✅ 有（pbgate2 的 30 格 ＋ 本輪 30 格 ＝ 60 格），**但每格仍然只有 1 個觀測** ⇒ 拆得開的是「有沒有這個機制」，拆不開的是「差多少」。 |

**9 個翻面格的歸因，逐條講**：

- ✅ **pi 那 4 格分得開**（`3522`／`3584`／`3686`／`3794`）：1003 那一側**全部**撞 `length`，
  1004 這一側 `length` 出現 0 次，接線參數逐位元相同。**機制被量到了。**
- △ **`lcb_3637_pi`、`lcb_3700_pi` 分得一半**：死因確定是牆鐘（`agent_rc=-9`），
  確定**不是** token 上限；但「為什麼要打 17／37 通」只有一個觀測，**不可歸因**。
- ❌ **另外 4 格（`3584_claude`／`3654_claude`／`3584_opencode`／`3654_opencode`）分不開**：
  1003 那一側**都不是** `length` 格，本輪也沒量到任何機制。
  **寫成「後端造成的」是超譯。**

**下一個該做的對照（本輪沒做）**：把 `wrap_agent.sh` 的 pi `maxTokens` 從 16384 改成 32000、
**在 1003 上**重跑那 10 格。若 `length` 消失 ⇒ 歸因縮到那個常數；若還在 ⇒ 是 thinking 本身。
⚠ 改它要先決定「改了之後 r535／展件那批用 pi 的歸檔資料還比不比得起來」——不在本輪授權範圍。

## 七、誠實邊界（不准淡化）

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
12. **沒量到 ≠ 量到 0**：沒量出網封鎖、codex（**刻意**）、hermes（沒裝）、N 臂、重試迴圈、
    A 層 10 題、MBPP+／HumanEval+／LCB v1／v3、以及 §六 末那個「改掉 16384」的對照。

口徑用「**可究責性 / 讓依賴有根據**」，不用「信任」。

## 八、機器上留下了什麼、清了什麼

本輪在 vacant-dev 上自己建了五個路徑，收官後全部刪除：
`/var/tmp/vacant_pbgate3`、`/var/tmp/vacant_pbgate3_smoke`（發射前就刪）、
`/var/tmp/pbgate3_negctl`（發射前就刪）、`/var/tmp/pbgate3_repo.tgz`、`/var/tmp/pbgate3_evidence.tgz`。
⚠ 這五個路徑**都是本輪自己建的**；`/var/tmp` 底下其他 `vacant_*` 目錄是別輪的，一個都沒動。
⚠ **沒有重開機、沒有殺任何不是自己起的行程**——人類的四個長跑行程
（29 天 ×2 的 `http.server`、17 天的 `claude --resume`、8420 那個）與 `vacant-exhibit.service`
收官後逐個確認仍然活著。
⚠ 本輪自己只用了 **33 MB**；同一段時間磁碟從 1.6 GB 掉到 0.9 GB，**那不是本輪造成的**
（`/tmp` 底下有別的 session 的 9.6 GB 工作樹）。
