# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-12 r1488；票 P20261112_0521-2 收案：G3 系列 taxonomy 單測＋假說口徑更正，驗收複核綠＋票移 qwen/done/）
- **r1488（票面 2 實質步已於 r1486 b04833f12 在樹、0 新碼）：** tests/test_reqloop_g3_series_taxonomy.py 3 測試（selftest 正控制／分母恆等 76=2+74、52=14+6+32、逐批合計／來源 sha256 grounded）；假說 md 第 7/9 行「檔名俱見於其短句內」→分母更正（call3：1/5 answer.txt・1/5 輸入檔名・3/5 無檔名；52 條：14/52・6/52・32/52）；R20261112_0422-1 在 tickets/done/、qwen/open/ 空。
- **r1488（驗收本輪新跑）：** `python3 ops/audits/g3_series_unverified_taxonomy.py --selftest && pytest tests/test_reqloop_g3_series_taxonomy.py -q` RC=0，selftest 末行 VERDICT: G3_SERIES_TAXONOMY_OK（正控制＋3 負控制全抓）；pytest 3 passed in 0.07s（票面 -q 與 pyproject addopts -q 疊成 -qq 吞 summary 行，如實）。
- **CI 一次讀取（不 poll）：** 輪首三分支（qwen27b f68cfac8／argon 30e8ee25／worker cc7d34f7）皆「還沒跑完」→下輪輪首讀一次。
- 簿記：STATE 頂條目＋NOW 覆寫（紅線行逐字保留、≤3KB）＋鏡像（head -5→ops/STATE.md、cp→ops/loop/NOW.md byte-identical）＋worktree 4 檔簿記同步（argon／worker，r1270 程序）＋票尾 3 行＋mv qwen/done/。

## 紅線（契約，不改）
- 無 push（迴圈自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. CI：三分支 HEAD（f68cfac8／30e8ee25／cc7d34f7）還沒跑完→下輪輪首 ci_status.py 一次讀取（不 poll）；若紅→讀 log 根因（不猜）。
2. G 系列候人類裁決（H2_REFUTED 停止規則）：解凍 extract/checks 或終止；vq-kax 候裁；新 G 票不接。

## 下輪入口（≤3）
- CI 狀態一次讀取（不 poll）：驗三分支新 HEAD 轉綠；若紅→讀 log 根因（不猜）。
- G 系列若人類裁決（解凍／終止）→依裁決開新票；不代決。
- 守衛：anchors 綠、freeze_check 12/12、鏡像 byte 一致、NOW.md ≤3KB。
