# 任務導向公開題組調查與 pilot 題庫（2026-09-27）

目的：Colab 上大量跑 A/B，每一格的設定如下。

- **A 組**：只裝 pi 0.87.1。
- **C 組**：pi，加上零設定 Vacant v3.6.1，照真實流程 `pipx install vacant-network` 再 `vacant install`。
- **模型**：gemma-4-12b QAT，vLLM。
- **執行方式**：每一跑是一個獨立 Linux 使用者＋bwrap，交出檔案，由 root 用隱藏答案計分。

這一份回答兩個問題：用哪些公開題組，以及它們在零設定 Vacant 的五類退回上**量不量得到東西**。

- 引用出處見 [`CITATIONS.md`](CITATIONS.md)。
- 三個 pilot 題庫：[`dabench/`](dabench/README.md)、[`databench/`](databench/README.md)、[`polyglot_py/`](polyglot_py/README.md)。
- 共用的觸發探針：[`common/trigger_probe.py`](common/trigger_probe.py)。

## 一、結論

**推薦**（依序；前三個已做成 pilot）：

| # | 題組 | 一句話理由 | pilot |
|---|---|---|---|
| 1 | **InfiAgent-DABench**（ICML 2024） | 「讀 CSV→算數值→交 `@name[value]`」的形狀，剛好同時碰得到 `unread`／`unsourced`／`failed_step`／`missing_output` 四類；計分完全確定性；7–14B 未微調的公開成績是 44–70%（ReAct），但也有 7B 只拿 2.3% 的例子（格式失敗），所以格式要寫清楚 | 30 題 |
| 2 | **DataBench／SemEval-2025 Task 8**（測試集 2025-01） | 同樣的形狀，但更新（SemEval 共同任務背書），有五種答案型別，表格大到不寫程式算不出來；官方計分器是 pip 套件；≤9B 的參賽系統前四名 64–77%，全部提交平均 55.4% | 30 題 |
| 3 | **Aider Polyglot（Python 34 題）** | 唯一「有測試可跑、會宣稱測試通過」的輕量題組，量得到 `test_claim`，而且每題都有官方參考解；缺點是可能落在地板、汙染最高 | 34 題 |
| 4 | WorkBuddy Bench Office（Tencent，2026-07） | 最「任務導向」：讀多個點名附檔、交指定路徑的 xlsx／md／json，五類裡能碰到四類。**沒做成 pilot**：沒有參考產出可當正控制，計分器寫死 `/workspace` 路徑，指令是簡體中文 | 建議下一個 |
| 5 | BIRD-Critic-SQLite（2026-03） | 新、免 Docker、答案扣住；7B／14B 為 27／34%。**要寄信取得解答與測資**，拿不到就不能本機計分 | 需人類寄信 |
| 6 | SciCode（NeurIPS 2024 D&B） | 子題層級 Gemma-3-12B 約 16%；測試集的金標程式碼不公開。代價是要 1 GB 的 h5，還要釘舊版 SciPy | 備選 |

**不推薦**：MLE-bench lite、ScienceAgentBench、GAIA、AppWorld、Terminal-Bench、HLE、DSBench、DiscoveryBench、KramaBench、DABstep（已用過且答案不公開）。理由見第四節。

**一個會影響既有題庫的發現**（第三節 3.2 有細節）：r534、BCB-Hard 這類「附 `run_tests.sh`」的題庫碰上零設定 Vacant，agent **跑了 `sh run_tests.sh`、輸出也顯示全過**，只要說一句「All tests pass.」，就會被退回「紀錄裡沒有跑過任何測試」。另外還會附一條「點名的檔沒打開」，指的是 `tests_visible/test_visible.py`。

這是誤退，要在 Colab A/B 用那些題庫之前先處理。證據等級是 L-fake：劇本 agent、真的掛鉤與病歷，通過輸出是寫死的。

## 二、「有效果」怎麼判：五類退回在結構上需要什麼

