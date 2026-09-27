# 引用與查證等級（2026-09-27）

[`SURVEY.md`](SURVEY.md) 與三個 pilot README 引用到的出處，逐條列在下面。每一條都標了查證等級，數字與日期以本表記的為準。

- **A**：本次（2026-09-27）直接下載原始檔、程式碼或論文核對過。有 sha256 就記下，對象是當天抓到的位元組；網頁會變，sha256 只證明「當天讀到的是這一份」。
- **B**：三個研究代理讀網頁、論文或 API 得到的，附 URL，**本文沒有逐條重驗**。
- **C**：查不到，或來源自相矛盾，照實寫出。

原始下載物都放在 session scratchpad，沒有進版控。題庫實際用到的上游檔案以各 pilot 的 `bank_manifest.json` 或 `source_*.json` 為準，那些才是釘死的版本。

## 一、零設定 Vacant 的判準（「有效果」的定義來源）

| 出處 | 支持什麼 | 等級 |
|---|---|---|
| `origin/claude/vacant-verification-redesign-jv7eou` @ `f0bfb18107382b4aa4116061c7b0c751431e86f3`：`vacant_network/trace/evidence.py`、`review.py`、`__init__.py`（`__version__ = "0.8.0"`） | 五類退回的觸發條件（SURVEY §二）：`OUTPUT_VERB`／`OUTPUT_PREP`／`FILE_LIKE`、點名檔的副檔名要 1–6 字元、`DOC_EXT`／`CODE_HINT_EXT`、`RUNNERS`、`_failed_steps`。依指示**沒有讀**該分支的 `ops/eval/evidence_20260927_nocap/u274/raw/` | A（`git show`／`git archive`） |
| 同分支 `decisions/DECISION_20260926_ZERO_CONFIG_V3.md` | v3.6「回合預算提醒預設關」；本地 12B 常見失敗是「說做完卻沒寫檔」（§四-3） | A |
| PyPI `vacant-network` | PyPI 上最新是 0.7.0（2026-09-19）。零設定 v3.6.1 不是 PyPI 版號，Colab 裝的輪子要另外確認 | A（PyPI JSON API） |

## 二、pilot 題組（A 為主）

### InfiAgent-DABench

| 出處 | 支持什麼 | 等級 |
|---|---|---|
| https://github.com/InfiAgent/InfiAgent @ `3d6c4a70198e0a41fadf539f5b43c88b8c1a2d9c`，`README.md`（sha256 `0ca9d31d…`） | 程式碼 Apache-2.0、資料 CC BY-NC 4.0（兩個徽章） | A |
| 同 repo `examples/DA-Agent/data/da-dev-questions.jsonl`（`49ae783b…`）、`da-dev-labels.jsonl`（`83b8fb81…`）、`da-dev-tables/`（68 個 CSV，共 60 MB） | 257 題（引用 52 個 CSV，目錄內共 68 個）；easy 82／medium 87／hard 88；92 題有非數值子答案；每個 CSV 的 sha256 記在 `dabench/bank_manifest.json` | A |
| 同 repo `examples/DA-Agent/eval_closed_form.py`（`8c4cbeed…`） | 官方判等：`extract_format`、`is_equal`；沒有回應的題不進分母 | A |
| 同 repo `pipeline/activities/eval.py`（`217d687a…`） | 官方 agent prompt 是 `Question: {question}\n{constraints}\n`，format 只給 reformat 步驟 | A |
| 同 repo `examples/DA-Agent/README.md`、`reformat.py` | 計分前用 GPT-3.5 把回應改成規定格式 | A |
| https://arxiv.org/abs/2401.05507 ；https://proceedings.mlr.press/v235/hu24s.html | ICML 2024；完整集 603 題／124 CSV，公開 dev、封閉 test；標籤由 OpenAI ADA 三次一致產生 | B |
| https://arxiv.org/html/2509.09245 （Jupiter；HTML sha256 `308fc899…`） | 未微調模型在 InfiAgent-DABench 的 Accuracy by Questions：Mistral-7B 2.33、Llama-3.1-8B 48.25、Qwen2.5-7B 43.97、Qwen2.5-14B 69.65；GPT-4o（ReAct）81.32 | A（curl 後逐字找到） |
| https://arxiv.org/html/2509.25084 （DataMind） | Qwen2.5-Coder-7B 15.05、14B 71.21（GPT-4o-mini 判分） | B |

