# R535 預註冊：重試回饋走**哪一條管道**才真的進得了模型的輸入

> **狀態：待凍結。** 本檔為發射前的預註冊正文。發射前必須：
> (1) Fable 核；(2) 人類簽字；(3) ledger 簽入；(4) §九 的四條 L 檢核全綠。
> 凍結之後 §〇～§十 **一個字都不准改**；要改只能加**附錄**。

人類指示（2026-09-19）：把 2026-09-18 兩跑解開 wire 之後看到的東西變成一輪可究責的量測。
Fable 裁決（2026-09-19）：四臂、兩層題庫、確認性檢定只有 H1、H2 是控制檢查、
H3 降為描述、`--sandbox none` ＋ `--test-timeout 30` ＋ 時序門 ＋ 汙染規則。

**題庫已於 2026-09-19 造完並釘值**（`bank_manifest.json` sha256 見 §二-1）。
**三個基建修法已併進 main 並釘死 sha**（§九 L-1：`cad1001`／`9420d81`／`e88c147`；
本檔凍結時 main HEAD ＝ `e88c147`）。

**剩一處 `<<TODO-FREEZE: …>>`**：`ops/gain/r535/` 底下那支**展開器**的檔名與 sha。
本檔只凍結它**必須滿足的規格**（§十三-1 的兩道牙齒）；實作由發射驅動那一側落地
（`ops/gain/r535/run_r535.py`），交件後由人類把檔名與 sha 補進來並簽入。
**佔位符沒補完就不准發射。**

---

## 〇、一句話

**`vacant run` 沒過就把可見驗收的失敗原文交回 agent 再試（最多 3 次）。回饋有兩條投遞管道：
寫檔進工作區（V1 預設，`--feedback-into file`）與塞進 argv（V2，`--feedback-into prompt`）。
2026-09-18 的兩次真 agent 實跑把 wire 全解開之後，`file` 這條管道的回饋文字
在第 2、3 次嘗試的請求裡出現次數是 0。本輪在一個為此設計的微型題庫上，
用同一顆模型、同一台機器、同一條 argv，量「換一條管道會不會改變最終可見通過率」。**

**唯一的變因是投遞管道**（三個重試臂都是 3 draw，`RS` 是不給回饋的重抽）。
本檔在 §四 事前寫死四臂各自的預測，在 §六 事前寫死狀態表與方向護欄，
在 §七 事前寫死「+5 pp 在任何可行 n 都測不出來」。

### 主要交付 ＝ **三個數字**（寫死；摘要與收官都照這三個講）

| # | 數字 | 為什麼是它 |
|---:|---|---|
| **1** | **M7_file（連同 M7_ws）**：RF 臂第 ≥2 次嘗試裡回饋進入輸入的比例。**預測 0**，命中 0 時報 **rule-of-three 上界**（`3/n_有第2次的格數`） | 它是本輪唯一**不靠統計檢定**就說得出話的量。§一 的觀察在 n=1 上成立，本輪把它變成一個有分母的數字 |
| **2** | **第 1 次嘗試可見失敗率**（**S1／S2 分開**；三臂合併 **n=150／120**） | ＝**閘門作用點的實測值**。零額外機時（§二-2「單發基線不另開臂」），而且它同時是 `NOT_TRIGGERED` 的判準來源 |
| **3** | **S1 的 H1 點估計 ＋ 95% 區間**（RP − RF） | 主假說的效果量。**報點估計與區間，不是報「顯不顯著」** |

**H1 的 `CONFIRMED_POSITIVE`／`CONFIRMED_NEGATIVE` 是附帶的，成立才引用。**
`RULED_OUT`／`INCONCLUSIVE` **事前就寫明是最可能的落點之一**（§七-4）。

### 為什麼不加 n（**事前寫死，收官不准回頭改**）

1. **綁定約束是出題與稽核品質，不是機時。** 90 題的設計、七項量具、V/GT 分離、
   跨層共用參考解的稽核（§十-14）——這些是本輪的成本所在。加 n 買不到它們。
2. **事前預期的機制情境落在 Δ ≥ +30 pp 那一列**（§七-1：n=50 檢定力 0.889）。
   「回饋完全進不了輸入 vs 一定進得了輸入」如果真的改變交付，效果量就在那個尺度。
   **n=50 對那個尺度有牙齒。**
3. **若真差只有 +10～+20 pp，那本身就是一個發現**——
   「看得到、只部分照做」。那要照 `INCONCLUSIVE` **帶區間**報，
   **不為了把它變顯著而加 n**。事後加 n 直到顯著是最典型的挑數字。

---

## 一、出發點：把 wire 解開之後看到的那一件事

2026-09-18 在 vacant-dev 上跑了兩次真 agent（pi 0.85.1 ＋ 1003 的 `gemma-4-12b-it-qat`），
形狀與結論記在 `docs/VACANT_RUN.md` §7.8（該節用的 run 名字是 `v1_real_pi`／
`v1_real_pi_explicit`；發射端的目錄名是 `vr1_run`／`run4`。
**兩組名字指的是同兩跑**，凍結時以 §十一 的對照表為準）。

2026-09-19 把兩跑的 `wire/*.req.bin` 逐通解開，數到的是：

```
vr1_run : 9 個請求   "Acceptance feedback" 0   "VACANT_FEEDBACK" 0   "feedback"(不分大小寫) 0
run4    : 9 個請求   同上全 0
```

**回饋檔確實寫出來了，而且足以決定修法**：713 bytes，逐字含
`ImportError: cannot import name 'add' from 'solution'`。沒被讀到的是它。

原因在請求本身，不在檔案：三次嘗試各是**一段全新對話**（roles 都從 `system,user` 開始），
user 訊息三次**逐字相同**：

```
Read TASK.md and do what it says. Use your tools to write the file.
```

pi 讀 `TASK.md`、寫 `solution.py`、結束，**從不 `ls` 工作區**。
於是那個檔對它而言不存在。

⇒ **V1 的檔案投遞，對「每次重試都是新對話、且不重掃目錄的 agent」結構性失效。**

### ⚠ 這個結論的限定範圍（**逐字帶著，不准擴大**）

上面這一句是對**這一條 argv、這一個 agent、這一個版本**的結論，
**不是對 `file` 模式的普遍結論**。至少三種情形不在它的射程內：

1. 會主動 `ls` 或掃工作區的 agent（Claude Code、Codex 的預設行為與 pi 不同）；
2. 使用者自己在 prompt 裡寫了「先看一下目錄有沒有新檔案」；
3. 把重試接在**同一段對話**裡的框架（pi 的 `-p` 是每次新對話）。

本輪量的是「在這個限定條件下，換管道有沒有差」。
**收官不得寫成「檔案投遞沒有用」，只能寫成「對這個 agent、這條 argv，檔案投遞的回饋
在第 ≥2 次嘗試的請求裡出現 0 次」。**

---

## 二、要跑什麼

### 二-1　題庫：兩層，**分開報，不合併**

| 層 | 內容 | n | 設計意圖 |
|---|---|---:|---|
| **S1** | **介面未給**：`TASK.md` 只用白話描述行為，不給函式名／簽章 | **50** | 單發會撞名字，回饋（`ImportError: cannot import name 'add'`）足以決定修法 |
| **S2** | **契約細節未給**：函式名給了，但邊界條件／回傳形狀／例外未寫明 | **40** | 單發會寫出「名字對、行為錯」的解，回饋是 assert 差異 |
| | **合計** | **90** | |

**兩層的 M1 分開報，任何情況下都不得合併成一個 90 的數字。**
它們的失敗機制不同（名字 vs 契約），合併會把兩件事講成一件事。

題庫由 `ops/gain/r535/build_bank.py` 確定性渲染，每題**七**件東西（共 **810 個檔**）：

```
bank/<task_id>/TASK.md                    ← 工作區樣板就是這一個檔
bank/<task_id>/TASK_explicit.md           ← 只有 PC 臂用（見 §二-4）
bank/<task_id>/tests_visible/test_visible.py
bank/<task_id>/hidden/test_hidden.py      ← 可見的**超集**，只給事後計分
bank/<task_id>/reference/solution.py      ← 參考解，必須全過
bank/<task_id>/reference/bad_{a,b,c}.py   ← 三個壞樁，必須全被擋
bank/<task_id>/meta.json
```

**釘值（已凍結）**：

| 項 | 值 |
|---|---|
| `ops/gain/r535/bank_manifest.json` sha256 | **`5e727b2ee884d80b197ec42f63af2bf73ce939bdd53c48fc8fc29e46e49c0794`** |
| 分支 | `bank/r535`（已 push 到 origin） |
| `files_sha256` 筆數 | **810** |
| S1 逐題 `task_id`（50 個） | 見 §十三-1（`manifest.strata.S1.task_ids`，**照這個順序**） |
| S2 逐題 `task_id`（40 個） | 見 §十三-1（`manifest.strata.S2.task_ids`，**照這個順序**） |
| 量具 `ops/gain/r535/gauge_bank.py` | **七項 90/90 全綠**（題庫作者跑一次、稽核者獨立重跑一次） |
| 判準用的尺 | `vacant/vrun/acceptance.py::run_suite` ＋ `render_failures`（**不准另寫第二把尺**） |

七項量具（逐字，`manifest.gauge`）：
`1_reference_passes`／`2_stakes_blocked`／`3a_wrong_name_feedback_names_it`／
`3b_wrong_behaviour_feedback_has_args_want`／`4_no_hidden_in_workspace`／
`5_task_md_withholds`／`6_explicit_diff_is_the_block_only`。

`TASK_explicit.md` 對 `TASK.md` 的 diff **是純插入**：4 行 ×71 題、5 行 ×16 題、6 行 ×3 題，
**非插入 opcode 0 題**（`difflib` 獨立重驗）。這是 §二-4 那條硬條件的可執行證據。

發射端的入口是 manifest 的五欄：`suite_path_for_launch`／`hidden_path_for_scoring`／
`workspace_template`（`["TASK.md"]`）／`workspace_template_pc`（`["TASK_explicit.md"]`）／`pc_arm`。

⚠ **`tests_visible/` 與 `hidden/` 都不進工作區。** `vacant run` 的原生形狀就是
`--suite` 必須在工作區外（`launcher.py` 是 `SystemExit`）：**agent 改得到的驗收不是驗收**。
R534 把 `tests_visible/` 放進工作區、pi 自己跑測試，閘門就沒東西可攔——那個形狀本輪不重複。

### 二-2　四臂

