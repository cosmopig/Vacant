# InfiAgent-DABench pilot 題庫（30 題）

這一份講**題目**：從哪裡來、選了哪些、長什麼樣、怎麼計分、量具量到什麼。Colab 的跑法不在這裡。
為什麼選這個題組、跟其他候選怎麼比，見 [`../SURVEY.md`](../SURVEY.md)。

## 一、來源（釘死）

| 項目 | 值 |
|---|---|
| 題組 | InfiAgent-DABench，closed-form validation 集（ICML 2024，arXiv 2401.05507） |
| 上游 | `InfiAgent/InfiAgent` @ `3d6c4a70198e0a41fadf539f5b43c88b8c1a2d9c`，`examples/DA-Agent/data/` |
| 題目檔 | `da-dev-questions.jsonl` sha256 `49ae783b…6f06126`（257 題） |
| 答案檔 | `da-dev-labels.jsonl` sha256 `83b8fb81…a5b18c2` |
| 授權 | 程式碼 Apache-2.0、**資料 CC BY-NC 4.0**（上游 README 兩個徽章）。本題庫是非商業用途；轉載要附出處 |

sha256 對不上，`build_bank.py` 就停下來，不會換成別的版本。每個 CSV 的 sha256 記在 `bank_manifest.json`。

## 二、選題規則（逐字在 `build_bank.py::RULE_TEXT`，manifest 記它的 sha256）

- **資格**（257 → 159 題）：
  - 每個子答案都是數值：排除 90 題。原因是零設定 Vacant 的 `unsourced` 只查數值和日期，字串答案它看不到；另外官方判等對字串分大小寫，雜訊大。
  - 官方正規式抽得回來：排除 1 題（id 273，標準答案是 `[`）。
  - 資料檔名沒有空白：排除 6 題。Vacant 以空白切詞來認「點名的檔」，檔名有空白就點名不到。
  - 資料檔 ≤ 1 MB：排除 1 題。
  - 標準答案的項目名出現在題目的格式欄裡：這一條沒有排除任何題。
- **分層與順序**：依官方 `level` 分 easy／medium／hard 三層。每層用 `random.Random("task-banks-20260927-dabench-<level>")` 打亂，得到候選順序。
- **取題**：每層依候選順序，取前 10 個「參考解重現得了標準答案」的題。依序檢查過、但重現不了的 3 題具名排除：

  | id | 層 | 參考解 vs 標準答案 | 可能的原因 |
  |---|---|---|---|
  | 8 | medium | 標準差 80.64 vs **80.86** | 限制寫明用母體標準差，標準答案卻是樣本標準差 |
  | 521 | hard | accuracy 0.76 vs **0.78** | 缺值處理方式沒寫清楚 |
  | 619 | hard | 標準差 2513.69 vs **2514.65** | 限制寫「numpy 內建」（ddof=0），標準答案看起來是 ddof=1 |

  「可能的原因」是我們的推測。**寫參考解時沒看標準答案，跑完之後也沒有為了對上答案改解讀**（紀律寫在 `reference/solutions.py` 開頭）。只修過一次程式錯誤：id 587／588 的 CSV 欄名尾端有空白，第一次跑出 KeyError，修正已記在函式 docstring。

選中的 30 題：

- easy：427, 57, 507, 218, 657, 517, 129, 55, 216, 666
- medium：426, 105, 721, 588, 35, 176, 688, 514, 250, 587
- hard：144, 725, 723, 378, 732, 39, 665, 249, 724, 669

資料夾名稱是 `dab_<id 三位數>`。

## 三、工作區形狀

```
templates/dab_427/                   hidden/dab_427/
    goal.md       題目＋限制＋答案格式        expected.json   標準答案（common_answers）
    contract.md   交件規格
    data/cost_data_with_errors.csv   官方 CSV，逐位元組
```

- `goal.md` 由官方的 `question`、`constraints`、`format` 三個欄位逐字組成，最後一行寫資料檔路徑。
- `contract.md` 規定三件事：
  1. 答案寫進工作區根目錄的 `answer.txt`，每行一個 `@name[value]`。
  2. 列出題目格式要求的全部項目名。有些項目不計分，例如 id 144 的兩個字串項也照列。
  3. 說明判等規則。
- `hidden/` 是**另一棵樹**，不在工作區裡。

**prompt 的形狀會決定機制觸發得到觸發不到**，下面是 `../common/trigger_probe.py` 量出來的結果。

- 用 r534 的 `TASK_MESSAGE`（goal＋contract 全文＋檔案清單）時：
  - `contract.md` 的「Write your final answer to `answer.txt`」會被 Vacant 認成「要求寫出的檔」。
  - `data/<file>.csv` 會被認成「點名的檔」。
  - goal.md／contract.md 整段貼在 prompt 裡，所以不會被當成「沒打開」。
- Colab 的 harness 如果**不貼全文、只叫 agent 去讀 goal.md**，這三件事都會變，要用 `--prompt-template` 重跑探針。

## 四、計分（`score.py`，只用標準函式庫）

