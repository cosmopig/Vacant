# DECISION 2026-09-19（三）— 展件從 L-none 變成 L-real：54 格、兩臂都真的跑了

前情：`decisions/DECISION_20260919_TWIN_V2_FIDELITY.md`（忠實度對照表，18 處不一樣）
的 §六-2 逐字寫著「**18 格仍然全是 L-none**（`requests_seen = 0`）。這一輪一次模型
都沒呼叫。」而電視畫面上寫死著大橫幅「**正在發生**／這一筆是真的 Vacant agent
此刻做的，不是重放」。

**那句話當時是假的。** 本輪把它變成真的——不是改掉那句話，是把底下的東西跑出來。

同時修掉對照表 A4 那一條：監視器印「同題關掉這層：**也擋下**」，而那一臂
（`liveAssemble` 寫死 `OFF: null`）**一次都沒跑過**。替一個沒發生的反事實作證，
是展場版鐵律 5 的正面違反，而且「展場的主視覺就是這個對照，這條錯得最貴」。
**現在 OFF 臂有 206 通真的模型呼叫。**

---

## 一、跑了什麼

| 項 | 值 |
|---|---|
| 格數 | **54 格**（3 位居民 × **9 題** × 2 種題面） |
| 每格幾跑 | **2 跑**（ON／OFF）⇒ 共 **108 次 `vacant run`** |
| 題目 | `s1_01_addmul`／`s1_05_initials`／`s1_12_hms`／`s1_24_is_pal`／`s1_30_ord_suffix`／`s1_31_money`／`s1_32_pct`／`s1_34_days_in`／`s1_49_rgb` |
| 居民 | DUL-89／KAL-52／LIV-51（`ops/exhibit/twin/roster.py` 程序生成） |
| ON 臂 | `--retry revise --max-attempts 3`（閘門＋回饋＋再 spawn） |
| OFF 臂 | `vacant_on=False`（純 tee：不驗收、不簽收據、不拒交） |
| agent | pi 0.85.1，走 `ops/vacantrun/wrap_agent.sh pi` |
| 模型呼叫總數 | **630 通**（ON 424 ／ OFF 206），逐通位元組落盤在 `wire_RUN-{ON,OFF}/` |
| 牆鐘 | 兩批共約 **83 分**：第一批 9m05s（18 格）＋第二批 73m43s（36 格），皆四條流並行 |
| 落盤 | `runs/twin_real_20260919/`（19 MB，含兩臂的 wire 與凍結快照） |
| 沙箱 | `bwrap`（54 格一致） |

### 題目怎麼挑的（換過兩次，判準都是展場判準）

舊的三題是 `s1_01_addmul`／`s1_02_span`／`s1_03_nwords`。兩條規則：

1. **需求一句話講得完。** `span` 與「什麼算一個 word」要先解釋才聽得懂，換掉。
   現在九題全部是一句話：加起來和乘起來／姓名縮寫／秒數變時鐘／是不是回文／
   第幾名的英文字尾／305 分寫成 $3.05／百分比／某年某月幾天／色碼拆成 r,g,b。
2. **全部取自 S1**，因為 S1 的坑是**客戶要的函式名字沒寫在需求裡**，
   而那正是展場要演的那件事。S2 的坑是行為被扣住（題面裡已經有函式名），
   那是另一個故事，混進來會讓「扣住／寫明」這一組對照失焦。

**為什麼從 3 題加到 9 題**：手機當導播（觀眾自己點要看哪一格）是已拍板的方向，
那條路吃的是**反事實對照的題目多樣性**，不是格數。3 題 × 3 居民＝18 格，
但觀眾按三下就把不同的題目看完了，剩下的只是換一個代號在演同一題。

「扣住／寫明」兩格用**同一題**，差別只有 `TASK.md` 有沒有那一塊 `## Interface`。
**這件事是可執行判準不是承諾**：`test_the_withheld_name_really_is_withheld`
逐題檢查那個名字在扣住版裡真的不存在、在寫明版裡真的存在（9 題 10 個名字全過）。

