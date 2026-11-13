# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1571、2026-11-13、0 model calls）
- 本輪（票 P20261113_1206-2 收口 done）：g3.py::run_g4 發射入口＋兩測已於 2dfe7b74d（r1570 auto-commit）在樹；本輪全面驗收綠→票尾結果→mv done/（doing/ 清空）。
- 驗收（全綠）：pytest tests/test_reqloop_g3_frozen_spec.py -k test_run_g4→2 passed；回歸 19＋80 passed（含 frozen anchors）；g4gate --dry-run RC=0（12 cells ready）／--fire RC=2；human_signoff 仍 null。
- 效果門（不變）：replay_claims.py --gate → deterministic=66/76 ≥ 30，false_pass=0，VERDICT: PASS。

## 紅線
- 凍結：repair.py／extract.py／checks.py／run_eval.py 未改（frozen anchors 綠）；g25 filing；g3 歷史產物未改。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；run_g4 已接線但本輪 0 發射。
- CI：argon 2 紅／worker 11 紅＝既有 freeze_check/now_redline 系（已上報規劃者、不代修；11-13 §1 禁開 sync/mirror 票）。

## 下一步
1. open/ 剩 1 張（P20261113_1206-3 d1 replay 驗證凍結規格）→doing/ 取票照做（11-13 §5：每張動產品碼或 D1 重播器）。
2. open/<3 張→規劃者依 11-13 §5 補票。
3. 不做 closure-check／closing-gauge／sync 類（11-13 §1 禁止）；G4 發射需人類簽核。
