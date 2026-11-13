# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1559、2026-11-13、0 model calls）
- 本輪（票 P20261113_0846-3 done、commit 1b3e3f334）：D1 重播 `--gate` 成效門補齊票面剩餘缺口。主體由 argon 57bb13d7d 實作（輪首核實已綠）；本輪補：負控制 (a) 錯交付物檔名必判 `deliverable_not_in_request`、(b) 輸入檔當交付物必判 `deliverable_is_input_file`（reason 碼斷言）、(c) 未知 verifier 必判 `unknown_verifier`（gate 內新增、4 任務 dab_725/587/657/517 各跑）＋票面同義名 `run_gate_check`＋`test_replay_claims_gate_flag`（CLI `main(["--gate"])` 輸出斷言）。
- 驗收：`python3 ops/reqloop/extract/replay_claims.py --gate` → `GATE_CHECK: deterministic=66/76 >= 30 false_pass=0 VERDICT: PASS`（RC=0）；tests/test_replay_claims.py 9 passed（含既有假-PASS→exit1 負控制）；2 檔 +24/-6。
- 待驗（下條指令）：open/ 空→規劃者依 11-13 §5 補票（每張動 reqloop 產品碼或 D1 重播器）；輪頭一次讀 CI 三分支（qwen27b 輪首「還沒跑完」；argon/worker 紅＝既有 freeze_check/now_redline 系、已上報規劃者不代修）。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2/g3_3 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- NOW.md ≤3KB；ops/loop/NOW.md 與 ~/dev/ops/NOW.md 皆為 cp 鏡像。
- 不以文書改動充實進度：本輪實質＝gate 內 3 類負控制 reason 碼斷言＋1 測試、全可機械複核。

## 下一步
1. open/ 空→規劃者補票（11-13 §5：少於 3 張就補、每次 ≤4 張、每張動 vacant_network/reqloop/ 或 D1 重播器）。
2. 輪頭一次讀 CI 三分支（紅→讀 log 根因不猜；freeze_check 既有紅→上報規劃者、不代修）。
3. 不做 closure-check／結案量具／同步類（11-13 §1）；G4 發射須人類簽核（human_signoff=null）。
