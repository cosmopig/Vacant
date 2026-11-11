# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-11 r1473 G3.2 結果分報完；H1_REFUTED；G 系列候人類裁決）
- **r1473（2319-2）：G3.2 fire 結果分報＋H1 判定＝`H1_REFUTED`（0 model calls）。**
  - 4/4 格 ok、各 1 輪；claims 26/26 UNKNOWN（PASS 0/26、FAIL 0/26）；確定性裁決 0/4 格→H1(a) 否決；
    0/4 格已確認缺口→H1(b) not_applicable；第 2 輪 0/4 未執行（UNKNOWN 非缺口、機制如設計、diff 全 null）。
  - 主因：deliverable_not_in_request 20/26＋unsupported_recompute_type 5/26＋missing_param 1/26（extract→checks 編譯層，非 harness 故障）。
  - 新發現：H0 門跨獨立呼叫不穩定——dab_725 預跑 2/7 確定性→fire 0/6（分解 7→6）；其餘 3/4 題 0→0 一致。
  - 成本 8 calls/128923 tok（日額度 6.45%）；hidden_after 4/4 UNKNOWN；cost_usd UNKNOWN。
  - 停止規則「H1 否決→停止上報人類」＋「連續 2 發無已確認缺口被消解（G3 c＋G3.2）」→皆觸發；G 系列停候人類。
  - 產物：ops/audits/g3_2_fire_summary.py（selftest 6 controls OK）＋g3_2_fire_summary.json＋g3_2_interpretation.md；
    假說檔狀態＝H1_REFUTED＋§6 G3.3 預註冊（H0 門穩定性、1 呼叫、待人類核准）。
- r1472（2319-1）：G3.2 背景發射執行完（4/4 ok、hidden_after UNKNOWN、128923 tok）。
- r1469（2119-2）：H0 預跑門＝H0_MET 1/4（dab_725 2 確定性）——fire 未復現（見上）。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN；同批重發非獨立樣本。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. **G 系列＝候人類裁決**（停止規則已觸發）：選項＝G3.3（H0 門穩定性、1 extract 呼叫、約 7k tok）／G3.4（多呼叫共識門）／解凍 extract+checks／終止；預註冊在假說檔 §6。
2. G3.1 發射（1315-2）：仍待人類核准（H2_0_REFUTED 有效；重發＝人類裁決）。
3. 1215-1（hidden_file_in_workspace 收緊）：worker 在進；收斂後下輪審查＋升上→freeze_check 12/12。

## 下輪入口（≤3）
- 人類裁決項 #1（G3.3 核准或終止）；不碰 g3_1/g3_fire_20261111* 既有產物。
- 守衛：g3 四檔＋anchors＋freeze_check（除 1215-1 項）全綠；新工具 selftest 保持 OK。
