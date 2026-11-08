# 当前状态（2026-11-08 r1257）

## 本轮交付（r1257，0 模型呼叫）
G3 gate 唯一 manifest 建造路径钉住（此前零测试）：tests/test_reqloop_g3gate.py +4 测试
（16→20 passed，0.27s）——build_manifest 选題（bank 顺序−seen 前 n）＋嵌套目录逐档
sha256＋build→load→verify_frozen→check_budget 闭环；fail-closed 三态（bank 缺／缺臂／
未见不足）；plan_report 12 格 NOT FIRED；--fire 有效核准→RC 3（核准但未接线、不发射）。
真 bank（30 题）重算＝frozen manifest 逐项一致；anchors＋g2 共 62 passed。

## 下一步（次轮，按序）
1. 巡本 commit CI 灯（一次；红灯＝例外才动手；本机无 gh，以轮首报告为准）。
2. G3（vq-1zf）续候人类明确核准（RLOOP_PLAN 无核准）——不发射、不入 queue、
   0 未授权模型呼叫。
3. 新审查指示来了照指示做。

## 红线（不变）
无 G3 fire／无模型调用／无 queue／无 hidden·scorer／不 push／不 reset·rebase·branch -f／
repair.py＋extract.py 冻结／CI 每轮至多点名一次。
