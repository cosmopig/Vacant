# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1587、2026-11-13、0 model calls）
- 本輪（票 P20261113_1708-1 done）：D4 g3.run_g4 接入 specs.load_frozen_specs 統一核驗口。decide_g4_launch 之後、任何 cell 之前逐檔對 manifest 4 題規格檔做 spec_sha256 密碼學核驗（fail-closed SpecIntegrityError、0 模型呼叫、無部分結果）；TDD 先紅後綠。
- 驗收（全綠、本輪新跑）：票面 1 passed（-q RC0）；g3_frozen_spec 11 passed；frozen_specs/anchors/g4_prereg 16 passed；g3gate+g3 65 passed；CLI --dry-run RC0／--fire RC2；git diff 2 檔 36+/1−。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、run_eval.py 1298 行／blob b6d2f37f…（仍凍結）；extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…（受控解凍、只加法、預設＝舊行為）；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射；1708-1 接線已完成（run_g4 統一核驗口），1507-2 接線已完成（g4gate 統一核驗口）。
- CI：輪首 qwen 還沒跑完；argon 2 紅／worker 11 紅＝既有、已上報、不代修。

## 下一步
1. open/ 1 張（1708-2 D1 missing-param 守衛）<3→規劃者依 11-13 §5 補票（每張動產品碼或 D1 重播器）；doing/ 空→取票照做。
2. G4 發射需人類簽核；不做 closure-check／結案量具類（11-13 §1 禁止）。
3. 達成效門（≥30/76 確定性＋負控制 0 假 PASS）前不發新真模型實驗。
