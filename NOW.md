# NOW.md — 現在狀態（每輪更新，≤3KB）

## 狀態（2026-11-11 r1447a G3.1 H2.0 預跑門收案＋假說檔交叉）
- **r1447（1315-2）：G3.1 H2.0 extract 預跑門＝H2_0_REFUTED**。4 題 18/18 claims 全 unverified（deliverable_not_in_request×14、unsupported_recompute_type:mean_col×4）、0/4 題確定性 claim；4 次 glm53 呼叫/27240 tok；報告 `ops/audits/g3_1_h20_prerun_report.json`；Vacant commit 3e45e212；驗收複核 rc 0（selftest OK＋4 passed）；票尾 3 行＋mv done/（ops 91b7593）。
- **r1447a（redo）：補對假說檔** `ops/reqloop/g3_1_candidate_hypothesis.md`（r1447 未開）：判定於 §2「required claims」正統口徑與腳本口徑一致（4 題 required 項均在表內且全 unverified→UNKNOWN）；H2.1＝not_applicable（§2，不得記通過/否決）；否決後果＝停同路徑工單＋上報人類，解凍或換路徑＝人類裁決。票尾/NOW/STATE 已修正。
- r1442（1315-1）：G3.1 預註冊凍結（manifest g3gate plan/1、16 任務檔、官方乾跑 exit 0、809dae937）。
- r1444（1152-2）：stray-labd audit evidence chain 重做＋升上（3127a77ad）。
- freeze_check 11/12：唯一紅＝diff_worker＝1215-1 WIP（如實呈紅、不碰在進產物）。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair/extract/checks/run_eval）；g25 filing 不改；g3.py 改動僅依核准工單。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. G3.1：H2.0＝REFUTED → 依假說 §2：不發完整批＋停同路徑工單（同題重試/靜態 prompt/錯誤字串 regex）＋上報人類；H2.1＝not_applicable；是否解凍凍結四檔或換路徑＝人類裁決；不佔配額。
2. 1215-1（hidden_file_in_workspace 收緊）：worker doing/ 在進；收案後下輪審查＋升上→freeze_check 12/12。
3. hidden 打分：10 格 ok 有 answer（native_pi 2＋reqlist_only 4＋full_rloop 4），人類/vlab 側。

## 下輪入口（≤3）
- bd ready（vq-kax 狀態＋人類裁決）→下一票；qwen doing/ 現空。
- G3.1 裁決上報材料＝報告 JSON＋commit 3e45e212＋票 P20261111_1315-2 票尾＋假說 §2；若人類解凍/換路徑→重凍 manifest＋重跑預跑門。
- 守衛：g3 四檔＋anchors＋freeze_check（除 1215-1 項外）全綠。
（MEMORY 上限 6 KB、NOW 上限 3 KB；超過的部分沒有附上，請先把它縮短）
