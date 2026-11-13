# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1555、2026-11-13、0 model calls）
- 本輪實質＝票 P20261113_0746-1（RequirementSet hash integrity）done：vacant_network/reqloop/requirements.py 新增 `goal_sha256`／`contract_sha256` 可選欄位（預設 ""、to_dict 非空才輸出、from_dict 向下相容）＋`verify_task_hash(task_dir)` 校驗（未綁定→(False,"unbound")；缺檔／hash 不符→(False,"mismatch: ...")；皆吻合→(True,"OK")）＋tests/test_reqloop_requirements.py 4 測試（1 正控＋3 負控：goal 篡改 1 字元／contract 缺檔／舊規格未綁定）。
- 驗收（本輪新跑）：`python3 -m pytest tests/test_reqloop_requirements.py`→"4 passed in 0.06s"（TDD 先紅 4 failed→綠）；回歸 test_freeze_g4_specs＋test_replay_claims＋test_reqloop_g3＋test_reqloop_g3gate→75 passed（舊行為未改、g4 規格 load 正常）；舊規格 to_dict 欄位集合不變（SANITY_OK）。commit da3f59ee2（2 檔、93 行純新增）。
- 未驗證：CI 裁決（輪首 qwen27b 未跑完；argon 2 紅／worker 11 紅＝既有 freeze_check／now_redline 系→上報規劃者、不代修）；G4 真發射須人類簽核（human_signoff=null、0 發射）。
- 票務：done/ 已收本票；doing/ 空、open/ 空→依 11-13 定案§5 待規劃者補票（≥3 張）。

## 紅線
- 凍結／受控解凍：repair.py／run_eval.py 凍結未動；g25 filing（6 sha256）未動；g3_1/g3_2/g3_3 歷史未改；4 規格自 hash 已被測試釘住。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑 full pytest；0 model calls；未發射實驗。
- NOW.md ≤3KB；ops/loop/NOW.md、ops/STATE.md cp 鏡像 byte-identical。
- 不以文書改動充實進度：本輪實質＝產品碼 1 方法＋2 欄位＋4 測試、全可機械複核。

## 下一步
1. open/ 已空→依 11-13 定案§5 規劃者補票（每張動 vacant_network/reqloop/ 或 D1 重播器；open/ 少於 3 張就補、每次最多 4 張）；候補方向＝D1 重播器接上 verify_task_hash／D3 重算原語。
2. 不再做 closure-check／結案量具／同步類工作（11-13 定案§1）；freeze_check 既有紅→上報規劃者、不代修。
3. G4 發射流程：人類簽核（填 manifest human_signoff）→重跑測試確認 0 model calls→才可排程發射。
（MEMORY 上限 6 KB、NOW 上限 3 KB；超過的部分沒有附上，請先把它縮短）
