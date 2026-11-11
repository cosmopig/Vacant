# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-11 r1469 G3.2 H0 預跑門完成＝H0_MET；doing/ 空）
- **r1469（2119-2）：G3.2 H0 extract 預跑門執行完畢 → `H0_MET`（1/4）**。
  - 4 凍結題各 1 次 extract＝4 calls／29914 tok（報告 `ops/audits/g3_2_h0_prerun_report.json`）。
  - dab_725：7 req、**2 確定性 claim（R1/R6 `answer_kv` numeric keys，可 PASS/FAIL 重算）**、5 unverified。
  - dab_587/657/517：0 確定性（全 unverified：deliverable_not_in_request、unsupported_recompute_type、model_declared_unverified、unknown_verifier:missing）。
  - 工具 `ops/audits/g3_2_extract_prerun.py`（150 行）＋test（80 行 4 案）；selftest VERDICT OK；回歸 12 passed；凍結 4 檔未動。
  - **完整批未發射**（票紅線：預跑不擅自點火）→ 上報人類：H0_MET 是否發射 full_rloop×4 格。
- r1468（2119-1）：G3.2 預註冊凍結（manifest＋tasks＋precheck，0 model calls）。
- r1467（1843-2）：e016 envleak audit 複核＋argon 鏡像；票候 worker 收斂。
- freeze_check 10/12：2 紅＝diff_worker＋wt_clean（worker 在進、非碼回歸）。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN；同批重發非獨立樣本。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. **G3.2 發射＝待人類核准**：H0 已過（MET）；核准後 approval 門 fail-closed＋`python3 -m vacant_network.reqloop.g3 --manifest ops/reqloop/g3_2/manifest.json`（full_rloop×4 格、300s/輪、2M tok 撞額停）。
2. G3.1 發射（1315-2）：仍待人類核准（H2_0_REFUTED 有效；重發＝人類裁決）。
3. 1215-1（hidden_file_in_workspace 收緊）：worker 在進；收斂後下輪審查＋升上→freeze_check 12/12。

## 下輪入口（≤3）
- 人類裁決 G3.2（發／停）→照裁決走；doing/ 現空，無待辦票。
- 守衛：g3 四檔＋anchors＋freeze_check（除 1215-1 項外）全綠；新工具 selftest 保持 OK。
（MEMORY 上限 6 KB、NOW 上限 3 KB）
