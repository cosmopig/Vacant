# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1569、2026-11-13、0 model calls）
- 本輪（票 P20261113_1100-3 done）：g3 `load_frozen_spec` 條目可檢查性守衛——空規格或全空殼（0/N 可確定性檢查）→ValueError fail-closed 拒發（口徑同 g4gate 1100-2：unverified／未知 verifier／參數缺陷）；寧拒不空轉：全 UNKNOWN 的規格發射只是無意義修復輪。
- 驗收（全綠）：pytest tests/test_reqloop_g3_frozen_spec.py→7 passed（RC 0）；回歸 8 檔 90 passed（含 frozen anchors）；g4gate --dry-run 12 cells ready RC=0。commit d39d9019a。
- DECISION：原正控制為全 unverified 規格、新守衛下依法即空殼須拒——正控制補 1 條可確定性檢查條目（tag_format、tag＝任務首個必要答案項、假通道答案必 PASS 不觸發修復輪）維持「合法規格正常載入」語義；負控制兩情形（空條目／全 unverified）合併 1 測滿足票面 7 passed。
- 效果門（不變）：replay_claims.py --gate → deterministic=66/76 ≥ 30，false_pass=0，VERDICT: PASS。

## 紅線
- 凍結：repair.py／extract.py／checks.py／run_eval.py 未改（frozen anchors 綠）；g25 filing；g3 歷史產物未改。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；發射管線未接線，另一步授權。
- CI：argon 2 紅／worker 11 紅＝既有 freeze_check/now_redline 系（已上報規劃者、不代修；11-13 §1 禁開 sync/mirror 票）。

## 下一步
1. open/ 3 張新票（P20261113_1206-1 g4gate 執行計畫矩陣／1206-2 g3 run_g4 管線分派／1206-3 d1 replay 驗證凍結規格）→doing/ 取票照做（11-13 §5：每張動產品碼或 D1 重播器）。
2. 不做 closure-check／closing-gauge／sync 類（11-13 §1 禁止）；G4 發射需人類簽核。
