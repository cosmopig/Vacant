# ctl12_colab_e4b — Evidence Controller Metrics
Plan sha256: `9e7ca731510a7120…`  Tasks: 12 × 3 reps
Note: 這是 16 題的探索，只判斷方向（DECISION_20261127_EVIDENCE_CONTROLLER.md）。

| Arm | Hidden Pass | Hidden Rate | Hidden Sat (macro/micro) | Tokens/Success | Broken-After-Pass | Mean Wall | Mean Attempts | Void |
|---|---|---|---|---|---|---|---|---|
| A | 6/36 | 0.1667 | 0.4881/0.4844 | 118098.5 | 0.0 (0/160) | 195.1s | 1.0 | 0 |
| B | 9/36 | 0.25 | 0.5646/0.5804 | 202516.2 | 0.0 (0/197) | 566.2s | 2.0 | 0 |
| C | 10/36 | 0.2778 | 0.6255/0.6538 | 241999.4 | 0.014 (3/214) | 635.0s | 2.306 | 0 |
| R | 10/36 | 0.2778 | 0.5522/0.5457 | 198083.6 | 0.0254 (5/197) | 527.0s | 2.25 | 0 |

## Paired Comparisons (task × rep)

| Comparison | Pairs | Ctrl Pass | Treat Pass | b (ctrl only) | c (treat only) | Delta (pp) | McNemar p | Delta Tokens/Cell | Delta Tokens/Success | Delta Wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| C_vs_B | 36 | 9 | 10 | 0 | 1 | 2.78 | 1.0 | 16593.0 | 39483.2 | 68.8 |
| C_vs_R | 36 | 10 | 10 | 3 | 3 | 0.0 | 1.0 | 12198.9 | 43915.8 | 108.0 |
