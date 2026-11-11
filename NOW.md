# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-11 r1468 G3.2 凍結；doing/ 空）
- **r1468（2119-1）：G3.2 預註冊凍結完成（不發射、0 model calls）**。選題＝16 候選（dabench 30 − g3_1 tasks/seen）→ screen top4＝dab_725/587/657/517（全 COMPATIBLE、決定性排序）；`ops/reqloop/g3_2/manifest.json`（plan/1、arms=[full_rloop]、逐檔 sha256、budget 4 格／300s／2M tok 撞額停、glm 唯一入口、成本缺值 UNKNOWN、approval fail-closed）；16 任務檔 `ops/reqloop/g3_2/tasks/`（與 ref 源一致）；precheck＋screen 輸出 hash 入 manifest（防 cherry-pick）；官方乾跑 **exit 0「DRY-RUN OK（0 模型呼叫；未發射）」**；commit 落 Vacant repo（auto/qwen27b）；票結案 done/。
- r1467（1843-2）：e016 envleak audit 驗收複核＋argon 鏡像（VERDICT OK rc=0；12 測試過）；票候 worker 收斂（round 79 在進）。
- freeze_check 10/12：2 紅＝diff_worker＋wt_clean（worker 在進、非碼回歸）。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair 2795／extract 1217／checks 2823／run_eval 1298 行）；g3.py 改動僅依核准工單。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN；同批重發非獨立樣本、不宣稱臂優。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. G3.2 發射：待人類核准。門＝H0 extract 預跑（4 題各 1 次 extract：≥1/4 題 ≥1 條 required claim 確定性裁決→發完整批 4 格；0/4→否決＋停同路徑＋上報）。核准前不發射、不佔配額。
2. G3.1 發射（1315-2）：仍待人類核准（H2_0_REFUTED 有效；H2.0 重發＝人類裁決）。
3. 1215-1（hidden_file_in_workspace 收緊）：worker 在進；收斂後下輪審查＋升上→freeze_check 12/12。

## 下輪入口（≤3）
- bd ready（vq-kax 狀態＋人類裁決）→下一票；doing/ 現空。
- G3.2 若核准：extract 預跑門→H0 裁決→（過）完整批 4 格（out_dir 如 g3_fire_G32_*）→audit 摘要。
- 守衛：g3 四檔＋anchors＋freeze_check（除 1215-1 項外）全綠。