| 臂 | `vacant run` 設定 | draw 數 | 工作區樣板 | 事前預測（§四 展開） |
|---|---|---:|---|---|
| **RS** | `--retry resample --max-attempts 3`（**不給回饋的重抽**） | 3 | `TASK.md` | **負控制**：分離「回饋被消費」與「重抽運氣」 |
| **RF** | `--retry revise --max-attempts 3 --feedback-into file` | 3 | `TASK.md` | **M7_file = 0**、**M7_ws = 0**；與 RS **可交換** |
| **RP** | `--retry revise --max-attempts 3 --feedback-into prompt` | 3 | `TASK.md` | 最終 M1 ≥ 0.6，且 ≥ PC − 20 pp |
| **PC** | `--retry none` | 1 | **`TASK_explicit.md` 複製成 `TASK.md`** | 第 1 次可見通過 ≥ 0.8 |

四臂**同一個題庫、同一顆模型（`gemma-4-12b-it-qat`）、同一台機器（1003）**。

### ⚠ RS ＝ **三次重抽**，不是單發（2026-09-19 更正）

**RS 是 `--retry resample`，不是 `--retry none`。** 裁決原本就是這樣寫的
（「不給回饋的重抽；負控制：分離『回饋被消費』與『重抽運氣』」），
派工轉述時誤植成 `--retry none`。這個更正改變了整個負控制的邏輯：

- **RS 與 RF／RP 都是 3 draw** ⇒ 「多抽兩次」不再是 RF vs RS 的差異。
- RF vs RS 剩下的差異只有兩個：
  **(i)** 工作區多一個 `VACANT_FEEDBACK.md`；
  **(ii)** `revise` **保留**工作區／`resample` **重置**工作區。
- 依已驗到的行為（每次只 `read TASK.md` → `write solution.py`，從不 `ls`），
  **(i) 與 (ii) 對這個 agent 都是惰性的** ⇒ **事前預測是「RF 與 RS 可交換」**
  （結果分佈相同），比「RF ≈ RS」強，也讓「任一方向顯著 ⇒ 異常」站得住。
- **不加第五臂。** 先前草稿提的 `RR` 就是這裡的 RS。

⚠ `resample` 的重置**連 `.git/` 一起清**，還原完再量一次樹雜湊，對不回起點
⇒ `ws_reset_failed`＝`infra_void`（不判拒交也不判通過）。
**這是 RS 獨有的一個失敗模式**，RF／RP／PC 都不會有 ⇒ 見 §二-5 I-7。

### 單發基線**不另開臂**（零額外機時）

三個 3-draw 臂的**第 1 次嘗試**與 `--retry none` **逐位元同構**：
同 argv（I-1）、同 `TASK.md`、launcher 第 1 次不注入任何東西
（`resample` 的重置發生在**沒過之後**，`revise` 的回饋也是；
`render_argv` 第 1 次把 placeholder 換成空字串）。

⇒ **S1 有 n = 150 個單發觀測、S2 有 n = 120 個**，不必為了基線多跑一臂。

⇒ **「重抽效果」在臂內配對取得**：`RS_final − RS_attempt1`（同一跑、同一題、同一個工作區起點）。
這是本輪對「重抽買到多少」最乾淨的估計，**不需要跨臂比較**。

### 二-3　逐字指令（四臂只差表列的那幾個旗標）

共同前綴（`<tid>`＝`task_id`，`<ws>`＝該格的工作區，`<rd>`＝該格的 run 目錄）：

```bash
vacant run \
  --workspace   <ws> \
  --run-dir     <rd> \
  --suite       ops/gain/r535/bank/<tid>/tests_visible \
  --task-id     r535_<arm>_<tid> \
  --vacant      1 \
  --sandbox     none \
  --test-timeout 30 \
  --stdin       devnull \
  <ARM_FLAGS> \
  -- pi -p "Read TASK.md and do what it says. Use your tools to write the file.<PH>"
```

| 臂 | `<ARM_FLAGS>` | `<PH>` |
|---|---|---|
| RS | `--retry resample --max-attempts 3` | （空） |
| RF | `--retry revise --max-attempts 3 --feedback-into file` | （空） |
| RP | `--retry revise --max-attempts 3 --feedback-into prompt` | `{VACANT_FEEDBACK}` |
| PC | `--retry none` | （空） |

⚠ RS **不給** `--feedback-into`（用預設 `file`）。`resample` 這條臂在 `launcher.py`
裡根本走不到寫回饋那一段（`if retry_arm == "revise":` 才寫）⇒ RS 的工作區
**一個回饋檔都不會有**。這是「不給回饋」的可執行保證，不是約定。

⚠ **`<PH>` 不是一個自由欄位。** `vacant/vrun/retry.py::check_argv_has_placeholder`
把兩種壞組合都做成 `SystemExit`：`--feedback-into file` 而 argv 裡有 placeholder ⇒ 死；
`--feedback-into prompt` 而 argv 裡沒有 placeholder ⇒ 死。
**沒有「安靜退回檔案模式」這條路**，所以「我以為在 prompt 模式」的錯不會活在資料裡。

pi 的接線沿用 `docs/AGENT_COMPAT.md` §3 那條：pi 不吃 `OPENAI_BASE_URL`，
要用 `--port <固定埠>` ＋ `PI_CODING_AGENT_DIR` 底下一份 `models.json` 把 provider
`baseUrl` 指向 proxy。**固定埠與 `models.json` 裡的埠必須是同一個數字**——
2026-09-18 有一跑因為兩邊差一號而 `requests_seen = 0`，畫面上只有 pi 自己的
`Connection error.`。⇒ 見 §九 L-0。

### 二-4　PC 臂的 `TASK` 置換規則（**寫死，不是實作細節**）

PC 的目的是量**天花板**：把 withhold 的介面／細節寫明之後，這顆模型在這個題庫上
單發能到多少。它必須滿足一條硬條件：

> **PC 的 agent argv 與其他三臂逐位元相同。**

所以 `TASK_explicit.md` **不是**以那個檔名進工作區，而是**複製進去改名為 `TASK.md`**
（`manifest.pc_arm.what` 逐字同義：「落地時改名成 `TASK.md`，其餘位元組相同」）。
不這麼做的話 argv 得改成 `Read TASK_explicit.md …`，那就多了一個變因，
PC 量到的天花板會混進「prompt 換了字」。

這條的可執行證據是量具第 6 項 `6_explicit_diff_is_the_block_only`：
兩份 `TASK*.md` 的 diff **只准是介面／細節那一塊，且必須是純插入**。
實測 90/90 全綠、非插入 opcode 0 題（§二-1）。
`manifest.pc_arm.gate` 把後果寫死：「兩份若在別處也不一樣，PC 就不是同一題的天花板，
`CEILING_TOO_LOW` 判準失效。」

### 二-5　可驗的不變量（**發射後逐格對帳，不是宣稱**）

| # | 不變量 | 怎麼驗 |
|---|---|---|
| **I-1** | **四臂第 1 次嘗試的 `argv_sha256` 逐格相同** | `render_argv` 在第 1 次把 placeholder 換成**空字串**（`retry.py` 規則 2），且 `argv_sha256` 算的是**替換後**的 argv ⇒ RP 與 RS/RF/PC 的第 1 次逐位元相同。對帳＝每個 `<tid>` 取四個 `run_*.json` 的 `attempts[0].argv_sha256`，四個值必須相同 |
| **I-2** | **RP 的每個第 ≥2 次嘗試 `feedback_in_prompt_bytes > 0`** | ＝指標 `F6`。`attempts[i].feedback_in_prompt_bytes`，第 1 次恆為 0 |
| **I-3** | **RF 的每個第 ≥2 次嘗試 `feedback_in_prompt_bytes == 0`** | 同上。`file` 模式 `render_argv` 早退、`n_sub=0` |
| **I-4** | **PC** 的 `attempts_used == 1`、`max_attempts == 1`；**RS／RF／RP** 的 `max_attempts == 3` | `rows.jsonl` |
| **I-5** | 每格 `requests_seen > 0` | `requests_seen == 0` ＝ agent 根本沒被中介到（§二-3 的那個坑）⇒ 該格 `infra_void` |
| **I-6** | 收據鏈 `ws_attempt` 筆數 ≥ `ws_verdict` 筆數，且 `ws_verdict` 恰好 1 筆 | `ops/gain/replay/verify_run_receipts.py --glob <rd>`；先跑 `--selftest` 證明它抓得到壞鏈 |
| **I-7** | **RS 的每次重置都回得到起點** | `attempts[i].reset.back_to_start == true`。false ⇒ `ws_reset_failed`＝`infra_void`。**RS 獨有**：這條臂的重置連 `.git/` 一起清，留著 `.git` 等於偷偷把上一次的失敗留在現場，而那在樹雜湊上看不出來 |
| **I-8** | **RS 的工作區從頭到尾沒有 `VACANT_FEEDBACK.md`** | 逐次快照 `_frozen_RUN-ON[_a<n>]/` 掃檔名。`resample` 走不到寫回饋那一段，所以這條應該恆真——**它是負控制的可執行證明，不是約定** |

---

## 三、指標

| 代號 | 定義 | 角色 |
|---|---|---|
| **M1** | **最終可見通過率**＝該格最後一次嘗試 `accepted == true` 的比例（`rows.jsonl` 的 `accepted`） | **主要** |
| **M7_file** | **回饋文字出現在第 ≥2 次嘗試任一通 wire 的比例**（RF 臂） | **RF 的承重證據** |
| **M7_ws** | **RF 臂第 ≥2 次嘗試裡，wire 出現 `read TASK.md`／`write solution.py` 以外任何工具呼叫**（`ls`、`bash`、read 其他檔）**的比例** | **「保留工作區」這條管道的承重證據** |
| **F6** | RP 的每個第 ≥2 次嘗試 `feedback_in_prompt_bytes > 0`（＝I-2） | RP 的機制門 |
| M2 | 第 1 次可見通過率（逐臂） | `NOT_TRIGGERED`／`CEILING_TOO_LOW` 的判準來源 |
| M3 | `attempts_used` 分佈（逐臂） | 成本；重試燒的是整個 agent 行程 |
| M4 | 隱藏通過率（事後計分，`hidden/`） | **描述性**，不進任何檢定 |
| M5 | `stop_reason` 分佈（`visible_pass`／`visible_fail`／`attempts_exhausted`／`infra_void` 各碼） | 對帳 |

### M7_file 的可執行定義（**不留解釋空間**）

1. 從 `<rd>/run_*.json` 取 `attempts[i].requests_seen_cumulative`，
   得到「第 i 次嘗試對應 `wire/index.jsonl` 的哪一段」；
2. 取 **i ≥ 2** 那幾段的每一通 `wire/<call_id>.req.bin`（**原始位元組**，不是有損的 JSONL）；
3. 在那些位元組裡找三個字串（UTF-8）：
   `Acceptance feedback`、`VACANT_FEEDBACK`、以及該格那一次回饋文字的**前 64 個位元組**；
4. 任一命中 ⇒ 該格計 1。`M7_file` ＝ 命中的格數 ÷ RF 有第 ≥2 次嘗試的格數。