判準取自零設定分支 `claude/vacant-verification-redesign-jv7eou` @ `f0bfb181`，檔案是 `vacant_network/trace/evidence.py`、`review.py`（vacant_network 0.8.0；v3.6.1 是零設定規格的版號）。Vacant **不判對錯**，它只看紀錄。每一類都要題目長成某個樣子才可能觸發：

| 類別 | 什麼時候退回 | 題目要長成什麼樣 |
|---|---|---|
| `missing_output` | 人的要求裡有「write/save/output/generate/create/… … to/in/into/as/at `<路徑.副檔名>`」（動詞之後 140 字元內），或有 `output path/file` 標籤；說做完時那個檔不存在 | 要求寫出一個**一開始不存在**的檔，而且用英文句型或繁中「寫入／存到／輸出到／產生」寫出來。簡中「生成」「输出」**認不出來** |
| `unread` | 人的要求裡**單獨點名**的檔（1–6 字元副檔名、檔名無空白、在工作區恰好對到一個檔、沒有整段貼在要求裡），這一回合沒有任何一步提到它 | 題目要點名輸入檔。`.parquet`（7 字元）、有空白的檔名都**點名不到** |
| `unsourced` | 交付物是文件類（.md .txt .csv .tsv .html .rst .tex 或無副檔名）；這一回合新寫的數值或日期，在讀到或算出的東西裡都找不到；是 agent 自己打的；而且任務有點名資料 | 答案要是**數字**，寫在**文字檔**裡。`.json`、`.py`、`.xlsx` 交付物不查 |
| `test_claim` | 最後的訊息說測試通過或 build 成功，但沒跑過 runner、最後一次失敗、或通過之後又改了程式 | 要有測試可跑。runner 只認 `pytest`、`python -m unittest/pytest`、`tox`、`npm test`、`go test`、`cargo test` 等；`sh run_tests.sh` **不算** |
| `failed_step` | agent 自己寫的腳本，或讀給定資料的指令失敗了（Traceback／Error:／Exception:），之後仍寫了交付物、沒再成功跑過同一件事，最後的訊息也沒提 | 需要寫腳本處理資料的任務 |

⇒ **最對味的是「點名資料檔＋要算出數值＋交文字答案檔」的資料分析題**，四類都碰得到。再搭配一個「有測試」的程式題補 `test_claim`。只交一個選項字母的題、或 LLM 評分的題（DSBench 七成是選擇題）量不到 `unsourced`；不交檔的題（AppWorld）連 `missing_output` 都量不到。

## 三、三個 pilot 的量具結果

### 3.1 計分器量具（零模型呼叫）

| pilot | 題數 | 正控制（已知正確⇒滿分） | 負控制（空檔／沒交／錯答案⇒0） | 參考解來源 |
|---|---|---|---|---|
| DABench | 30（easy/medium/hard 各 10） | 參考解 30/30、標準答案 30/30 | 沒交 30/30、空檔 30/30、全錯 30/30、只對第一項 13/13、放錯資料夾 30/30 | 我們照限制獨立寫；39 個候選重現 35 個，3 題因標準答案與限制矛盾具名排除 |
| DataBench | 30（五型別各 6） | 參考解 30/30、官方答案 30/30 | 沒交、空檔、錯答案、放錯資料夾各 30/30；計分器與官方 AST 相同 | 我們依題意獨立寫；50 個候選重現 48 個，排除 1 題 |
| Polyglot-Py | 34 | 官方參考解 34/34（unittest 與 pytest 判定一致） | stub、沒交、空檔、語法錯、竄改工作區測試檔各 34/34 | Exercism 官方 `example.py` |

### 3.2 觸發探針（`common/trigger_probe.py`，L-fake）

每一步都走**真的** `adapters.hook.handle`，病歷是真的簽章鏈，最後由 `evidence_for` 取發現。prompt 形狀照 r534 的 `TASK_MESSAGE`。

