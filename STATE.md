# STATE.md — Vacant 現況（人類可讀；保持 ≤ 5 行）

## Current State
（2026-11-08 r1263＋redo：Actions 停擺實證——remote auto/qwen27b＝6b19961d（push 已達）但 auto-ci.yml 仍 26 跑、最後 f03d1177 停在 11-07 13:22 failure → push 到達仍未觸發＝Actions 端問題、需人工（本地無解、.github/workflows/ 不準動）；三分支對齊清零——worker 補 tests/test_reqloop_ci_contract.py（sha256 一致）→ in-scope diff 1→0、argon ff-only 同 HEAD、7 passed×3 分支。Redo（審查點名三檔未開啟）：extract.py/g3gate.py/repair.py 全部開啟（head＋ast）並重驗依賴項——**extract.py 實為 1217 行/blob e757aec5（舊簿記「901」為誤載，更正）**；g3gate --plan RC 0 NOT FIRED；filing 3 sha256 MATCH。）
G2.5 現況：G1 39/39・FP0・REAL14 9/9・PHASE3 fixed7・u2・r2w0・err0、G2 dev 9/9 vs 7/9（人手需求）全綠；anchor 測試機械化釘住 repair(2795/5147f8c3)・extract(1217/e757aec5)＋filing 3 sha（5 測×3 分支）。
G3 未發（vq-1zf 等 RLOOP_PLAN.md 明確人批；本輪 g3gate --plan 重驗：RC 0・NOT FIRED・verify_frozen OK・0 model calls；ops/reqloop/g3_gate/ manifest 凍結 11-08 04:50Z）。
紅線：0 model calls（queue 空；g3gate --plan 為離線前置門非發射）、本輪無 git push（迴圈自動推）、main c097899e 未動、repair.py(2795)／extract.py(1217) blob 與 anchor 一致、checks.py／run_eval.py／filing 未改、無 reset/rebase/branch -f。
下一步：下輪再查 Actions 一次（API 單調用）：新跑綠→紅解除；新跑紅→乾淨 venv 複現修；仍無跑→升級人工。主線 G2.5 等工單。
