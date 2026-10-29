# e001_pi_AC_baseline — polyglot_py 子集

cells：68（scored 68／pending 0／infra 0）

| 臂 | n | 通過 | 率 | 呼叫/成功 | token/成功 | 逾時 | 均牆 s | vacant_home B |
|---|---|---|---|---|---|---|---|---|
| A | 34 | 15 | 0.4412 | 117.07 | 3299729 | 6 | 627.5 | 0 |
| C | 34 | 20 | 0.5882 | 86.2 | 2346870 | 4 | 607.7 | 5224614 |

A_vs_C：配對 34，只有 A 過 2、只有 C 過 7，McNemar p=0.1797

report.py 無 per-task/per-suite 行；依預註冊計畫 §2（packets/e001_dabstep_analysis.md，round 141）從各格 score.json 直接彙整並在此記錄。McNemar 與 report.py 同式。pending＝格子未完成，不進分母；incomplete pair 不計入 p 值。
