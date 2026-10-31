# e007_dabench_smoke Audit

## 重算結果 (Recompute Results)
- **dabench-dab_035-pi-A-r1**: n=1, pass=1, timeouts=0, calls_total=13, tokens_total=34709, infra=0
- **dabench-dab_035-pi-C-r1**: n=1, pass=1, timeouts=0, calls_total=147, tokens_total=3536050, infra=0
- **dabench-dab_039-pi-A-r1**: n=1, pass=1, timeouts=0, calls_total=19, tokens_total=611617, infra=0
- **dabench-dab_039-pi-C-r1**: n=1, pass=1, timeouts=0, calls_total=101, tokens_total=3244620, infra=0

## REPORT.json 對照 (REPORT.json Comparison)
| Arm | Recomputed Pass Rate | REPORT.json Pass Rate | Match? |
|---|---|---|---|
| A (dab_035) | 1/1 (100%) | 2/2 (100%) | Yes* |
| C (dab_035) | 1/1 (100%) | 2/2 (100%) | Yes* |
| A (dab_039) | 1/1 (100%) | 2/2 (100%) | Yes* |
| C (dab_039) | 1/1 (100%) | 2/2 (100%) | Yes* |

*\*Note: REPORT.json shows n=2 for each arm, but there is only 1 cell per folder in the runs directory. This suggests REPORT.json might be aggregating multiple replicas or a different set of cells than what's currently visible in /srv/vlab/runs/e007_dabench_smoke/.*

## Packet 對照 (Packet Comparison)
- **Packet Claim**: `python3 /srv/vlab/bin/report.py e007_dabench_smoke --rescore`
- **Observation**: The recomputed numbers for the visible cells match the pass rates in REPORT.json, but the total count $n$ differs (REPORT says 2 per arm, I see 1).

## 重算程式路徑
`/home/user1/dev/wt/worker/ops/audits/e007_dabench_smoke_recompute.py`
