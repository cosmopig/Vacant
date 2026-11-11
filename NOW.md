# NOW.md — 現在狀態（每輪更新，≤3KB）

## 狀態（2026-11-11 r1442 G3.1 凍結；r1444 並行）
- **r1442（1315-1）：G3.1 預註冊凍結完成**。manifest→`vacant.reqloop.g3gate.plan/1`（arms=[full_rloop]×4 題 dab_035/055/105/218、逐檔 sha256；budget max_cells 4／300s/輪／2M tok 撞額停不重試／glm 唯一入口／hard_token_cap=false／cost_missing=UNKNOWN；approval→`ops/approvals/g3_vq-1zf_fire_20261111.json` 常設授權）；16 任務檔落地 `ops/reqloop/g3_1/tasks/`（與 ref 源一致）；官方乾跑 **exit 0「DRY-RUN OK（0 模型呼叫；未發射）」**（改前 exit 1 plan schema mismatch）；precheck 隨新 schema；commit 809dae937；g3 系列 5 檔 95 passed。
- r1444（1152-2，並行）：stray-labd audit evidence chain 重做（selftest 6 組真實控制、matcher 收緊、報告工具實跑產出）；8 真測試 passed；已升上 mainline。
- freeze_check 11/12：唯一紅＝diff_worker＝worker 並行 WIP 票 1215-1（如實呈紅、不碰在進產物）。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair 2795 行／extract 1217 行／checks 2823 行／run_eval 1298 行）；g25 filing 不改；g3.py 改動僅依核准工單。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN；同批重發非獨立樣本、不宣稱臂優。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. G3.1 發射：待人類核准。門＝H2.0 extract 預跑（4 題各 1 次 extract：≥1/4 題 ≥1 條 required claim 確定性裁決→發完整批 4 格；0/4→否決＋停止同路徑工單＋上報人類）。核准前不發射、不佔配額。
2. 1215-1（hidden_file_in_workspace 收緊）：worker doing/ 在進；收案後下輪審查＋升上→freeze_check 12/12。
3. hidden 打分：10 格 ok 有 answer（native_pi 2＋reqlist_only 4＋full_rloop 4），人類/vlab 側。

## 下輪入口（≤3）
- bd ready（vq-kax 狀態＋人類裁決）→下一票；doing/ 現空。
- G3.1 若核准：extract 預跑門→H2.0 裁決→（過）完整批 4 格（out_dir 如 g3_fire_G31_*）→audit 摘要（同 c 發腳本口徑）。
- 守衛：g3 四檔＋anchors＋freeze_check（除 1215-1 項外）全綠。
