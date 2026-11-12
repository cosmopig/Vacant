# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-12 r1490；CI 巡燈輪：argon／worker 轉綠、qwen27b tip 跑件中）
- **CI 一次讀取（不 poll）：** argon@30e8ee25 🟢 5275 passed（0 failed）；worker@252b88b3 🟢 5275 passed（0 failed）——上輪皆「還沒跑完」（worker 末次完成紅燈 3 failed c8430163、根因＝worktree 分岔、r1484 已修），本輪綠＝該紅燈收斂之驗證；qwen27b tip 5f30ee95（r1489 簿記、0 測試改動）跑件中（state.json）→下輪輪首一次讀取。
- **較上輪好的命令：** ci_status.py worker 紅燈 3 failed→綠 5275 passed；argon pending→綠。
- **守衛（本輪新跑）：** freeze_check 12/12 FROZEN_STATE_OK RC=0（anchors 5 passed、ci_contract 2 passed、diff in-scope 0、filing 6 sha MATCH、bk 鏡像同步、now_redline 與磁碟相符）；test_reqloop_freeze_check 27 passed；NOW.md ≤3KB 鏡像 byte-identical；/srv/vlab/queue 空。
- **無新產品工作：** tickets open/doing 空、bd ready 空；G 系列候人類裁決（vq-kax）、新 G 票不接；0 model calls、0 新碼。

## 紅線（契約，不改）
- 無 push（迴圈自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. qwen27b tip 5f30ee95 CI 跑件中→下輪輪首 ci_status.py 一次讀取（不 poll）；若紅→讀 log 根因（不猜）。
2. G 系列候人類裁決（H2_REFUTED 停止規則）：解凍 extract/checks 或終止；vq-kax 候裁；新 G 票不接。

## 下輪入口（≤3）
- qwen27b 5f30ee95 CI 一次讀取（不 poll）：若紅→讀 log 根因不猜；若綠→三分支全綠收口。
- G 系列若人類裁決（解凍／終止）→依裁決開新票；不代決。
- 守衛：anchors 綠、freeze_check 12/12、鏡像 byte 一致、NOW.md ≤3KB。
