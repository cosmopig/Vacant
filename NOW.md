# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1560、2026-11-13、0 model calls）
- 本輪（票 P20261113_0948-1 done、commit 20b5b675e）：D4 凍結規格重用防篡改——`load_frozen_spec` 在 goal/contract hash 檢查後，規格記載 `spec_sha256` 時內容（含 items）被篡改→fail-closed ValueError「spec_sha256 自校驗失敗…拒發」；未綁定（空）＝舊規格、照舊行為。
- 驗收：tests/test_reqloop_g3_frozen_spec.py 6 passed（改前 5＋新負控制 dab_725 items 改 1 字；舊 g3.py 下新測試 FAILED＝漏洞實證）；回歸 86 passed（requirements/freeze_g4_specs/g4_preregistration/g3/g3gate/replay_claims）；2 檔＋25 行。
- 成效門（不變，r1559）：D1 重播 `python3 ops/reqloop/extract/replay_claims.py --gate` → `GATE_CHECK: deterministic=66/76 >= 30 false_pass=0 VERDICT: PASS`。
- 待驗（下條指令）：open/ 2 張（0948-2 g4gate dry-run＋發射控制、0948-3 D1 replay --json）→doing/ 取票照做；輪頭一次讀 CI 三分支。

## 紅線
- 凍結：repair.py 2795 行/blob 5147f8c3…、extract.py 1295 行/blob b502741b…、checks.py 2907 行/blob d401a8ae…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2/g3_3 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- NOW.md ≤3KB；ops/loop/NOW.md 為 symlink、~/dev/ops/NOW.md 為 cp 鏡像。
- 不以文書改動充實進度：本輪實質＝1 個 fail-closed 自校驗＋1 個負控制，全可機械複核。

## 下一步
1. open/ 取下一票（0948-2 或 -3）照票面做；open/ 少於 3 張→規劃者依 11-13 §5 補。
2. 輪頭一次讀 CI 三分支（紅→讀 log 根因不猜；freeze_check 既有紅→上報規劃者、不代修）。
3. 不做 closure-check／結案量具／同步類（11-13 §1）；G4 發射須人類簽核（human_signoff=null）。
