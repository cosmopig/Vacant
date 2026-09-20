# DECISION 2026-09-20 — **有 Vacant 的 pi ∶ 沒有 Vacant 的 pi**，同題同機同時跑

> **狀態：發射前凍結（非預註冊檢定）。** 這一份凍結的是**設計與判準**，不是假說檢定。
> 判準在發射前寫死，結果回來之後不准改判準。
> 🔴 **不准**與 R535／R530／R534／G 實驗／pbgate 任何一批的數字合併、平均或相減。
> 🔴 **不准**寫「複製」「效果消失」「顯著」「優於」「證明」。

- run：`runs/abpi_lcb2_20260920/`（收工後入庫）
- 執行端：vacant-dev `user1@100.124.254.83`（Ubuntu 24.04、kernel 6.8.0-137、Python 3.12.3）
- 工作根：`/var/tmp/vacant_abpi`，repo 子集自 `integrate/20260919` @ `b182df9e`
- 題庫樹雜湊：`find templates hidden -type f | sort | xargs sha256sum | sha256sum` ＝ `ba80fcfa6326f666…`
- agent：**pi 0.85.1**（`@earendil-works`，`~/.local/opt/node-v22.23.2-linux-x64/bin/pi`）
- 套件：`vacant-network` **0.8.0**
- 證據等級：**L-real**（真模型）

## 一、為什麼開這一批：pbgate 兩批都**只跑了 V 臂**

`runs/pbgate_lcb2_20260919`（pi×1004，20 格）與 `runs/pbgate2_agents_lcb2_20260920`
（三個 agent×1003，30 格）都把閘門放到公開題庫上跑過，但**兩批都沒有對照臂**：

> `pbgate2_matrix.sh`：`臂固定 V`；`DECISION_…_CROSSAGENT.md` §一：「只跑 V 臂」

⇒ 「有 Vacant」與「沒有 Vacant」**從來沒有在同一組題、同一台機器、同一段時間裡並排跑過**。
展場的雙世界對照要講的正是這一句，而支撐它的資料到現在為止是缺的。本輪補這一格。

## 二、設計：3 臂 × 20 題 × 2 後端 × 5 重複 ＝ **600 格**

| 臂 | 怎麼跑 | proxy | 收尾驗收 | 收據 | 拒交 |
|---|---|---|---|---|---|
| **ON** | `vacant run --vacant 1` | act | ✅ | ✅ | ✅ |
| **TEE** | `vacant run --vacant 0` | tee（只記錄） | ❌ | ❌ | ❌ |
| **BARE** | **完全不跑 `vacant run`** | 無 | ❌ | ❌ | ❌ |

**兩個對照各回答一個不同的問題，不可以混講：**

- **TEE 是機制對照**——proxy 還在、pi 的設定逐字相同，**只拿掉閘門**。
  ON−TEE 的差 ⇒ 閘門本身做了什麼。
- **BARE 是產品對照**——連 proxy 都沒有。TEE−BARE 的差 ⇒ **被包起來這件事本身**
  有沒有改變 agent 的行為。這一格是「Vacant 會不會拖慢／弄壞 agent」的唯一證據。

⚠ **三臂的 pi 設定必須逐字相同，否則整批不可判讀。** 做法：三臂都走同一支凍結的
`ops/vacantrun/wrap_agent.sh pi`（同一個 provider 形狀、同一個 `maxTokens:16384`）。
BARE 臂把 `VACANT_RUN_PROXY` 指向**後端本身**——那個變數名在 argv 裡仍然出現，
但它不是 proxy。**看 log 的人不要讀成「BARE 有 proxy」。**
（若改用 pi 原生預設，ON∶BARE 就會同時差「有沒有 Vacant」與「輸出預算」兩件事，
 而 `DECISION_…_CROSSAGENT.md` §四已經量過那個預算會單獨造成 5 格拒交 ⇒ 不可接受。）

其餘對齊：`cwd=工作區`、`stdin=/dev/null`、prompt 逐字相同、工作區純度 fail-closed 擋門
（四個檔，多一個少一個就停）、agent 逾時 900s、外包 1200s、`--test-timeout 120`、
`--retry none`、`--sandbox none`、模型 `gemma-4-12b-it-qat`。

**兩個後端一起跑**（不是二選一）：

| 代號 | 位址 | LM Studio | thinking | 發射前普查 |
|---|---|---|---|---|
| `b1003` | `100.119.113.56:1234` | 0.4.24 | **是** | `reasoning_len=472` |
| `b1004` | `100.86.226.21:1234` | 0.4.17 | **否** | `reasoning_len=0` |

理由：`vacant-gate-numbers-are-framework-bound` 已經立過「閘門數字綁框架×後端」。
本輪**不假設**這個對照跨後端成立，直接兩台都量。
⚠ **`reasoning_tokens` 不可用來判 thinking（兩台都回 None）**，要看 `reasoning_content`
——上表那兩個數字是這樣量的。

