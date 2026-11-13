# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1554、2026-11-13、0 model calls）
- 本輪實質＝票 P20261113_0708-2（G4-PREREG）done：4 題×3 臂 12 格預註冊實驗包——ops/reqloop/g4/manifest.json（preregistered／approval_required=true／human_signoff=null；4 規格 spec_sha256 釘住）＋ops/reqloop/g4/README.md（假設／sha256 清單／對照設計／核准門禁）＋tests/test_g4_preregistration.py 3 測試（manifest 完整＋規格 hash 吻合含自 hash 重算／signoff=null 發射門 fail-closed＋正控制／dry-run 12 格＋0 model calls）。
- 驗收（本輪新跑）：`python3 -m pytest tests/test_g4_preregistration.py -q`→RC=0（無 -q「3 passed in 0.04s」）；TDD 先紅→綠；回歸 test_freeze_g4_specs 4 passed；commit 3a0227729（3 檔純新增）。
- 未驗證：CI 裁決（輪首 qwen27b 還沒跑完；argon 2 紅／worker 11 紅＝既有 freeze_check／now_redline 系→上報規劃者、不代修）；G4 真發射須人類點頭（本輪 0 發射）。

## 紅線
- 凍結／受控解凍：repair.py／run_eval.py 凍結未動；g25 filing（6 sha256）未動；g3_1/g3_2/g3_3 歷史未改；4 規格自 hash 已被測試釘住。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑 full pytest；0 model calls；未發射實驗。
- NOW.md ≤3KB；ops/loop/NOW.md、ops/STATE.md cp 鏡像 byte-identical。
- 不以文書改動充實進度：本輪實質＝預註冊包（manifest＋README＋3 測試）、全可機械複核。

## 下一步
1. open/ 只剩 1 張（requirementset-hash-integrity）→依 11-13 定案§5 由規劃者補至 ≥3 張；或照票面取下一張。
2. 不再做 closure-check／結案量具／同步類工作（11-13 定案§1）；freeze_check 既有紅→上報規劃者、不代修；本輪新 3 檔 worktree 同步裁決留規劃者。
3. G4 發射流程：人類簽核（填 manifest human_signoff）→重跑測試確認 0 model calls→才可排程發射。
