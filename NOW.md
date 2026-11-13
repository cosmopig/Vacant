# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1557、2026-11-13、0 model calls）
- 本輪（票 P20261113_0846-1 done，commit 86af7ce4a）：`g3.load_frozen_spec` 雙格式相容——巢狀（`reqset`）與扁平（`items` 在根＝RequirementSet.load() 原生／G4 規格）；goal/contract_sha256 根優先、reqset 兜底、皆無 fail-closed。新增正控制（4 份真實 G4 規格 dab_725/587/657/517 載入成功、條目數 6/5/8/6 對 g4 manifest）＋負控制（扁平 goal_sha256 篡改 1 碼→ValueError）。
- 驗收：tests/test_reqloop_g3_frozen_spec.py 5 passed；g3/g4/regression 81 passed。票面「4 passed」為計數差（既有 3＋新 2），已記票尾。
- 待驗（下條指令）：下輪開 open/ 下一票；輪頭一次讀 CI 三分支（argon 2 紅／worker 11 紅＝既有 freeze_check/now_redline 系，已上報規劃者）。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2/g3_3 歷史未動；4 規格自 hash 已被測試釘住。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- NOW.md ≤3KB；ops/loop/NOW.md cp 鏡像 byte-identical。
- 不以文書改動充實進度：本輪實質＝load_frozen_spec 雙格式＋2 測試、全可機械複核。

## 下一步
1. open/ 2 張：P20261113_0846-2（RequirementSet spec_sha 完整性）、P20261113_0846-3（D1 replay gate CLI）→doing/ 取下一票照做。
2. 輪頭一次讀 CI 三分支（紅→讀 log 根因不猜；freeze_check 既有紅上報規劃者、不代修）。
3. 不做 closure-check／結案量具／同步類（11-13 §1）；G4 發射須人類簽核（human_signoff=null）。

（MEMORY 上限 6 KB、NOW 上限 3 KB；超過的部分沒有附上，請先把它縮短）
