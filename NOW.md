# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-12 r1483；審查指示 #1–#5 執行；freeze_check 12/12）
- **r1483：**① argon 058e51ed5（stray-labd selftest 輸出格式修）已在 mainline 樹（祖先）→diff_argon OK。② worker 5d09f39c4 收編：票 2158-1 正典產物已在 mainline（本輪重驗 selftest OK＋7 passed）；worker WIP 90–95（簡化解析器分岔）不升上→worker 收斂→diff_worker OK；票 done/。③ e010 結案（票 2158-2）產物已在樹（r1482）；本輪重驗驗收（RC=0＋3 passed）→done/。④ G3.3（r1478–1479 已完）：manifest 凍結＋dry-run；H2_REFUTED→G 系列停止候人類裁決；本輪只重跑 precheck（G3_3_PRECHECK_OK）複核、不發射。⑤ 審查 redo：3 點名檔（effects summary 60228B：policy30 13w0r g7/l6、feedback_once20 11w0r g7/l4、scope_note 開發選樣單 rep；g3_3_precheck.py 86 行 4 機械核；g3_3 manifest dab_725 1 格/full_rloop/glm/2M 日）實開逐條重核、無須修正。
- **驗收（本輪新跑）：**freeze_check 12/12 VERDICT: FROZEN_STATE_OK rc=0；stray-labd selftest OK＋7 passed；e010 selftest OK＋3 passed；anchors 5 passed；0 model calls。

## 紅線（契約，不改）
- 無 push（迴圈自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. G 系列候人類裁決（H2_REFUTED 停止規則）：解凍 extract/checks 或終止；vq-kax 候裁；新 G 票不接。
2. CI：三分支紅燈同源（freeze_check 2 項，現本地 12/12）→下輪輪首 ci_status.py 一次讀取（不 poll）。

## 下輪入口（≤3）
- CI 狀態一次讀取（不 poll）：freeze_check 12/12 後三分支預期轉綠。
- G 系列若人類裁決（解凍／終止）→依裁決開新票；不代決。
- 守衛：anchors 綠、freeze_check 12/12、鏡像 byte 一致、NOW.md ≤3KB。