⚠ **分母是「有第 ≥2 次嘗試的格數」，不是 n。** 第 1 次就過的格子沒有第 2 次可以看，
把它們算進分母會把「沒被觸發」偽裝成「被讀到了」。分子分母都要逐層落盤。

⚠ **這是單邊的。** 命中 0 只說明「這三個字串沒出現在請求 body 裡」，
不說明「agent 沒有以任何方式受到那個檔的影響」（例如它 `ls` 過但沒把內容貼進 prompt）。
**收官要寫成「回饋文字沒有出現在模型輸入裡」，不是「agent 沒看到回饋」。**
⇒ 這個洞正是 **M7_ws** 要補的那一半。

### M7_ws 的可執行定義（**與 M7_file 同一段 wire，不同的問題**）

M7_file 問「**我們寫的字**有沒有進到模型輸入裡」；
M7_ws 問「**agent 有沒有去看工作區**」。兩個都是 0，RF 與 RS 的可交換預測才站得住。

1. 同 M7_file 步驟 1–2，取 RF 臂 **i ≥ 2** 那幾段的 `wire/<call_id>.{req,resp}.bin`；
2. 從 request body 的 `messages[*].tool_calls` 與 response 的工具呼叫段落
   解析出**該次嘗試實際發起過的工具呼叫**（pi 的工具名：`bash`／`read`／`write`／
   `edit`／`edit-diff`／`truncate`／`index`）；
3. **允許清單只有兩筆**：`read` 的參數是 `TASK.md`、`write` 的參數是 `solution.py`；
4. 出現任何**不在允許清單**的工具呼叫（含 `ls`、任何 `bash`、read 其他檔、
   read `VACANT_FEEDBACK.md`）⇒ 該格計 1。
   `M7_ws` ＝ 命中的格數 ÷ **RF 有第 ≥2 次嘗試的格數**（分母與 M7_file 相同）。

⚠ **分母同 M7_file**：第 1 次就過的格子沒有第 2 次可以看。
⚠ **M7_ws > 0 不等於 M7_file > 0**：agent 可以 `ls` 完什麼都不做。
  兩個指標要**分開報，不合併成一個「有沒有看工作區」的數字**。
⚠ **這一段要解析 pi 的工具呼叫格式，它是框架相依的**。
  解析器必須有 `--selftest`（餵一段已知含 `ls` 的 wire，要能翻紅），
  否則「M7_ws = 0」跟「解析器沒認出任何工具呼叫」在輸出上同形。

---

## 四、事前預測——**在看到任何資料之前寫死**

裁決原文（逐字，**RS 那一列已於 2026-09-19 更正**）：

> | 臂 | 設定 | 事前預測 |
> |---|---|---|
> | `RS` | **`--retry resample --max-attempts 3`（不給回饋的重抽）** | **負控制：分離「回饋被消費」與「重抽運氣」**；`1−(1−p₁)³` 是三個 3-draw 臂**共同的**獨立抽樣參考線 |
> | `RF` | `--feedback-into file`，≤3 次 | **M7_file = 0**、**M7_ws = 0**；與 RS **可交換** |
> | `RP` | `--feedback-into prompt`，≤3 次 | 最終 M1 ≥ 0.6，且 ≥ PC − 20 pp |
> | `PC` | `--retry none` ＋ **`TASK_explicit.md`**（把 withhold 的介面／細節寫明） | 第 1 次可見通過 ≥ 0.8 |

> **更正紀錄（2026-09-19，留在檔案裡）**：本檔草稿把 RS 寫成 `--retry none`，
> 那是**派工轉述的誤植**，裁決原本就是「不給回饋的重抽」。
> 草稿因此報了一個矛盾（「`--retry none` 拿不到 `1−(1−p₁)³`」）——
> **那個矛盾正是誤植的徵狀**，那個預測只有三次 draw 才講得通。
> 更正之後：不加第五臂（草稿提的 `RR` 就是 RS）、§五-2 的方向護欄整張換掉、
> 「本設計沒有無回饋重抽臂」那句話刪除。

### 四-1　`R_indep = 1−(1−p₁)³` 是什麼（**讀法寫死**）

> `R_indep` ＝ `1 − (1 − p₁)³`
> ＝「如果三次嘗試是**互相獨立**的重抽，最終會到哪裡」。

`p₁` ＝ **RS／RF／RP 三臂第 1 次通過率的合併估計**（S1 共 150 次、S2 共 120 次第 1 次嘗試；
**PC 的第 1 次不算進去**，它是不同的 `TASK.md`）。合併的合法性由 **I-1** 背書：
三臂第 1 次的 argv 逐位元相同、工作區樣板相同 ⇒ 是同一個條件下的 3 × n 次抽樣。

**`R_indep` 是三個 3-draw 臂共同的參考線，不是誰的上界。**
可交換預測下 `E[RF] = E[RS]` ⇒ 沒有誰是誰的上界，那個講法（草稿 §四-1 的版本）**作廢**。

`R_indep` **一定高估**（三次不獨立：同模型、同 TASK、同溫度）。
所以 **`RS_final` 與 `R_indep` 的差，量的是 draw 之間的相依度**——
那是本輪順手拿到的一個量，不是假說。

**MC1（機制對帳 1）不做區間檢定**，只**並排印三個數**：
`RS_attempt1`（單發）、`RS_final`（三次重抽）、`R_indep`（獨立參考線）。
三個數之間的關係要用文字描述，**不得**寫成任何一個檢定的結論。

### 四-2　四臂各自的事前預測（收官逐條對照）

| 臂 | 事前預測 | 若不成立，代表什麼（事前寫死） |
|---|---|---|
| RS | **3 draw，無門檻**。並排報兩個數：`RS_attempt1`（＝該臂的單發通過率）與 `RS_final`（三次重抽後）。題庫的**設計意圖**是第 1 次可見**失敗**率 **S1 ≥ 0.8**、**S2 在 0.4–0.8**（`manifest.strata.*.expected_first_attempt_visible_fail`）⇒ `RS_attempt1` 對應 **S1 ≤ 0.2**、**S2 在 0.2–0.6** | **RS 這一列刻意沒有門檻**：它是負控制，不是要被通過或不通過的假說。第 1 次失敗率低於 §六-2 的門檻 ⇒ 題庫沒有製造出窗口 ⇒ `NOT_TRIGGERED`。⚠ 上面那個預期是**設計意圖不是量測值**（`honesty_bounds[1]`）：收官要把實測失敗率與這個預期**並排報**，不可以只報一個 |
| RF | **M7_file = 0** 且 **M7_ws = 0**；與 RS **可交換**（結果分佈相同） | M7_file > 0 ⇒ 這個 agent **會**把回饋讀進輸入，§一 的限定句在本題庫上就不成立；M7_ws > 0 而 M7_file = 0 ⇒ 它看了工作區但沒把回饋貼進 prompt。**兩種都要逐題印出它在 wire 上做了什麼**（§五-2） |
| RP | M1 ≥ 0.6，且 M1 ≥ PC − 20 pp | 低於 0.6 ⇒ 「回饋進得了輸入」買不到交付；低於 PC − 20 pp ⇒ 管道補不回「一開始就講清楚」 |
| PC | 第 1 次可見通過 ≥ 0.8 | < 0.5 ⇒ `CEILING_TOO_LOW`（§六）：題目對這顆模型太難，管道問題根本沒被提出來 |

### 四-3　**不得與別輪併 n**（寫死）

本輪的數字**不得**與 R530／R532／R534／`docs/VACANT_RUN.md` §7.8 的兩跑併表或併 n。
prompt 不是我們寫的（agent 命令由使用者給）、工具面由框架自己決定、
預算形狀是「整個 agent 行程重跑」而不是「同一段對話多說一輪」。三個變因都不同。

---

## 五、統計

### 五-1　確認性檢定**只有 H1**

| 假說 | 比的是 | 檢定 | 家族 |
|---|---|---|---|
| **H1-S1** | RP vs RF，S1 層 | 配對精確 McNemar（`research.mcnemar_exact(b, c)`） | **進**家族 |
| **H1-S2** | RP vs RF，S2 層 | 同上 | **進**家族 |
| H2 | RF vs RS（**兩者都是 3 draw**） | 控制檢查，單獨 α = 0.05 精確雙尾 | **不進** |
| H3 | RP vs RS | **描述** | **不進** |
| MC1 | `RS_attempt1` / `RS_final` / `R_indep` 三數並排 | **不檢定**（§四-1） | **不進** |

**Holm 家族 ＝ {H1-S1, H1-S2}，大小 2**，用 `vacant/research.py::holm_bonferroni`。
配對輔助量（逐題差 ∈ {−1, 0, +1}）另跑 `research.wilcoxon_signed_rank_exact`，
**與 McNemar 並列印出，不取代它**。
**H1 的效果量一律報 `research.boot_ci` 的 95% 區間**（2.5/97.5，§五-3）。

**H3 降為描述**：印 `b`、`c`、exact p、95% 區間，**不進家族、不進狀態表**。
理由：RP 與 RS 同時差了兩件事（回饋進輸入 ＋ `revise` 保留工作區 vs `resample` 重置），
它分不開。**注意 draw 數已經不是理由了**——RS 改成 `resample` 之後三臂都是 3 draw。

### 五-2　H2 是**控制檢查**，它的觸發條件與方向護欄

RS 與 RF **都是 3 draw**（§二-2 的更正）⇒ 兩臂剩下的差異只有
**(i)** 工作區多一個 `VACANT_FEEDBACK.md`、**(ii)** `revise` 保留工作區／`resample` 重置。
依已驗到的行為，兩個都是惰性的 ⇒ **事前預測是「RF 與 RS 可交換」**（結果分佈相同）。
**這比「RF ≈ RS」強，也正是「任一方向顯著 ⇒ 異常」站得住的理由。**

但 (ii) 要有量看得見，所以護欄同時讀 **M7_file**（(i) 這條管道）與 **M7_ws**（(ii) 這條管道）。

#### 觀測 → 狀態 → 能寫什麼（**整張表照抄，不准自行外推**）

| 觀測 | 狀態 | 能寫的 |
|---|---|---|
| **RF < RS 顯著**（α=0.05 精確雙尾） | `MECHANISM_BREACH` | 負控制異常，機制待查 |
| **RF > RS 顯著，M7_file = 0，M7_ws = 0** | `MECHANISM_BREACH` | 同上（兩臂**應可交換**，我們的模型解釋不了） |
| **RF > RS 顯著，M7_file = 0，M7_ws > 0** | **`STALE_WORKSPACE_EFFECT`**（**描述性，不凍結**） | 「保留工作區被讀到並改變結果」；**不得**寫成檔案投遞有效；逐題印 wire |
| **M7_file > 10%（任一層）** | `MECHANISM_BREACH` | **預測被證偽：檔案被讀了。** H1 收官句要帶「RF 有部分投遞」；**§一 的限定句在本題庫上不成立** |
| **不顯著** | 無狀態 | 印 `(b, c)`、p、**95% 區間**、TOST、M7_file、M7_ws |

