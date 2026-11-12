# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-12 r1486；審查指示全數完成：argon 合併＋4 票結案＋兩票補驗收；三分支收斂；freeze_check 12/12）
- **r1486（argon a78871977 合併，f570989b9 clean）：** l007_closure_check 改 repo 快照（ops/loop/L007.md＋ops/BACKLOG.md；sha256 釘 d52d668f…／6599f4d3… 與活檔 byte 一致）＋stray_labd --run 冪等（兩次 --run 輸出 byte 一致 0daa79fd…、VERDICT OK）＋缺 session 檔 fail-closed＋L007.md vendoring＋2 測試檔 12 passed（本輪新跑）。
- **r1486（4 票結案、open/ 空）：** 2158-2（e010）＋0111-1（g3.3 凍結＋乾跑）＝已完成票移 done/；0422-1＝新增單測 tests/test_reqloop_g3_series_taxonomy.py 3 passed＋假說 md 第 7/9 行過度宣稱更正（5 條：1/5 含 answer.txt、1/5 輸入檔名、3/5 無檔名；4 批 52 條：14/52、6/52、32/52 精確分母）；0455-1＝g3_3_precheck 抽離 check_precheck 純函式＋4 負控制 selftest OK＋manifest 測試 9 passed＋票面探針 NEG_CONTROLS_OK（票面欄位名與凍結 manifest 實際 schema 不符、按實際 schema 實作 4 類篡改、票尾＋docstring 記錄）。
- **CI 一次讀取（不 poll）：** qwen27b b04833f1 跑件中；argon a7887197 2 紅＝freeze_check（worktree 未收斂之期待、本輪收斂後新 HEAD 預期轉綠）；worker c8430163 跑件中。

## 紅線（契約，不改）
- 無 push（迴圈自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. G 系列候人類裁決（H2_REFUTED 停止規則）：解凍 extract/checks 或終止；vq-kax 候裁；新 G 票不接。
2. CI：三分支新 HEAD 下次跑預期轉綠→下輪輪首 ci_status.py 一次讀取（不 poll）。

## 下輪入口（≤3）
- CI 狀態一次讀取（不 poll）：驗三分支新 HEAD 轉綠；若紅→讀 log 根因（不猜）。
- G 系列若人類裁決（解凍／終止）→依裁決開新票；不代決。
- 守衛：anchors 綠、freeze_check 12/12、鏡像 byte 一致、NOW.md ≤3KB。
