# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1553、2026-11-13、0 model calls）
- 本輪實質＝票 P20261113_0708-1（G4-SPEC）done：4 題 dab_725／dab_587／dab_657／dab_517 凍結需求規格落盤——ops/reqloop/extract/freeze_specs.py（讀 g26_claim_replay.json＋g3_2 workspace：選 deterministic＋有存驗證原語；共 25 條 6+5+8+6；交付物全為非輸入檔 answer.txt）＋ops/reqloop/g4/specs/4 份（task_id／goal_sha256／contract_sha256／items＋spec_sha256 自 hash）＋tests/test_freeze_g4_specs.py 4 測試（load／workspace hash 吻合／≥10 條 deterministic／負控制 4 全紅）。
- 驗收（本輪新跑）：`python3 -m pytest tests/test_freeze_g4_specs.py -q`→RC=0（無 -q 複跑「4 passed in 0.07s」）；`freeze_specs.py --check`→4/4 OK；相關回歸 74 passed（g3 系＋replay、舊行為未改）；commit 7e6a52d02（6 檔純新增）。
- 未驗證：CI 完成裁決（輪首 qwen27b 還沒跑完→下輪頭三分支一次讀、不 poll）；freeze_check 8 紅＝既有（stash 複驗同紅、GUARD_CONTENT_PIN 過時、源自 D4 票 g3.py 改動、非本票引入、未代修）；成效門（11-13 定案 ≥30/76）最終裁決屬人類（現況 K1=66/76 已達、K0=14/76）；G4 發射須人類點頭。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、run_eval.py 332cd324…（凍結未動）；extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob 764119e2…（受控解凍、只加法）；g25 filing（6 sha256）；g3_1/g3_2/g3_3 歷史未改。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑 full pytest；0 model calls；未發射實驗。
- NOW.md ≤3KB；ops/loop/NOW.md、ops/STATE.md cp 鏡像 byte-identical。
- 不以文書改動充實進度：本輪實質＝新工具＋4 規格＋4 測試＋票結案、全可機械複核。

## 下一步
1. 照 tickets/qwen/open/ 做（2 張：g4-preregistration／requirementset-hash-integrity，照票面取下一張；open/ 不足 3 張由規劃者補）。
2. 不再做任何 closure-check／結案量具／同步類工作（11-13 定案）；freeze_check 8 紅屬既有→上報規劃者、不代修；in-scope diff 6 檔同步裁決留規劃者。
3. G4 發射前須人類點頭。
