# ops/gain/replay — 離線重放（零 API 呼叫）

這個目錄承重什麼：`runs/*/calls.jsonl` 存了每一通模型呼叫的**完整回覆**，所以任何新的
選擇／聚合機制都可以用歷史上真實產生的候選解重放，不必再花一次機時。
2026-09-03 的機制重做（DECISION_20260903_R440P）就是靠這個做出來的。

紀律（違反＝結果作廢）：
- **選擇只准用 `visible_check`**；`hidden_check` 只用來計分。用 hidden 決定要交哪一份＝作弊。
- **零 API 呼叫**：只讀本機 JSONL＋跑本機沙箱。跑實驗的機器上有 run 在跑時尤其重要。
- 用 runtime 自己的 `extract_code`／`meets_demand`，不要自己重寫判定邏輯。

主要入口：
- `audit_fable_r440p.py <run> [workers]` — 稽核層的獨立重放，五項主張逐條重算
  （無損性、早停、嚴格等預算、池子上限、單抽對照）。R440P 的數字出自這支。
- 其餘檔案是 workflow 各 agent 的分析腳本，保留當證據；`*.jsonl` / `*.json` 是它們的快取。