---

## 二、後端是哪一台哪一版（**不可與 1003 的數字混講**）

| 項 | 值 |
|---|---|
| 端點 | **1004**＝`100.86.226.21:1234`（LM Studio **0.4.17**） |
| 模型 | `gemma-4-12b-it-qat` |
| 推論模式 | **非 thinking** |
| 執行端 | vacant-dev（`100.124.254.83`，Ubuntu、8 核），沙箱後端 `bwrap` |
| 並行 | 4 串（1004 的槽數；**沒有超派**） |

### 「非 thinking」是量的，不是宣告的

判準是**回應裡有沒有 `reasoning_content`**，逐通掃 `wire_*/*.resp.bin` 的 SSE 塊：

```
回應檔數：635（635 個都解析得出 SSE 塊）
含非空 reasoning_content 的回應數：0 ／塊數：0
usage.reasoning_tokens 的取值分佈：{'None': 632}
回應宣稱的 model：{'gemma-4-12b-it-qat': 21200 塊}
```

⚠ **`usage.reasoning_tokens` 不可以當判準**：這 632 筆全部回 `None`，而 1003 也回
`None`——拿它當尺會把 thinking 的 1003 與非 thinking 的 1004 判成同一台。
本輪的判準是 `reasoning_content` 在不在。

⚠ 1003（0.4.24）把**同一份 gguf** 跑成 thinking 模式。**本批的數字全部在 1004 產，
所以內部一致；與 1003 的任何數字不可混講成一批。**

---

## 三、結果：逐格

每題三位居民各一格，所以每格顯示的是 3 格的合計。

```
題目                 扣住介面（held）          寫明介面（pc）
                     ON收下/拒交 ｜ OFF事後過   ON收下/拒交 ｜ OFF事後過
s1_01_addmul         收0 拒3 ｜ OFF過 0/3      收3 拒0 ｜ OFF過 3/3
s1_05_initials       收0 拒3 ｜ OFF過 0/3      收3 拒0 ｜ OFF過 3/3
s1_12_hms            收0 拒3 ｜ OFF過 0/3      收3 拒0 ｜ OFF過 3/3
s1_24_is_pal         收0 拒3 ｜ OFF過 0/3      收3 拒0 ｜ OFF過 3/3
s1_30_ord_suffix     收0 拒3 ｜ OFF過 0/3      收3 拒0 ｜ OFF過 3/3   ← 扣住那 3 格全部逾時，見下
s1_31_money          收0 拒3 ｜ OFF過 0/3      收3 拒0 ｜ OFF過 3/3
s1_32_pct            收0 拒3 ｜ OFF過 0/3      收0 拒3 ｜ OFF過 0/3   ← 唯一「寫明也過不了」的題
s1_34_days_in        收0 拒3 ｜ OFF過 0/3      收3 拒0 ｜ OFF過 3/3
s1_49_rgb            收0 拒3 ｜ OFF過 0/3      收3 拒0 ｜ OFF過 3/3

扣住介面 n=27：ON 收下  0／拒交 27；OFF 事後過  0；進迴圈 27、迴圈救回 0
寫明介面 n=27：ON 收下 24／拒交  3；OFF 事後過 24；進迴圈  3、迴圈救回 0
全批 54 格：進迴圈 30 格、**迴圈救回 0 格**；ON 嘗試次數分佈 {1 次: 24, 3 次: 30}
```

**證據等級（逐格推導，不是宣告）**：ON **L-real 54/54**、OFF **L-real 54/54**、
`void_cells` **0**、兩臂起點逐位元相同 **54/54**。

### ⚠ 有 3 格的「拒交」有一部分是我們的 `--timeout` 造成的

