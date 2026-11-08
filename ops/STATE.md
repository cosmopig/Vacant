# STATE.md — Vacant 現況（人類可讀；保持 ≤ 5 行）

## Current State
（2026-11-08 r1264＋redo：CI 紅燈根因定案——公開 API 單調用：`auto-ci.yml` state=**disabled_manually**（人工禁用，非「基建故障」）；26/26 紅跑全在 11-07 07:27–13:22、全部早於 scipy 修復 3db4a7f3（commit 13:49、在 HEAD 2bb2d306 樹內）→ **紅燈修復已在樹、但從未在 GitHub 跑過**。DECISION: 不代人類翻人工開關（保守可逆）——升級：re-enable auto-ci.yml 即可見綠燈，或明示本地 vacant-ci 為正統通道。redo：CI 值改從 ~/dev/ops/ci/<sha>.json 直接重算（qwen27b/argon@2bb2d306 5066/5139 🟢、worker@ce4c16c2 5064/5137 🟢，0 failed）；effects_20261105_summary.json、extract.py、repair.py 直接開啟重算。）
G2.5 現況：vq-el4 全 25 項 closed（bd list 本輪確認）；effects 審計（ops/audits/effects_20261105_summary.json 本輪開啟＋重算，blob 856c2c71／file sha256 a710f7e4）：policy30 30 cells w2r 13(g7/l6)・r2w 0・pg 10・sw 7；once20 20 cells w2r 11(g7/l4)・r2w 0・sw 9；共 50 cells、**current-code 重驗 50/50 與獨立評分一致**、local(d38d2eb2 舊 checker) 45/50（5 分歧全歸因舊 checker）；scope＝開發選樣（已見題）、非未見任務效力、單 rep。
G3 未發（vq-1zf 等 RLOOP_PLAN.md 明確人批；本輪 g3gate --plan 重跑：RC 0・NOT FIRED・verify_frozen OK・budget OK・0 model calls）。
紅線：0 model calls（queue 空）、本輪無 git push（迴圈自動推 qwen27b）、.github/workflows/ 只讀未改、無 reset/rebase/branch -f、repair.py（2795 行/5147f8c3）與 extract.py（1217 行/e757aec5）本輪直接開啟（head＋wc -l＋git hash-object）未變、checks.py/run_eval.py/filing 未改、未讀 /srv/eval hidden 與 scorer.py。
下一步：① 人類處理 Actions（re-enable auto-ci.yml 或明示本地 CI 為正統通道）——唯一外部阻塞；② G2.5 等工單；③ 每輪守：in-scope diff 0（簿記鏡像同輪同步 worker/argon）＋三分支 anchors 5 passed＋本地 CI 綠燈。
