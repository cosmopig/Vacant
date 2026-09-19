# R530 題目目錄格式（規格）

這一份是**題庫代理照著做的那張圖**。`ow_01_csvjson` 與 `ow_02_ratelimit`
是兩個已經落地的實體範例——**形狀以這份文件為準，不以那兩題的內容為準**。

執行語意在 `vacant_network/vrun/acceptance.py`（驗收 runner；2026-09-18 從
`ops/gain/r530/acceptance.py` 搬進套件，舊路徑是 re-export、指令照舊）與
`ops/gain/r530/tasks.py`（載入與釘死）的 docstring 裡；
這份講的是**檔案長什麼樣**。

---

## 一、一題 ＝ 三個目錄

```
ops/gain/r530/templates/<task_id>/     ← 工作區樣板（worker 看得到全部）
    goal.md            目標敘述
    contract.md        介面契約
    tests_visible/
        test_*.py      可見驗收（2–3 條，**同時是出貨閘門**）
    run_tests.sh       一行：跑可見驗收（worker 可以自己跑）

ops/gain/r530/hidden/<task_id>/        ← 隱藏驗收（**永遠不進工作區**）
    test_*.py          ≥10 條
    ANCHORS.md         §五-2 的公平性複核對照表

ops/gain/r530/gauge/<task_id>/         ← 量具樁（PR-3／E-3）
    good.py            參考解：必須**全過**可見與隱藏
    bad_*.py           已知壞樁（≥3）：每一個都**必須被擋**
```

`task_id` 用 `ow_<兩位數>_<短名>`（小寫、底線）。

### 硬性檢查（`tasks.load_task` 會拒收，不是警告）

| 檢查 | 判準 | 不過會怎樣 |
|---|---|---|
| 兩個目錄都在 | `templates/<id>/`、`hidden/<id>/` | `TaskBankError`，發射停 |
| `goal.md`／`contract.md` 都在 | 檔案存在且非空 | 同上 |
| `tests_visible/` 有 `test_*.py` | ≥1 檔 | 同上 |
| `hidden/` 有 `test_*.py` | ≥1 檔 | 同上 |
| 樣板大小 | **200 B – 30 KB**（Fable 裁決的 10–30 KB，下界放寬到 200 B 讓最小題目過得去） | 同上 |
| 樣板裡沒有 `hidden`／`rubric` 字樣的路徑 | 結構性紅線（§五-3 第 1 條） | 同上 |

---

## 二、`goal.md`

一段話，講**客戶要什麼、為什麼要、他們踩過什麼坑**。
**不給步驟、不給演算法、不給資料結構。** 英文（worker 是
`gemma-4-12b-it-qat`，本 repo 既有 prompt 全英文；換語言會多一個與機制無關的差異）。

寫法上唯一的硬規則：**目標敘述裡的每一句「客戶困擾」都要有一條隱藏驗收對應**
（`ANCHORS.md` 的反向檢查那一節）。對不到就代表那句話是**沒有被量到的需求**，
要嘛補一條驗收，要嘛從目標敘述刪掉——留著＝在計分之外偷偷加難度。

## 三、`contract.md`

介面簽名 ＋ 語意的**釘死點**：錯誤訊息格式、退出碼、捨入規則、排序規則、
邊界的開閉。契約存在的理由是「三條臂的產出要能被同一套測試呼叫」，
**不是**給提示。

判斷一句話該進 `goal` 還是 `contract` 的標準：
**它是「客戶想要的效果」還是「我們選的一種表達方式」。**
「壞行要指出行號」是效果（goal）；「`line <N>: <reason>` 恰好一行、exit 2」
是表達方式（contract）。

契約要**釘到隱藏驗收寫得出斷言**為止。釘不到的東西不要出現在隱藏驗收裡。

## 四、`tests_visible/test_*.py`

- **2–3 條**。它們同時是 `A-CONF`／`A-GATE` 的出貨閘門。
- 每一條是一個零引數的 `check_*()` 函式；正常回傳＝過，丟例外＝不過。
- `import solution` 就好——runner 會把工作區放進 `sys.path`。
- 斷言訊息要說出 **got 與 want**：那三個欄位逐字會進 `A-GATE` 的回饋
  （`acceptance.CASE_LINE`）。零資訊的 `assert x == y` 會讓回饋變成
  「你的程式壞了」，而那是 R460 §3.2 已經量過的壞回饋。
- **可見驗收的輸入與期望值 worker 看得到、跑得到**，這是設計要的（§八-5）。

## 五、`hidden/test_*.py`

- **≥10 條**，含邊界情況。
- 同樣是 `check_*()`，同樣 `import solution`。
- **不准 `time.sleep`**（Fable 裁決的 10 秒／檔逾時會把它變成一條 timeout）。
- 要開暫存檔就用 `tempfile`：`TMPDIR` 指向沙箱的 `/tmp`，**不在工作區底下**。
  寫進工作區會改變樹雜湊，而 `openwork_arms.run_cell` 對「跑隱藏驗收不得動到
  工作區」有一條硬斷言，會直接讓那一格炸掉。
- **不准與任何一條可見驗收逐字相同**（同樣的 args 與 expected）。
  可以測同一個需求的不同輸入——那是設計，不是重複。

### 兩種寫法，一個檔案只准用一種

1. 一組 `check_*()` ⇒ 每個函式一條 case，依**定義順序**執行。
2. 一個 `main()` ⇒ 整個檔案算**一條** case。

其餘的東西（helper）放在同目錄的 `_support.py` 之類**不以 `test_` 開頭**的檔名裡。

## 六、`hidden/ANCHORS.md`

§五-2 的公平性複核表，兩張：

