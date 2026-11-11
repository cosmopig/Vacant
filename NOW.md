# NOW.md — 現在狀態（每輪更新，≤3KB）

## 狀態（2026-11-11 r1443）
- r1443（1152-1）：G3 unverified 原因持久化——report.unverified 逐條存進 trec.unverified_reasons＋evidence["reason"]（g3.py 僅此、0 model calls）；test_unverified_reasons_persisted 負/正控制＋end-to-end；GUARD_CONTENT_PIN 解凍記錄；worktree 已同步，freeze_check 11/12（唯一紅＝diff_worker：worker loop 並行 WIP 3 檔、非本輪遺漏、不碰）。
- r1442：30f387a04（argon）審完採 2 測試、未完整 merge（舊線、會回退較新產物）；worker 產物（G3.1 manifest freeze 等 6 檔）升上 mainline；NOW.md 紅線契約行修復＋鏡像 byte 一致。
- G3.1：H2.0＋H2.1 已凍結；待人類核准，核准前不發射、不佔配額（vq-kax）。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不改；g3.py 改動僅依核准工單（vq-kax AMEND-3 為其核准；1152-1 unverified 原因持久化依該票），執行順序以工單為準。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN；同批重發非獨立樣本，不宣稱臂優。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. G3.1 H1/H2 裁決：c 發 4/4 格完成 ≥1 輪 content_reverify 但 final_verdict 全 UNKNOWN、claims verdict 全 None——H2 未測得；裁決歸人類（預註冊升級）。
2. hidden 打分：10 格 ok 有 answer（native_pi 2＋reqlist_only 4＋full_rloop 4），人類/vlab 側。
3. vq-kax（G3 重發殘項）待人類核准；核准前不點火。

## 下輪入口（≤3）
- bd ready（vq-kax 狀態＋人類裁決）→下一票；doing/ 現空。
- diff_worker 紅（worker loop WIP stray_labd_ps 3 檔）：審查後升上 mainline 或 worker 側收束→freeze_check 12/12。
- 守衛：g3 四檔＋anchors＋freeze_check（除上項外）全綠。
