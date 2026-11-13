# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1574、2026-11-13、0 model calls）
- 本輪（票 P20261113_1307-2 done）：g3 CLI 偵測 experiment=="G4" manifest 自動分派——--dry-run 轉 build_g4_execution_plan 印「G4 DRY-RUN: 12 cells ready (0 model calls)」RC 0（改前「plan schema 不符」RC 1）；--fire 走 run_g4 簽核門未簽核→「G4 FIRE REFUSED: human_signoff is null」RC 2 fail-closed；pi 臂 PiChannel 以 tasks_dir=ops/reqloop/g3_2/tasks 建構（接上 r1573 缺口）；TDD 先紅後綠→mv done/。
- 驗收（全綠）：票面兩條命令 RC=0／RC=2 逐字吻合；63 passed（frozen_spec/g4_prereg/anchors/replay_claims/g3gate）；G3 舊路徑 --dry-run 輸出逐字不變；human_signoff 仍 null；g3.py 41 行≤45、2 檔。

## 紅線
- 凍結：repair.py／extract.py／checks.py／run_eval.py 未改（frozen anchors 綠）；g25 filing；g3 歷史產物未改。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；run_g4 與 CLI 已接線、本輪 0 發射。
- CI：argon 2 紅／worker 11 紅＝既有 freeze_check/now_redline 系（已上報規劃者、不代修；11-13 §1 禁開 sync/mirror 票）。

## 下一步
1. open/ 剩 1 張（P20261113_1307-3 g4gate 任務工作區 hash 守衛）→doing/ 取票照做。
2. open/<3 張→規劃者依 11-13 §5 補票（每張動產品碼 vacant_network/reqloop/ 或 D1 重播器）。
3. 不做 closure-check／closing-gauge／sync 類（11-13 §1 禁止）；G4 發射需人類簽核。
