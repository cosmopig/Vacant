# DataBench（SemEval-2025 Task 8）pilot 題庫（30 題）

這一份講**題目**。為什麼選這個題組見 [`../SURVEY.md`](../SURVEY.md)。形狀跟 [`../dabench/`](../dabench/README.md) 相同：一張表、一個問題、交一個答案檔。它補兩件 DABench 給不了的事：

- **新**：SemEval-2025 Task 8 的測試集在 2025-01 才公開。
- **答案型別多樣**：五種型別各 6 題，分別是 boolean、category、number、list[number]、list[category]。

## 一、來源（釘死）

| 項目 | 值 |
|---|---|
| 題組 | DataBench（LREC-COLING 2024），SemEval-2025 Task 8 的**測試集**，也就是 `data/066_IBM_HR` … `data/080_Books` 這 15 個資料集，共 522 題 |
| 上游 | HF `cardiffnlp/databench` @ `e75d53add267d2f9cfa32efd65ad77f0807adfad`（README 的 config `semeval`、split `test`） |
| 釘死 | `source_files.json`：每個 `qa.parquet`／`all.parquet` 的 sha256，也就是 HF LFS oid，下載後逐檔驗過 |
| 授權 | HF 資料集卡標 MIT。各表格的原始來源（Kaggle、政府開放資料等）各有自己的授權，未逐一查證 |
| 官方計分器 | PyPI `databench-eval` 4.0.1（MIT）。wheel 的 sha256 是 `473638b7e130e7e7…`，`databench_eval/eval.py` 的 sha256 是 `7ee3dd61…`。它的 `default_compare` 與 GitHub `jorses/databench_eval` main 分支上的逐字相同（2026-09-27 核對） |

## 二、選題規則（`build_bank.py::RULE_TEXT`）

- **資格**（522 → 392 題）：
  - 表格轉成 CSV 後 ≤ 2 MB。實際排除 4 個資料集：067_TripAdvisor、068_WorldBank_Awards、070_OpenFoodFacts、079_Coffee，共 130 題。
  - 答案不為空值。
- **分層與順序**：依官方 `type` 分五層。每層用 `random.Random("task-banks-20260927-databench-<type>")` 打亂候選順序。
- **取題**：每層依候選順序取前 6 個「參考解重現得了官方答案」的題。
  - 依序檢查過、但重現不了的只有 1 題，具名排除：`076_NBA#29`「List the 5 players with the least games played」。我們逐列取 GP 最小的 5 列，官方答案是另一組 5 人。
  - 參考解寫法的紀律與 DABench 相同：看題目寫、沒看答案、跑完後不為了對上答案改解讀。
  - 修過兩次程式錯：
    1. `labels_en` 欄其實是字串，不是陣列。這個欄屬於 070 資料集，後來因為大小被排除了。
    2. **把資料從 parquet 改成 CSV 之後，整批重選**（見下一節）。

### ⚠ 為什麼工作區放的是 CSV 不是官方的 parquet（R6）

**觸發探針量出來的問題**：Vacant 認「點名的檔」只看 1–6 個字元的副檔名，而 `.parquet` 有 7 個字元。所以如果照官方給 parquet，資料檔永遠不算被點名，`unread` 在結構上不可能觸發。

第一版（parquet）的探針結果：no_read 劇本 0/30 觸發 `unread`，`materials_named` 裡只有 goal.md 和 contract.md。那一版的報告被後來的重跑蓋掉了，沒有落盤；判準本身寫在 `vacant_network/trace/evidence.py` 的 `Evidence.materials`，也就是正規式 `\.[A-Za-z0-9]{1,6}$`，可以直接讀碼核對。

改法：`all.parquet` 用 pandas 2.2.3 的 `to_csv(index=False, lineterminator="\n")` 轉出 `data/<資料集>.csv`。資格門檻也跟著改成以 CSV 大小計算，候選順序因此整個重排，參考解重新寫、重新重現：50 個候選重現了 48 個。

選中的 30 題（資料夾名 `db_<資料集編號>_<qa 列號>`）：

| 型別 | 題目 |
|---|---|
| boolean | 071_02, 080_04, 076_00, 066_04, 076_06, 072_02 |
| category | 071_12, 066_10, 069_08, 074_11, 073_10, 078_11 |
| number | 072_26, 071_15, 071_19, 080_23, 077_18, 074_13 |
| list[category] | 066_34, 069_29, 075_28, 073_31, 076_31, 078_36 |
| list[number] | 072_30, 074_27, 066_37, 072_33, 072_38, 078_28 |

## 三、工作區形狀