`s1_30_ord_suffix__held` 三位居民**全部**跑到 300 秒被砍（ON 8 次嘗試＋OFF 2 格，
共 10 次 `agent_rc = -9`、`agent_timed_out = true`）。launcher 砍掉 agent 之後
照樣凍結工作區、照樣送驗收——**那是對的**（它交出去的就是那些位元組），
但兩者的 `stop_reason` 都是 `visible_fail`，只看那個欄位就會把
「**我們沒等它**」講成「**它做不出來**」。

⇒ 本輪把它變成資料：`attempts[*].agent_timed_out`＋`any_attempt_timed_out`
（pack）、`draft_done.timed_out`＋`timed_out_note`（事件流），
守門的是 `test_a_killed_attempt_is_distinguishable_from_one_that_just_failed`。
**那 3 格在展場上必須標出來**，不可以和其他 24 格拒交混講。

### ⚠ `s1_32_pct` 是唯一一題「寫明介面也過不了」

失敗的是邊界情況，不是名字：`pct(0, 0)` 期望 `0.0`，它回 `None`。
那個條件**寫在需求文字裡**（「When the second quantity is zero…」），
它沒讀到。⇒ **「把介面寫明就會過」不是定律**，第一批 3 題剛好全過是那 3 題的
性質。展場不可以把「寫明 ⇒ 會過」講成規則。

`pack.evidence_level` 是 fail-closed 的：`requests_seen == 0` 一律落成 L-none，
`--evidence L-real` 蓋不過去。可執行判準在
`tests/test_twin_fidelity.py::test_evidence_level_is_derived_per_cell_never_declared`
與 node check 的 N10。

### 最值得放在展場牆上的那個數字：**它每一次都說自己做完了**

```
ON 臂（逐次嘗試）：(stop_reason, agent_rc) → 次數
   ('visible_fail',  0)    82      ← 交付物沒過驗收，而 agent 回報「成功」
   ('visible_fail', -9)     8      ← 這 8 次是被我們的 300 秒上限砍掉的，不算
   ('visible_pass',  0)    24
OFF 臂：('ungated', 0) 52 ／ ('ungated', -9) 2
```

**90 次沒過驗收的嘗試裡，82 次 `agent_rc = 0`**（其餘 8 次是我們砍的，扣掉不算）。
框架跑完、印出結果、退出碼 0、語氣很有把握；閘門在行程結束的那一刻才量出 0/2。

⚠ 第一批寫的是「27 次全部 rc=0」。擴到 54 格之後**那句話要修正**：
`-9` 真的出現了，而且集中在同一題。所以正確的講法是
「**沒有被我們砍掉的失敗嘗試，全部回報成功（82/82）**」。

⚠ 這**不是 pi 的怪癖**：同日的跨框架量測顯示 pi／OpenCode／Claude Code／Codex
四個 agent 的拒交格 `agent_rc` **全部是 0**。
⇒ 「agent 自己說它做完了」與「它做出來的東西通過驗收了」是兩件事，
而現在的工具鏈**只把前者交給使用者**。那正是這個系統要處理的那件事，
也是展場最容易讓外行聽懂的一句話。

### 展場那一句現在可以這樣講

**54 格裡，30 格有差別，24 格沒有差別。**

- **24 格沒有差別**（介面寫明而且它做對了）：兩臂都交出能過的東西。
  **有沒有這一層，結果一樣。** 展場不可以只演有差別的那些。
- **30 格有差別**（27 格介面被扣住 ＋ 3 格 `s1_32_pct` 寫明也沒做對）：
  - 有這一層 ⇒ 閘門擋下 → 把失敗原文給它 → 它再跑一次 → 再擋 → 再給 → 再跑 →
    三次用完 ⇒ **拒交**，而且留下一條從創世驗得到鏈頭的簽章鏈。
  - 沒有這一層 ⇒ 一次 spawn、沒有人量、**東西就這樣出去了**，沒有任何收據。
    我們**事後**用同一把尺量那 30 份交付：**30 份全部不會過**。

⇒ 一句話：**沒有這一層，30 件事後量起來不合格的東西出貨了；有這一層，那 30 件
被擋下來，而且擋下來這件事留了一張你可以自己重算的收據。**

