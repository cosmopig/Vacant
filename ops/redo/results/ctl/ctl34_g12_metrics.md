# ctl34_pi_gemma12b — Evidence Controller Metrics
Plan sha256: `77ce804923be5ece…`  Tasks: 34 × 2 reps
Note: 這是 16 題的探索，只判斷方向（DECISION_20261127_EVIDENCE_CONTROLLER.md）。

| Arm | Hidden Pass | Hidden Rate | Hidden Sat (macro/micro) | Tokens/Success | Broken-After-Pass | Mean Wall | Mean Attempts | Void |
|---|---|---|---|---|---|---|---|---|
| A | 23/68 | 0.3382 | 0.6757/0.7103 | 6495966.3 | 0.0 (0/400) | 896.0s | 1.0 | 0 |
| B | 31/68 | 0.4559 | 0.8335/0.82 | 2450455.6 | 0.0256 (13/507) | 905.1s | 1.926 | 0 |
| C | 32/66 | 0.4848 | 0.8091/0.7942 | 1889338.6 | 0.0062 (3/481) | 807.4s | 1.894 | 2 |
| R | 33/68 | 0.4853 | 0.8263/0.8133 | 2184711.2 | 0.0095 (5/525) | 863.2s | 1.824 | 0 |

## Paired Comparisons (task × rep)

| Comparison | Pairs | Ctrl Pass | Treat Pass | b (ctrl only) | c (treat only) | Delta (pp) | McNemar p | Delta Tokens/Cell | Delta Tokens/Success | Delta Wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| C_vs_B | 66 | 30 | 32 | 1 | 3 | 3.03 | 0.625 | -230307.7 | -632632.9 | -94.0 |
| C_vs_R | 66 | 32 | 32 | 2 | 2 | 0.0 | 1.0 | -166042.2 | -342462.1 | -1.9 |
