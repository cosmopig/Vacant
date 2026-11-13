# NOW.md — Vacant 現況（≤3KB；本檔每輪覆寫、歷史見 STATE.md）

## 現況（r1552、2026-11-13、0 model calls）
- 本輪實質＝票 P20261113_0545-1（D4）done：g3.py 凍結規格重用——load_frozen_spec（<spec_dir>/<tid>.json：task_id／goal_sha256／contract_sha256 校驗＋reqset 反序列化；缺檔／雜湊不符／損壞→ValueError fail-closed 拒發，絕不默默降級重新擷取）＋run_g3 spec_dir 參數（None＝舊行為動態擷取）＋CLI --spec-dir；tests/test_reqloop_g3_frozen_spec.py 3 測試（正控制：合法凍結規格→0 次 client 擷取呼叫、需求清單以凍結規格逐條渲染逐字進 prompt；負控制×2：goal 篡改一字／規格損壞→拒發且 0 呼叫）。
- 驗收（本輪新跑）：`pytest tests/test_reqloop_g3_frozen_spec.py`→「3 passed in 0.73s」；票面驗收指令（含 -q）RC=0；既有 g3 系 91 測試全綠（舊行為未改）；--dry-run RC=0；commit a262f6f36（2 檔）。
- 未驗證：CI 完成裁決（延下輪頭一次讀、不 poll）；成效門（11-13 定案 ≥30/76）最終裁決屬人類、本輪只交付 D4 產品碼；無實際凍結規格檔產出（屬 G4 預跑步驟，G4 發射須人類點頭）。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、run_eval.py 332cd324…（仍凍結）；extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob 764119e2…（受控解凍、只加法、再改須重立錨留記錄）；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- NOW.md ≤3KB；ops/loop/NOW.md cp 鏡像 byte-identical。
- 不以文書改動充實進度：本輪實質＝D4 加法＋測試＋票結案、全可機械複核。

## 下一步（2026-11-13 人類定案改寫，凌駕舊的下一步）
1. 照 tickets/qwen/open/ 做（D4 已 done；open/ 3 張：freeze-g4-specs／g4-preregistration／requirementset-hash-integrity，照票面取下一張）。
2. 不再做任何 closure-check／結案量具／同步類工作。
3. extract.py／checks.py 受控解凍：只加法、新參數預設＝舊行為、run_eval.py --all 三門數字與 g25 filing 相同；G4 發射前須人類點頭。