| pilot | clean（照規矩做） | missing | no_read | failed_script | test_claim 劇本 |
|---|---|---|---|---|---|
| DABench | **30/30 不退回** | 30/30 `missing_output` | 30/30 `unread`（＋30/30 `unsourced`） | 30/30 `failed_step` | — |
| DataBench | **30/30 不退回** | 30/30 | 30/30 `unread`（＋數值兩型 12/12 `unsourced`） | 30/30 | — |
| Polyglot-Py | **34/34 不退回** | 34/34 | — | 34/34 | 沒跑就宣稱 34/34、跑失敗仍宣稱 34/34 |

施工時抓到四件事，前三件已修進題庫，第四件影響既有題庫：

1. **DataBench 原本是 parquet**（探針量到）：`unread` 0/30 觸發，因為副檔名有 7 個字元。已改成 CSV，並整批重選。
2. **`python3 -m unittest two_bucket_test`（模組名、沒有 `.py`）不算點名測試檔**（讀判準碼發現）⇒ 正確的解也會被推回「測試檔沒打開」。contract 已改成 `python3 -m unittest two_bucket_test.py`，unittest 接受檔案路徑；改完後 clean 劇本用的就是這個寫法，34/34 不退回。
3. **paasio 的 `test_utils.py`**（探針量到）：它在檔案清單裡被點名，只跑主測試檔不打開它，就會被推回。這是 Vacant 的規則，題庫沒有改，README 裡寫明；clean 劇本改成先讀全部測試檔。
4. **r534 形狀的 `sh run_tests.sh`**：我們用 r534 的 `lcb_3522` 樣板，讓劇本 agent 寫一個解、跑 `sh run_tests.sh`，輸出設為「0 check(s) failed」，再說「All tests pass.」。零設定 Vacant 回的是：
   - `test_claim`（sub=`none`：沒跑過測試）
   - `unread tests_visible/test_visible.py`

   換成 `python3 -m pytest -q tests_visible` 就沒有 `test_claim`，但會多一條 `unread run_tests.sh`。
   - 腳本與結果：[`common/runtests_sh_probe.py`](common/runtests_sh_probe.py)、`common/runtests_sh_probe_report.json`。
   - 兩個指令都沒有真的執行，輸出是寫死的通過字樣；量的是 Vacant 對「指令文字＋輸出」的判讀。

**探針的誠實邊界**：它只證明「這些題的形狀讓機制觸發得到、照規矩做不會被誤退」。它**不證明**真模型會犯這些錯、不證明退回之後會改對，也沒量到 pi 的事件正規化那一層，因為劇本用的是 Claude 的掛鉤格式。**Colab 的 harness 若不是把 goal.md／contract.md 全文貼進 prompt，要用 `--prompt-template` 重跑探針。**

### 3.3 需要的套件與資料大小

| pilot | agent 那一側 | 計分端 | 重新渲染／量具 | 題庫大小（templates／hidden） |
|---|---|---|---|---|
| DABench | pandas、numpy、scipy（scikit-learn 可選） | python3 標準函式庫 | 參考解重現要 pandas、scipy | 2.0 MB／120 KB |
| DataBench | pandas | pandas＋numpy | pandas＋pyarrow | 5.6 MB（不重複約 1.8 MB）／120 KB |
| Polyglot-Py | python3（pytest 可選） | python3 標準函式庫（要用沙箱包起來） | pytest | 560 KB／404 KB（＋reference 136 KB） |
| 觸發探針 | — | — | cryptography＋零設定分支的 vacant_network | — |

三個題庫的**答案都在網路上公開**：DABench 在 GitHub、DataBench 在 HF、Exercism 解答到處都有。agent 若有對外網路，就可能直接查到答案。另外，`hidden/` 與 `reference/` 都等於答案，必須放在 agent 的使用者讀不到的地方：`reference/reproduction.json` 裡有參考解的輸出，Polyglot 的 `reference/` 就是官方解。bwrap 以唯讀掛整個根目錄時，放在 repo 裡照樣讀得到。最省事的做法是讓 agent 的沙箱**看不到整個 repo**，只把 `templates/<id>/` 複製進工作區。