⚠ 注意這句話裡**沒有**「Vacant 讓它做對了」。兩臂的交付物正確與否**完全一致**
（ON 拒交的 30 格，OFF 事後稽核也是 30 格沒過；ON 收下的 24 格，OFF 也是 24 格過）。
這一層改變的是**不合格的東西會不會出去**，不是它合不合格。

---

## 四、可究責性這一端的驗收（全部落盤、可重跑）

| 檢查 | 指令 | 結果 |
|---|---|---|
| 尺本身有沒有牙齒（負控制） | `python3 -m vacant.vrun.verify_receipts --selftest` | **PASS** |
| 這一批的收據鏈 | `--glob 'runs/twin_real_20260919/runs/*'` | **總判 OK**，54 條鏈、168 筆 entry 逐筆驗過 |
| 展件頁面 | `node ops/exhibit/twin/twin_viewer_node_check.mjs` | **15/15 全過**（N1–N14） |
| 測試 | `.venv/bin/python -m pytest tests/ -q` | **全綠** |

`verify_receipts` 另外誠實報出 `arms_without_receipts = ["RUN-OFF"]`——
**那不是失敗，那是結論**：OFF 臂本來就沒有收據，尺自己說得出來。

### N4 這一次才真的被考到

`N4 交付物樹雜湊 ＝ 鏈上的 ws_end_sha256` **54/54 過**。

這一條在 fixture 批上**驗不到**：fixture 全部是 1 次嘗試，第 1 次的凍結快照
（`_frozen_RUN-ON`）剛好等於最後一次，讀錯也看不出來。**本批有 30 格是 3 次嘗試**，
`ws_end_sha256` 指的是 `_frozen_RUN-ON_a3` ⇒ 對照表 E1 修的那個坑
（`delivery_of` 讀錯快照）第一次被真資料考過。

⚠ 順帶一個對展件有利的後果，現在是**看得到的**：ON 臂 held 格的交付物是
`['TASK.md', 'VACANT_FEEDBACK.md', 'solution.py']`，OFF 臂是
`['TASK.md', 'solution.py']`。觀眾在收據頁上會看到那個回饋檔**就躺在那裡**。

### E2 這一次也真的被考到

對照表 E2（`redact_paths` 只比對「現在的 run_dir」）這一輪走了最強的路徑：
**在 Linux（`/var/tmp/vacant_twinreal/...`）跑、搬到 macOS 的 worktree 重 pack**。
`tests/test_twin_fidelity.py::test_pack_has_no_absolute_build_paths` 過
（`/Users/`、`/home/`、`worktrees/agent-` 一個都沒有漏進 `twin_pack.json`
與展件頁面）。順手補了一刀：清洗原本只掃 `_frozen_RUN-ON`，**OFF 臂的路徑不會被清**
——同一個形狀換一臂。已改成兩臂都掃，判準在同一條測試裡。

---

## 五、哪些忠實度缺口因此被修掉

