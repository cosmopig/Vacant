# T03 — 確認批：34 題 × 5 次＝170 對（S2）

**前提**：T02＝GO。**規模**：0 行碼；340 格，單機約 3 天、兩台約 1.5 天。

## 步驟
1. `python3 ops/redo/redo.py preflight --plan ops/redo/plans/redo1_pi_gemma12b_polyglot34.json` → `PREFLIGHT_OK`
   （含「計畫檔已 commit」）。
2. 發射（MISSION §五的那一段，`ROOT=~/dev/ops/redo_runs/redo1`）。
3. 每一輪最多一次 `status`。runner 不在了（`pgrep -f "^python3 ops/redo/redo.py run"` 沒有、而且 state 還是 INCOMPLETE）
   就用同一行指令再啟動。
4. 出現 `infra_void`：照 MISSION §五處理（修端點 → 刪那一格的目錄 → 再啟動）。每處理一次在票尾記一行（哪一格、為什麼）。

## 驗收
- `status` 顯示 170/170 對，state ∈ {EFFECTIVE, UNRESOLVED, CONTRADICTS}。
- `REPORT.json` 的 `harness_changed_mid_run` 是 false。
- `REPORT.md`／`REPORT.json` 複製到 `ops/redo/results/redo1_REPORT.{md,json}` 並 commit。

## 禁止
- 跑到一半不看數字改計畫；不因為某一格的結果刪格；不改 `redo.py`。
- 等待期間不要找別的事做（見 MISSION §四）。

## 票尾（做完填這三行，再把票移到 done）
- commit：
- 驗收指令的實際輸出（逐字貼最後一行）：
- 沒做完的：