### DataBench／SemEval-2025 Task 8

| 出處 | 支持什麼 | 等級 |
|---|---|---|
| https://huggingface.co/datasets/cardiffnlp/databench @ `e75d53add267d2f9cfa32efd65ad77f0807adfad`，`README.md`（`1bcf676b…`） | config `semeval` 的 test split＝`data/066`–`080`；MIT；每個資料夾有 all／qa／sample.parquet | A |
| 同 repo 30 個 parquet（sha256＝LFS oid，見 `databench/source_files.json`） | 測試集 522 題；型別：number 156、boolean 129、list[number] 91、category 74、list[category] 72 | A（下載後逐檔驗 sha256） |
| https://pypi.org/project/databench-eval/4.0.1/ ：wheel sha256 `473638b7e130e7e732d3f8c2dce246979b6ebeb57eac64394fef643055bfaeef`，`databench_eval/eval.py` sha256 `7ee3dd61…`，LICENSE 為 MIT | 官方 `default_compare`；與 https://github.com/jorses/databench_eval main 分支的 `src/databench_eval/eval.py` 逐字相同 | A |
| https://aclanthology.org/2025.semeval-1.324.pdf （sha256 `554e1dec…`） | Osés Grijalba 等。測試集 522 題／15 個資料集，2025-01-09 釋出。第一名 95.02（TeleAI）。≤9B 開源系統（Table 7）：76.63、68.97、65.64、64.56、43.10，其餘 ≤8.24。baseline 26.00。全部提交平均 55.43（Table 9） | A（pdftotext 核對） |
| LREC-COLING 2024 論文（同 HF repo 的 `Databench-LREC-Coling-2024.pdf`） | DataBench 原始論文 | B |

### Aider Polyglot（Python）

| 出處 | 支持什麼 | 等級 |
|---|---|---|
| https://github.com/Aider-AI/polyglot-benchmark @ `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`，`README.md`（`9a06b876…`） | 題目版權屬 Exercism；來源是 Exercism 各語言 track | A |
| 同 repo `python/exercises/practice/` 的 280 個檔（blob sha1 見 `polyglot_py/source_tree.json`） | 34 題；每題有 `.meta/example.py` 參考解；paasio 有第二個測試檔 `test_utils.py` | A |
| https://github.com/Aider-AI/aider/blob/main/benchmark/benchmark.py （`ba350b7b…`）、`benchmark/prompts.py`（`204ff3b6…`） | instructions 的組法（introduction＋instructions＋append）；只把 solution 檔加進對話；`.py` 用 `pytest`、逾時 180 秒；失敗後回餵測試輸出 | A |
| https://github.com/Aider-AI/aider/blob/main/aider/website/_data/polyglot_leaderboard.yml （`85a50b25…`） | 225 題的 pass_rate_2：gemma-3-27b-it 4.9、gpt-4o-mini 3.6、Qwen2.5-Coder-32B-Instruct 8.0／16.4、Llama 4 Maverick 15.6、Qwen3 32B 40.0 | A |
| https://aider.chat/2024/12/21/polyglot.html | 2024-12-21 發佈；225 題是「7 個模型裡 ≤3 個解得出」的 Exercism 題 | B |
| https://github.com/exercism/python/blob/main/LICENSE | Exercism Python track 為 MIT | B |

## 三、其他候選（B 為主）

