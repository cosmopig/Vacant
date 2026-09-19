# DECISION 2026-09-19（三）— 展件的 18 格從 L-none 變成 L-real：兩臂都真的跑了

前情：`decisions/DECISION_20260919_TWIN_V2_FIDELITY.md`（忠實度對照表，18 處不一樣）
的 §六-2 逐字寫著「**18 格仍然全是 L-none**（`requests_seen = 0`）。這一輪一次模型
都沒呼叫。」而電視畫面上寫死著大橫幅「**正在發生**／這一筆是真的 Vacant agent
此刻做的，不是重放」。

**那句話當時是假的。** 本輪把它變成真的——不是改掉那句話，是把底下的東西跑出來。

同時修掉對照表 A4 那一條：監視器印「同題關掉這層：**也擋下**」，而那一臂
（`liveAssemble` 寫死 `OFF: null`）**一次都沒跑過**。替一個沒發生的反事實作證，
是展場版鐵律 5 的正面違反，而且「展場的主視覺就是這個對照，這條錯得最貴」。
**現在 OFF 臂有 47 通真的模型呼叫。**

---

## 一、跑了什麼

| 項 | 值 |
|---|---|
| 格數 | **18 格**（3 位居民 × 3 題 × 2 種題面） |
| 每格幾跑 | **2 跑**（ON／OFF）⇒ 共 **36 次 `vacant run`** |
| 題目 | `s1_01_addmul`／`s1_12_hms`／`s1_31_money`（`ops/gain/r535/bank/`） |
| 居民 | DUL-89／KAL-52／LIV-51（`ops/exhibit/twin/roster.py` 程序生成） |
| ON 臂 | `--retry revise --max-attempts 3`（閘門＋回饋＋再 spawn） |
| OFF 臂 | `vacant_on=False`（純 tee：不驗收、不簽收據、不拒交） |
| agent | pi 0.85.1，走 `ops/vacantrun/wrap_agent.sh pi` |
| 模型呼叫總數 | **143 通**（ON 96 ／ OFF 47），逐通位元組落盤在 `wire_RUN-{ON,OFF}/` |
| 牆鐘 | **9 分 05 秒**（2026-09-19T10:14:19Z → 10:23:24Z），四條流並行 |
| 落盤 | `runs/twin_real_20260919/`（4.2 MB，含兩臂的 wire 與凍結快照） |

### 題目為什麼換

舊的三題是 `s1_01_addmul`／`s1_02_span`／`s1_03_nwords`。換掉後兩題的判準是
**展場判準**（觀眾走到展場前面時有沒有差別），不是難度：`span` 與「什麼算一個
word」要先解釋才聽得懂。現在三題的需求各自一句話講得完——**把兩個數字加起來和
乘起來**、**把秒數變成時鐘標籤**、**把 305 分寫成 $3.05**——而且三題的坑是
同一個：**客戶要的那個函式名字沒寫在需求裡**。觀眾看第二格就懂了。

