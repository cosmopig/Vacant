# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-11 r1472 G3.2 full_rloop×4 已發射跑完；待結果分報票）
- **r1472（2319-1）：G3.2 背景發射執行完（H0_MET＋常設核准 g3_vq-1zf_fire_20261111.json approved=true）。**
  - fired_at 2026-11-11T23:28:45Z、PID=637896（nohup）；log /home/user1/dev/ops/g3_fire/20261111_g3_2/fire.log。
  - 4/4 cells status=ok（dab_725/587/657/517×full_rloop、各 1 輪、requirement_list=true）；model_calls=8、tokens=128923（＜2M 上限）。
  - hidden_after 全 UNKNOWN（打分流 /srv/vlab scorer；本端未讀 hidden/scorer）；產物 g3_result.json＋cells/*/round_1/answer.txt。
  - 驗收 exit 0 → G3_2_FIRE_LAUNCH_RECORDED_OK；票 mv done/。
- r1469（2119-2）：H0 extract 預跑門＝H0_MET 1/4（dab_725 2 確定性 claim；ops/audits/g3_2_h0_prerun_report.json）。
- r1468（2119-1）：預註冊凍結（manifest＋tasks＋precheck，0 model calls）。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN；同批重發非獨立樣本。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. **G3.2 結果分報＝待新票**：讀 g3_result.json＋各輪 claim 裁決→逐 claim 分報（PASS/FAIL/UNKNOWN）＋成本；同批不重發（非獨立樣本）。
2. G3.1 發射（1315-2）：仍待人類核准（H2_0_REFUTED 有效；重發＝人類裁決）。
3. 1215-1（hidden_file_in_workspace 收緊）：worker 在進；收斂後下輪審查＋升上→freeze_check 12/12。

## 下輪入口（≤3）
- G3.2 結果分報（未完成 #1）；不碰 g3_1/g3_fire_20261111* 既有產物。
- 守衛：g3 四檔＋anchors＋freeze_check（除 1215-1 項）全綠；新工具 selftest 保持 OK。