**併發**：8 條 lane（每後端 4 條，＝`lms` 實測 parallel=4 封頂）。
⚠ **每條 lane 混三臂、也混重複次序**。後端會隨時間漂（R419 量過），
臂與時間綁在一起就分不開「Vacant 造成的差」與「跑得比較晚造成的差」。

## 三、判準（發射前寫死）

**A. 閘門的判決** ＝ `run_RUN-ON.json` 的 `accepted` 逐字。**只有 ON 臂有。**
⚠ 檔名隨臂變：`--vacant 0` 落的是 `run_RUN-**OFF**.json`。找錯檔名會讓 TEE 的
`requests_seen` 假裝成 null——那正是本 repo 在抓的病，已在發射前修掉並複驗。

**B. 事後可見驗收** `postaudit_visible_*` ＝ 衍生物，零模型呼叫。
🔴 **不准填進 `accepted`。** TEE/BARE 沒有閘門就是沒有判決。
反事實欄位叫 `counterfactual_would_refuse`，**ON 臂不填**（ON 有真判決，不需要推算）。

**C. 事後隱藏測資** `postaudit_hidden_*` ＝ 衍生物，量「交出去的東西真的對嗎」。

**D. 三態**：BARE **沒有 proxy ⇒ 沒有量 `requests_seen` 的管道**，落 **null 不是 0**。
`meta.json` 帶一句 `measurement_gap` 說明。

**E. 負控制（不過就整批不可引用）**：兩把尺都要擋得住退化樁
（整支 `solution.py` 只有 `def <entry>(*a,**k): return None`），20 題全擋。
> **已於發射後、判讀前跑完：`hidden_blocks_all=True`、`visible_blocks_all=True`、
> `USABLE=True`、20 題零漏。**

**F. V/GT 分離**：隱藏測資的任何位元組不准出現在任何一格的任何落盤裡。

## 四、可以講什麼、不可以講什麼（發射前先寫死）

| 可以講 | 不可以講 |
|---|---|
| 逐格列「ON 這一格被擋／TEE 這一格交出去了」 | 把兩個臂的比率相減當成效果量 |
| 「agent 退出碼 0、自己宣告完成，閘門仍在行程結束那一刻擋下來」（跨後端若成立） | 「Vacant 讓 pi 做得比較好」——**閘門不改模型，它只決定要不要放行** |
| 「這一格 BARE 交出去的東西過不了它自己工作區裡就放著的驗收」 | 「沒有 Vacant 就會出錯 N%」——n=5 的描述性觀測不是率的估計 |

🔴 **最重要的一條**：本批**不量「Vacant 讓 agent 變強」**，那是 G 實驗的地盤，
而 `vacant-twin-54-lreal` 已經記過「迴圈救回 0/30」。本批量的是
**同一批交付，有沒有人在出口檢查，結果差在哪裡。**

## 五、發射紀錄

- 發射（UTC）：**2026-09-20 03:53:47**
- 發射前冒煙：三臂各一格（`lcb_3522`，b1004）＋ b1003 一格，**四格全通**
- 發射前後端普查：兩台 `/v1/models` HTTP 200、`17*23` 都回 `391`
- 磁碟擋門：`$ROOT` 低於 1500MB 時整條 lane 停下來講話（那台只有 38G）

## 六、沒量到的（先寫，免得回來補成好看的）

- **只有 pi**。不跨 agent。`CROSSAGENT` 那批已經立過逐格判決不跨框架 ⇒
  本批任何數字**綁死在 pi 0.85.1 上**。
- **沒有 enclosure**（`--sandbox none`）⇒ ON 臂的 `tier` 預期是 B′ 不是 A。
  本批量的是**閘門**，不是附身層級。
- **沒有重試**（`--retry none`）⇒ 不含 V1／V2 回饋管道。
- **非預註冊**、n=5、無檢定。
- 🔴 **已知污染（發射當下就記下，不是事後補的）**：發射後約前 25 分鐘，
  **同一台 vacant-dev 上另有一批 A 級重現性實驗在打 b1003**
  （`/var/tmp/vacant-rep-20260920`、`/var/tmp/venc_rep`，約 30 次 12 秒級的短跑）。
  ⇒ **b1003 早期那幾格的 `cell_wall_s` 帶著別人的負載**，牆鐘不可與後段直接比。
  判決欄位（`accepted`／`stop_reason`／`requests_seen`）不受影響。
  兩批互不干涉已逐項確認（對方沒碰 `/var/tmp/vacant_abpi`，我方沒碰它的目錄）。
- **併發條件與獨佔不同**：冒煙獨佔時每格 15–19 秒，8 條 lane 併發後第一格 110 秒。
  ⇒ **本批的牆鐘只能批內比，不可與 pbgate 兩批的牆鐘並排。**
