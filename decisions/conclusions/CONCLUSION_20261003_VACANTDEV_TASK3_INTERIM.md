# 期中結論：任務導向 94 題 × 零設定 v3.7，在 vacant-dev＋1003／1004（LM Studio GGUF）上（第 1、2 次）

預註冊：`decisions/prereg/PREREG_20261002_VACANTDEV_REPLICATION_V37.md`。紀錄：`ops/vacantdev_replication_20261002/RUNLOG.md`；
分析輸出 `ops/vacantdev_replication_20261002/results/report_t3L_s12.json`（凍結的 `analyze_task3.py`，只餵第 1、2 次的格子）。
**期中**：第 3 次的 186 格 void（10-02 1003 的 llama-server 記憶體耗盡崩潰期間）排在 DABstep 之後補跑，補完再出最終版。

| | 答對（第 1＋2 次） | 
|---|---|
| A（沒裝） | 119／188 |
| C37（照常安裝 v3.7） | 124／188 |

- 主要檢定（每題平均，dab_657 第 2 次補跑仍 void ⇒ 兩組拿掉）：+2.7 個百分點，C37 好 14 題、A 好 11 題，**p＝0.37 ⇒ 沒有量到差別**。
- 分題庫：DABench 90.0%→93.3%、DataBench 71.7%→73.3%、Polyglot 33.8%→36.8%。兩台分開：g1003 A 58／92、C37 66／92；g1004 A 61／95、C37 58／95。
- 機制：A 組「說做完卻沒寫答案檔」**0 格**（A 沒交的全是撞 1800 秒時限）；C37 只退回 2 格。⇒ 在這個後端，Vacant 在 Colab 補到的那種情況幾乎不發生。
- 和 Colab 任務導向（72.3% vs 75.0%，p＝0.36）同方向、同結論。

能說：「換到 GGUF＋LM Studio 後端，任務導向 94 題照常安裝 v3.7 與沒裝仍然沒有量到差別（期中，第 1、2 次）。」
不能說：最終結論（第 3 次還沒補）；把它和 DABstep 混講。
