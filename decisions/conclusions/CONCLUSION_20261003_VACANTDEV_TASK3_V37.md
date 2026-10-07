# 結論：任務導向 94 題 × 零設定 v3.7，在 vacant-dev＋1003／1004（LM Studio GGUF）上（最終版，第 1–3 次）

預註冊：`decisions/prereg/PREREG_20261002_VACANTDEV_REPLICATION_V37.md`；同題的 Colab 批次：`CONCLUSION_20261002_COLAB_TASK3_V37.md`。
紀錄：`ops/vacantdev_replication_20261002/RUNLOG.md`；分析輸出 `results/report_t3L_final.json`（凍結的 `analyze_task3.py`）。
原始紀錄：`~/Vacant_colab_raw/vacantdev_replication_20261002/`（147 個 chunk，sha256 全部驗過）。本檔取代 10-03 的期中版（同檔名改名，git 歷史可查）。

## 一、跑了什麼

- 94 題（DABench 30、DataBench 30、Polyglot Python 34）× A／C37 × 3 次＝564 格；每格 1800 秒、不設回合上限、`pi --print`。
- 10-02 18:27 起 1003 的 `llama-server.exe` 記憶體耗盡崩潰 ⇒ 238 格 void ⇒ 補跑一次：第 2 次的 25 單位在 10-03 早上補完（可行性規則在 40 格時誤擋，見 RUNLOG）；
  第 3 次的 186 格在 d37L 之後補完（那一輪照紀錄停掉 feasibility）。補跑期間 1003 又崩潰 2 次，`keep_gemma.sh` 自動重載，沒有留下 void。
- 最後 void：`dab_657` 第 2 次（補跑一次仍 void）⇒ 照預註冊兩組拿掉。它之後被佇列額外又跑了一次，**那次不採用**。
- 安裝失敗 0；逾時 A 68、C37 56（大多是 Polyglot）。

## 二、預註冊的檢定

| | 答對（第 1／2／3 次） | 合計 |
|---|---|---|
| A（沒裝） | 58／61／68 | 187 |
| C37（照常安裝 v3.7） | 63／61／62 | 186 |

**主要檢定**：每題平均差 **−0.4 個百分點**，C37 好 14 題、A 好 14 題，Wilcoxon（常態近似）**p＝0.87 ⇒ 沒有量到差別**。
分題庫：DABench 91.1%→92.2%、DataBench 75.6%→72.2%、Polyglot 37.3%→38.2%。

## 三、機制

- A 組「說做完卻沒寫答案檔」：**0 格**（DABench／DataBench；A 沒交的全是撞時限）。Vacant 在 Colab 補到的那種情況，這個後端下不發生。
- C37 退回 4 格（`unsourced` 3、`test_claim/failed` 1），之後答對 3。**傷害 0**：唯一最後沒過的（`pg_go_counting` 第 1 次），退回前的版本用計分器驗過，本來就只過 5／11（agent 說測試通過、最後一次跑其實失敗——退回是對的，只是它沒修好）。

## 四、和 Colab 放在一起

| | Colab（vLLM，每格 1200 秒、2 次） | GGUF（每格 1800 秒、3 次） |
|---|---|---|
| A → C37 | 72.3% → 75.0%（p＝0.36） | 66.3% → 66.0%（p＝0.87） |
| A「說做完沒寫檔」 | 5／120 | 0 |

✅「任務導向 94 題、不設回合上限：照常安裝 v3.7 在兩個推論引擎上都沒有量到差別；Vacant 把對的改成錯 0 次。」
❌「Vacant 沒有用」；❌ 把 DABstep 的結果外推到這裡。
