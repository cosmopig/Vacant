# Sandbox comparison

Evidence: real-agent. Completed cells include infra_void in denominators.

| Arm | Hidden pass | Visible pass | Infra void | False success heuristic |
|---|---:|---:|---:|---:|
| A | 8/24 | 15/24 | 1 | 0 |
| A2 | 7/24 | 17/24 | 1 | 0 |
| C | 8/24 | 15/24 | 0 | 0 |
| G | 9/24 | 19/24 | 4 | 0 |

## Paired comparisons

A/A2 control: `{"n": 24, "delta": -0.041666666666666664, "improved": 2, "regressed": 3, "p": 1.0, "ci95": [-0.20833333333333334, 0.125]}`
- C-A: `{"n": 24, "delta": 0.0, "improved": 1, "regressed": 1, "p": 1.0, "ci95": [-0.125, 0.125], "noise_floor": 0.041666666666666664, "decision": "no measurable gain"}`
- G-A: `{"n": 24, "delta": 0.041666666666666664, "improved": 5, "regressed": 4, "p": 1.0, "ci95": [-0.20833333333333334, 0.2916666666666667], "noise_floor": 0.041666666666666664, "decision": "no measurable gain"}`

## Costs (totals)

Incomplete call/token totals are lower bounds (>=), not final costs; UNKNOWN stays unknown. No cost means are estimated.

| Arm | Wall s | Calls | Input tokens | Output tokens | Incomplete cells | Feedback | Vacant bytes | Trace bytes | Workspace bytes (cache/log/other) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | 3608.7490000000003 | >= 106 | >= 291569 | >= 11620 | 1 | 0 | 0 | 0 | {'pytest_cache': 0, 'logs': 0, 'other': 700296} |
| A2 | 3140.37 | >= 81 | >= 189374 | >= 10757 | 1 | 0 | 0 | 0 | {'pytest_cache': 0, 'logs': 0, 'other': 703469} |
| C | 3642.223 | 133 | 329377 | 11863 | 0 | 3 | 422376 | 325897 | {'pytest_cache': 0, 'logs': 0, 'other': 704571} |
| G | 7320.477 | >= 228 | UNKNOWN | UNKNOWN | 4 | 8 | 0 | 0 | {'pytest_cache': 3065, 'logs': 0, 'other': 736247} |

## Per-task matrix

| Task | Sample | Arm | Hidden | Visible | Infra |
|---|---:|---|---|---|---|
| billing | 1 | A | True | True | False |
| billing | 1 | A2 | True | True | False |
| billing | 1 | C | True | True | False |
| billing | 1 | G | True | True | False |
| billing | 2 | A | True | True | False |
| billing | 2 | A2 | True | True | False |
| billing | 2 | C | True | True | False |
| billing | 2 | G | True | True | False |
| csv_export | 1 | A | True | True | False |
| csv_export | 1 | A2 | False | True | False |
| csv_export | 1 | C | True | True | False |
| csv_export | 1 | G | False | False | True |
| csv_export | 2 | A | True | True | False |
| csv_export | 2 | A2 | True | True | False |
| csv_export | 2 | C | True | True | False |
| csv_export | 2 | G | False | True | False |
| duration | 1 | A | False | True | False |
| duration | 1 | A2 | False | True | False |
| duration | 1 | C | False | True | False |
| duration | 1 | G | False | True | False |
| duration | 2 | A | False | True | False |
| duration | 2 | A2 | False | True | False |
| duration | 2 | C | False | True | False |
| duration | 2 | G | False | True | False |
| inventory_output | 1 | A | True | True | False |
| inventory_output | 1 | A2 | False | True | False |
| inventory_output | 1 | C | False | True | False |
| inventory_output | 1 | G | False | True | False |
| inventory_output | 2 | A | False | True | False |
| inventory_output | 2 | A2 | False | True | False |
| inventory_output | 2 | C | False | False | False |
| inventory_output | 2 | G | False | True | False |
| merge_counts | 1 | A | True | True | False |
| merge_counts | 1 | A2 | True | True | False |
| merge_counts | 1 | C | True | True | False |
| merge_counts | 1 | G | True | True | False |
| merge_counts | 2 | A | True | True | False |
| merge_counts | 2 | A2 | True | True | False |
| merge_counts | 2 | C | True | True | False |
| merge_counts | 2 | G | False | False | False |
| money | 1 | A | False | True | False |
| money | 1 | A2 | False | True | False |
| money | 1 | C | False | False | False |
| money | 1 | G | False | True | False |
| money | 2 | A | False | True | False |
| money | 2 | A2 | False | False | False |
| money | 2 | C | False | True | False |
| money | 2 | G | False | True | False |
| pagination | 1 | A | False | False | False |
| pagination | 1 | A2 | False | False | False |
| pagination | 1 | C | False | False | False |
| pagination | 1 | G | True | True | False |
| pagination | 2 | A | False | False | False |
| pagination | 2 | A2 | False | False | False |
| pagination | 2 | C | False | False | False |
| pagination | 2 | G | True | True | False |
| recipients | 1 | A | False | False | False |
| recipients | 1 | A2 | False | False | False |
| recipients | 1 | C | False | False | False |
| recipients | 1 | G | False | True | False |
| recipients | 2 | A | False | False | False |
| recipients | 2 | A2 | False | False | False |
| recipients | 2 | C | False | False | False |
| recipients | 2 | G | True | True | False |
| report_output | 1 | A | False | True | False |
| report_output | 1 | A2 | False | False | True |
| report_output | 1 | C | False | True | False |
| report_output | 1 | G | False | False | True |
| report_output | 2 | A | False | False | True |
| report_output | 2 | A2 | False | True | False |
| report_output | 2 | C | False | True | False |
| report_output | 2 | G | False | True | False |
| sales | 1 | A | False | False | False |
| sales | 1 | A2 | True | True | False |
| sales | 1 | C | False | False | False |
| sales | 1 | G | True | True | False |
| sales | 2 | A | False | False | False |
| sales | 2 | A2 | True | True | False |
| sales | 2 | C | False | False | False |
| sales | 2 | G | False | False | True |
| shipping | 1 | A | False | False | False |
| shipping | 1 | A2 | False | True | False |
| shipping | 1 | C | True | True | False |
| shipping | 1 | G | False | True | False |
| shipping | 2 | A | False | False | False |
| shipping | 2 | A2 | False | False | False |
| shipping | 2 | C | False | False | False |
| shipping | 2 | G | False | False | True |
| stock | 1 | A | False | True | False |
| stock | 1 | A2 | False | True | False |
| stock | 1 | C | False | True | False |
| stock | 1 | G | True | True | False |
| stock | 2 | A | True | True | False |
| stock | 2 | A2 | False | True | False |
| stock | 2 | C | True | True | False |
| stock | 2 | G | True | True | False |

## Infra-void table

| Task | Sample | Arm | Reason |
|---|---:|---|---|
| csv_export | 1 | G | model/process error |
| report_output | 1 | A2 | timeout |
| report_output | 1 | G | timeout |
| report_output | 2 | A | timeout |
| sales | 2 | G | timeout |
| shipping | 2 | G | timeout |

## Contamination flags (retained in denominators)

None detected (heuristic, not proof of isolation).

Missing scheduled cells: `[]`
