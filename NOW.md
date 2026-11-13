# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1561、2026-11-13、0 model calls）
- 本輪（票 P20261113_0948-2 done、commit 530ca359e）：G4 預註冊離線檢驗＋發射門控制封裝為產品模組 `vacant_network/reqloop/g4gate.py`——`load_g4_manifest`（schema／4 題×3 臂×12 格／規格檔路徑）、`g4_dry_run`（複用 `RequirementSet.verify_self_hash` 核 4 份凍結規格自 hash＋manifest↔規格一致，fail-closed）、`decide_g4_launch`（`human_signoff is None`→`LaunchRefused`）、CLI `--dry-run` RC0／`--fire` 未簽核 RC2（0 model calls）。測試改由產品模組引入。
- 驗收：`python3 -m vacant_network.reqloop.g4gate --dry-run`→`G4 DRY-RUN: 12 cells ready (0 model calls)` RC=0；`--fire`→`G4 FIRE REFUSED: human_signoff is null` RC=2；tests/test_g4_preregistration.py 3 passed；回歸 86 passed；負控制（cells 篡改／hash 不符／未簽核）全拒。
- 成效門（不變，r1559）：D1 重播 `python3 ops/reqloop/extract/replay_claims.py --gate` → `GATE_CHECK: deterministic=66/76 >= 30 false_pass=0 VERDICT: PASS`。
- 待驗：open/ 剩 1 張（0948-3 D1 replay --json）；open/<3 張→規劃者依 11-13 §5 補票。

## 紅線
- 凍結：repair.py 2795 行/blob 5147f8c3…、extract.py 1295 行/blob b502741b…、checks.py 2907 行/blob d401a8ae…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2/g3_3 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；g4gate 核准後發射管線未接線、另一步授權。
- 不以文書改動充實進度：本輪實質＝1 個產品模組（4 API＋CLI）＋測試改引產品模組，全可機械複核。

## 下一步
1. 取 open/ 下一票（0948-3 D1 replay --json）照票面做；open/<3 張→規劃者依 11-13 §5 補（每張動產品碼或 D1 重播器）。
2. 輪頭一次讀 CI 三分支（紅→讀 log 根因不猜；freeze_check 既有紅→上報規劃者、不代修）。
3. 不做 closure-check／結案量具／同步類（11-13 §1）；G4 發射須人類簽核（human_signoff=null）。