| # | 對照表原文 | 本輪狀態 |
|---|---|---|
| **A4** | 活模式 `OFF: null`，**這一批根本沒有 OFF 臂**，一次都沒跑 ⇒ 印「也擋下」是替沒跑過的反事實作證 | **修掉（生產端）**：54 格都有真的 OFF 臂，206 通、`same_start_as_on` 54/54。電視端要讀得到還缺 P10 |
| **A6** | 橫幅寫死「正在發生／真的 agent 此刻做的」，而 18 格全是 L-none ⇒ 那句話是假的 | **底下的東西變真了**：54/54 L-real。電視端已改讀 `task_opened.evidence`（另一條線），**標籤會自己變對** |
| **B2** | 「沒量」被壓成「量了，沒過」 | **修掉且加固**：OFF 臂的 `accepted` 恆為 `null`、`stop_reason=ungated`，`validate` 會咬（負控制在 `test_validate_rejects_an_off_arm_that_claims_a_gate_or_a_receipt`） |
| **C1** | V1 的重試迴圈整段在展件上消失，**而那正是 R530／R532 量到增益的那個東西** | **修掉**：事件流上 114 筆 `gate_ran`、**60 筆 `revised`**、168 筆 `draft_done`。逐格看得到「擋下 → 給失敗原文 → 再跑一次」 |
| **C2** | 事件契約裡沒有證據等級這個欄位 | **生產端給了**：`task_opened.evidence` ＋ `counters.evidence_counts`，逐格 |
| **C3** | `blocked_by` 寫死，四種停止理由講成一件事 | **真的分出來了**：本批第一次出現 `attempts_exhausted`（30 格）與 `visible_pass`（24 格）。fixture 批只有 `visible_fail`，分不分得開看不出來 |
| **E1** | `delivery_of`／`pack` 讀第 1 次的快照配最後一次的裁決 ⇒ 資料長成「驗收沒過＋收下了」 | **第一次被真資料考過**：30 格 3 次嘗試，N4 54/54 |
| **E2** | `redact_paths` 與位置有關 ⇒ 建置機器路徑漏進展場螢幕 | **跨機器考過**，並補上 OFF 臂那一半 |
| — | 鐵律 3 的 `infra_void` | **新增可執行處理**：跑掛的格抽進 `void_cells`，不進 `cells`、不進事件流、不進 `evidence_counts`。本批 0 格，但冒煙時真的觸發過一次（agent 路徑寫成相對路徑 ⇒ `agent_spawn_failed`），**fail-visible 不是靜靜跑錯** |
| — | 逾時與失敗同形 | **新增**：`agent_timed_out` 進 pack 與事件流。本批 3 格（`s1_30_ord_suffix__held`）10 次被砍，不標就會被講成「它做不出來」 |

### 一個順手修掉、但沒人點名過的

`revised` 事件原本把**重試臂**（`revise`／`resample`）寫在一個叫 `arm` 的欄位裡，
而電視的去重鍵是 `ts|type|task_id|arm|reviewer`。加了 OFF 臂之後這會壞：
patch 過的電視按 `arm` 分 ON／OFF 時，`revised` 會掉進一個叫 `"revise"` 的第三組，
**那一格的重改拍就從 ON 那一串裡消失**。⇒ 重試臂改名 `retry_arm`，`arm` 專職分臂。

### 另一個：`feedback_bytes` 的 0 會說謊

本批走 `--feedback-into file`（預設）⇒ 回饋寫進工作區的 `VACANT_FEEDBACK.md`、
**不進 prompt** ⇒ 每一次嘗試的 `feedback_in_prompt_bytes` 都是 **0**。
畫面上只看到一串 0，會被讀成「根本沒給它回饋」。**兩件事在展場上差很多**：
一個是機制沒動，一個是機制動了而 agent 沒去讀。
⇒ `draft_done` 加上 `feedback_delivery` ＋ `feedback_note`，逐字寫出走的是哪一條管道，
並標明「它有沒有去讀是另一回事——R535 量過檔案這條管道在 wire 上零命中」。

---

## 六、哪些還沒修

**`vacant_hm` 本輪一個字都沒動**（與前一輪同）。對照表 §四那 13 條電視端 patch
仍然全部未套用，其中：

