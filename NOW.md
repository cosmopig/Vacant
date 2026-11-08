# 当前状态（2026-11-08 ~08:11 UTC，r1245 redo）

## r1245 交付
- 新增 `tests/test_reqloop_frozen_anchors.py`（commit `5fb3d00a`，未 push）：把审查指示#3
  （repair 2,795 行/blob 5147f8c3；extract 1,217 行/blob e757aec5）固化成守卫＋篡改负控制。
  `pytest tests/test_reqloop_frozen_anchors.py` → 3 passed；验收对（extract_run_eval+g3gate）53 passed 无回归；
  frozen_anchors+repair+r1169 合计 116 passed。repair.py/extract.py 未改动。
- vq-4xt 已关闭（reason 含 SHA＋验收输出）；唯一开放项 vq-1zf（G3，P1，待人类核准——不發射、不入队、0 模型呼叫）。

## redo 接地（审查点名 3 檔未開啟 → 本轮全部实读＋核对）
- `g25_all_gates_filing.json`（blob `4b24cd5b`，116 行，全读）：vq-el4.14 / round 1228，
  generated 2026-11-08T05:01:59+00:00，head d826f5b5（auto/argon）；**三门全 PASS**
  （G1 39/39・0 冤枉；REAL14 9/9・0 冤枉・errors 0；PHASE3 errors 0、fixed 7、unresolved 2）；
  sources（phase1/2/3.json）与 code（extract/checks/run_eval sha256）均入档。
- `effects_20261105_summary.json`（blob `856c2c71`，60,228 B，python 载读）：
  policy30 g7·l6（localized tokens_true 17,385,851）、once20 g7·l4（localized 13,293,271）
  ——与 r1244 redo2 重算值一致；scope_note＝开发选样/单 rep/缺值 None（hidden_after 全 UNKNOWN）。
- `build_g25_all_gates_filing.py`（blob `23dac11c`，205 行）：fail-closed builder
  （三门任一未过或 raw 缺值 → exit 2，不写「达标」备案）。
- 锚点（本轮实测，三分支 qwen27b/argon/worker 同 blob）：repair `5147f8c3`/2,795 行、
  extract `e757aec5`/1,217 行、g3gate `0d90f166`。**收回**上下文沿用的「g3gate 6f93f4e5」
  锚点（与当前文件不符，本轮未验证前不重复该声明）。

## 环境异常（待人类检查，勿自行修复）
- 时钟在本轮中途回跳约 6h47m（14:41→07:5x UTC）。
- `ops/loop/STATE.md` 历史丢失（现仅本轮一条；未入 git，无本地备份可恢复）。
- ops 工作区 git status 大量 ` D`（ci/*.json、effects2_20261106 等）——非本轮所为。

## 红线（未动）
G3 未發射｜0 模型呼叫｜未入队｜main 未动、未 push｜未读隐藏分卷｜repair/extract 冻结未破｜
CI 未轮询（280eda92 运行中，下轮头看一次）。
