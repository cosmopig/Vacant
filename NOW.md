# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1558、2026-11-13、0 model calls）
- 本輪（票 P20261113_0846-2 done，commit c1b9f4dc9）：`RequirementSet` 原生 `spec_sha256` 欄位＋`compute_spec_sha256`／`verify_self_hash`（unbound/OK/mismatch 三態）。`from_dict` 載入者以來源 dict 深拷貝快照（`raw`）為自 hash 依據——G4 檔案規格的 spec_sha256 即整份檔案 dict 之 canonical JSON sha256（同 freeze_specs._canon），4 題載入後原生自校驗全 `(True,"OK")`；`to_dict` 維持舊格式（spec_sha256 非空才輸出），run_eval `_req_digest` 相續不受影響。
- 驗收：tests/test_reqloop_requirements.py 5 passed（改前 AttributeError）；回歸 406 passed（g3_frozen_spec/freeze_g4_specs/g4_preregistration/trusted_deliverable/extract_run_eval/extract/g3/repair/g2/real_slice/checks）；freeze_specs --check 4/4 OK。
- 待驗（下條指令）：open/ 取 P20261113_0846-3（D1 replay gate CLI）照做；輪頭一次讀 CI 三分支。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2/g3_3 歷史未動；4 規格自 hash 已被測試釘住。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- NOW.md ≤3KB；ops/loop/NOW.md symlink 指本檔；~/dev/ops/NOW.md 為 cp 鏡像。
- 不以文書改動充實進度：本輪實質＝spec_sha256 欄位＋2 方法＋1 測試（4 控制），全可機械複核。

## 下一步
1. open/ 1 張：P20261113_0846-3（D1 replay gate CLI）→doing/ 照做。open/ 少於 3 張→規劃者補票（11-13 §5、每張動 reqloop 產品碼或 D1 重播器）。
2. 輪頭一次讀 CI 三分支（紅→讀 log 根因不猜；freeze_check 既有紅上報規劃者、不代修）。
3. 不做 closure-check／結案量具／同步類（11-13 §1）；G4 發射須人類簽核（human_signoff=null）。
