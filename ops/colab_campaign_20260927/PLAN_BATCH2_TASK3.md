# 第二批（任務導向三題庫）的施工計畫

> 寫給執行的 agent。主線（Opus）規劃、Sonnet 施工（2026-09-26 人類：規劃好後用 sonnet 去做）。
> 第一批（五組程式題庫，前綴 `c5`）正在 Colab G4 上跑；這一批等第一批收完才發射。**不要碰 Colab。**

## 目標

把任務題庫 agent 做好的三個 pilot 題庫（分支 `worktree-agent-a60e6be4976f52c82` @ `027a6a16`，
`ops/vacantrun/task_banks_20260927/{dabench,databench,polyglot_py}`）轉成 Colab 執行器吃的**題目目錄**格式，
驗證計分器，產出 staged 目錄與 plan。

## 執行器吃的格式（`ops/colab_campaign_20260927/cell.sh`，不准改 cell.sh）

每題一個目錄 `<staged>/<bank>/<id>/`：
- `instruction.txt`：給 pi 的**那一句**（整題的唯一輸入）。**預設用第一批同一句**：
  `Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.`
  ——若某題庫的交付物不是單一檔、或 goal／contract 的檔名不同，要改就改工作區檔名去配合這一句，不要改這一句；真的不行就停下來回報。
- `workspace/`：agent 看得到的全部檔案（會被複製到 `/app`，agent 的 cwd 就是 `/app`）。**不准**有答案、參考解、reproduction、hidden 的任何東西。
- `hidden/`：計分要的答案（只在計分那一步出現，由另一個新使用者在圍牆裡讀）。
- `scorer.py`：`python3 scorer.py <hidden 目錄> <最後的工作區目錄>`，stdout **最後一行**是一個 JSON 物件，至少有 `"pass": true|false`
  （這一題算不算做對），另外放題庫自己的欄位（例如 `score`、`note`）。沒交檔 ⇒ `pass: false`、`note` 寫原因、**不准丟例外沒輸出**
  （沒輸出＝那一格被判 infra_void）。只能用標準函式庫，或 Colab 系統 python 3.13 裡本來就有的 pandas／numpy（DataBench 需要時）。
  計分時的 cwd 不固定、沒有網路保證；逾時 900 秒（整支），polyglot 會執行 agent 的程式 ⇒ 每個測試檔另設時限（照第一批 `scorers/code_suite.py` 的做法：
  一個測試檔一個行程、60 秒、RLIMIT_AS 2 GB）。

## 要做的事

1. 讀三個題庫各自的 README、builder、scorer、gauge、manifest，以及 `SURVEY.md` 第「發現與注意事項」節（特別是：prompt 形狀、`.parquet` 不算點名、`python3 -m unittest foo_test` 不帶 `.py`）。
2. 寫 `ops/colab_campaign_20260927/stage_task_bank.py`：一個題庫 → staged 目錄＋印出 plan 的 tasks 陣列（`{"bank","id","dir":"/srv/eval/staged/<bank>/<id>"}`）。
   bank 名用 `dabench`、`databench`、`polyglot_py`（不要有連字號）。id 只能有 `[A-Za-z0-9_.]`。
3. 每個題庫各自的 `scorers/<bank>.py`（照原題庫計分器的判等**逐字**搬，寫明出處）；staged 時複製成 `scorer.py`。
4. **量具**（在這台 Mac 上，用 scratchpad 的 venv；不動 repo 依賴）：對每一題，把參考答案／參考解放進一份工作區副本 ⇒ 跑 staged 的 scorer.py ⇒ 必須 `pass: true`；
   空工作區（沒交）、空檔、錯答案、stub ⇒ 必須 `pass: false` 而且有輸出 JSON。結果寫 `ops/colab_campaign_20260927/task3_gauge.json`（每題每種輸入一列）。
   任何一題過不了 ⇒ 具名排除、寫原因，不要安靜丟掉。
5. **觸發探針用我們這一句重跑**：任務題庫 agent 的 `common/trigger_probe.py` 有 `--prompt-template`；用上面那一句重跑，報告 Vacant 五類在這個 prompt 形狀下各觸發得到幾題
   （他原本的結果假設 r534 的 prompt 形狀）。
6. 掃描 staged：工作區裡沒有任何 hidden／reference／reproduction 的檔、沒有答案字串（至少對 DABench／DataBench 的標準答案逐題 grep）。
7. 產出：staged 目錄放 `/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/0ea239a6-ec82-4ca5-89a9-d4a11558d16e/scratchpad/deploy_task3/staged`，
   `plan_task3.json`（`{"seed": 20260929, "arms": ["A","C361"], "samples": [1], "tasks": […]}`）放同一層；agent 那一側需要的 python 套件清單寫進 README。
8. 在你的 worktree commit（繁中訊息，結尾兩行 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 與
   `Claude-Session: https://claude.ai/code/session_01L4jGpNdwDCwezsShEASrW7`），**不要 push**。題庫原始檔若是私有的（答案），不要 commit 答案進 repo——照任務題庫 agent 的做法。

## 回報

分支、sha、每個題庫可用題數／排除數與原因、量具結果（正控制幾／幾、負控制幾／幾）、觸發探針結果（五類各幾題）、staged 總大小、agent 端需要的套件。