「扣住／寫明」兩格用**同一題**，差別只有 `TASK.md` 有沒有那一塊 `## Interface`。
這比「換一題比較簡單的」誠實得多。

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
回應檔數：143（143 個都解析得出 SSE 塊）
含非空 reasoning_content 的回應數：0 ／塊數：0
usage.reasoning_tokens 的取值分佈：{'None': 143}
回應宣稱的 model：{'gemma-4-12b-it-qat': 4674 塊}
```

⚠ **`usage.reasoning_tokens` 不可以當判準**：這 143 通全部回 `None`，而 1003 也回
`None`——拿它當尺會把 thinking 的 1003 與非 thinking 的 1004 判成同一台。
本輪的判準是 `reasoning_content` 在不在。

⚠ 1003（0.4.24）把**同一份 gguf** 跑成 thinking 模式。**本批的數字全部在 1004 產，
所以內部一致；與 1003 的任何數字不可混講成一批。**

---

## 三、結果：逐格

```
cell                           題面  ON裁決 嘗試 ON通數 ON停止理由           OFF通 OFF事後稽核
DUL-89__s1_01_addmul__held     扣住  拒交    3   6     attempts_exhausted   2     沒過
DUL-89__s1_01_addmul__pc       寫明  收下    1   2     visible_pass         2     過
DUL-89__s1_12_hms__held        扣住  拒交    3   9     attempts_exhausted   4     沒過
DUL-89__s1_12_hms__pc          寫明  收下    1   2     visible_pass         2     過
DUL-89__s1_31_money__held      扣住  拒交    3   9     attempts_exhausted   4     沒過
DUL-89__s1_31_money__pc        寫明  收下    1   2     visible_pass         2     過
KAL-52__s1_01_addmul__held     扣住  拒交    3   6     attempts_exhausted   2     沒過
KAL-52__s1_01_addmul__pc       寫明  收下    1   2     visible_pass         2     過
KAL-52__s1_12_hms__held        扣住  拒交    3   11    attempts_exhausted   4     沒過
KAL-52__s1_12_hms__pc          寫明  收下    1   2     visible_pass         2     過
KAL-52__s1_31_money__held      扣住  拒交    3   9     attempts_exhausted   3     沒過
KAL-52__s1_31_money__pc        寫明  收下    1   2     visible_pass         3     過
LIV-51__s1_01_addmul__held     扣住  拒交    3   6     attempts_exhausted   2     沒過
LIV-51__s1_01_addmul__pc       寫明  收下    1   2     visible_pass         2     過
LIV-51__s1_12_hms__held        扣住  拒交    3   13    attempts_exhausted   4     沒過
LIV-51__s1_12_hms__pc          寫明  收下    1   2     visible_pass         2     過
LIV-51__s1_31_money__held      扣住  拒交    3   9     attempts_exhausted   3     沒過
LIV-51__s1_31_money__pc        寫明  收下    1   2     visible_pass         2     過
```

**證據等級（逐格推導，不是宣告）**：ON **L-real 18/18**、OFF **L-real 18/18**、
`void_cells` **0**。

`pack.evidence_level` 是 fail-closed 的：`requests_seen == 0` 一律落成 L-none，
`--evidence L-real` 蓋不過去。可執行判準在
`tests/test_twin_fidelity.py::test_evidence_level_is_derived_per_cell_never_declared`
與 node check 的 N10。

### 最值得放在展場牆上的那個數字：**退出碼全部是 0**

```
ON 臂（逐次嘗試）：(stop_reason, agent_rc) → 次數
   ('visible_fail', 0)     27      ← 交付物沒過驗收，而 agent 回報「成功」
   ('visible_pass', 0)      9