| 題組 | 出處 URL | 支持什麼 |
|---|---|---|
| QRData | https://aclanthology.org/2024.findings-acl.548 ；https://github.com/xxxiaol/QRData ；https://arxiv.org/html/2402.17644 | 411 題（選擇 248／數值 163）；CC BY-NC 4.0；`benchmark/eval.py` 數值 ±3%；GPT-4 57.9、隨機基線 23.0、7B 15.8–37.0 |
| DSBench | https://github.com/LiqiangJing/DSBench ；https://arxiv.org/abs/2409.07703 ；https://huggingface.co/datasets/liqiang888/DSBench | ICLR 2025；分析 466／建模 74；`compute_answer.py` 用 gpt-4o 判；343 題為選項字母；Llama3-8B 16.95、GPT-4o 28.11／AutoGen 34.12 |
| DA-Code | https://aclanthology.org/2024.emnlp-main.748/ ；https://github.com/yiyihum/da-code ；https://arxiv.org/html/2410.07331 | 500 題；評分函式分布；容差 1e-2；GPT-4 30.5、Deepseek-Coder-33B 10.8 |
| KramaBench | https://arxiv.org/abs/2506.06541 ；https://github.com/mitdbg/KramaBench | 104 題／1.7 GB；ParaPLUIE 指標；最佳 55.83% |
| DiscoveryBench | https://github.com/allenai/discoverybench ；https://arxiv.org/html/2407.01725 | ICLR 2025；LLM judge（HMS） |
| TableBench | https://github.com/TableBench/TableBench ；https://tablebench.github.io/ ；arXiv 2408.09174 | AAAI 2025；886 題；EM／ROUGE-L |
| DataSciBench | https://github.com/THUDM/DataSciBench ；https://arxiv.org/html/2502.13897 | gated；Gemma-2-9B 12.66 |
| DataSpace | https://github.com/HKUSTDial/DataSpace ；arXiv 2608.03451 | 410 題，公開 gold 只有 60 題；授權兩處不一致（C） |
| InfiniteScienceGym | https://github.com/utahnlp/infinite-science-gym ；https://arxiv.org/abs/2604.13201 | COLM 2026；程序生成、刻意放無法回答的題；Gemma 3 27B 24.2 |
| DABstep | https://huggingface.co/datasets/adyen/DABstep ；https://arxiv.org/abs/2506.23719 | 450 題的答案欄是空的，只能上傳排行榜計分 |
| DAComp／FDABench／DSBC | https://github.com/ByteDance-Seed/DAComp ；https://github.com/fdabench/FDAbench ；https://arxiv.org/html/2507.23336 | 都有 LLM judge 或雲端資料庫依賴 |
| SciCode | https://github.com/scicode-bench/SciCode ；https://arxiv.org/abs/2407.13168 ；https://scicode-bench.github.io/leaderboard/ ；https://artificialanalysis.ai/models/gemma-3-12b | 80／338；test_data.h5 約 1 GB（Google Drive）；Gemma 3 12B 子題 16.4%（AA 網頁內嵌資料） |
| ScienceAgentBench | https://github.com/OSU-NLP-Group/ScienceAgentBench ；https://arxiv.org/html/2410.05080v3 | 102 題，64 題 png 用 GPT-4o 判；2025-01 起推薦容器化評測 |
| MLE-bench | https://github.com/openai/mle-bench ；https://arxiv.org/abs/2410.07095 | lite 22 題／158 GB；要 Kaggle 帳號與 GPU |
| SpreadsheetBench | https://github.com/RUCKBReasoning/SpreadsheetBench ；https://arxiv.org/abs/2406.14991 ；https://shortcut.ai/blog/posts/spreadsheetbench-verified ；https://huggingface.co/datasets/KAKA22/SpreadsheetBench | Verified 400（2025-12）；CC BY-SA 4.0；CodeQwen-7B 0.33 |
| Spider 2.0 | https://github.com/xlang-ai/Spider2 ；https://arxiv.org/abs/2411.07763 ；https://spider2-sql.github.io/ | Lite 的 SQLite 部分 135 題；DBT 題數有 68／69／70 三種說法（C）；Qwen2.5-Coder-32B 5.85 |
| BIRD mini-dev | https://github.com/bird-bench/mini_dev | 500 題；llama3-8b EX 24.40 |
| BIRD-Critic-SQLite | https://huggingface.co/datasets/birdsql/bird-critic-1.0-sqlite ；https://github.com/bird-bench/BIRD-CRITIC-1 | 2026-03；500 題；不需 Docker；sol_sql／test_cases 要寄信取得；Qwen2.5-Coder-7B 27.40、14B 33.60 |
| BIRD-Interact | https://arxiv.org/abs/2510.05318 | LLM 使用者模擬器 |
| CORE-Bench | https://github.com/siegelz/core-bench ；https://arxiv.org/abs/2409.11363 ；https://hal.cs.princeton.edu/corebench_hard | Easy／Medium／Hard 差異；Hard 已被宣布解決 |
| ResearchCodeBench | https://github.com/PatrickHua/ResearchCodeBench ；https://arxiv.org/abs/2506.02314 | 212 片段；環境重 |
| AlgoTune | https://github.com/oripress/AlgoTune ；https://arxiv.org/abs/2507.15887 | 154 題；加速比計分 |
| AppWorld | https://github.com/StonyBrookNLP/appworld ；https://arxiv.org/html/2407.18901 ；https://appworld.dev/appworld/leaderboard.json | 750 題；加密、不得明文轉載；不交檔 |
| LiveBench | https://github.com/LiveBench/LiveBench ；https://arxiv.org/abs/2406.19314 ；https://livebench.ai/table_2024_11_25.csv | HF 上只有舊題；gemma-2-9b-it data_analysis 36.4 |
| GAIA | https://huggingface.co/datasets/gaia-benchmark/GAIA ；https://arxiv.org/abs/2311.12983 ；https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/ | gated、不得以可爬形式轉載；355／466 題要上網；計分器有已知漏洞 |
| HLE | https://arxiv.org/abs/2501.14249 ；https://lastexam.ai/ | o3-mini judge；GPT-4o 2.7% |
| FinanceBench | https://github.com/patronus-ai/financebench ；https://huggingface.co/datasets/PatronusAI/financebench | 開放 150 題；沒有官方自動計分器 |
| OfficeQA | https://github.com/databricks/officeqa ；https://arxiv.org/html/2603.08655v1 | Full 246／Pro 133；`reward.py` 確定性；22% 的題要上網 |
| LAB-Bench | https://github.com/Future-House/LAB-Bench ；https://arxiv.org/abs/2407.10362 | 選擇題；SeqQA 可離線 |
| OfficeBench／SheetCopilot | https://github.com/zlwang-cs/OfficeBench ；https://github.com/BraveGroup/SheetCopilot | 要 Docker／Windows Excel 或 LibreOffice |
| Terminal-Bench 2.0 | https://arxiv.org/abs/2601.11868 ；https://docs.harborframework.com/core-concepts/sandboxes/pre-integrated-sandboxes.md | 一定要容器；Qwen3-8B 約 2.5%（https://arxiv.org/abs/2602.21193 ） |
| WorkBuddy Bench | https://github.com/Tencent/workbuddy-bench ；https://arxiv.org/abs/2607.20911 ；http://workbuddybench.com/ | Office 50 題。結構事實為 **A**：研究代理下載的 `wb-bench-office-v1.0` 壓縮檔，本文直接讀過 `dataset.toml`（created 2026-07-15、50 題、composite verifier）、`task.toml`、`tests/verifier.toml`、`judge.yaml`、`grading/test_verify.py`（寫死 `/workspace`）。授權與成績為 B |