- 判準逐字搬自官方 `eval_closed_form.py`：
  - `extract_format`：用正規式 `@(\w+)\[(.*?)\]` 抽項目，同名的取最後一個。
  - `is_equal`：字串完全相等，或兩邊都是數字且差 < 1e-6。
- **主指標 ABQ**：一題裡每個計分項都對，這題才算 1。
- **次指標 PSAQ**：判對的項目比例。

與官方不同的地方（manifest 的 `scoring.deviations_from_official` 逐條記）：

1. 官方在計分前用 GPT-3.5 把回應改寫成規定格式；這裡沒有這一步，agent 必須自己照格式寫。
2. `answer.txt` 不存在、是空的、或抽不到項目，都算 0 分，**而且留在分母**。官方會把沒有回應的題拿出分母。
3. 官方 agent 的 prompt 只有 `Question: …\n{constraints}`，format 只給改寫步驟用；這裡把 format 放進 goal.md。

```bash
python3 score.py --hidden hidden/dab_427 --workspace /path/to/ws     # 一行 JSON：abq、psaq、status…
```

## 五、量具（零模型呼叫）

`gauge_bank.py`（`gauge_report.json`）逐題量了 8 種交件：

| 交件 | 預期 | 結果 |
|---|---|---|
| 參考解的輸出 | 滿分 | **30/30** |
| 標準答案原文 | 滿分 | **30/30** |
| 夾雜說明文字 | 滿分 | 30/30 |
| 檔不存在 | 0 | **30/30** |
| 空檔 | 0 | **30/30** |
| 每個值都改錯 | 0（ABQ 與 PSAQ 都是 0） | **30/30** |
| 只有第一項對（多項題） | ABQ 0 | 13/13 |
| 答案放在子資料夾 | 0 | 30/30 |
| 樣板裡出現標準答案字面值 | 無 | 無 |

參考解重現：檢查了 39 個候選，重現 35 個，排除的 3 題見第二節；hard 層的 id 453 也重現不了，但選到 669 時已經取滿，用不到它。

`../common/trigger_probe.py`（`trigger_probe_report.json`，L-fake，vacant_network 0.8.0＝零設定分支 `f0bfb181`）：

| 劇本 | 預期 | 30 題 |
|---|---|---|
| clean（讀資料、印出值、寫檔） | 不退回 | 30/30 沒有任何發現 |
| missing（沒寫檔就說做完） | `missing_output` | 30/30 |
| no_read（沒打開資料就寫編的數） | `unread` | 30/30，另外 30/30 還帶 `unsourced` |
| failed_script（自己的腳本報錯仍交編的數） | `failed_step` | 30/30，其中 12 題另帶 `unsourced` |

## 六、在 Colab 上用

- agent 那一側要能 `import pandas, numpy, scipy`。scikit-learn 在選中的題裡用不到，但 agent 可能會想用；statsmodels 不需要。計分端只要 python3。
- **`hidden/` 與 `reference/` 都不能讓 agent 的使用者讀到。** `reference/reproduction.json` 裡有參考解算出的答案。bwrap 以唯讀方式掛整個根目錄時，放在 repo 裡的這兩個資料夾一樣看得到。請把它們搬到 root 擁有、權限 0700 的目錄，並用 agent 的使用者試一次 `cat`，確認讀不到。
- **答案在 GitHub 上公開**（上游 repo）。agent 如果有對外網路，就能直接查到答案。這是汙染面，跑之前請確認 agent 的網路政策。
- 題庫大小：`templates/` 2.0 MB（30 個 CSV，中位數 56 KB、最大 292 KB），`hidden/` 120 KB。

## 七、誠實邊界

1. **只收數值題** ⇒ 題庫偏向「算一個數」。DABench 原本有 36% 的子答案是字串或分類，這 30 題不代表整個 DABench，數字也不可以跟 DABench 論文或排行榜互引。
2. 參考解重現只證明**存在一個**照限制做的解會得到標準答案，不證明限制只有一種合理解讀。標準答案本身是上游用 OpenAI ADA 三次一致產生的（研究代理讀論文得知，未重驗），不是人工逐題算的。
3. 汙染：dev 集的題目和答案從 2024-01 起就在 GitHub 上，12B 模型可能看過。
4. 觸發探針是 L-fake：它證明機制在這個形狀上**觸發得到**、照規矩做**不會被誤退**。它不證明真模型會犯這些錯，也不證明退回之後會改對。

## 八、重跑

```bash
V=<有 pandas/scipy 的 venv>/bin/python
$V gauge_bank.py --reproduce        # 參考解重現 → reference/reproduction.json
python3 build_bank.py               # 渲染（會下載上游固定 commit 的檔，快取在 ~/.cache/vacant_task_banks）
python3 build_bank.py --check       # 驗磁碟與 manifest 沒漂
python3 gauge_bank.py               # 計分器量具
<repo>/.venv/bin/python ../common/trigger_probe.py --vacant-src <含 vacant_network/ 的資料夾> --bank dabench
```
