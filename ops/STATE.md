# STATE.md — Vacant 現況（人類可讀；保持 ≤ 5 行）

## Current State
（2026-11-08 r1265：**主線 G2.5 已完結且全綠**——本輪實跑 `run_eval.py --all` EXIT 0（三門全 PASS：G1 抓錯 39/39・冤枉 0；REAL14 抓錯 9/9・冤枉 0/5；PHASE3 fixed7／unresolved2／rejected0／right_to_wrong0／error0）；reqloop 相關 242 passed；anchors（test_reqloop_frozen_anchors）5 passed×3 分支；in-scope diff qwen27b↔worker↔argon 皆 0；`g3gate --plan` EXIT 0（G3 已備妥・NOT FIRED・0 model calls）。**本輪無實質代碼改動**：主線已完結、唯一剩餘工作 G3 阻塞於人類核准，故未造假進展。）
G3（唯一剩餘項）：vq-1zf open；`g3gate --plan` 全綠（12 格＝4 題×3 臂、verify_frozen OK、budget OK、入口＝glm）；紅線#5 嚴禁未核准 `--fire`／入 queue／產生未授權模型呼叫——發射需人類於 RLOOP_PLAN.md 或明確指示給核准信號。
CI：三分支 HEAD（qwen27b d56f36de／argon f499a037／worker 70c61bb4）皆純簿記 commit；本地 vacant-ci pending（prompt 給定、本輪未 poll）；GitHub auto-ci.yml 仍 disabled_manually（r1264 已升級人類：re-enable 或明示本地 CI 正統）。
紅線（本輪全守）：0 model calls（queue 空、vibe_calls 今日 0 筆）、無 git push（迴圈自推 qwen27b）、.github/workflows/ 只讀、無 reset/rebase/branch -f、repair.py 2795/5147f8c3・extract.py 1217/e757aec5・checks.py/run_eval.py/filing 未改、未讀 /srv/eval hidden 與 scorer.py。
下一步（需人類決策）：① 核准 G3 發射（`--fire`）或指派其他 in-scope 工作——主線已完結、無其他可單方推進的代碼工作；② 確認三分支 CI 轉綠（一次、不 poll）；③ 每輪守 anchors 5 passed＋in-scope diff 0（簿記鏡像同步 worker/argon）。
