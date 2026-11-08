# NOW（r1267 redo#3・2026-11-08）

## 現在在哪（本輪複核值）
- G2.5 主線完成、全綠：filing 4681 B、code sha 3/3、sources sha 3/3（phase1 3c6fb35a／phase2 6b7cb831／phase3 ada235bb）本輪重算 MATCH；anchors＋ci-contract 7 passed；in-scope diff 0×2；0 model calls。
- G2.5 數字引 **7/2**（filing 的 `out/all/phase3.json`）；standalone `eval_phase3_glm53.json`（11-07 15:07 舊版碼、6/3）**不得引用**。dab_039＝fixed（獨立 scorer 過；visible R3 PASS、R1/R2/R4 UNKNOWN 已記入 row）。
- unresolved 2 格＝模型能力非 gate 失敗：dab_055（stalled、5/5 FAIL、R3/R4 需求級退步已記入 row）、dabstep-1273（max_rounds、R1 FAIL＋R2 UNKNOWN）。假設（待授權驗證）：dab_055 在 hand-written 需求下 fixed（g2-truth 9/9）但在 glm53 擷取需求下未修成→擷取需求可操作性可能較低。
- 唯一未閉＝G3（vq-1zf）：12 格已備（g3gate --plan EXIT 0）、等人類核准 `--fire`；未核准不點火。
- CI：三支最後完成皆 green（5066 passed／74 skipped）；worker@d5d6f2af（純簿記 HEAD）running、不 poll；通道裁決（auto-ci.yml vs local vacant-ci）等人類。
- 本輪修正：NOW 兩檔 2994 B 貼 3 KB cap（harness 請縮短）→ 覆寫精簡版；r1267 條目「1996 B」係同輪舊測值（HEAD 實值 2994 B），已註明。

## 下一步
1. 人類核准 G3 `--fire` → 點火後回讀 receipt＋scoring，按 gate 紀律記錄（UNKNOWN 不升級）。
2. 人類裁決 CI 通道 → 照裁決執行。
3. 兩者之前：維持紅線、0 代碼改動、每輪只複核＋記錄，不為 commit 改檔。

## 紅線（本輪全守）
0 model calls・無 push（迴圈自推）・`.github/workflows/` 只讀・無 reset/rebase/branch -f・
repair.py／extract.py／checks.py／run_eval.py／filing 未改・未讀 /srv/eval hidden 與 scorer.py・
無 sleep 輪詢・G3 未核准不點火・standalone 6/3 舊檔不引用。
