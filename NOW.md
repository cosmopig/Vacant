# NOW.md — 現在狀態（每輪更新，≤3KB）

## 狀態（2026-11-11 r1448 NOW.md 紅線契約行恢復＋鏡像同步）
- **r1448（審查指示 #2）：now_redline 4 failed→5 passed；bk_now DRIFT→OK**。根因＝r1447a 改寫把守衛要求的紅線契約行換成簡略式、且未同步 ops/loop/NOW.md 鏡像。修：恢復契約行（值自磁碟重算、與舊鏡像 r1444 行一致）＋鏡像 cp byte 一致。abbf37fe0（argon）已審查：其狀態段為 r1437 時代、整併將回退 r1442–r1447a 狀態→不 merge、只採其契約行格式（DECISION：最保守可逆）。
- **r1447/r1447a（1315-2）：G3.1 H2.0 extract 預跑門＝H2_0_REFUTED**（0/4 題確定性 claim、報告 `ops/audits/g3_1_h20_prerun_report.json`、驗收複核 rc 0、假說檔已對 H2.1＝not_applicable）。
- r1442（1315-1）：G3.1 預註冊凍結（乾跑 exit 0、809dae937）；r1444（1152-2）：stray-labd audit chain 重做＋升上（3127a77ad）。
- freeze_check：now_redline/bk_now/bk_state OK（本輪修）；diff_worker/diff_argon＝本輪簿記無 sync counterpart（各分支自有 loop 按序同步——argon 已同步至 r1444、worker round 52 WIP；本輪不向 active worktree 雙寫、待下輪同步收）；wt_clean＝worker 1215-1 WIP 殘留——如實呈紅。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不改；g3.py 改動僅依核准工單。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. G3.1：H2.0＝REFUTED → 依假說 §2：不發完整批＋停同路徑工單（同題重試/靜態 prompt/錯誤字串 regex）＋上報人類；H2.1＝not_applicable；是否解凍凍結四檔或換路徑＝人類裁決；不佔配額。
2. 1215-1（hidden_file_in_workspace 收緊）：worker doing/ 在進；收案後下輪審查＋升上；diff_worker/diff_argon 待各分支 loop 同步本輪簿記→freeze_check 12/12（本輪不碰 live worktree）。
3. hidden 打分：10 格 ok 有 answer（native_pi 2＋reqlist_only 4＋full_rloop 4），人類/vlab 側。

## 下輪入口（≤3）
- bd ready（vq-kax 狀態＋人類裁決）→下一票；qwen doing/ 現空。
- G3.1 裁決上報材料＝報告 JSON＋commit 3e45e212＋票 P20261111_1315-2 票尾＋假說 §2；若人類解凍/換路徑→重凍 manifest＋重跑預跑門。
- 守衛：g3 四檔＋anchors＋freeze_check（除 1215-1 項外）全綠。
（MEMORY 上限 6 KB、NOW 上限 3 KB；超過的部分沒有附上，請先把它縮短）
