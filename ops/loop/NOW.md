# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1572、2026-11-13、0 model calls）
- 本輪（票 P20261113_1206-3 done）：D1 重播器 `ops/reqloop/extract/replay_claims.py` 加 `verify_frozen_specs`＋`--verify-specs`——4 題 G4 凍結規格（dab_725/587/657/517）spec_sha256 自校驗＋22 條 checkable 條目逐條正控制（必 PASS）／負控制（錯值，必非 PASS），0 假 PASS→PASS；輸出 `FROZEN_SPECS: 4 tasks, 22 checkable, 0 false_pass VERDICT: PASS` RC=0；2 新測（正路徑＋篡改 spec 負控制）12 passed。
- 成效門（不變）：`python3 ops/reqloop/extract/replay_claims.py --gate`→`GATE_CHECK: deterministic=66/76 >= 30 false_pass=0 VERDICT: PASS`。
- G4 狀態：run_g4 已接線但 0 發射；真發射仍須人類簽核（human_signoff=null）。
- open/＋doing/ 皆空→規劃者依 11-13 §5 補票（每張動產品碼 vacant_network/reqloop/ 或 D1 重播器，<3 張要補）。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2/g3_3 歷史未動；g26 歷史報告（g26_claim_replay.json）本輪被背景迴圈重生成一次，已還原未 commit。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- 不以文書改動充實進度：本輪實質＝verify_frozen_specs＋--verify-specs（2 檔＋131/−0、2 新測），全可機械複核。

## 下一步
1. open/＋doing/ 空→規劃者依 11-13 §5 補票（每張動產品碼 vacant_network/reqloop/ 或 D1 重播器）。
2. 輪頭一次讀 CI 三分支（紅→讀 log 根因不猜；freeze_check 既有紅→上報規劃者、不代修）。
3. 不做 closure-check／結案量具／同步類（11-13 §1）；G4 發射須人類簽核（human_signoff=null）。
