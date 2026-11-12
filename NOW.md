# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-12 r1489；資深審查三指示驗證輪：Step 1/2 全數已於 r1484–r1488 在樹，本輪機械複核全綠＋CI 一次讀取）
- **Step 1（審查#1，本輪複核）：** a78871977 為 HEAD 祖先（merge-base=YES）；兩舊票（2158-2／0111-1）在 done/、open/doing 空；worktree 收斂；freeze_check 12/12 FROZEN_STATE_OK（本輪新跑）。
- **Step 2（審查#2，本輪複核）：** g3_3_precheck --selftest VERDICT: G3_3_PRECHECK_OK RC=0（正控制＋4 負控制）；manifest 9＋taxonomy 3＝12 passed；anchors 5 passed；e010 selftest RC=0；兩票在 done/、票尾記錄在案。
- **較上輪好的命令：** worker 末次完成 CI 紅燈 3 failed（c8430163）→該 2 測試檔於現 HEAD 本輪實測 32 passed（含該 3 紅）＝紅根因（worktree 分岔）已修、在跑 CI 預期轉綠。
- **CI 一次讀取（不 poll）：** 三分支皆「還沒跑完」（9f3fdf62／3e0530ee／252b88b3）；vacant-ci 跑 worker@252b88b3 中（06:33:45 起）；鄰近綠 8a4ef5a9／30e8ee25 各 5275 passed。
- 簿記：STATE 頂條目＋NOW 覆寫（紅線行逐字保留、≤3KB）＋鏡像（head -5→ops/STATE.md、cp→ops/loop/NOW.md byte-identical）＋worktree 4 檔簿記同步（argon／worker，r1270 程序）。

## 紅線（契約，不改）
- 無 push（迴圈自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. CI：三分支新 HEAD（9f3fdf62／3e0530ee／252b88b3）跑件中（worker 06:33:45 起）→下輪輪首 ci_status.py 一次讀取（不 poll）；若紅→讀 log 根因（不猜）。
2. G 系列候人類裁決（H2_REFUTED 停止規則）：解凍 extract/checks 或終止；vq-kax 候裁；新 G 票不接。

## 下輪入口（≤3）
- CI 狀態一次讀取（不 poll）：驗三分支新 HEAD 轉綠；若紅→讀 log 根因（不猜）。
- G 系列若人類裁決（解凍／終止）→依裁決開新票；不代決。
- 守衛：anchors 綠、freeze_check 12/12、鏡像 byte 一致、NOW.md ≤3KB。
