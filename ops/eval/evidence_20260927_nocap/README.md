# 不設回合上限的缺檔退回（2026-09-27）

裁決：`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §十一；產品：v3.6（提醒預設關，`decisions/DECISION_20260926_ZERO_CONFIG_V3.md` §十）。

- `stage0/`：正式批次（15 回合上限）的離線分析——「說做完卻沒有答案檔」有多少、C 組真的缺檔退回之後怎樣（`output.txt`、每一跑 `rows.json`）。
- `s36nc/`：S36 的 36 題、不設上限、A 對 v3.6、每題 2 次。`raw/`＝每 2 小時歸檔的原始資料（`MANIFEST.jsonl` 每包的 sha256、內容）；
  `progress.jsonl`、`driver*.log`＝驅動紀錄（每次覆蓋成最新）。