## 四、比較表

欄位說明：

- **免 Docker**：pip 環境就能跑。
- **觸發**：五類裡結構上碰得到的。M＝missing_output、R＝unread、S＝unsourced、T＝test_claim、F＝failed_step。括號表示要改寫交件形式才碰得到。
- **12B 估計**：我們的推估，依據是鄰近規模模型的公開成績。**沒有任何題組公開過 gemma-4-12b 的成績。**
- **token**：題目本身的量，不含 agent 迴圈。

事實出處見 CITATIONS.md。「A」是本次下載原始檔核對過的；其餘是研究代理讀網頁或論文得到的，附 URL，未逐條重驗。

### 4.1 資料分析

| 題組 | 出處／日期 | 題數 | 授權 | 免 Docker | 自動計分 | 交付物 | 觸發 | 12B 估計 | 每題 token | 汙染 | 判定 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **InfiAgent-DABench** | ICML 2024；arXiv 2401.05507 | 公開 dev 257 題（引用 52 個 CSV）；test 封閉（A） | 程式 Apache-2.0、資料 CC BY-NC 4.0（A） | ✓ pandas/scipy | 確定性：`@name[value]` 字串相等或 float 差<1e-6（A）；官方另有 GPT-3.5 改格式步驟，可省 | 答案字串（可寫進 txt） | M R S F | 30–70%（未微調 ReAct：Qwen2.5-7B 44.0、Llama-3.1-8B 48.3、Qwen2.5-14B 69.7；Mistral-7B 只有 2.3%）（A） | 題目約 300；CSV 中位數 56 KB | 高（2024-01 起答案在 GitHub） | **pilot** |
| **DataBench／SemEval-2025 T8** | LREC-COLING 2024＋SemEval 2025 | test 522 題／15 表（2025-01） | HF MIT（A）；表格來源各異 | ✓ pandas | 確定性：`databench_eval` 4.0.1（A） | 一行答案 | M R S(數值題) F | 40–75%（≤9B 系統前四名 64–77，另一半 <10%；全部提交平均 55.4；baseline 26.0）（A） | 題目約 130；表格 40–240k 列 | 中（答案已上 HF） | **pilot** |
| QRData | ACL Findings 2024 | 411（選擇 248、數值 163） | CC BY-NC 4.0 | ✓ | 確定性：數值 ±3%、選擇題前綴比對 | 答案字串 | M R S(數值題) F | 未知；舊 7B 15–37%，隨機基線 23% | 約 130＋CSV | 高 | 備選（只取 163 題數值題） |
| DSBench（分析 466） | ICLR 2025 | 466＋建模 74 | 程式 MIT；資料限非商業、ModelOff 題目有版權 | ✓（分析部分 8 MB） | **LLM judge（gpt-4o）**；343 題是單一選項字母 | 選項／數值 | M R (S 很少) | 15–25%（Llama3-8B 17） | 導言平均約 750 詞 | 高 | 不選：LLM 判、七成選擇題 |
| DA-Code | EMNLP 2024 | 500 | 程式 MIT；資料來源未聲明 | 評分端 ✓，官方 agent 要 Docker | 確定性（csv/ml/image/text 比對，容差 1e-2） | **指定檔名的檔**（result.csv…） | M R F (S 看交付物) | 地板風險（33B 10.8%） | 平均 5.7 個檔 | 中（gold 在公開雲端硬碟） | 備選：形式最對味但可能地板 |
| KramaBench | arXiv 2506.06541（MIT） | 104 題、1.7 GB data lake | 未標明 | ✓ | 部分用 LLM 指標 | 答案 | R S F | 地板（GPT-4o 1.6–8.3%） | 大 | 中 | 不選 |
| DiscoveryBench | ICLR 2025 | 264＋903 | ODC-BY | ✓ | **LLM judge** | 自然語言假說 | — | — | — | 中 | 不選 |
| TableBench | AAAI 2025 | 886 | 程式 MIT、資料 Apache-2.0 | ✓ | EM／EM±10%／ROUGE-L（一部分是連續分數） | 「Final Answer:」字串 | 表格內嵌⇒(R S) 要改寫 | 20–55% | 約 1 KB | 高 | 不選：不是讀檔題 |
| DataSciBench | arXiv 2502.13897 | 222 | HF gated（自動核准） | 需要 MetaGPT；dl 類要 GPU | 多數確定性；視覺化用 VLM judge；GT 半自動 | 指定檔名 | M R F | 約 13%（Gemma-2-9B 12.66） | — | 中 | 不選 |
| DataSpace | KDD Cup 2026；arXiv 2608.03451 | 410（公開 gold 僅 60） | MIT／CC BY 4.0（兩處不一致） | ✓ | 確定性表格比對 | CSV 檔 | M R F | 未知 | 大（含 PDF／影片） | 低 | 觀察 |
| InfiniteScienceGym | COLM 2026；arXiv 2604.13201 | 程序生成（評測集 500） | MIT | 出題要跑 HF 模型（GPU） | 確定性；**刻意放了無法回答的題**，量「編數字」 | 答案 | R S F | 約 24%（Gemma-3-27B 24.2） | — | 無（換 seed 就是新題） | 值得跟進：最貼近 `unsourced` |
| DABstep | arXiv 2506.23719 | 450 | CC BY 4.0 | ✓ | 確定性，但**答案不公開** | 短答 | — | hard 地板 | — | 低 | 使用者已排除 |

