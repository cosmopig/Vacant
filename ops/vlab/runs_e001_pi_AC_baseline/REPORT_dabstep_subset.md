# e001_pi_AC_baseline — dabstep 子集

cells：52（scored 52／pending 0／infra 0）

| 臂 | n | 通過 | 率 | 呼叫/成功 | token/成功 | 逾時 | 均牆 s | vacant_home B |
|---|---|---|---|---|---|---|---|---|
| A | 26 | 13 | 0.5 | 108.62 | 3057129 | 1 | 228.5 | 0 |
| C | 26 | 14 | 0.5385 | 64.93 | 1645720 | 1 | 169.6 | 18531396 |

A_vs_C：配對 26，只有 A 過 0、只有 C 過 1，McNemar p=1.0

report.py 無 per-task/per-suite 行；依預註冊計畫 §2（packets/e001_dabstep_analysis.md，round 141）從各格 score.json 直接彙整並在此記錄。McNemar 與 report.py 同式。pending＝格子未完成，不進分母；incomplete pair 不計入 p 值。
