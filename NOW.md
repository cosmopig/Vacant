# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1570、2026-11-13、0 model calls）
- 本輪（票 P20261113_1206-1 done）：g4gate 加 `build_g4_execution_plan`——g4_dry_run 通過後逐題驗 `ops/reqloop/g3_2/tasks/<task>/workspace/{goal.md,contract.md}` 齊備，組裝 12 格（task_id/arm/workspace/spec_file/n_checkable）；缺檔→ValueError fail-closed；CLI `--plan` JSON 印出 RC 0。
- 驗收（全綠）：pytest tests/test_g4_preregistration.py→5 passed（改前 4）；--dry-run「12 cells ready (0 model calls)」RC=0；--plan JSON RC=0；--fire 未簽核 RC=2；回歸 9 檔 115 passed（含 frozen anchors）；純加法 2 檔 +65/-0；human_signoff 仍 null。commit cb38cc438。
- 效果門（不變）：replay_claims.py --gate → deterministic=66/76 ≥ 30，false_pass=0，VERDICT: PASS。

## 紅線
- 凍結：repair.py／extract.py／checks.py／run_eval.py 未改（frozen anchors 綠）；g25 filing；g3 歷史產物未改。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；發射管線未接線，另一步授權。
- CI：argon 2 紅／worker 11 紅＝既有 freeze_check/now_redline 系（已上報規劃者、不代修；11-13 §1 禁開 sync/mirror 票）。

## 下一步
1. open/ 剩 2 張（P20261113_1206-2 g3 run_g4 管線分派／1206-3 d1 replay 驗證凍結規格）→doing/ 取票照做（11-13 §5：每張動產品碼或 D1 重播器）。
2. open/<3 張→規劃者依 11-13 §5 補票。
3. 不做 closure-check／closing-gauge／sync 類（11-13 §1 禁止）；G4 發射需人類簽核。
（MEMORY 上限 6 KB、NOW 上限 3 KB；超過的部分沒有附上，請先把它縮短）