### 4.2 程式／科學／工程

| 題組 | 出處／日期 | 題數 | 授權 | 免 Docker | 自動計分 | 交付物 | 觸發 | 12B 估計 | 每題 token | 汙染 | 判定 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Aider Polyglot（Py）** | aider.chat 2024-12 | 34（全集 225） | Exercism MIT（A） | ✓ | 確定性：測試全過（A：benchmark.py） | 改好的 .py | M T F R(測試檔) | 5–25%（全集 pass_rate_2：gemma-3-27b 4.9、gpt-4o-mini 3.6、Qwen2.5-Coder-32B 8.0–16.4）（A） | 題目＋stub 中位數約 785；測試約 1.2k | **最高** | **pilot**（地板風險） |
| SciCode | NeurIPS 2024 D&B | 80 主題／338 子題（test 65/288） | Apache-2.0 | ✓（numpy/scipy/sympy/h5py，要釘舊 SciPy） | 確定性：數值 target（h5 1 GB） | 函式 .py | T F M | 子題約 16%（Gemma-3-12B，AA） | 1.5k–6k | 中低（test 金標不公開） | 備選 |
| ScienceAgentBench | ICLR 2025 | 102 | 程式 MIT、題目多為 CC BY 4.0 | 官方推薦 Docker；重型領域套件 | 64 題 png 要 **GPT-4o judge** | 程式＋輸出檔 | M F | 地板 | 約 425＋資料 | 中 | 不選 |
| MLE-bench lite | ICLR 2025 | 22 競賽 | MIT；資料依 Kaggle 規則 | ✓ 但 158 GB、要 Kaggle 帳號、GPU、24 h | 確定性（獎牌門檻） | submission.csv | M F | 地板 | — | 中 | 不選 |
| SpreadsheetBench Verified | NeurIPS 2024 D&B；Verified 2025-12 | 400 | CC BY-SA 4.0 | ✓ openpyxl＋LibreOffice（重算公式） | 確定性逐格比對 | 修改後的 .xlsx | M R F | 地板風險（2024 小模型約 0–3%） | 約 120＋試算表 | 中高（golden 公開） | 備選：先試 10 題 |
| Spider 2.0-lite（SQLite 135） | ICLR 2025 | 135＋DBT 68 | MIT | ✓（435 MB） | 確定性（結果表比對） | .sql／.csv | M R F | 地板（Qwen2.5-Coder-32B 在 Lite 5.85%） | 約 270＋schema | 高（gold 公開） | 不選 |
| BIRD mini-dev | 2024 | 500 | CC BY-SA 4.0 | ✓（801 MB） | EX | SQL | M F | 25–35%（Llama3-8B 24.4） | — | 高 | 備選 |
| **BIRD-Critic-SQLite** | 2026-03 | 500 | 資料 CC BY-SA、程式 MIT | ✓（官方明言不用 Docker；DB 1.8 GB） | 確定性測試函式 | 修正後 SQL | M F T | 27–34%（Qwen2.5-Coder-7B/14B） | 約 1.1k 字元 | 低（答案扣住） | **需寄信取得答案** |
| CORE-Bench | 2024（TMLR 2025） | 270 | MIT | Easy ✓（資訊抽取）；Medium 要 Docker | 確定性（95% 區間） | report.json | M R | Hard 已飽和 | capsule 最大 10 GB | 中 | 不選 |
| ResearchCodeBench | NeurIPS 2025 D&B | 212 片段 | CC BY-SA 4.0 | ✓ 但 conda 環境很重 | 單元測試 | .py 片段 | T F | 約 10% | 整篇論文 | 高 | 不選 |
| AlgoTune | NeurIPS 2025 | 154 | MIT | ✓ | 有效性確定、主分數是加速比（有計時噪音） | solver.py | T F | 未知 | — | 中 | 不選 |

