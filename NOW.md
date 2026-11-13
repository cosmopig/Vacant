# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1568、2026-11-13、0 model calls）
- 本輪（票 P20261113_1100-2 done）：g4gate dry-run 加規格可確定性檢查守衛——每題規格 0 條可檢查＝全空殼→ValueError fail-closed（逐條缺陷：unknown_verifier／參數缺陷／交付物＝輸入檔）；cells 加 n_checkable（725=4/6、587=5/5、657=8/8、517=5/6）；負控制三類全 fail-closed（重算 spec_sha256、守衛在可檢查性非 hash 觸發）。
- 驗收（全綠）：pytest tests/test_g4_preregistration.py→4 passed；`python3 -m vacant_network.reqloop.g4gate --dry-run`→「G4 DRY-RUN: 12 cells ready (0 model calls)」RC=0；--fire 未簽核 RC=2；回歸 12 檔 228 passed（含 frozen anchors）。
- DECISION：拒發條件＝「每題 0 條可檢查」而非「任一條目缺參」——凍規 dab_725 4/6、dab_517 5/6 含永久 UNKNOWN 條目仍可满足（r1565/r1566 正負控制已證）；逐條硬拒會與票面驗收 RC=0 衝突。個別缺陷計入 n_checkable 與 fail 訊息。
- 成效門（不變）：`replay_claims.py --gate`→deterministic=66/76 >= 30 false_pass=0 VERDICT: PASS。

## 紅線
- 凍結：repair.py／extract.py／checks.py／run_eval.py 全未改（frozen anchors 綠）；g25 filing；g3 歷史未動；g26 歷史報告未改。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；發射管線未接線、另一步授權。
- CI：argon 2 紅／worker 11 紅＝既有 freeze_check/now_redline 系（已上報規劃者、不代修）。

## 下一步
1. open/ 剩 1 張（P20261113_1100-3 g3 load_frozen_spec 可檢查性過濾）→doing/ 取票照做。
2. open/<3 張→規劃者依 11-13 §5 補票（每張動產品碼或 D1 重播器）。
3. 不做 closure-check／結案量具／同步類（11-13 §1）；G4 發射須人類簽核。