```
templates/db_071_15/                  hidden/db_071_15/
    goal.md       官方 question 逐字＋資料檔路徑    expected.json   answer、type
    contract.md   answer.txt 一行；這題的答案型別與寫法
    data/071_COL.csv
```

`contract.md` 會告訴 agent 這一題的答案型別，以及該怎麼寫：

- boolean 寫 `True` 或 `False`
- 清單用 Python 語法
- 數字截到小數兩位比

SemEval 的參賽系統要自己判斷型別，這裡直接告訴 agent，這是偏差，manifest 有記。

## 四、計分（`score.py`，需要 pandas＋numpy）

`default_compare` 逐字搬自 `databench-eval` 4.0.1，只拿掉 `self`。`gauge_bank.py --official-eval <eval.py>` 會用 AST 比對，確認與官方原始碼相同，本次結果是 `true`。判準摘要：

- boolean：接受 true/yes/y 與 false/no/n。
- number：`trunc(x*100)` 相等，也就是截到小數兩位，不是四捨五入。
- category：字串相等，不相等時再試著當日期比。
- list 類：集合相等而且長度相等，順序不管。

與官方不同的地方：

1. 官方是一行一題的 `predictions.txt`；這裡每題一個 `answer.txt`，取**第一個非空行**。
2. 檔不存在或是空的，算 0 分。
3. 告訴 agent 答案型別（見上一節）。

```bash
python3 score.py --hidden hidden/db_071_15 --workspace /path/to/ws   # {"correct": 0|1, "type": …, "status": …}
```

## 五、量具（零模型呼叫）

`gauge_bank.py`（結果在 `gauge_report.json`）：

| 交件 | 預期 | 結果 |
|---|---|---|
| 參考解 | 1 | **30/30** |
| 官方答案原文 | 1 | **30/30** |
| 答案＋後面幾行說明 | 1 | 30/30 |
| 檔不存在 | 0 | **30/30** |
| 空檔 | 0 | **30/30** |
| 依型別造的錯答案 | 0 | **30/30** |
| 答案只在子資料夾 | 0 | 30/30 |
| `default_compare` 與官方 AST 相同 | 是 | **是** |

錯答案的造法：boolean 反過來、number ×1.5＋1、category 換成不存在的值、清單第一項換掉。

`../common/trigger_probe.py`（結果在 `trigger_probe_report.json`，L-fake）：

| 劇本 | 預期 | 30 題 |
|---|---|---|
| clean | 不退回 | 30/30 沒有任何發現 |
| missing | `missing_output` | 30/30 |
| no_read | `unread` | 30/30；其中 12 題另帶 `unsourced`，就是 number 與 list[number] 兩層。boolean／category 的答案裡沒有數字，所以 `unsourced` 結構上不會觸發 |
| failed_script | `failed_step` | 30/30 |

## 六、在 Colab 上用

- **agent 那一側**只需要 pandas，資料是 CSV。
- **計分端**需要 pandas＋numpy。
- **重新渲染**需要 pandas＋pyarrow（讀 parquet 用）。
- **`hidden/` 與 `reference/` 都不能讓 agent 的使用者讀到**，`reference/reproduction.json` 裡有答案。做法與 DABench 相同：放在 root 擁有、0700 的目錄。
- **答案在 HF 上公開**。agent 若有對外網路，就能直接查到答案。
- **大小**：`templates/` 5.6 MB。同一張表被多題共用，git 只存一份；不重複的 CSV 約 1.8 MB，最大的是 076_NBA 1.27 MB。`hidden/` 120 KB。

## 七、誠實邊界

1. **boolean 有 50% 猜中率**，category 題的選項往往也很少。五個型別要分開報，不可以合成一個數當主要結論（R5）。
2. 我們把資料從 parquet 換成 CSV。CSV 讀回來的欄位型別會跟 parquet 不同，例如 category 會變成字串。有 48/50 的參考解在 CSV 上重現了官方答案，但**這不等於官方答案在所有 CSV 讀法下都成立**。
3. 汙染：測試集的題目在 2025-01 公開，答案之後也上了 HF。比 DABench 新，但不是沒有汙染。
4. 題目都很短，只有一句話，不少題有歧義，例如「best」、「driest」、「highest tier」。參考解選的解讀記在 `reference/solutions.py`。
5. 觸發探針是 L-fake，同 DABench 第七節第 4 點。

## 八、重跑

```bash
V=<有 pandas/pyarrow 的 venv>/bin/python
$V gauge_bank.py --reproduce
$V build_bank.py
python3 build_bank.py --check
$V gauge_bank.py --official-eval <databench_eval-4.0.1 wheel 解出的 databench_eval/eval.py>
<repo>/.venv/bin/python ../common/trigger_probe.py --vacant-src <含 vacant_network/ 的資料夾> --bank databench
```