`MECHANISM_BREACH` 觸發時：

1. **該層所有引用 RF／RS 的句子凍結**，不得當成果；
2. **逐題印出 `M7_file > 0`／`M7_ws > 0` 的題在 wire 上做了什麼**
   （哪一通、哪一段字串或哪一個工具呼叫命中、該次嘗試的 `argv_sha256` 與
   `feedback_in_prompt_bytes`）；
3. H1 仍然可以收官（`MECHANISM_BREACH` 不在 H1 那條鏈上），
   **但 H1 的收官句必須帶「負控制異常，機制待查」**。

`STALE_WORKSPACE_EFFECT` **不凍結任何句子**，它是一個描述性的發現：
「`revise` 保留下來的工作區本身是一條管道，而且它被用到了。」
它與本輪的主問題（回饋走哪條管道）是**兩件事**，收官要分開寫。

### 五-3　區間與 TOST：**凍結為函式預設，且先寫清楚 TOST 多半不會成立**

#### 兩個區間，用途不同，**不可互換**

| 用途 | 怎麼算 | 數值 |
|---|---|---|
| **差值的報告區間** | `research.boot_ci`，**2.5 / 97.5 百分位 ＝ 95%**（與 R534 §五-3 同） | n=50 半寬約 **±18 pp**；n=40 約 **±20 pp** |
| **TOST** | `research.tost_equiv_boot(diffs, delta=0.15)`，**用函式預設 α=0.05 ⇒ 90% CI** | n=50 半寬約 **±14 pp**；n=40 約 **±16 pp** |

- **一切「RP − RF 是多少」的句子一律報 95% 區間。**
- **`RULED_OUT` 讀的是 95% 區間的上緣 < +15 pp**（§六-2 第 6 列），不是 TOST 的旗標。
- TOST（δ = 15 pp）只是一個**形式檢定**，報它的 `equivalent` 布林值與 CI，不拿它下結論。

#### 事前聲明（**逐字，收官照抄**）

> **TOST 在本 n 下幾乎不會成立，它是形式檢定；
> 負控制的承重證據是 M7_file 與 M7_ws。**

依據是實跑模擬（§七-3，300 次 × 2000 bootstrap）：
**即使真差是 0，`equivalent` 也只在 300 次裡成立 24 次（n=50）／16 次（n=40）。**
δ = 15 pp 的窗只比 90% CI 的半寬（14／16 pp）大一點點，
所以 `equivalent = true` 需要觀測均差幾乎壓在 0 上。
⇒ **TOST 不成立是「量不到」不是「有差」。**

#### ⚠ 禁語（逐字，收官照抄）

- **「等價」這兩個字任何句子都不出現。** 不准寫「兩臂等價」「沒有差異」「效果為 0」。
- 只准兩種措辭：**「TOST（δ=15 pp）成立／不成立」** 或 **「±15 pp 內未區分開」**。
- TOST 不成立時**不得**寫成「兩臂有差」——TOST 不成立與 H1 顯著是兩件獨立的事。

---

## 六、狀態表

### 六-1　求值順序（**照抄，由上往下，第一個成立的就是狀態**）

```
INVALID → NOT_TRIGGERED → CEILING_TOO_LOW → CONFIRMED_POSITIVE →
CONFIRMED_NEGATIVE → RULED_OUT → INCONCLUSIVE
```

逐條編號（收官照這個順序求值，**不准跳號、不准回頭**）：

```
1. INVALID
2. NOT_TRIGGERED
3. CEILING_TOO_LOW
4. CONFIRMED_POSITIVE
5. CONFIRMED_NEGATIVE
6. RULED_OUT
7. INCONCLUSIVE
```

`MECHANISM_BREACH` 與 `STALE_WORKSPACE_EFFECT` 都是 **RF／RS 控制鏈上的狀態**，
**不在上面這條鏈上**：它們可以與 1–7 任何一個同時成立，
且兩者**互斥**（同一個觀測不會同時落進兩個，見 §五-2 的觀測表）。
`MECHANISM_BREACH` 成立時，H1 的收官句必須帶「負控制異常，機制待查」；
`STALE_WORKSPACE_EFFECT` **不凍結任何句子**。

**每一層各自求值一次**（S1 一個狀態、S2 一個狀態），**不合併**。

### 六-2　逐狀態判準與**方向護欄**

> 四狀態表缺方向護欄是 R532 AMEND1 的教訓（`EFFECTIVE` 在 Δ 為負時誤觸發）。
> 本檔每一個狀態都寫死方向，**沒有方向的判準不准進表**。

| # | 狀態 | 判準 | **方向護欄** |
|---|---|---|---|
| 1 | **`INVALID`** | 該層 `infra_void` 剔除 **> 10%**（剔除是三臂一起，見 §九 L-4） | 無方向可言。觸發 ⇒ 該層**所有**數字不得引用，連描述性的都不行 |
| 2 | **`NOT_TRIGGERED`** | **S1**：RS/RF/RP 三臂合併的第 1 次可見**失敗**率 **< 0.6**；**S2**：**< 0.3** | 單邊：只在**失敗率太低**時觸發。失敗率太高**不觸發**這個狀態（那是 `CEILING_TOO_LOW` 的事）。⚠ 分母＝**三臂**合併，S1 共 150 個第 1 次嘗試、S2 共 120 個；**PC 的第 1 次不算進去**（不同 `TASK.md`） |
| 3 | **`CEILING_TOO_LOW`** | PC 的第 1 次可見通過 **< 0.5** | 單邊：只在**太低**時觸發。PC 高不觸發任何狀態（那是預期的） |
| 4 | **`CONFIRMED_POSITIVE`** | 該層 H1 的 Holm 調整後 p < 0.05 **且 `c > b`**（＝**RP 贏 RF** 的方向） **且** F6 全格成立 | **方向寫死：只有 RP > RF 才算。** RP < RF 而顯著 ⇒ 走 5，不准落進這一格 |
| 5 | **`CONFIRMED_NEGATIVE`** | 該層 H1 的 Holm 調整後 p < 0.05 **且 `b > c`**（＝**RF 贏 RP**） | **方向寫死。** 這一格的意思是「把回饋塞進 argv 反而更差」，是一個真的結論，不是失敗 |
| 6 | **`RULED_OUT`** | H1 不顯著 **且 RP − RF 的 95% 區間上緣 < +15 pp** | **單邊寫死（上緣）**：本輪問的是「argv 管道有沒有買到東西」，買到負的不歸這一格（歸 5）。另報 TOST（δ=15 pp）的旗標當形式紀錄，**但判準是 95% 上緣不是 TOST**。依 §七-3，n=50 的 95% 半寬約 ±18 pp ⇒ **這一格事前就知道很難達成** |
| 7 | **`INCONCLUSIVE`** | 以上皆不成立 | 無方向。⚠ **它是預設落點，不是失敗。** 依 §七-1，+10 pp 的真效果在 n=50 的檢定力只有 **0.086** ⇒ 落在這一格是**事前就預期的最可能結果**（§〇「為什麼不加 n」已寫死不為此加 n） |
| — | **`MECHANISM_BREACH`** | 見 §五-2 的觀測表（RF < RS 顯著／RF > RS 顯著且 M7_ws = 0／M7_file > 10%） | 整張護欄表在 §五-2，**不在這裡重述**。它與 1–7 任何一個可同時成立 |
| — | **`STALE_WORKSPACE_EFFECT`** | RF > RS 顯著、M7_file = 0、**M7_ws > 0** | **描述性，不凍結任何句子。** 方向寫死：只有 RF **>** RS 才進這一格（RF < RS 走 `MECHANISM_BREACH`）。**不得**寫成「檔案投遞有效」 |

### 六-3　收官句模板（逐字，照抄）

- `CONFIRMED_POSITIVE`：「在 S<k>（n=<n>）上，把回饋接進 argv 相對於寫檔進工作區，
  最終可見通過率高 **<Δ> pp（95% 區間 <lo>–<hi> pp）**（b=<b>, c=<c>, Holm 調整後 p=<p>）。
  **這是對 `gemma-4-12b-it-qat` ＋ pi 0.85.1 ＋ 本題庫的結論，不可外推。**」
- `INCONCLUSIVE`：「在 S<k>（n=<n>）上，本輪**沒有區分開**兩條管道
  （點估計 <Δ> pp，**95% 區間 <lo>–<hi> pp**，Holm 調整後 p=<p>）。
  依 §七 的事前檢定力表，本輪對 +10 pp 的真效果檢定力只有 <power>，
  **『沒顯著』不可以讀成『沒有效果』。**」
- `RULED_OUT`：「在 S<k>（n=<n>）上，RP − RF 的 **95% 區間上緣 <hi> pp < +15 pp**
  ⇒ **±15 pp 內未區分開**。TOST（δ=15 pp）<成立／不成立>。」
  **（禁語：不出現「等價」兩個字。）**
- 帶 `MECHANISM_BREACH` 時，上面各句後面一律再接：「**負控制異常，機制待查**
  （H2 <方向>，M7_file=<x>，M7_ws=<y>）。本層引用 RF／RS 的句子已凍結。」
- 帶 `STALE_WORKSPACE_EFFECT` 時，另起一段（**不接在 H1 的句子後面**）：
  「另觀測到：RF > RS 顯著而 M7_file=0、M7_ws=<y> ⇒
  **保留下來的工作區被讀到並改變了結果**。這與本輪的主問題（回饋走哪條管道）是兩件事，
  **不得**寫成檔案投遞有效。逐題 wire 見 <路徑>。」
- **三個數字（§〇）一律另起一段照抄**：
  「M7_file=<x>（rule-of-three 上界 <u>）、M7_ws=<y>；
  第 1 次可見失敗率 S1=<f1>（n=150）／S2=<f2>（n=120）；
  S1 的 RP−RF = <Δ> pp（95% 區間 <lo>–<hi>）。」

---

## 七、事前檢定力（**發射前算完，凍結**）

方法：`vacant.research.mcnemar_power(n, p_disc, ψ, alpha=0.025)`
（精確雙尾，對 K 與 B 全枚舉，無近似）。
**α 用 0.025**：Holm 家族大小 2，第一個被檢定的假說走的就是 α/2，這是最保守的那一格。
`Δ = p_disc × (2ψ − 1)` ⇒ `ψ = (Δ/p_disc + 1) / 2`。
`p_disc` 事前取 **0.40**（RP 與 RF 的不一致對率；沒有實測，是設計假設 ⇒ 附 §七-2 的敏感度）。

### 七-1　主表（p_disc = 0.40，α = 0.025）

