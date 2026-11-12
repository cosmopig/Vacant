# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1491；審查兩步指示複核：驗收全數重跑皆綠；CI 三分支跑件中）
- **審查 Step 1（本輪複核、全綠）：** a78871977 為 auto/qwen27b 祖先（merge f570989b9 在樹、`git merge-base --is-ancestor`＝YES）；兩舊票（R20261111_2158-2／R20261112_0111-1）在 done/、open/doing 空（ls 實證）；freeze_check 12/12 FROZEN_STATE_OK（diff_worker@c6e472a0c／diff_argon@b69f3f974 in-scope 0 檔、wt_clean 3/3、filing 6 sha MATCH）。
- **審查 Step 2（本輪全數重跑、皆綠）：** `python3 ops/audits/g3_series_unverified_taxonomy.py --selftest`→G3_SERIES_TAXONOMY_OK＋3 passed；`python3 ops/audits/g3_3_precheck.py --selftest`→G3_3_PRECHECK_OK（4 負控制）＋`HOME=/var/tmp/ci-home pytest tests/test_reqloop_g3_3_manifest.py`→9 passed。票面探針欄位與實際 schema 的偏差不隱藏（0455-1 票尾＋script 16–17 行已記錄；實作 n3＝`tasks[*].n_deterministic_claims`、覆蓋等同）。
- **較上輪好的命令：** `HOME=/var/tmp/ci-home pytest tests/test_reqloop_g3_3_manifest.py` → 9 passed RC=0（本輪首次以 CI 的 HOME 釘住跑；票面記錄原先未釘此 HOME）。
- **CI 一次讀取（不 poll）：** 三分支皆「還沒跑完」（qwen27b 1e5fecc8／argon b69f3f97／worker c6e472a0）→下輪輪首一次讀取。
- **審查 redo（本輪完成）：** 5 點名檔逐檔實開＋交叉核對（effects_20261105_summary.json 全開、l007_closure_check.py 全開＋selftest 重跑 L007_CLOSURE_OK、g3-1 票全讀、extract.py／repair.py 行數＋blob 實測與紅線契約行完全一致）——未發現不符、無數字更正。
- **無新產品工作：** 票 open/doing 空、bd ready 空；0 新碼、0 model calls；G 系列候人類裁決（vq-kax）、新 G 票不接。

## 紅線（契約、不變）
- 不 push（loop 自推 auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN、不補 0。
- 不寫 /srv/vlab/queue；CI 不 poll；不跑 full pytest。

## 未完（≤3、交下輪）
1. CI 一次讀取（ci_status.py、不 poll）：三新 HEAD 跑件中；若紅→讀 log 根因不猜。
2. G 系列候人類裁決（H2_REFUTED 停止規則）：解凍 extract/checks 或終止；vq-kax 候決；新 G 票不接。
3. （無）——若人類裁決後開新票，依票接。

## 下輪入口（≤3）
- ci_status.py 一次讀取（不 poll）：若紅→讀 log 根因不猜；若綠→三分支收斂、記錄數字。
- G 系列若人類裁決（解凍／終止）→依裁決開新票、不代決。
- 守衛：anchors 綠、freeze_check 12/12、鏡像 byte-identical、NOW.md ≤3KB。
