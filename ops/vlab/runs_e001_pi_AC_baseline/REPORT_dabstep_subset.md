# e001_pi_AC_baseline — dabstep 子集

cells：50（scored 50／pending 0／infra 0）

| 臂 | n | 通過 | 率 | 呼叫/成功 | token/成功 | 逾時 | 均牆 s | vacant_home B |
|---|---|---|---|---|---|---|---|---|
| A | 25 | 13 | 0.52 | 89.62 | 2339843 | 1 | 168.2 | 0 |
| C | 25 | 14 | 0.56 | 61.71 | 1526926 | 1 | 162.7 | 17729022 |

A_vs_C：配對 25，只有 A 過 0、只有 C 過 1，McNemar p=1.0

report.py 無 per-task/per-suite 行；依預註冊計畫 §2（packets/e001_dabstep_analysis.md，round 141）從各格 score.json 直接彙整並在此記錄。McNemar 與 report.py 同式。pending＝格子未完成，不進分母；incomplete pair 不計入 p 值。
