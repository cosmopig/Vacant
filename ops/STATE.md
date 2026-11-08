# STATE.md — Vacant 現況（人類可讀；保持 ≤ 5 行）

## Current State
（2026-11-08 r1264：CI 紅燈根因定案——公開 API 單調用：`auto-ci.yml` state=**disabled_manually**（人工禁用，非先前判斷的「基建故障」）；26/26 紅跑全在 11-07 07:27–13:22、全部早於 scipy 修復 3db4a7f3（commit 13:49、在 HEAD 2bb2d306 樹內）→ **紅燈修復已在樹、但從未在 GitHub 跑過**；測試體 0 處 scipy（1 passed）、本機三分支 CI 全 🟢（5056–5064/0 failed）。DECISION: 不代人類翻人工開關（保守可逆）——升級：re-enable auto-ci.yml 即可見綠燈，或明示本地 vacant-ci 為正統通道。）
G2.5 現況：G1 39/39・FP0・REAL14 9/9・PHASE3 fixed7・u2・r2w0・err0、G2 dev 9/9 vs 7/9（人手需求）全綠；vq-el4 全 25 項 closed（vq-el4.25 本輪建→關）；anchors 釘 repair(2795/5147f8c3)・extract(1217/e757aec5)＋filing 3 sha，本輪 5 passed、三分支 in-scope diff 0。
G3 未發（vq-1zf 等 RLOOP_PLAN.md 明確人批；本輪 g3gate --plan 重跑：RC 0・NOT FIRED・verify_frozen OK・budget OK・0 model calls）。
紅線：0 model calls（queue 空）、本輪無 git push（迴圈自動推 qwen27b）、.github/workflows/ 只讀未改、無 reset/rebase/branch -f、repair.py／extract.py／checks.py／run_eval.py／filing 未改、未讀 /srv/eval hidden 與 scorer.py。
下一步：① 人類處理 Actions（re-enable auto-ci.yml 或明示本地 CI 為正統通道）——唯一外部阻塞；② 主線 G2.5 等工單；③ 每輪守：in-scope diff 0（簿記鏡像同輪同步 worker/argon）＋三分支 anchors 5 passed＋本地 CI 綠燈。