| # | 還在的問題 |
|---|---|
| **D1** | `byAgent[lt.ON.worker]` 找不到居民代號 ⇒ **每一筆被靜靜丟棄**。**活模式現在仍然一格都播不出來。** 這是頭號路障 |
| A1／A2／A5 | 電視仍會演「三人同儕評審 0/0」「抽樣稽核：沒抽中」「擋下（評審否決）」——生產端一個事件都不發，但**不發事件擋不住電視自己編** |
| A3 | 仍寫「依信譽紀錄路由給 X」，不讀 `routed.basis`（生產端誠實寫 `random` ＋ 反證字串） |
| A6／P6 | 橫幅仍寫死「正在發生」，不讀 `task_opened.evidence`。**本批全部 L-real，所以那句話碰巧成立了——但它成立的理由不是它讀了資料** |
| B3／P4 | 生產端兩個 hash 都帶了（`prompt_sha256` ＋ `chain_head`），電視端還沒拆成兩行 |
| P10 | `OFF` 現在有真資料了，電視端還沒有任何一行程式讀它 |
| P13 | 電視取**第一筆** `gate_ran`；本批 30 格各有 3 筆 ⇒ 取到的是第 1 次那一筆 |
| **C4** | per-cell 的 `verify_url`：**另一條線已做**（`cell_verify_url()` ＋ `/r/<cell_id>`）。本輪沒動，合併後就有 |
| **D3** | 離線靜態伺服器（`serve_twin.py`）**沒做**；`file://` 下活模式被 CORS 擋 |
| — | 手機端（`phone.html`）**一行程式都還沒寫** |
| — | `meets_demand` 仍一律 `null`（要隱藏測資才答得出來，而隱藏測資不進展件） |

---

## 七、還不能說的話

1. **不能說「Vacant 讓 agent 做對了」。**
   **30 格進了重試迴圈，救回來 0 格。** 三次嘗試、每次都拿到可見驗收的失敗原文，
   30 格全部 `attempts_exhausted`。更強的說法是：**兩臂的交付物正確與否完全一致**
   （ON 拒交 30／OFF 事後稽核沒過 30；ON 收下 24／OFF 事後稽核過 24）。
   本批量到的是「閘門擋住了不合格的交付」，**不是**「迴圈提升了成功率」。
   R530／R532 量到增益是別的批、別的題、別的條件，**不可以拿本批當那件事的證據**。

2. **不能說「有這一層比較好」。** 54 格裡有 **24 格兩臂結果一樣**（介面寫明而且
   它做對了）。差別只出現在那 30 格。展場要講的是那個條件，不是
   「Vacant 總是比較好」。

2b. **不能說「把介面寫明就會過」。** `s1_32_pct` 寫明版三格全部沒過
   （`pct(0, 0)` 期望 `0.0`、回 `None`，而那個條件寫在需求文字裡）。
   第一批 3 題剛好全過是那 3 題的性質，不是定律。

3. **事後稽核不是裁決。** OFF 臂那個「沒過」是我們**跑完之後**用同一把尺補量的，
   當時沒有任何人量、沒有進收據鏈、沒有簽章、agent 也不知道它會發生。
   資料上三個旗標一起走（`when="after_the_run"`／`is_verdict=false`／`signed=false`），
   頁面上必須印成「我們事後量的」，**不可以印成「OFF 也被擋下」**。

4. **「通過驗收」≠「符合需求」。** 驗收是**單邊保證**（`vacant/suitegauge.py` 同一條）：
   擋得住已知壞解 ≠ 涵蓋真需求。`meets_demand` 一律 `null`。

5. **L-real 只證明「模型通道經過 Vacant」**（`requests_seen > 0` ＋ wire 裡逐通的
   `model` 欄位），**不證明上游真的是那台機器**——一個假上游可以對任何 model id
   回一句話。這是殘餘風險，寫在 `pack.py` 誠實邊界 1。本輪的佐證是 635 份回應
   逐通落盤、`model` 全部是 `gemma-4-12b-it-qat`，但那仍然是佐證不是證明。

6. **這一批是 12B、非 thinking、1004。** 與 1003（0.4.24，thinking）的任何數字
   **不可混講成一批**。

7. **n = 54，但**「獨立」的單位是**9 題**不是 54 格。** 三位居民跑的是同一組題目、
   同一個模型、同一組參數，代號與造型是展件的敘事不是實驗因子。
   **居民之間不可當成獨立重複**——每題三格高度相關（本批 9 題裡有 8 題
   三位居民的結果完全相同）。

