# STATE.md — Vacant 現況（人類可讀；保持 ≤ 5 行）

## Current State
（2026-11-08 r1263：Actions 停擺實證——remote auto/qwen27b＝6b19961d（r1262 push 已達）但 auto-ci.yml 仍 26 跑全數、最後一跑 f03d1177 停在 11-07 13:22 failure → push 到達仍未觸發新跑＝Actions 端問題，需人工（本地無解、.github/workflows/ 不準動）；同輪三分支對齊清零——worker 補 tests/test_reqloop_ci_contract.py（sha256 與 qwen27b 一致）→ in-scope diff 1→0，argon ff-only 至同 HEAD，7 passed（守門2＋anchor5）×3 分支。）
G2.5 現況：G1 39/39・FP0・REAL14 9/9・PHASE3 fixed7・u2・r2w0・err0、G2 dev 9/9 vs 7/9（人手需求）全綠；filing hash 已 anchor 測試機械化釘住（5 測）。
G3 未發（vq-1zf 等 RLOOP_PLAN.md 明確人批；發射路徑已備：ops/reqloop/g3_gate/＋manifest 凍結）。
紅線：0 model calls（queue 空）、本輪無 git push（迴圈自動推）、main c097899e 未動、repair.py(2795)/extract.py(901)/checks.py/run_eval.py/filing 未改、無 reset/rebase/branch -f。
下一步：下輪再查 Actions 一次（API 單調用）：新跑綠→紅解除；新跑紅→乾淨 venv 複現修；仍無跑→升級人工。主線 G2.5 等工單。