OFF 臂：('ungated', 0)     18      ← 沒有人量，一樣回報「成功」
```

**27 次沒過驗收的嘗試，27 次 `agent_rc = 0`。** 框架跑完、印出結果、退出碼 0、
語氣很有把握；閘門在行程結束的那一刻才量出 0/2。

⚠ 這**不是 pi 的怪癖**：同日的跨框架量測顯示 pi／OpenCode／Claude Code／Codex
四個 agent 的拒交格 `agent_rc` **全部是 0**。
⇒ 「agent 自己說它做完了」與「它做出來的東西通過驗收了」是兩件事，
而現在的工具鏈**只把前者交給使用者**。那正是這個系統要處理的那件事，
也是展場最容易讓外行聽懂的一句話。

### 展場那一句現在可以這樣講

**9 格有差別，9 格沒有差別。**

- **介面寫明的 9 格**：兩臂結果一樣（都做對了）。**有沒有這一層沒有差別。**
- **介面被扣住的 9 格**：
  - 有這一層 ⇒ 閘門擋下 → 把失敗原文給它 → 它再跑一次 → 再擋 → 再給 → 再跑 →
    三次用完 ⇒ **拒交**，而且留下一條從創世驗得到鏈頭的簽章鏈。
  - 沒有這一層 ⇒ 一次 spawn、沒有人量、**東西就這樣出去了**，沒有任何收據。
    我們**事後**用同一把尺量那份交付：**0/2，不會過**。

---

## 四、可究責性這一端的驗收（全部落盤、可重跑）

| 檢查 | 指令 | 結果 |
|---|---|---|
| 尺本身有沒有牙齒（負控制） | `python3 -m vacant.vrun.verify_receipts --selftest` | **PASS** |
| 這一批的收據鏈 | `--glob 'runs/twin_real_20260919/runs/*'` | **總判 OK**，18 條鏈、54 筆 entry 逐筆驗過 |
| 展件頁面 | `node ops/exhibit/twin/twin_viewer_node_check.mjs` | **15/15 全過**（N1–N14） |
| 測試 | `.venv/bin/python -m pytest tests/ -q` | **全綠** |

`verify_receipts` 另外誠實報出 `arms_without_receipts = ["RUN-OFF"]`——
**那不是失敗，那是結論**：OFF 臂本來就沒有收據，尺自己說得出來。

### N4 這一次才真的被考到

`N4 交付物樹雜湊 ＝ 鏈上的 ws_end_sha256` **18/18 過**。

這一條在 fixture 批上**驗不到**：fixture 全部是 1 次嘗試，第 1 次的凍結快照
（`_frozen_RUN-ON`）剛好等於最後一次，讀錯也看不出來。**本批有 9 格是 3 次嘗試**，
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
| **A4** | 活模式 `OFF: null`，**這一批根本沒有 OFF 臂**，一次都沒跑 ⇒ 印「也擋下」是替沒跑過的反事實作證 | **修掉（生產端）**：18 格都有真的 OFF 臂，47 通、`same_start_as_on` 18/18。電視端要讀得到還缺 P10 |
| **A6** | 橫幅寫死「正在發生／真的 agent 此刻做的」，而 18 格全是 L-none ⇒ 那句話是假的 | **底下的東西變真了**：18/18 L-real。**但橫幅仍然寫死**，電視端 P6 沒改 ⇒ 見 §七-8 |
| **B2** | 「沒量」被壓成「量了，沒過」 | **修掉且加固**：OFF 臂的 `accepted` 恆為 `null`、`stop_reason=ungated`，`validate` 會咬（負控制在 `test_validate_rejects_an_off_arm_that_claims_a_gate_or_a_receipt`） |
| **C1** | V1 的重試迴圈整段在展件上消失，**而那正是 R530／R532 量到增益的那個東西** | **修掉**：事件流上 36 筆 `gate_ran`（9 格各 3 次＋9 格各 1 次）、**18 筆 `revised`**、54 筆 `draft_done`。逐格看得到「擋下 → 給失敗原文 → 再跑一次」 |
| **C2** | 事件契約裡沒有證據等級這個欄位 | **生產端給了**：`task_opened.evidence` ＋ `counters.evidence_counts`，逐格 |
| **C3** | `blocked_by` 寫死，四種停止理由講成一件事 | **真的分出來了**：本批第一次出現 `attempts_exhausted`（9 格）與 `visible_pass`（9 格）。fixture 批只有 `visible_fail`，分不分得開看不出來 |
| **E1** | `delivery_of`／`pack` 讀第 1 次的快照配最後一次的裁決 ⇒ 資料長成「驗收沒過＋收下了」 | **第一次被真資料考過**：9 格 3 次嘗試，N4 18/18 |
| **E2** | `redact_paths` 與位置有關 ⇒ 建置機器路徑漏進展場螢幕 | **跨機器考過**，並補上 OFF 臂那一半 |
| — | 鐵律 3 的 `infra_void` | **新增可執行處理**：跑掛的格抽進 `void_cells`，不進 `cells`、不進事件流、不進 `evidence_counts`。本批 0 格，但冒煙時真的觸發過一次（agent 路徑寫成相對路徑 ⇒ `agent_spawn_failed`），**fail-visible 不是靜靜跑錯** |

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
| P13 | 電視取**第一筆** `gate_ran`；本批 9 格各有 3 筆 ⇒ 取到的是第 1 次那一筆 |
| **C4** | **per-cell 的 `verify_url` 仍然沒做**：18 格共用同一個 `twin_viewer.html`。手機連動最基本的那一步還是缺的 |
| **D3** | 離線靜態伺服器（`serve_twin.py`）**沒做**；`file://` 下活模式被 CORS 擋 |
| — | 手機端（`phone.html`）**一行程式都還沒寫** |
| — | `meets_demand` 仍一律 `null`（要隱藏測資才答得出來，而隱藏測資不進展件） |