| 真實效果 Δ | ψ | **n = 50（S1）** | **n = 40（S2）** |
|---:|---:|---:|---:|
| **+5 pp** | 0.5625 | **0.0286** | **0.0251** |
| **+10 pp** | 0.6250 | **0.0860** | **0.0679** |
| **+20 pp** | 0.7500 | **0.4245** | **0.3274** |
| **+30 pp** | 0.8750 | **0.8893** | **0.7908** |

自我對帳（ψ = 0.5 ＝ H0 時回傳的是檢定的 size，精確檢定保守 ⇒ 必須 ≤ α）：

```
n=50 p_disc=0.25  size=0.01288      n=40 p_disc=0.25  size=0.01111
n=50 p_disc=0.40  size=0.01359      n=40 p_disc=0.40  size=0.01350
n=50 p_disc=0.55  size=0.01591      n=40 p_disc=0.55  size=0.01397
```

**達到 power ≥ 0.80 需要的 n（p_disc=0.40, α=0.025）**：

| Δ | n_required | 對本輪的意思 |
|---:|---:|---|
| +5 pp | **> 1600** | 18 倍題量還不夠。**本輪測不出來** |
| +10 pp | **394** | 需要 S1 的 7.9 倍、S2 的 9.9 倍。**本輪測不出來** |
| +20 pp | **98** | S1 差 2 倍、S2 差 2.5 倍。**本輪半條牙齒** |
| +30 pp | **41** | S1（50）與 S2（40）大致就在這個量級。**本輪唯一有牙齒的效果尺度** |

⚠ **「> 1600」的意思要精確**：它是「**本檔的搜尋上限 `cap = 1600` 之內找不到**」
（附錄 A 那段倍增＋二分，`cap` 是本檔自己設的），
**不是**「超出 `research.mcnemar_n_required` 的搜尋範圍」——
那一支的 `n_max` 是它自己的參數（本檔寫成時預設 20000），與這裡的 1600 無關。
**引用這一格時要帶著 `cap = 1600`**，否則換一個預設就會讀成不同的斷言。

### 七-2　敏感度（p_disc 不是實測值）

| p_disc | Δ=+5pp | Δ=+10pp | Δ=+20pp | Δ=+30pp |
|---|---|---|---|---|
| **0.25**，n=50 / n=40 | 0.0366 / 0.0279 | 0.1381 / 0.0977 | 0.7278 / 0.5675 | ψ>1，**不可能**（Δ 不能大於 p_disc） |
| **0.40**，n=50 / n=40 | 0.0286 / 0.0251 | 0.0860 / 0.0679 | 0.4245 / 0.3274 | 0.8893 / 0.7908 |
| **0.55**，n=50 / n=40 | 0.0281 / 0.0227 | 0.0714 / 0.0532 | 0.3106 / 0.2256 | 0.7131 / 0.5729 |

⚠ **`p_disc` 越大，同一個 Δ 的檢定力越低**（同樣的淨差被更多雜訊對稀釋）。
收官要用**實測** `p_disc` 重算一次，**兩張表並列**。

### 七-3　TOST 的區間半寬（實跑，不是估的）

`research.tost_equiv_boot(diffs, delta=0.15)`，每格 300 次模擬、每次 2000 bootstrap：

| n | 真差 | 半寬中位數 | 半寬 p10–p90 | `equivalent` 觸發 |
|---:|---:|---:|---|---:|
| 50 | 0 pp | **14.0 pp** | 13.0–16.0 pp | **24 / 300** |
| 50 | +5 pp | 14.0 pp | 12.0–16.0 pp | 21 / 300 |
| 50 | +10 pp | 14.0 pp | 12.0–16.0 pp | 10 / 300 |
| 40 | 0 pp | **16.2 pp** | 15.0–17.5 pp | **16 / 300** |
| 40 | +5 pp | 16.2 pp | 13.8–17.5 pp | 19 / 300 |
| 40 | +10 pp | 16.2 pp | 13.7–17.5 pp | 9 / 300 |

解析對照（`sd(d) = √(p_disc − Δ²)`）：n=50 ⇒ se=0.0894、90% CI 半寬 14.7 pp、95% CI 半寬 17.5 pp；
n=40 ⇒ se=0.1000、90% CI 半寬 16.4 pp、95% CI 半寬 19.6 pp。

**兩個區間都用，用途不同（§五-3 已凍結，這裡只是對帳）**：

| | 半寬 n=50 | 半寬 n=40 | 用在哪 |
|---|---:|---:|---|
| **95% CI**（`boot_ci` 2.5/97.5） | **±18 pp** | **±20 pp** | **所有差值的報告區間**；`RULED_OUT` 讀它的上緣 |
| **90% CI**（`tost_equiv_boot` 預設 α=0.05） | ±14 pp | ±16 pp | **TOST 的形式旗標**，不拿它下結論 |

⇒ **`RULED_OUT`（95% 上緣 < +15 pp，而半寬就有 ±18 pp）事前就知道很難達成**，
與 TOST 的 24/300 是同一件事的兩個講法。**兩者都不是「沒有效果」的證據。**

### 七-4　**這張表在資料之前就要被讀懂**（否則收官會誤讀）

1. **+5 pp 的真效果在任何可行的 n 都測不出來。** n=50 的檢定力 0.029、n=40 是 0.025——
   那基本上就是 α 本身（檢定沒有牙齒）。要到 power 0.80 需要 **n > 1600**
   （＝本檔搜尋上限 `cap = 1600` 之內找不到，見 §七-1 的 ⚠），
   那是 18 倍以上的題量，本輪不可能做到，
   **而且這件事現在就寫在這裡，不是收官時才發現的**。
2. **+10 pp 也測不出來**（0.086 / 0.068）。
3. **本輪真正有牙齒的只有 +30 pp**（0.889 / 0.791）。+20 pp 是半條牙齒（0.425 / 0.327）。
4. ⇒ **`INCONCLUSIVE` 是事前就預期的最可能落點**（§六-2 第 7 列）。
5. ⇒ **收官時「沒顯著」不可以讀成「沒有效果」**（R532 §十 的同一條）。
   它與「效果是 0」和「效果是 +10 pp」**都相容**，本輪區分不了。
6. ⇒ 反過來：**如果 H1 真的顯著了，那代表觀測到的效果很大**（本輪只看得見大效果）。
   那時候要特別小心 §五-2 的混淆，以及「單次點估計是上偏的」（R460 的 +13.33 → 五次複製
   +0.83～+5.83 已經演過一次）。

---

## 八、規模與時程（**估計，不是實測**）

| 項 | 值 |
|---|---:|
| 題數 | 90（S1 50 ＋ S2 40） |
| 臂 | 4 |
| 格數（`vacant run` 呼叫次數） | **360** |
| 嘗試次數上限 | 90×3（RS）＋ 90×3（RF）＋ 90×3（RP）＋ 90×1（PC）＝ **900** |
| 每次嘗試牆鐘（2026-09-18 實測，load ≈ 71） | 4–6 s |
| 每次驗收牆鐘（§九 L-3 的時序門上限） | ≤ 2 s |
| 粗估總牆鐘（單串） | **900 × (6 + 2) s ≈ 2.0 h**，加 spawn／凍結／簽章／`resample` 重置開銷取 **3–5 h** |

⚠ **這是估計。** 900 是**上限**（第 1 次就過的格子不會用到第 2、3 次），
而 4–6 s 來自 n=1 的兩跑。冒煙塊（§九 L-5）就是為了回填它。

---

## 九、發射前擋門（**任何一條紅就不准發射**）

背景：vacant-dev 現在 load **71**（72 個跨 uid 孤兒），根因與修法見
[`ops/gain/r535/ORPHAN_CLEANUP_NEEDED.md`](../ops/gain/r535/ORPHAN_CLEANUP_NEEDED.md)。
**發射前先讀它。**

> 本檔草稿寫成時該檔還在分支 `fix/sandbox-kill-leak` 上、`ops/check_repo_links.py` 對這條連結判紅；
> **2026-09-19 已隨 `cad1001` 併進 main，連結現在是綠的。**（留下這段是因為當時的
> 處置方式本身是紀律：引用要指向它該在的地方，不得為了讓 CI 綠而改寫引用。）

### L-0　pi 接線自檢（**不是「我設了設定」，是 `requests_seen`**）

先跑一格冒煙，確認 `requests_seen > 0`。`--port` 與 `models.json` 的埠必須是同一個數字。
2026-09-18 有一跑因為差一號而完全沒被中介到，畫面上只有 pi 的 `Connection error.`。

### L-1　`--sandbox none`，**且釘死三個 commit sha**

- **`--sandbox none`**：不降權到別的 uid ⇒ **不會再造跨 uid 孤兒**。
- **`kill_status` 照樣落盤**（`SandboxResult.kill_status`：`""`／`"reaped"`／`"leaked:<試了什麼>"`）。
  ⚠ 這個欄位是下表第 1 列加的；**在那之前 main 上只有 `attempts[i].orphans_killed`**，
  兩者不同形，對帳器要認得出來。

#### 三個要釘的 sha（**全部已在 main，`--rebase` 併入所以與分支上的不同號**）

| # | 修法 | 分支上的 | **main 上的（釘這個）** | 對本輪資料的地位 |
|---:|---|---|---|---|
| 1 | 沙箱 `_kill_group`／`kill_status`（跨 uid `killpg` 被 EPERM 擋下還被吞掉） | `013f927` | **`cad1001`** | **不影響本輪資料** |
| 2 | wireproxy `quiesce`／`requests_seen` 少算 | `f7d0351` | **`9420d81`** | **會影響本輪資料** |
| 3 | 測試逾時（超時被記成答錯） | `a221e41` | **`e88c147`** | 不改 runtime，但**是 L-4 的證據** |

**發射的 commit 必須在這三個之後。** 本檔凍結時 main 的 HEAD ＝ `e88c147`。

#### 為什麼三者的地位不一樣（**不要都寫「不影響」**）

- **第 1（沙箱）：不影響本輪資料。** 本輪走 `--sandbox none`，不降權到別的 uid ⇒
  修法動的 `UnshareSandbox` 收尾路徑**不會被走到**。
  **釘 sha 是為了讓後人知道本輪的 `kill_status` 欄位是哪一版產生的**，
  不是因為本輪依賴那個修法。
- **第 2（wireproxy）：會影響本輪資料**，兩條理由都是承重的：
  ① `requests_seen` 少算會讓 **I-5 誤判 `infra_void`**（`requests_seen == 0`
     ＝「agent 根本沒被中介到」，那是 L-0 與 I-5 的判準）；
  ② `requests_seen_cumulative` 是 **`M7_file`／`M7_ws` 的分段依據**（§三），
     少算會把某一次嘗試的 wire 歸到錯的 attempt 上。
  而 **`M7_file` 是 §〇 主要交付的第一個數字** ⇒ **發射前必須在這個修法之後。**
