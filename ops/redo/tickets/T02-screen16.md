# T02 — 篩選：16 題 × 1 次（S1）

**前提**：T01 done。**規模**：0 行碼；32 格，單機約 6–8 小時。

## 步驟
1. `python3 ops/redo/redo.py preflight --plan ops/redo/plans/screen16_pi_gemma12b.json` → `PREFLIGHT_OK`。
2. 發射（同 MISSION §五，`ROOT=~/dev/ops/redo_runs/screen16`，計畫檔 `screen16_pi_gemma12b.json`）。
3. 之後每一輪最多一次 `python3 ops/redo/redo.py status --root ~/dev/ops/redo_runs/screen16`，寫一行進 NOW.md，結束那一輪。
4. 16 對跑完：`report`，把 `REPORT.md` 複製成 `ops/redo/results/screen16_REPORT.md`、`REPORT.json` 複製成
   `ops/redo/results/screen16_REPORT.json`，commit。

## 判定（計畫檔 `prereg.go_rule`，逐字）
- **GO**：`treatment_only_c ≥ control_only_b + 3`，而且 R3 的 `accepted_but_wrong == 0` ⇒ 做 T03。
- **NO-GO**：其餘 ⇒ 不做 T03。把報告原樣寫進 `decisions/conclusions/CONCLUSION_<日期>_REDO_SCREEN16.md`
  （數字＋「篩選沒有通過，原生 agent 上沒有看到離線估計的那個量級」），回報人類，這條線停。

## 禁止
- 這 16 題是看過結果挑的：這一批的數字**不可以**當成效果寫進任何對外的檔。
- NO-GO 之後不准改條件重篩。

## 票尾（做完填這三行，再把票移到 done）
- commit：
- 驗收指令的實際輸出（逐字貼最後一行）：
- 沒做完的：