---

## 七、還不能說的話

1. **不能說「Vacant 讓 agent 做對了」。**
   **9 格進了重試迴圈，救回來 0 格。** 三次嘗試、每次都拿到可見驗收的失敗原文，
   9 格全部 `attempts_exhausted`。本批量到的是「閘門擋住了不合格的交付」，
   **不是**「迴圈提升了成功率」。R530／R532 量到增益是別的批、別的題、別的條件，
   **不可以拿本批當那件事的證據**。

2. **不能說「有這一層比較好」。** 介面寫明的那 9 格，兩臂結果一樣。
   差別只出現在**客戶沒把介面講清楚**的那 9 格。展場要講的是後者那個條件，
   不是「Vacant 總是比較好」。

3. **事後稽核不是裁決。** OFF 臂那個「沒過」是我們**跑完之後**用同一把尺補量的，
   當時沒有任何人量、沒有進收據鏈、沒有簽章、agent 也不知道它會發生。
   資料上三個旗標一起走（`when="after_the_run"`／`is_verdict=false`／`signed=false`），
   頁面上必須印成「我們事後量的」，**不可以印成「OFF 也被擋下」**。

4. **「通過驗收」≠「符合需求」。** 驗收是**單邊保證**（`vacant/suitegauge.py` 同一條）：
   擋得住已知壞解 ≠ 涵蓋真需求。`meets_demand` 一律 `null`。

5. **L-real 只證明「模型通道經過 Vacant」**（`requests_seen > 0` ＋ wire 裡逐通的
   `model` 欄位），**不證明上游真的是那台機器**——一個假上游可以對任何 model id
   回一句話。這是殘餘風險，寫在 `pack.py` 誠實邊界 1。本輪的佐證是 143 通 SSE
   逐通落盤、`model` 全部是 `gemma-4-12b-it-qat`，但那仍然是佐證不是證明。

6. **這一批是 12B、非 thinking、1004。** 與 1003（0.4.24，thinking）的任何數字
   **不可混講成一批**。

7. **n = 18，而且三位居民不是三個獨立重複。** 三位居民跑的是同一組題目、同一個模型、
   同一組參數，代號與造型是展件的敘事不是實驗因子。**居民之間不可當成獨立樣本。**

8. **展場現在仍然不可以播活模式。** 電視端 D1 沒改 ⇒ 每一筆事件都會被靜靜丟棄。
   而且橫幅那句「正在發生／真的 Vacant agent 此刻做的」**仍然是寫死的**——
   本批碰巧 18 格全 L-real 讓它成立，但它**不是因為讀了證據等級才成立**。
   下一批只要有一格 L-none，同一行程式就會再說一次謊。**P6 要照改。**

9. **凍結重放不是「正在發生」。** 展件資料是預跑好的（展場硬約束 1：真模型每題
   等不起）。畫面上要講「這是那一天真的跑出來的紀錄，你可以自己重驗」，
   **不是「此刻正在跑」**。

---

## 八、動了哪些檔

```
ops/exhibit/twin/run_twin.py            一格兩跑（ON／OFF）；OFF 的事後稽核；
                                        --shard／--arms／--merge-only；題目換三題
ops/exhibit/twin/pack.py                pack_off()；兩臂的 redact_paths／model_from_wire／
                                        delivery_of；infra_void 抽進 void_cells
ops/exhibit/twin/to_events.py           off_events()：arm 標籤、OFF 不發 gate_ran／receipt、
                                        postaudit 事件；retry_arm 改名；feedback_delivery
ops/exhibit/twin/twin_viewer_node_check.mjs   N13（反事實臂真的跑過）、N14（事後稽核非裁決）
ops/exhibit/twin/twin_pack.json         重生（18 格真跑、L-real 18/18）
examples/twin_viewer.html               重組（0.83 MB）
runs/twin_real_20260919/                新增：36 跑的全部落盤（4.2 MB）
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
