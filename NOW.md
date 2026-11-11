# NOW.md — 現在狀態（每輪更新，≤3KB）

## 狀態（2026-11-11 r1442）
- 審查指示 #1 執行：30f387a04（argon、not_run 修法）已審——功能 qwen27b 已有（r1433）且較新；採用其剩餘 diff＝2 測試（逐字、測試檔與其 git diff=0；11 passed）；未做完整 merge（其為舊線、完整 merge 會回退較新產物，已如實記錄）。
- worker 產物（G3.1 manifest freeze＋precheck＋tests＋labd audit，6 個 in-scope 檔、ticket 1152-1 worker 已關）審查後升上 mainline → 三分支 in-scope diff 0。
- NOW.md 紅線契約行修復（凍結 4 檔＋filing 6 sha256、值自磁碟重算）＋ops/loop/NOW.md 鏡像 byte 一致；freeze_check 5 紅（diff×2、bk_now、wt_clean、now_redline）逐項修復。
- G3.1：H2.0＋H2.1 已凍結；待人類核准，核准前不發射、不佔配額（vq-kax）。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不改；g3.py 改動僅依 vq-kax 工單（AMEND-3 為其核准、執行順序以工單為準）。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN；同批重發非獨立樣本，不宣稱臂優。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. G3.1 H1/H2 裁決：c 發 4/4 格完成 ≥1 輪 content_reverify 但 final_verdict 全 UNKNOWN、claims verdict 全 None——H2 未測得；裁決歸人類（預註冊升級）。
2. hidden 打分：10 格 ok 有 answer（native_pi 2＋reqlist_only 4＋full_rloop 4），人類/vlab 側。
3. vq-kax（G3 重發殘項）待人類核准；核准前不點火。

## 下輪入口（≤3）
- bd ready（vq-kax 狀態＋人類裁決）→下一票；doing/ 現空。
- 守衛：g3 三檔＋anchors＋freeze_check（12 項，含 now_redline、diff_worker/argon）全綠。