8. **「正在發生」這四個字仍然不准對觀眾說。** 展件資料是**預跑好的**
   （展場硬約束 1：真模型每題等不起，本批平均每格數十秒到 5 分鐘）。
   電視端已改成讀 `task_opened.evidence`，所以 L-real 的格子標籤會變對——
   但「L-real」的意思是**這一格真的有模型參與**，不是**此刻正在跑**。
   畫面上要講「這是那一天真的跑出來的紀錄，你可以自己重驗」。

9. **有 3 格的拒交是我們砍出來的。** `s1_30_ord_suffix__held` 三格 10 次嘗試全部
   300 秒逾時。那 3 格**不可以**和其他 24 格拒交混講成「它做不出來」。

10. **`s1_30_ord_suffix` 的逾時本身沒有被解釋。** 我們只知道它會跑到上限被砍，
   不知道它在做什麼（wire 有逐通位元組，但本輪沒有分析）。
   **不要替它編一個原因。**

---

## 七之一、為什麼**不**補跑那 3 格逾時

1004 在收官時整台閒著，補跑的誘惑很大。**刻意不補**，理由是：

那 3 格（`s1_30_ord_suffix__held`）是在 `--timeout 300` 底下被砍的。用比較長的
上限重跑它們，就會讓**同一批 54 格裡有兩種逾時條件**——而逾時條件會直接改變
「拒交」的意義。那比「有 3 格被我們砍掉」更糟：前者是一個**寫在資料上、
標得出來、讀得懂**的缺口，後者是一個**混在批裡、看不出來**的混淆。

⇒ 想知道「給它更長時間會不會做出來」是一個**好問題**，但那是**另一個掛牌的探針**
（同一題、只改 `--timeout`、自己一批、自己一份紀錄），不是往這一批打補丁。
本輪不做，也不假裝已經知道答案（§七-10）。

同理，本輪**沒有任何格需要補跑**：54/54 都是 L-real、`void_cells` 0、
OFF 臂 54/54 都跑成、9 題 × 3 居民一格不缺。

## 七之二、與活模式那條線的接口（`twin/v2-live-mobile`）

另一條線同日交付了 `serve_twin.py`＋`phone.html`＋電視端 P1–P13。兩條線**接得上**，
但有一條**必須寫清楚、否則會再犯一次 A4** 的規則。

### 接得上的部分（不必改對方一行）

`serve_twin.py` 是逐格呼叫 `to_events.events_for_cell(cell, ...)` 再整塊吐出的
⇒ 本輪加的 OFF 事件**自動跟著走**，不需要對方改程式。
而電視的證據徽章改讀 `task_opened.evidence` 之後，**本批 L-real 的格子標籤會自己變對**
——不必改任何文案，那正是 C2 當初要的形狀（電視要有資料才改得對）。

### ⚠ 一條硬規則：`OFF.accepted` 永遠是 `null`，**不可以拿事後稽核去填它**

電視現在仍寫死 `OFF: null`（`index.html:2024-2025`，註解寫著「這一批沒有跑過
OFF 臂」）。本輪之後那句話不再成立，那一行可以接真資料了。但接的時候：

| 欄位 | 值 | 不可以做的事 |
|---|---|---|
| `OFF.accepted` | **恆為 `null`** | 拿 `postaudit.all_pass` 去填它 |
| `OFF.meets_demand` | **恆為 `null`** | 同上（要隱藏測資才答得出來） |
| `OFF` 有沒有收據 | `verdict.has_receipt = false` | 印成「收據待補」——是**沒有**，不是還沒到 |
| OFF 那份交付過不過 | 在**另一個事件** `postaudit` 裡 | 把它畫成 OFF 臂的裁決 |

把 `postaudit.all_pass` 寫進 `OFF.accepted`，畫面就會變成「**關掉這層，另一邊也判了**」
——那是 A4 的同一個錯換一個方向：原本是替沒跑過的反事實作證，
變成替**沒發生過的判定**作證。那一臂當場沒有任何人量過，這是它的定義。

⇒ 電視要印 OFF 那一格的結果，**只能**印成「我們**事後**用同一把尺量：N/M」，
並且旁邊掛著 `postaudit` 自己帶的三個旗標。