- **第 3（測試逾時）：不改 runtime，但它是 L-4 的證據。**
  它改的是 `_run` 的預設 `sandbox_timeout_s` 3 → 30 與 `test_t4` 的逐案例逾時。
  它證明了「**超時被記成答錯**」這個失效模式**在本 repo 真的會發生**——
  同一份測試單獨跑會過、全套跑就紅，因為機器一忙連跑一個 trivial 函式都可能超過 3 秒。
  **L-4 的汙染規則就是為它寫的**，引用 L-4 時指向 `e88c147` 比指向一段描述有力。
  它也是 §九 L-2（`--test-timeout 30`）那個數字的來源：
  「30 s 足以抓到無窮迴圈」是關於**迴圈**的敘述（成立）；
  「3 s 足以跑完一個 trivial 函式」是關於**機器負載**的敘述（不成立）。

#### 6 條測試 ＋ 負控制

`tests/test_sandbox_kill.py`：
`test_timeout_kills_the_whole_group_and_records_it`、
`test_no_timeout_leaves_kill_status_empty`、
`test_group_alive_reports_true_when_we_lack_permission`、
`test_unkillable_group_is_reported_as_leaked`、
`test_sudo_path_is_attempted_for_unshare_backend`、
`test_unshare_backend_overrides_the_kill_path`。
**負控制 3 條轉紅**（把修法拿掉，那 3 條要翻紅）——
沒有負控的「全綠」跟把測試關掉在輸出上同形。

### L-2　`--test-timeout 30`

微型題參考解 < 1 s，30 s 仍抓得到無窮迴圈。
（預設是 10 s，那是 R530 凍結的常數；本輪明講改成 30 是因為要在 load 71 下發。）

⚠ **這個數字有實證出處，不是拍的**：`e88c147`（L-1 第 3 列）把 `_run` 的預設
`sandbox_timeout_s` 從 3 改成 30，正是因為「全套跑就紅、單獨跑會過」——
機器一忙，連跑一個 trivial 函式都可能超過 3 秒，`logic`／`exc` 被判成 `timeout`。
**「30 s 足以抓到無窮迴圈」是關於迴圈的敘述（成立）；
「3 s 足以跑完一個 trivial 函式」是關於機器負載的敘述（不成立）。**

### L-3　**F8 時序門**（發射前，用參考解）

1. 用 `bank/<tid>/reference/solution.py` 跑**同一支驗收 runner**（`vacant/vrun/acceptance.py`，
   `--sandbox none`、`--test-timeout 30`）；
2. **S1／S2 每題「可見」與「隱藏」各 ≤ 2 s 牆鐘**。任一題超過 ⇒ 紅，不准發射；
3. driver **每 15 分鐘記一次 `uptime`** 進 `<runs>/r535/driver_uptime.jsonl`；
4. **1 分鐘 load > 80 ⇒ 暫停派工**（不是砍 run）。恢復條件：1 分鐘 load ≤ 75 連續兩次取樣。

⚠ 時序門量的是**參考解**在當下負載下的牆鐘，**不是** agent 的牆鐘。
它保證的是「30 s 的逾時上限相對於真實耗時有 15 倍餘裕」，
**不保證** agent 那一側不會因為負載而變慢。後者靠 L-4 的汙染規則接住。

### L-4　汙染規則（**凍結**）

> **這條規則有一個已發生的先例，不是假想的風險**：`e88c147`（L-1 第 3 列）
> 就是「超時被記成答錯」發生在本 repo 自己的測試套件裡——
> `test_t4_four_failure_kinds_and_two_distinct_loader_reasons` 全套跑會紅、單獨跑會過。
> **引用本節時指向那個 commit，不要只指向這段描述。**

```
任一嘗試的可見結果含 kind == "timeout"
  ⇒ 該工作區快照（<rd>/_frozen_RUN-ON[_a<n>]/）在孤兒清掉後**重算**
      · 重算通過 ⇒ 該題該臂 infra_void，**三臂一起剔除**（S1/S2 各自層內）
      · 重算不通過 ⇒ 真的無窮迴圈，維持原判
  ⇒ 剔除 > 10% ⇒ 該層 INVALID（§六-2 第 1 列）
```

⚠ **重算救得回判定，救不回「假失敗觸發的那次重試」。**
一次假逾時會讓三個 3-draw 臂多跑一輪（RS 還會多重置一次工作區）——
那一輪的 agent 行為已經發生了，事後重算改不掉。**所以是剔題不是改分。**

#### RS／RF／RP：保守版（維持）

**三臂＝ RS／RF／RP**（配對比較的那三個）。
**任一次嘗試（含最後一次——閘門拒交是基建造成的）被重算翻轉 ⇒ 該題三臂一起 void。**
理由：那一格的**嘗試序列本身**已經被假失敗改寫了，重算只能救判定救不回序列。

#### PC：**不需要 void**（本檔精化，裁決原文沒有指定）

**PC 沒有重試路徑**（`--retry none`，只有一次嘗試）⇒ **沒有任何路徑會被假失敗改變**。
所以：

- `kind == "timeout"` 的 PC 格 ⇒ 孤兒清掉後對 `_frozen_RUN-ON/` 重算，
  **直接採用重算後的判定**。不 void、不連坐、**不進 10% 的分子**。
- **只有快照缺失、重算不了的 PC 格才 `infra_void`。**
- **PC 覆蓋率 < 80% 的層**：`CEILING_TOO_LOW` 的判定要標
  「**天花板估計不完整**」，並**允許補跑 PC**（PC 不進任何配對檢定 ⇒ 補跑不破配對）。

### L-5　冒煙塊先跑（發射 360 格之前）

S1 取 3 題 × 四臂 ＝ 12 格。要看到：`requests_seen > 0`（I-5）、
四臂第 1 次 `argv_sha256` 相同（I-1）、RP 第 2 次 `feedback_in_prompt_bytes > 0`（I-2）、
RF 第 2 次 `== 0`（I-3）、**RS 每次重置都回得到起點（I-7）**、
**RS 的工作區始終沒有 `VACANT_FEEDBACK.md`（I-8）**、收據鏈過（I-6）、
**`m7_ws` 解析器在冒煙的 wire 上跑得出東西**（含它的 `--selftest` 翻紅）、
每次嘗試牆鐘落在 §八 的估計裡。
**冒煙塊的資料不進分析**（它是量具校準，不是樣本），
而且**冒煙的三題不得從 `plan.jsonl` 拿掉**——正式跑時它們照樣要從乾淨的工作區重跑一次。

### L-6　Stage B 與 Stage C

- **Stage B（r530 重量級題庫）在 load < 4 之前不准發。** `lcb_3686` 要 46 s，
  而 10 s 是它凍結的常數 ⇒ 帶著 load 71 發它就是在製造假逾時。**本檔不含 Stage B。**
- **Stage C（第二基質 10 題、只跑 RF／RP，看「file 從不被讀」是不是 pi 專屬）
  ＝選配、不進預註冊。** S1／S2 歸檔後才准動；接不上就丟，不補。

---

## 十、誠實邊界（**收官必帶，現在就寫**）

1. **n 小、單一模型、單一 agent、單一題庫 ⇒ 不可外推。**
   S1 n=50、S2 n=40；模型只有 `gemma-4-12b-it-qat`（Q4_0）；agent 只有 pi 0.85.1；
   題庫是**為這個問題自造的**。本輪的任何數字都是「這四件事同時成立時」的數字。
   換掉其中任何一個都要重跑。
2. **「檔案投遞失效」的限定範圍**（§一的 ⚠ 逐字）：這是對**這條 argv、這個 agent**
   的結論，不是對 `file` 模式的普遍結論。會 `ls` 的 agent、或 prompt 裡叫它先看目錄的
   使用者，情況不同。**收官不得寫成「檔案投遞沒有用」。**
3. **在 load 71 下發射的殘餘風險。** 依據是「V1 那兩跑就是在 load ≈ 71 下跑的，
   每次嘗試 4–6 s、判定正確」——那是 **n=1 的依據**。
   L-3 的時序門與 L-4 的汙染規則是兩道網，但它們接的是**逾時**這一種汙染；
   負載讓模型端點變慢、讓 agent 提早放棄、讓 pi 的內部逾時觸發，
   **這三種本輪都量不到**，只能靠 `agent_wall_s` 的分佈事後描述。
4. **可見套件擋得住已知壞解 ≠ 涵蓋真需求**（`vacant/suitegauge.py` 的單邊保證）。
   `gauge_bank.py` 兩個方向都過（參考解全過、三個壞樁全被擋）只是**單邊**保證，
   它不代表「驗收套件固定點已解」，也不代表可見套件涵蓋了 `TASK.md` 說的全部需求。
   ⇒ **M1 量的是「客戶給的那幾條過了」，不是「做對了」。**
5. **M7_file 是單邊的**（§三的 ⚠）：命中 0 只說明那三個字串沒出現在請求 body 裡，
   不說明 agent 沒有以任何方式受到那個檔的影響。
6. **RF 與 RS 的差別是兩條管道，不是 draw 數。** RS ＝ `--retry resample`，
   與 RF／RP 同樣是 3 draw（§二-2 的更正）⇒ 「多抽兩次」已經被控制掉了。
   剩下的兩個差異是 **(i)** 工作區多一個 `VACANT_FEEDBACK.md`、
   **(ii)** `revise` 保留工作區／`resample` 重置工作區。
   **這兩個在本設計裡沒有再被拆開**——M7_file 與 M7_ws 分別給它們一個觀測窗，
   但如果兩個都 > 0，本輪分不出是哪一個造成的。
   H3（RP vs RS）仍然降為描述：RP 與 RS 同時差了管道與「保留 vs 重置」兩件事。
7. **PC 不是「正確答案」的上界，是「把話講清楚」的上界。**
   `TASK_explicit.md` 是我們寫的，它寫得好不好會直接搬進 PC 的數字。
   PC ≥ 0.8 沒達成，可能是題目太難，也可能是我們的 explicit 版寫得不夠 explicit——
   **本輪分不開這兩者。**
8. **重試不是免費的。** 每一次嘗試都燒一整個 agent 行程的 token 與時間。
   `--max-attempts 3` 是**成本上限不是目標值**。逐次用量落盤（`attempts[i].requests_seen`／
   `agent_wall_s`／`ws_*_sha256`），等預算的定義是「上限相同、實際用量落盤」，
   不是強制用滿（R530 的裁決）。
9. **`{block}` 裡的路徑指的是凍結快照**（`_frozen_RUN-ON_a2/solution.py`），不是 agent
   自己那個檔。這是 V0 就有的性質，V1／V2 都沒有改 `render_failures`（凍結碼）。
   「路徑看起來不是它的檔」有沒有害到它，**本輪沒有量**——寫成沒量，不要寫成沒有。
10. **`vacant run` 的 proxy 是 records 不是 verifies。** 它只證明「這些 bytes 經過我」，
    不阻止 agent 走別的路徑繞過它。本輪沒有加出網封鎖（`block_egress.sh`，需要 root），
    所以 `requests_seen > 0` 證明的是「有經過」，不是「全部都經過」。
