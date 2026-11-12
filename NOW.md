# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1496；審查指示#1 argon 合併＋BACKLOG 同步四項驗收 RC=0；#2 worker 未收斂、不升上）
- **審查#1 完成（merge 3a50221ca）：** `git merge --no-edit auto/argon` 合入 5f7d0b774（g3_series_unverified_taxonomy --run 冪等＋逐批守恆；l007/e010 BACKLOG 快照釘選→目標條目行 sha256；6 檔＋77/−6）；~/dev/ops/BACKLOG.md 正典同步入 repo ops/BACKLOG.md（line 50 e004 [x]，repo 內外不分岔）；驗收四項全 RC=0：taxonomy G3_SERIES_TAXONOMY_OK／l007 L007_CLOSURE_OK／e010 E010_CLOSURE_OK／pytest 3 檔 14 passed（100%；-qq 吞摘要行、RC 為準）。
- **審查#2 未收斂、不升上：** R20261112_0820-1 在 tickets/doing/；worker worktree `g3_2_precheck.py --selftest` 崩（line 31 NameError: name 'hashlib' is not defined）＋3 檔 WIP 未 commit（g3_2_fire_summary.py／g3_2_precheck.py／tests/test_reqloop_g3_2_fire_summary.py）→依審查「或待 worker 收斂後升上」，本輪不升上、worker 在途檔不碰。
- **CI 一次讀取（不 poll）：** 三分支皆跑件中（qwen27b 3a50221c 新 merge HEAD／argon 5f7d0b77／worker fc607803）。
- **較上輪好的命令：** l007＋e010 closure selftest＋pytest 3 檔（argon 新版）→本輪全 RC=0（上輪 repo 內 BACKLOG line 50 仍 [ ] 分岔、新版檢查未入樹）。
- **紅線：** 無 push（loop 自推）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、凍結 4 檔未改（anchors 5 passed）、0 model calls、未跑 full pytest。

## 紅線（契約、不變）
- 不 push（loop 自推 auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN、不補 0。
- 不寫 /srv/vlab/queue；CI 不 poll；不跑 full pytest。

## 未完（≤3、交下輪）
1. R20261112_0820-1（doing/）：worker 收斂後重驗驗收三項（g3_2_precheck --selftest VERDICT: G3_2_PRECHECK_OK＋4 負控／g3_2_fire_summary --selftest／pytest manifest＋fire_summary）→升上三分支對齊→freeze_check。
2. e013 票（tickets/qwen/bounced/）：候規劃者把驗收 grep 改 `grep -F -- "- [x]"`（或 `-e`）重驗；產物已在樹（760ed5774）、無需重做。
3. G 系列候人類裁決（vq-kax）；CI 下輪一次讀取。

## 下輪入口（≤3）
- worker 收斂檢查：若自測轉綠→按票重驗驗收指令→升上→freeze_check；wt_clean worker 側 WIP 是 worker 迴圈在途、不碰。
- ci_status.py 一次讀取（不 poll）：若紅→讀 log 根因不猜；若綠→記錄數字。
- 守衛：anchors 5 passed、NOW.md ≤3KB、ops/loop/NOW.md 與 root byte-identical。