### 4.3 通用 agent／辦公

| 題組 | 出處／日期 | 題數 | 授權 | 免 Docker | 自動計分 | 交付物 | 觸發 | 12B 估計 | 汙染 | 判定 |
|---|---|---|---|---|---|---|---|---|---|---|
| **WorkBuddy Bench Office** | Tencent；arXiv 2607.20911（2026-07） | 50（本次看過壓縮檔：dataset.toml 2026-07-15、50 題） | Tencent License（排除歐盟） | 官方用 Docker，但 Office 題只需 python:3.12＋pytest/openpyxl/pandas | composite：`eval_core` 確定性檢查＋`judge.yaml` LLM rubric；只取前者就是確定性 | 指定路徑的 xlsx／md／json | M R S(md/txt) F | 未知；可取原子檢查通過率當連續分數 | 低（2026-07；但 gold 在壓縮檔裡） | **建議下一個**（見第五節） |
| AppWorld | ACL 2024 | 750 | Apache-2.0＋加密、禁止明文轉載 | ✓（pip） | 確定性狀態測試 | **不交檔**（改 API 狀態） | F | 約 5%（Qwen3-8B） | 低 | 不選 |
| LiveBench（data_analysis） | ICLR 2025 | 公開 150（2024 舊題） | Apache-2.0 | ✓ | 確定性 | 回覆文字（表格內嵌） | (M R S) 要改寫 | 35–45%（Gemma-2-9B 36.4） | 高（公開題是舊題；新題不公開） | 不選 |
| GAIA | ICLR 2024 | 466（val 165） | gated、不得以可爬形式轉載 | ✓ | quasi-exact（有已知漏洞） | 短答 | R S | 離線地板；76% 題要上網 | 高 | 不選 |
| HLE | 2025 | 2,500 | MIT、gated | ✓ | o3-mini 當 judge | 答案 | — | 地板 | 中 | 不選 |
| OfficeQA | Databricks 2025-12 | Full 246／Pro 133 | 資料 CC BY-SA、程式 Apache | ✓（語料 460 MB+） | 確定性 reward.py | 數值答案 | R S F | Pro 地板；Full easy 題待試 | 低（gated） | 觀察：22% 題要上網 |
| FinanceBench | 2023 | 開放 150 | CC BY-NC | ✓（PDF 705 MB） | **沒有官方自動計分** | 文字 | R S | — | 高 | 不選 |
| LAB-Bench（SeqQA） | 2024 | 600 公開 | CC BY-SA | ✓ | 選擇題 | 選項 | — | — | 中 | 不選：不交檔 |
| OfficeBench／SheetCopilot | 2024／2023 | 300／221 | Apache／GPL | ✗ Docker／Windows Excel 或 LibreOffice | 規則檢查 | 檔 | M R | — | 中 | 不選 |
| Terminal-Bench 2.0 | ICLR 2026 | 89 | — | ✗ 一定要容器 | pytest | 環境狀態 | T F | 約 2.5%（Qwen3-8B） | 中 | 不選 |

