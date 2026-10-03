# 分析報告（c5）

## 主要檢定（預註冊第六節）

完整配對 920；A 過 748、C361 過 758；不一致對 b（只有 C361 過）＝59、c（只有 A 過）＝49；McNemar 精確雙尾 p＝0.3866（α＝0.05）。

## 各題庫（描述）

| 題庫 | 配對 | A 過 | C361 過 | 只有 C 過 | 只有 A 過 | p（描述用） |
|---|---|---|---|---|---|---|
| humanevalplus | 155 | 150 | 150 | 2 | 2 | 1 |
| lcb_v1 | 89 | 62 | 68 | 15 | 9 | 0.307 |
| lcb_v2 | 118 | 88 | 87 | 16 | 17 | 1 |
| lcb_v3 | 189 | 153 | 149 | 11 | 15 | 0.557 |
| mbppplus | 369 | 295 | 304 | 15 | 6 | 0.0784 |

## 描述

```json
{
 "A": {
  "n": 920,
  "pass": 748,
  "visible_pass": 837,
  "false_done": 89,
  "no_solution": 42,
  "timeouts": 71,
  "wall_p50": 293.45000000000005,
  "calls": 7648,
  "prompt_tokens": 50116596,
  "completion_tokens": 5174519
 },
 "C361": {
  "n": 920,
  "pass": 758,
  "visible_pass": 846,
  "false_done": 88,
  "no_solution": 34,
  "timeouts": 65,
  "wall_p50": 355.2,
  "calls": 8594,
  "prompt_tokens": 55493649,
  "completion_tokens": 5091099
 },
 "C361_vacant": {
  "c_arm_ok": 920,
  "install_fail": 0,
  "cells_with_review": 858,
  "review_actions": {
   "continue": 472,
   "allow": 855
  },
  "cells_sent_back": 309,
  "sendback_kinds": {
   "test_claim/none": 455,
   "failed_step/-": 21,
   "unsourced/-": 1
  },
  "test_claim_none_after_running_run_tests_sh": 293
 }
}
```

infra_void 格子 0；不完整的單位 0（清單在 report.json）。
