# 当前状态（2026-11-08 r1261）

## 本轮交付（r1261，0 模型呼叫）
审查#3 机械化：tests/test_reqloop_frozen_anchors.py 新增 filing code sha 守卫
（filing_code_violations＋绿灯＋漂移负控制）→pytest 3→5 passed；「code hash 与备案
100% 吻合」由每轮人工重算改为机器直接变红。同轮新鲜复验：reqloop 353 passed；
run_eval --all RC 0 三门 PASS（G1 39/39·FP0／REAL14 9/9·0/5／PHASE3 fixed7·u2·
r2w0·err0）；filing 6 sha 全 MATCH；worker diff＝0；anchors 5 passed×3 分支；
argon ff 对齐。工单 vq-el4.21。redo：审查点名 effects_20261105_summary.json
已直接开启＋逐格重算（blob 856c2c71 未变；w2r policy30 g7/l6、once20 g7/l4
与 11-06 点名数逐项吻合、两臂加總与 top-level 一致）→零更正。

## 下一步（次轮，按序）
1. 三分支新 SHA CI 灯各巡一次（红灯＝例外才动手；本机无 gh，以轮首报告为准，不乾等）。
2. G3（vq-1zf）续候人类明确核准——不发射、不入 queue、0 未授权模型呼叫。
3. repair.py／extract.py／checks.py／run_eval.py 或 filing 任何变动 → 锚点／filing
   守衛直接红灯＝例外，先停下报，不自行解冻。

## 红线（不变）
无 G3 fire／无模型调用／无 queue／无 hidden·scorer／不 push／不 reset·rebase／
branch -f／repair.py＋extract.py 冻结／CI 每轮至多点名一次。