⚠ 另外：`index.html:1374`／`:1380` 用 `t.OFF.accepted && !t.OFF.meets_demand` 算
`offLeaked`。那是 `replay_371`（G 實驗）的形狀——那一批**真的有**可量的 OFF 裁決。
接上 twin 的資料之後那兩行恆為 0，**而那是對的**：沒有隱藏測資就答不出漏出。
不要為了讓數字好看而改用 `postaudit`。

### 會撞的檔（合併順序由協調端決定）

| 檔 | 誰動了 | 形狀 |
|---|---|---|
| `ops/exhibit/twin/to_events.py` | **兩邊** | 對方加 `cell_verify_url()`／`follow()`；我改 `events_for_cell`／`validate`／`build` 的 counters。位置不重疊，預期可自動合 |
| `ops/exhibit/twin/twin_viewer_node_check.mjs` | **兩邊** | 兩邊都往檔尾 append 檢查 ⇒ 預期在尾端衝突，兩邊的檢查都要留 |
| `examples/twin_viewer.html` | **兩邊** | **產生物**：合併後重跑 `build_viewer.py` 即可，不要手動合 |
| `ops/exhibit/twin/{pack,run_twin}.py`、`twin_pack.json`、`runs/`、`tests/test_twin_*` | 只有我 | — |
| `serve_twin.py`、`phone.html`、`phone_node_check.mjs`、`exhibit_boot.sh`、`tests/test_serve_twin.py` | 只有對方 | — |

⚠ **`twin_pack.json` 只有我動**，所以真跑資料不會被合併吃掉。
⚠ 我的基底是 `ec338da2`，而 `twin/v2-live` 之後已經前進到 `a0470866`
（那一筆是措辭複查）——合併前要先把基底對齊。

## 八、動了哪些檔

```
ops/exhibit/twin/run_twin.py            一格兩跑（ON／OFF）；OFF 的事後稽核；
                                        --shard／--arms／--merge-only；題目換三題
ops/exhibit/twin/pack.py                pack_off()；兩臂的 redact_paths／model_from_wire／
                                        delivery_of；infra_void 抽進 void_cells
ops/exhibit/twin/to_events.py           off_events()：arm 標籤、OFF 不發 gate_ran／receipt、
                                        postaudit 事件；retry_arm 改名；feedback_delivery
ops/exhibit/twin/twin_viewer_node_check.mjs   N13（反事實臂真的跑過）、N14（事後稽核非裁決）
ops/exhibit/twin/twin_pack.json         重生（54 格真跑、L-real 54/54、OFF 臂 54/54）
examples/twin_viewer.html               重組（0.83 MB）
runs/twin_real_20260919/                新增：108 跑的全部落盤（19 MB）
runs/twin_fixture_20260919/events.jsonl 重生（跟著新的 to_events 走）
tests/test_twin_events.py               批的前提換了 ⇒ 那一條測試跟著換方向
tests/test_twin_fidelity.py             §七 新增 6 條：反事實臂／事後稽核／證據等級／infra_void
```

**`vacant/` 一個字都沒動。** 本輪是那一支的呼叫端，不是那一支。

### 重跑指令（零機時的那幾步）

```bash
python3 -m vacant.vrun.verify_receipts --selftest
python3 -m vacant.vrun.verify_receipts --glob 'runs/twin_real_20260919/runs/*'
python3 ops/exhibit/twin/pack.py --runs runs/twin_real_20260919 \
    --out ops/exhibit/twin/twin_pack.json
python3 ops/exhibit/twin/to_events.py --pack ops/exhibit/twin/twin_pack.json \
    --out runs/twin_real_20260919/events.jsonl
python3 ops/exhibit/twin/build_viewer.py --check
node ops/exhibit/twin/twin_viewer_node_check.mjs
.venv/bin/python -m pytest tests/test_twin_*.py tests/test_consent.py -q
```

發射指令（要機時）留在 `runs/twin_real_20260919/`，後端與並行度見 §二。
