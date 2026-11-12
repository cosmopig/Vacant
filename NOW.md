# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1501；e016 結案測試假負控制修復（CI 紅燈根因）＋argon e016 同步（diff_argon→0 differ、10/12）；worker 票 0820-1 收斂態驗收：項1 缺裁決行→bounce open/（附 1 行修法、不代修）、項2/3 實測綠）
- **實質修復（真 bug）：** test_e016_closure_check.py::test_snapshot_pins「他項」replace 源＝已勾選 e004 行（r1493 結案）→no-op→`assert other != text` 必紅（r1500 入樹測試自身缺陷、CI 紅燈根因）；改以现存 [ ] 行（line 61 /tmp 2.9G）；三樹 selftest VERDICT: E016_CLOSURE_OK＋pytest 3 passed（改前 qwen 1 failed/2 passed）。commit 4e7ad6e18。
- **argon 同步：** e016 兩檔補入（6a0e98338）→diff_argon 0 differ；worker 同步修後測試（b0448a338、非其 WIP 檔）。freeze_check 10/12：唯二 BROKEN＝diff_worker/wt_clean＝worker 在途 WIP（預期、非 mainline 缺陷）。
- **worker 票 R20261112_0820-1：** 收斂態（888b24ed6＋1d7c4ae1f、樹 clean）；驗收項1 ✗＝`g3_2_precheck.py --selftest` RC=0、正控＋5 負控全過但**無 `VERDICT: G3_2_PRECHECK_OK`**（run_selftest return 前未印、裁決行契約 r1468/vq-el4.39）→bounce done/→open/（票尾附修法：return 0 前加該行）；項2 ✓ G3_2_FIRE_SUMMARY_SELFTEST_OK、項3 ✓ 8 passed。不代修＝污染收斂判准（r1496 先例）。
- **較上輪好的命令：** 三樹 `e016_closure_check.py --selftest && pytest tests/test_e016_closure_check.py` 全 RC=0（上輪 qwen/worker 該測試必紅）；freeze_check diff_argon 由 BROKEN（2 檔差）轉 OK。
- **紅線：** 無 push（loop 自推）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、凍結 4 檔＋filing 未改、0 model calls、未跑 full pytest、不以文書改動充實進度。

## 紅線（契約、不變）
- 不 push（loop 自推 auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN、不補 0。
- 不寫 /srv/vlab/queue；CI 不 poll；不跑 full pytest。

## 未完（≤3、交下輪）
1. worker 重驗 0820-1 項1（補裁決行、mv done/）→升上三分支（含 `tests/test_reqloop_g3_fire_summary.py` 20 行 WIP 裁定——不屬 0820-1 驗收、r1428 票）→freeze_check 12/12。
2. e013 票（tickets/qwen/bounced/）：候規劃者把驗收 grep 改 `grep -F -- "- [x]"`（或 `-e`）重驗；產物已在樹（760ed5774）、無需重做。
3. G 系列候人類裁決（vq-kax、0 呼叫）；CI 下輪一次讀取（不 poll）。

## 下輪入口（≤3）
- worker 收斂檢查：自測轉綠→按票重驗三項→升上→freeze_check（wt_clean worker 側 WIP 在途、不碰）。
- ci_status.py 一次讀取（不 poll）：若紅→讀 log 根因不猜。
- 守衛：anchors 5 passed、NOW.md ≤3KB、ops/loop/NOW.md 與 root byte-identical。
