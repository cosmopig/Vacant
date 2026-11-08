# STATE.md — Vacant 現況（人類可讀；保持 ≤ 5 行）

## Current State
（2026-11-08 r1262：GitHub auto CI 紅燈診斷——26 跑全紅（11-07 07:27→13:22，全敗 ReqLoop 步）；乾淨 venv 複現根因＝test_pin_survives_venv_symlink 斷言 scipy/numpy（不在安裝合約）；3db4a7f3 已改 pytest（在 HEAD、不在 f03d1177）→ HEAD 乾淨 venv 三步全綠（379/3・1・37/1）；新增 tests/test_reqloop_ci_contract.py（合約守門＋scipy 負向控制＋回歸模擬紅燈驗證）；round-head 的「CI」報表實為本地 CI，曾遮蔽 GitHub 紅。）
G2.5 現況：G1 39/39・FP0・REAL14 9/9・PHASE3 fixed7・u2・r2w0・err0、G2 dev 9/9 vs 7/9（人手需求）全綠；r1258–1261 護欄（g3gate 負向控制、bd remember 紅線、filing hash 紅線）在案。
G3 未發（vq-1zf 等 RLOOP_PLAN.md 明確人批；發射路徑已備：ops/reqloop/g3_gate/＋manifest 凍結）。
紅線：0 model calls（queue 空、vibe_calls 無新條）、本輪無 git push、main c097899e 未動、repair.py(2795)/extract.py(901)/checks.py/run_eval.py/filing 未改。
Actions 自 11-07 13:22 無新跑（stalled）；下一觸發＝迴圈自動 push；仍無跑或仍紅→需人工。