11. **一次 run 不是複製。** 本輪是**一次** run，每一個點估計都要當單次值讀。
    R460 的 +13.33 → 五次複製 +0.83～+5.83 已經演過一次「單次點估計是上偏的」。
12. **口徑**：本輪講的是**可究責性**（讓依賴有根據），**不是信任**。
    經典定義（Gambetta 1988、Mayer 1995）把「不依賴監督」寫進信任的必要條件，
    而監督正是這個系統的全部。`vacant run` 能強制的只有「沒過就不出貨」；
    **「回饋一定出現在模型的輸入裡」不等於「不可忽略」**——看得到 ≠ 照做。
13. **本輪不得與 R530／R532／R534／`docs/VACANT_RUN.md` §7.8 併表或併 n**（§四-3）。
14. **S1 與 S2 不是完全獨立的 90 題**（`manifest.honesty_bounds[6]`，2026-09-19 稽核時發現）。
    兩對題**跨層共用同一份參考解**：`s1_32_pct`／`s2_06_pct` 與 `s1_35_rle`／`s2_29_rle`。
    那是設計使然——S1 withhold 的是**名字**、S2 給名字 withhold **行為細節**，
    同一個函式在兩層各出現一次就是這個對照的形狀，**題庫不用改**。
    但後果是：**「S1／S2 分開報不合併」在本檔不是慣例而是必要條件**——
    合併之後這兩對會被當成四個獨立觀測，而它們不是。
    ⚠ **七項量具一項都抓不到這件事**，因為每一項都是**逐題**判定的。
15. **`hidden` 是 `visible` 的超集** ⇒ hidden 全過蘊含 visible 全過。
    兩個數字**不獨立，不可以當成兩個證據**（`honesty_bounds[3]`）。
    M4（隱藏通過率）因此只能是描述性的，不進任何檢定。
16. **PC 只切掉一個對立解釋，不是 RP 的配對對照**（`honesty_bounds[5]`）。
    PC 切掉的是「講明白了它也寫不出來」。
    **PC 高不等於「RP 沒提升＝管道壞了」**——PC 與 RP 差的不只是講不講明白，
    還差了「一次 vs 多次嘗試」。
17. **兩層共用同一顆模型對同一函式的熟悉度。**
    S1 與 S2 有大量同名／同功能的題（`*_mean`、`*_tally`、`*_chunks`、`*_hms`、
    `*_rle`、`*_pct`、`*_parse_kv`、`*_initials`、`*_ordinal`…），
    同一顆模型對同一個函式的熟悉度會同時搬進兩層。
    ⇒ **S1 與 S2 的差值方向可以互相印證，數值不可相加。**
    兩層同向 ⇒ 證據互相加強（但不是兩個獨立證據）；兩層反向 ⇒ 要當成一個
    **需要解釋的觀測**寫出來，不得只報其中一層。
18. **題庫作者事前標了風險題，這是判斷不是量測**（量具零模型呼叫，沒有任何一題被真模型跑過）：
    - **最可能第一次就過**（會削弱 S1 的正控制性質）：`s1_13_mean`、`s1_15_chunks`、
      `s1_48_cumsum`、`s1_12_hms`、`s1_35_rle`、`s1_21_total`（6/50）。
    - **PC 也可能失敗**（超出模型能力）：`s2_24_round_money`
      （`2.675` 的二進位表示問題，要走 `Decimal` 才過）、`s1_11_caps`、`s1_44_by_length`。
    ⇒ 收官時把這 9 題的實測結果**單獨列一節**與事前標記並排，
    但**不得**因此把它們從樣本裡拿掉（事後剔題＝挑數字）。

---

## 十一、收官必產的東西

| 產物 | 內容 |
|---|---|
| **§〇 的三個數字** | **M7_file（含 M7_ws，附 rule-of-three 上界）／第 1 次可見失敗率（S1、S2 分開，n=150／120）／S1 的 H1 點估計＋95% 區間**。摘要與收官都照這三個講 |
| `ops/gain/r535/analyze_r535.py` | 兩層 × 四臂；`primary`（家族 2、Holm）、`per_stratum`、`m7_file`／**`m7_ws`**（逐題、逐通、命中字串或工具呼叫）、`f6`、**`mc1`**（`RS_attempt1`／`RS_final`／`R_indep` 三數並排，**不做檢定**）、`cost`（`attempts_used` 分佈）、`hidden`（描述性、每列 `not_a_test`）、`decision_state`（§六 求值順序寫死，含 `STALE_WORKSPACE_EFFECT`）、`ci95`（`boot_ci` 2.5/97.5）、`tost`（含禁語檢查）；`--selftest` ＋ `--mutation-check` |
| **`m7_ws` 解析器的 `--selftest`** | 餵一段已知含 `ls` 的 wire 必須翻紅。**沒有它，「M7_ws = 0」跟「解析器沒認出任何工具呼叫」在輸出上同形** |
| `ops/gain/r535/power_table.json` | §七 三張表的機器可讀版（含產生它的 seed 與版本；由附錄 A 的程式碼產生，**不准手抄**） |
| `ops/gain/replay/r535/r535_analyze.json` | 仲裁值 |
| **`runs/r535/plan.jsonl`** ＋ 它的 sha256 | 發射前落盤的 360 格計畫，sha256 **簽進第一筆收據**（§十三-1 牙齒一） |
| **`plan.jsonl` ↔ `rows.jsonl` 的逐格對帳表** | 360 格每一格「有一列」或「明寫 void 原因」；**少一格或多一格都是 `INVALID`**（牙齒二） |
| `receipts_verify.json` | 360 格逐格驗鏈（先 `--selftest`） |
| `runs/r535/driver_uptime.jsonl` | L-3 的 15 分鐘 `uptime` 取樣 |
| 三方對帳 | 分析器（A）／不讀分析器的獨立重算（B）／第三次直接掃 `rows.jsonl`（C），仲裁欄位逐位元相同 |
| run 名字對照表 | `vr1_run`／`run4` ↔ `v1_real_pi`／`v1_real_pi_explicit`（§一） |
| 稽核檔 | `DECISION_2026xxxx_R535_FABLE_AUDIT.md` |

⚠ 分析器必須在**第一格收官之前**落地（R529 §六-4 的教訓：首塊在分析器 commit 之前收官，
「沒讀 rows」就變成不可查證的宣稱）。

---

## 十二、鐵律（**照抄，違反＝run 作廢**）

1. **KS-1**：任何 prompt 模板禁止「你有責任／會被懲罰」類措辭；
   **四臂模板逐字相同**，唯一差異＝回饋投遞管道（RP 的 argv 尾端那一段）。
   `vacant/memory.py::assert_ks1_clean` 是可執行防呆，不要繞過。
   ⚠ **範圍是「我們接上去的那一段」，不是使用者自己的 prompt**（2026-09-18 人類裁決）。
   本輪的 argv 是我們寫的，所以整條都受管。
2. **A4**：教訓只准坑型層級抽象、禁止逐字測資（`lesson_leaks_test_data`）。
   本輪對應的是 **V/GT 紅線**：回饋只吃 `run_suite(suite="visible")` 的結果，
   `hidden/` 的存在、條數、內容一律不進回饋。
   可執行防呆＝`tests/test_vacant_run_retry.py::test_feedback_file_never_contains_hidden_testdata`
   ＋**負向控制** `test_vgt_canary_scan_has_teeth`。
   沒有負控的「零命中」跟把掃描關掉在輸出上同形。
3. **全 I/O JSONL 落盤**、retry×4、`infra_void` 規則（09 §3.5）。
   `wire/index.jsonl` ＋ `wire/<call_id>.{req,resp}.bin` **原始位元組**逐通落盤。
4. **記憶不跨臂共享**；行為依賴歷史的部分禁用快取。
   本輪四臂各自獨立的工作區、獨立的 run 目錄、獨立的 pi session。
5. **demo 只能說「看得到提升」**；「證明提升」保留給預註冊 batch run。
   本檔就是那個預註冊——但它的檢定力（§七）只看得見 +30 pp 等級的效果，
   **所以它能「證明」的範圍很窄，那個窄法現在就寫在這裡**。
6. wire-format：logbook 已 break（2026-07）；`~/.vacant-mcp` 等舊資料要清掉重鑄。

---

## 十三、逐格註冊（`R535_BLOCK:`）

**格 ＝（層 × 臂）＝ 8 格。** 每格一行。發射器**整組**比對，少一格就發不出去。

```
R535_BLOCK: r535_s1_RS stratum=S1 n=50 arm=RS retry=none   feedback_into=file   max_attempts=1 task=TASK.md suite=bank/<tid>/tests_visible sandbox=none test_timeout=30
R535_BLOCK: r535_s1_RF stratum=S1 n=50 arm=RF retry=revise feedback_into=file   max_attempts=3 task=TASK.md suite=bank/<tid>/tests_visible sandbox=none test_timeout=30
R535_BLOCK: r535_s1_RP stratum=S1 n=50 arm=RP retry=revise feedback_into=prompt max_attempts=3 task=TASK.md suite=bank/<tid>/tests_visible sandbox=none test_timeout=30
R535_BLOCK: r535_s1_PC stratum=S1 n=50 arm=PC retry=none   feedback_into=file   max_attempts=1 task=TASK_explicit.md->TASK.md suite=bank/<tid>/tests_visible sandbox=none test_timeout=30
R535_BLOCK: r535_s2_RS stratum=S2 n=40 arm=RS retry=none   feedback_into=file   max_attempts=1 task=TASK.md suite=bank/<tid>/tests_visible sandbox=none test_timeout=30
R535_BLOCK: r535_s2_RF stratum=S2 n=40 arm=RF retry=revise feedback_into=file   max_attempts=3 task=TASK.md suite=bank/<tid>/tests_visible sandbox=none test_timeout=30
R535_BLOCK: r535_s2_RP stratum=S2 n=40 arm=RP retry=revise feedback_into=prompt max_attempts=3 task=TASK.md suite=bank/<tid>/tests_visible sandbox=none test_timeout=30
R535_BLOCK: r535_s2_PC stratum=S2 n=40 arm=PC retry=none   feedback_into=file   max_attempts=1 task=TASK_explicit.md->TASK.md suite=bank/<tid>/tests_visible sandbox=none test_timeout=30
```

**8 個 run 目錄根**（發射器要它們逐字出現在本檔）：
`runs/r535/r535_s1_RS`、`runs/r535/r535_s1_RF`、`runs/r535/r535_s1_RP`、`runs/r535/r535_s1_PC`、
`runs/r535/r535_s2_RS`、`runs/r535/r535_s2_RF`、`runs/r535/r535_s2_RP`、`runs/r535/r535_s2_PC`

### 十三-1　展開成 360 格的**確定性規則**（凍結時展開，不准臨場決定）

