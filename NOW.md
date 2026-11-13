# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1566、2026-11-13、0 model calls）
- 本輪（票 P20261113_1100-1 done）：G4-SPEC params 補齊收尾——freeze_specs.py `_ITEM_FIXES` 為 25 條全注入 params（answer_kv keys／tag_format tag／kv_recomputed mean_col・median_col・std_col・pearson＋data_file），4 份凍結規格重生＋manifest spec_sha256 同步＋可檢查性測試（錯誤答案→FAIL≥1、0 假 PASS）。功能 r1565（輪尾超時）已實作（8fc2dcb7e），本輪完成驗收＋簿記。
- 驗收（全綠）：`freeze_specs.py --check`→4 題 OK RC=0；test_freeze_g4_specs 5 passed；test_g4_preregistration 3 passed；回歸 75 passed（含 frozen anchors）。
- 獨立驗證：負控制 wrong_answer→4 題 FAIL≥1、PASS 0；正控制正確值（657 mean/median/std Close=4349.27/3599.77/4113.51、517 pearson=-0.55，stdlib 獨立重算）→值條目全 PASS，規格可满足。
- 成效門（不變）：`replay_claims.py --gate`→deterministic=66/76 >= 30 false_pass=0 VERDICT: PASS。

## 紅線
- 凍結：repair.py blob 5147f8c3…／extract.py／checks.py／run_eval.py 全未改（frozen anchors 5 passed）；g25 filing；g3_1/g3_2/g3_3 歷史未動；g26 歷史報告未改。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；g4gate 核准後發射管線未接線、另一步授權。
- CI：argon 2 紅／worker 11 紅＝既有 freeze_check/now_redline 系（已上報規劃者、不代修）。

## 下一步
1. open/ 剩 2 張（P20261113_1100-2 g4gate dry-run 可檢查性守衛、1100-3 g3 load_frozen_spec 可檢查性過濾）→doing/ 取票照做。
2. open/<3 張→規劃者依 11-13 §5 補票（每張動產品碼或 D1 重播器）。
3. 不做 closure-check／結案量具／同步類（11-13 §1）；G4 發射須人類簽核。
