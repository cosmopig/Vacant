# ctl12_pi_qwen9b — Evidence Controller Metrics
Plan sha256: `9d8f8681a346f5a1…`  Tasks: 12 × 3 reps
Note: 這是 12 題 × 3 次的探索，只判斷方向（DECISION_20261127_EVIDENCE_CONTROLLER.md）。

| Arm | Hidden Pass | Hidden Rate | Hidden Sat (macro/micro) | Tokens/Success | Broken-After-Pass | Mean Wall | Mean Attempts | Void |
|---|---|---|---|---|---|---|---|---|
| A | 19/36 | 0.5278 | 0.8355/0.8493 | 436230.1 | 0.0 (0/240) | 278.6s | 1.0 | 0 |
| B | 26/36 | 0.7222 | 0.8809/0.8525 | 429790.9 | 0.0035 (1/284) | 278.3s | 1.306 | 0 |
| C | 26/36 | 0.7222 | 0.9378/0.9293 | 324264.4 | 0.0 (0/277) | 308.2s | 1.306 | 0 |
| R | 26/36 | 0.7222 | 0.9388/0.926 | 344449.8 | 0.0 (0/277) | 299.5s | 1.333 | 0 |

## Paired Comparisons (task × rep)

| Comparison | Pairs | Ctrl Pass | Treat Pass | b (ctrl only) | c (treat only) | Delta (pp) | McNemar p | Delta Tokens/Cell | Delta Tokens/Success | Delta Wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| C_vs_B | 36 | 26 | 26 | 5 | 5 | 0.0 | 1.0 | -76213.5 | -105526.5 | 29.9 |
| C_vs_R | 36 | 26 | 26 | 3 | 3 | 0.0 | 1.0 | -14578.3 | -20185.4 | 8.7 |