每個 `R535_BLOCK:` 展開成 `n` 個 `vacant run` 呼叫，逐題的 run 目錄是

```
runs/r535/<block_id>/<tid>/
```

`<tid>` 的來源與**順序**：`ops/gain/r535/bank_manifest.json` 的
`strata.S1.task_ids`／`strata.S2.task_ids`，**照 manifest 裡的原始順序**取用
（**不重排、不抽樣、不跳過**）。

| 項 | 值 |
|---|---|
| `bank_manifest.json` sha256 | **`5e727b2ee884d80b197ec42f63af2bf73ce939bdd53c48fc8fc29e46e49c0794`** |
| 展開器 | `<<TODO-FREEZE: ops/gain/r535/run_r535.py 的展開段（發射驅動那一側正在造）＋它的 sha>>` |
| 展開器必須滿足的規格 | **本檔凍結的是規格不是實作**：下面「牙齒一／牙齒二」兩節。實作落在發射驅動側，交件後補檔名與 sha |

**S1 的 50 個 `<tid>`（逐字，照這個順序）**：

```
s1_01_addmul       s1_02_span         s1_03_nwords       s1_04_toc          s1_05_initials
s1_06_parity       s1_07_flipwords    s1_08_nvowels      s1_09_pin          s1_10_uniq
s1_11_caps         s1_12_hms          s1_13_mean         s1_14_mid          s1_15_chunks
s1_16_flat         s1_17_pairs_to_map s1_18_flip_map     s1_19_tally        s1_20_top_key
s1_21_total        s1_22_digit_list   s1_23_cross_sum    s1_24_is_pal       s1_25_shift_letters
s1_26_cells        s1_27_parse_kv     s1_28_split_path   s1_29_strip_zeros  s1_30_ord_suffix
s1_31_money        s1_32_pct          s1_33_band         s1_34_days_in      s1_35_rle
s1_36_longest_run  s1_37_same_letters s1_38_shared_start s1_39_wrap_at      s1_40_bullets
s1_41_squeeze      s1_42_snakeify     s1_43_camelise     s1_44_by_length    s1_45_group_first
s1_46_merge_spans  s1_47_pairwise_diff s1_48_cumsum      s1_49_rgb          s1_50_ends
```

**S2 的 40 個 `<tid>`（逐字，照這個順序）**：

```
s2_01_mean         s2_02_tally        s2_03_top_n        s2_04_split_csv    s2_05_clamp
s2_06_pct          s2_07_median       s2_08_dedupe       s2_09_chunks       s2_10_wrap
s2_11_titleize     s2_12_slugify      s2_13_parse_int    s2_14_range_sum    s2_15_normalize
s2_16_size_label   s2_17_ordinal      s2_18_is_palindrome s2_19_group_by_first s2_20_merge
s2_21_flatten      s2_22_only_in_first s2_23_running_total s2_24_round_money s2_25_truncate
s2_26_initials     s2_27_count_lines  s2_28_parse_kv     s2_29_rle          s2_30_caesar
s2_31_mean_by      s2_32_sort_versions s2_33_is_leap     s2_34_hms          s2_35_pluralize
s2_36_mask         s2_37_column       s2_38_in_range     s2_39_strip_comments s2_40_first_match
```

⚠ **360 行的逐格展開不寫進本檔**：它是上面 8 行 × 90 個 `<tid>` 的機械笛卡兒積。
**牙齒在下面兩道，不在行數上。**

#### 牙齒一：發射前把計畫落盤並簽進收據

展開器（落在 `ops/gain/r535/run_r535.py`）必須**讀 manifest 而不是讀本檔**，並且：

1. 把 `bank_manifest.json` 的 sha256 與 §十三-1 釘的值**逐位元比對**——不相等就拒絕啟動；
2. 把 **360 格（4 臂 × 90 題）的完整計畫寫成 `plan.jsonl`**，落在 run 目錄根
   （`runs/r535/plan.jsonl`），每列一格：`block_id`／`arm`／`stratum`／`task_id`／
   `run_dir`／`arm_flags`／`workspace_template`／`suite`；
3. **`plan.jsonl` 的 sha256 簽進第一筆收據**。⇒ 「發射時打算跑哪 360 格」
   從此是一個**被簽章背書的事實**，不是事後可以改的說法。

#### 牙齒二：收官對帳，**少一格或多一格都是 `INVALID`**

收官時把 `plan.jsonl` 的 360 列與實際的 `rows.jsonl` 逐格對帳：

```
每一格必須「有一列 rows」或「明寫 void 原因」（§九 L-4 的哪一條）
少一格  ⇒ INVALID（該層）
多一格  ⇒ INVALID（該層）
```

⚠ **「多一格」也判 `INVALID`**，不是只擋少的：多出來的那一格代表有人在凍結之後
加跑了計畫外的東西，而那正是「挑數字」最自然的入口。
（PC 的補跑是**唯一的例外**，見 §九 L-4，且補跑要另寫一份 `plan_pc_refill.jsonl` 並簽入。）

---

## 十四、發射前檢查清單（**逐條打勾才准發**）

- [ ] 唯一剩下的 `<<TODO-FREEZE: …>>` 補完（展開器的檔名與 sha，§十三-1）
- [x] `bank_manifest.json` sha256 釘死＝`5e727b2ee884d80b197ec42f63af2bf73ce939bdd53c48fc8fc29e46e49c0794`
- [x] 三個基建修法都在 main：`cad1001`（沙箱）／`9420d81`（wireproxy）／`e88c147`（測試逾時）
- [x] `gauge_bank.py` **七項 90/90 全綠**（作者一次、稽核者獨立重跑一次）
- [ ] `build_bank.py --check` 在**發射當下的 checkout** 上重跑一次，確認題庫沒漂
- [ ] 分支 `bank/r535` 併進 main（題庫 810 個檔）
- [x] §五-2 的護欄表已定案（RS 更正為 `--retry resample` 之後，草稿提的三個選項作廢；
      新增 `M7_ws` 與 `STALE_WORKSPACE_EFFECT`）
- [ ] 展開器落地（發射驅動側）：manifest sha 比對 ＋ 寫 `plan.jsonl` ＋ sha 簽進第一筆收據
- [ ] `m7_ws` 解析器落地並 `--selftest` 翻紅（餵已知含 `ls` 的 wire）
- [ ] L-0 pi 接線自檢：`requests_seen > 0`
- [ ] L-1 發射的 commit 在 `cad1001`／`9420d81`／`e88c147` **三者之後**（本檔凍結時 main HEAD ＝ `e88c147`）
- [ ] L-1 `tests/test_sandbox_kill.py` 6 條綠、負控 3 條紅
- [ ] L-3 F8 時序門：S1/S2 每題可見＋隱藏各 ≤ 2 s
- [ ] L-5 冒煙 12 格：I-1～I-8 全過（含 RS 的 I-7 重置回得到起點、I-8 工作區無回饋檔）
- [ ] vacant-dev 的 72 個孤兒已清（`sudo -n pkill -9 -u nobody -f "m solution tests_visible"`）
- [ ] `ops/gain/r535/analyze_r535.py` 已落地並 `--selftest` 綠
- [ ] Fable 核 ＋ 人類簽字 ＋ ledger 簽入

---

## 附錄 A、§七 的數字是怎麼算出來的（**照抄可重跑，零模型呼叫**）

`ops/gain/r535/power_table.json`（§十一）要由這一段產生，**不准手抄**。

```python
# §七-1 主表 ＋ §七-2 敏感度 ＋ 自我對帳
from vacant.research import mcnemar_power
ALPHA = 0.025                        # Holm 家族大小 2 的最保守那一格
for p_disc in (0.25, 0.40, 0.55):
    for delta in (0.05, 0.10, 0.20, 0.30):
        if delta > p_disc:           # psi > 1 ⇒ 該格不可能，要印「不可能」不是印 0
            continue
        psi = (delta / p_disc + 1) / 2      # Delta = p_disc * (2*psi - 1)
        for n in (50, 40):
            print(p_disc, delta, n, mcnemar_power(n, p_disc, psi, alpha=ALPHA))
# 自我對帳：psi=0.5 ＝ H0，回傳的是檢定的 size，精確檢定保守 ⇒ 必須 <= ALPHA
for n in (50, 40):
    for p_disc in (0.25, 0.40, 0.55):
        print(n, p_disc, mcnemar_power(n, p_disc, 0.5, alpha=ALPHA))

# §七-1 的 n_required：mcnemar_power 對 n 單調遞增 ⇒ 倍增 + 二分。
# ⚠ 不要用 research.mcnemar_n_required 的線性掃描：它從 n=1 掃到 n_max，
#   而 mcnemar_power 是全枚舉的精確檢定、大致 O(n^2)（實測 n=400 單次 2.98 s）
#   ⇒ Delta=+5pp 那一格會掃到 n_max 而且跑不完（本檔實測：>10 分鐘未收斂）。
#   本檔的四個數字改用倍增＋二分算出來（下面這一段），cap=1600。
#   （**已於 `69324dc` 修正**——但本節保留原始處置作為史實：
#     預註冊凍結的是「當時怎麼做的」，不是「後來變成怎樣」。）
def n_req(p_disc, psi, target=0.80, cap=1600):
    n = 8
    while n <= cap:
        if mcnemar_power(n, p_disc, psi, alpha=ALPHA) >= target:
            lo, hi = n // 2, n
            while lo < hi:
                mid = (lo + hi) // 2
                if mcnemar_power(mid, p_disc, psi, alpha=ALPHA) >= target:
                    hi = mid
                else:
                    lo = mid + 1
            return lo
        n *= 2
    return None                       # ＝「> cap」，不是「算不出來」
```

```python
# §七-3 TOST 半寬：實跑 tost_equiv_boot，不是解析近似
import random, statistics
from vacant.research import tost_equiv_boot
for n in (50, 40):
    for true_d in (0.0, 0.05, 0.10):
        rng, p_disc = random.Random(20260919), 0.40
        psi = (true_d / p_disc + 1) / 2
        halfw, eq = [], 0
        for t in range(300):                      # 每格 300 次模擬
            diffs = [(1.0 if rng.random() < psi else -1.0)
                     if rng.random() < p_disc else 0.0 for _ in range(n)]
            r = tost_equiv_boot(diffs, delta=0.15, seed=t)   # 預設 2000 bootstrap
            halfw.append((r["ci_hi"] - r["ci_lo"]) / 2)
            eq += int(bool(r["equivalent"]))
        print(n, true_d, statistics.median(halfw), eq, "/300")
```

⚠ **§七-3 的模擬有一個自己的邊界**：它假設逐題配對差是 i.i.d. 的三點分佈。
真資料不是——題目難度不同、兩對題跨層共用參考解（§十-14）。
所以那張表給的是**區間半寬的量級**，不是對實測 CI 的預測。