## 五、下一步建議（依效益排序）

1. **先在 Colab 上各跑一小批 pilot**，每題 A／C 各 1–2 跑，看三件事：12B 的成功率有沒有落在 15–85% 之間、C 組實際觸發了哪幾類、有沒有誤退。Polyglot 若接近 0，下一步是加一層**非 Polyglot 的 Exercism Python 題**：同一套計分器、同一個授權，難度較低，另外抽樣分層報。
2. **WorkBuddy Bench Office**：50 題裡大約 24 題的輸入全是 csv/xlsx/md/json、輸出在 `output/` 底下，不含 PDF、docx、pptx、mock 服務，可以先做這一批。要處理三件事：
   - 每題的參考產出要從 `gold_answer.json` 手工組出來，才能做正控制。
   - `eval_core.py` 寫死 `/workspace` 路徑。Colab 上可以用 bwrap `--bind <ws> /workspace` 解決，Mac 上做不到。
   - contract 要另外用英文寫出「Write … to `output/xxx.xlsx`」，否則 `missing_output` 認不出簡中的「生成」。
3. **BIRD-Critic-SQLite**：需要人類寄信到 bird.bench25@gmail.com 取得解答與測資。拿到之後，它是「新＋答案扣住＋12B 落在中段」的最佳 SQL 題組。
4. **InfiniteScienceGym**：刻意放了「無法回答」的題，可以直接量「編數字」，也就是 `unsourced` 的目標行為。出題要在 GPU 上跑 Qwen3-4B，Colab 有 GPU，可以就地生成。
5. **r534／BCB 題庫的 `run_tests.sh` 誤退**：在 Colab 用它們之前，二擇一：
   - contract 改成叫 agent 跑 `python3 -m pytest -q tests_visible/test_visible.py`，並把 run_tests.sh 移出工作區。
   - 在 Vacant 那一側把 `sh run_tests.sh` 認成 runner，這是改產品碼，要另開裁決。

## 六、誠實邊界（整份）

1. **12B 估計全是推估。** 沒有任何題組公開過 gemma-4-12b（不思考）的成績；估計依據是鄰近規模模型，而且多數是不同的 agent 框架。
2. 比較表裡標 A 的欄位，是本次直接下載原始檔或程式碼核對過的；其餘來自三個研究代理讀的網頁或論文，每條都附 URL（CITATIONS.md），**未由本文逐條重驗**。會改變推薦的幾條已經重驗：DABench 的授權與計分碼、DataBench 的測試集範圍與計分碼、Polyglot 的 34 題、stub、測試跑法。
3. 三個 pilot 都是 20–40 題的**試跑規模**，用來看地板、天花板與機制觸發，**不是**用來做檢定的題庫。題數與分層都是為了這個目的選的。
4. 三個題組的答案都公開在網路上；12B 的訓練資料可能看過 DABench 與 Exercism，DataBench 測試集比較新但不能排除。
5. pilot 的所有改寫（stub 移到 contract、parquet 轉 CSV、只收數值題、告訴 agent 答案型別）都記在各自 manifest 的 `deviations_from_official` 或 `selection_rule` 裡。**數字不可與原排行榜互引。**
