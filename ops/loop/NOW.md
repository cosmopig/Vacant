# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-12 r1487；票 P20261112_0521-1 收案：驗收機械複核全綠＋票移 qwen/done/）
- **r1487（票面 4 步實證已在樹、0 新碼）：** argon a78871977 已於 mainline（f570989b9、is-ancestor=TRUE）；殘留 2 票已 done/（doing/、open/ 皆空，ls 實證）；argon worktree＝191f54eee＝mainline HEAD；worker 744564dd1 in-scope diff 0（diff --name-only 空）。
- **r1487（驗收本輪新跑）：** `python3 ops/reqloop/freeze_check.py && pytest tests/test_reqloop_freeze_check.py -q` RC=0、12/12 VERDICT: FROZEN_STATE_OK、27 passed；票尾 3 行＋mv qwen/done/；簿記 4 檔（STATE 頂條目＋NOW＋2 鏡像）。
- **CI 一次讀取（不 poll）：** 輪首三分支（qwen27b/argon 191f54ee、worker 744564dd）皆「還沒跑完」→下輪輪首 ci_status.py 讀一次。

## 紅線（契約，不改）
- 無 push（迴圈自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. CI：三分支新 HEAD（191f54ee／744564dd）跑完→下輪輪首 ci_status.py 一次讀取（不 poll）；若紅→讀 log 根因（不猜）。
2. G 系列候人類裁決（H2_REFUTED 停止規則）：解凍 extract/checks 或終止；vq-kax 候裁；新 G 票不接。

## 下輪入口（≤3）
- CI 狀態一次讀取（不 poll）：驗三分支新 HEAD 轉綠；若紅→讀 log 根因（不猜）。
- G 系列若人類裁決（解凍／終止）→依裁決開新票；不代決。
- 守衛：anchors 綠、freeze_check 12/12、鏡像 byte 一致、NOW.md ≤3KB。