1. **正向**：`hidden_id`／`anchor_kind`（`goal` 或 `contract`）／
   `anchor_quote`（**逐字引用**）／`derivation`（一句話說明怎麼推過去）。
   指不到 anchor 的那一條**刪掉**，或把目標／契約改到指得到為止。
2. **反向**：目標敘述裡的每一句「客戶困擾」對到哪一條驗收。

⚠ 作者自己填第一版，**複核者不得是作者**。複核結果落盤
`ops/gain/r530/_fairness_review.json`，sha256 進 AMEND1。

## 七、`gauge/`

- `good.py`：參考解。**必須全過**可見與隱藏。不全過的意思不是「參考解寫得不好」，
  是**驗收與契約對不起來**——那要改題目。
- `bad_*.py`：**至少三個**已知壞樁，每一個都必須被隱藏驗收擋下來。
  刻意做一個「最接近正確」的（只有一兩條驗收抓得到），
  一個只擋得住明顯亂寫的套件量不出 R530 想量的差。
- 檔案的頂層要 `def`／`class` 出契約要求的那個名字；
  `gauge.py` 會把它複製成工作區裡的 `solution.py`。

跑法：

```
python3 ops/gain/r530/gauge.py --task-set all --backend auto
```

`verdict != OK` ⇒ 發射閘門 E-3 紅。
**「沒有樁」不計入覆蓋**（`coverage_n != n_tasks`）——量不到不是通過。

---

## 八、寫完一題之後要跑的三件事

```bash
# 0. 工具協定探針（真後端，會燒幾十個 token）——**只要換模型就要重跑**
#    2026-09-13 實測 gemma-4-12b-it-qat：原生 tools 通、```bash 圍欄不通。
python3 ops/gain/r530/sandbox.py --backend auto   # 順便確認沙箱退到哪一級

# 1. 載得起來嗎、sha256 是多少
python3 ops/gain/r530/tasks.py --task-set <task_id>

# 2. 雙向量具：參考解全過、每個壞樁都被擋
python3 ops/gain/r530/gauge.py --task-set <task_id> --backend auto

# 3. 整條迴圈跑得完嗎（零模型呼叫，替身後端）
python3 ops/gain/r530/run_r530.py --out runs/_smoke/<task_id> \
  --task-set <task_id> --seed smoke-<task_id> --backend none \
  --brain stub --smoke

# 4. 冒煙檢核表 C1–C8（真後端那一份跑完之後）
python3 ops/gain/r530/smoke_checklist.py --run runs/_smoke/<run>
```

三件都綠才算一題寫完；真後端冒煙另外要過 §三-6 的 C1–C8。

---

## 九、**這份格式還沒被回答的問題**（給 Fable，不是給題庫代理）

1. **拒交的格子，主指標讀哪一個？** `rows.jsonl` 現在同時落
   `hidden_frac`（最終工作區有多好，**不管有沒有出貨**）與
   `hidden_frac_delivered`（拒交 ⇒ 0.0）。兩個數字在 `A-GATE`／`A-CONF` 上不同，
   在 `A-SOLO` 上恆等（它沒有拒交語意）。
   **analyzer 要在看到資料之前指名一個**，這支不挑。
2. **可見 2–3 條、隱藏 ≥10 條的比例是不是太容易過擬合。** 預註冊 §四-3 已經
   事前承認過擬合空間結構性地大；題庫代理寫題時要知道這件事，
   但**不准為了讓數字好看去調條數**。
3. **收據型別的名字有兩套。** Fable 給建置代理的裁決寫 `ws_attempt`／
   `ws_verdict`，同一天更新的預註冊 §五-4／§三-6 C6 寫 `openwork_attempt`／
   `openwork_verdict`。目前 `verify_run_receipts.py` **兩套都認**，
   落盤用的是前者。**要由人類／Fable 收斂成一套**，收斂之前不准刪掉任一邊。
4. **`bad_*.py` 只被一條隱藏驗收抓到，算不算覆蓋夠。** 目前 `gauge.py` 印
   `caught_by_n`，判準只看「有沒有被擋」。要不要加「至少被兩條抓到」這條門檻，
   是 Fable 的裁決不是作者的選擇。

---

## 一〇、兩條 Fable 2026-09-14 裁准的實作決定（記在這裡，免得被當成手滑）

### 一〇-1　`max_tool_calls = 120` 是**推導**不是預註冊指名

預註冊指名的預算是呼叫數、completion token、脈絡、牆鐘四項。`max_tool_calls`
不在裡面，而舊值 `40` 在每格 72 通之下**會先咬到**：真後端實測每通約一次工具
呼叫（`A-SOLO/ow_01` 20 通 19 次），40 的上限會讓 `stop_reason` 變成
`budget_tool_calls` 而不是預註冊指名的那幾個——**同一件事被記成另一種語意**。
按同一個比例提到 120。

⇒ 引用預算時要分得開：**四項是裁決，這一項是推導**。改回去不影響任何別的東西。

### 一〇-2　份層級的預算檢查排在格層級**之前**

`A-CONF` 是 3 份 × 每份 24 通 ＝ 72 ＝ 整格上限，所以**第 3 份用完的那一刻
兩個上限同時成立**。判定順序因此是有語意的：

| 先問誰 | 第 3 份用完時記成 | 算不算拒交 |
|---|---|---|
| 格層級（`max_model_calls`） | `budget_calls` | **不算** |
| 份層級（`max_calls_per_attempt`） | `attempts_exhausted` | **算** |

P-W3（「`A-CONF` 的拒交件數 > 0」）讀的是後者。先問格層級會讓「三份都抽過
而且都沒過」被記成「沒跑完」——那是兩件事，而且只差一個 `if` 的順序。

⇒ **份層級先問**。`A-SOLO`／`A-GATE` 的「一份」就是整格，所以它們在同一個位置
記的是 `budget_calls`，語意不變。
