# Fixture report — personal preference pilot v0.1

這些是工程邊界，不是本人偏好，也不是模型試驗。P5 沒有跑。
F01–F05b 的 exit code 是 `python -m vacant_network check` 這個行程的退出碼。
F05c 之後的檢查沒有對應的 intake 退出碼；actual_exit 0 表示觀察與預期一致，1 表示這條夾具沒有對上。

| Fixture | Exit expected | Exit actual | OK | Command | Expected | Actual |
|---|---:|---:|---|---|---|---|
| F01 | 0 | 0 | yes | `/usr/bin/python3 -m vacant_network check --contract /workspace/ops/personal_pilot/reporting/work/F01/control/contract.json --dir ops/personal_pilot/reporting/work/F01/artifact --json` | accept; human_acceptance null; contract validate exit 0 | check=0 validate=0 outcome=accept human=None integrity=True |
| F02 | 40 | 40 | yes | `/usr/bin/python3 -m vacant_network check --contract /workspace/ops/personal_pilot/reporting/work/F02/control/contract.json --dir ops/personal_pilot/reporting/work/F02/artifact --json` | FAIL observed 3 expected recomputed 4 | {"check_id": "total_cost_units", "status": "FAIL", "observed": 3, "expected_or_constraint": {"recomputed": 4, "max": 20, "note": "boolean is not an integer"}, "evidence_path": "plan.json#/total_cost_units", "error_type": "artifact"} |
| F03 | 40 | 40 | yes | `/usr/bin/python3 -m vacant_network check --contract /workspace/ops/personal_pilot/reporting/work/F03/control/contract.json --dir ops/personal_pilot/reporting/work/F03/artifact --json` | FAIL required, group, dependency/order, and both budgets; preference text ignored | failed=['choice_group_0', 'dependencies_and_sequence', 'required_options', 'total_cost_units', 'total_person_hours'] |
| F04 | 40 | 40 | yes | `/usr/bin/python3 -m vacant_network check --contract /workspace/ops/personal_pilot/reporting/work/F04/control/contract.json --dir ops/personal_pilot/reporting/work/F04/artifact --json` | FAIL and the unknown id is still present twice | ["no_such", "no_such", "label_audit"] |
| F05a | 41 | 41 | yes | `/usr/bin/python3 -m vacant_network check --contract /workspace/ops/personal_pilot/reporting/work/F05a/control/contract.json --dir ops/personal_pilot/reporting/work/F05a/artifact --json` | checker internal fault is UNKNOWN, intake hold | status=UNKNOWN detail=exit 2: checker fault: injected checker fault |
| F05b | 41 | 41 | yes | `/usr/bin/python3 -m vacant_network check --contract /workspace/ops/personal_pilot/reporting/work/F05b/control/contract.json --dir ops/personal_pilot/reporting/work/F05b/artifact --json` | timeout is UNKNOWN and timed_out | status=UNKNOWN evidence={'rc': None, 'timed_out': True, 'wall_ms': 401, 'argv0': '/usr/bin/python3', 'independent': True} |
| F05c | 0 | 0 | yes | `/usr/bin/python3 -c reconcile_report after deleting sidecar` | original intake accept kept; report_integrity_unknown; stop | {"ok": false, "code": "report_integrity_unknown", "stop": true, "intake_outcome": "accept"} |
| F05d | 0 | 0 | yes | `/usr/bin/python3 -c reconcile_report after swapping candidate hash` | stale sidecar hash is report_integrity_unknown; intake outcome unchanged | candidate file hashes do not match the files submitted to this check |
| F06 | 2 | 2 | yes | `/usr/bin/python3 -c assert_calibration_sources` | H label and unseen source refused; no model call | holdout_refused=True unseen_refused=True calls=0 |
| F07 | 0 | 0 | yes | `/usr/bin/python3 -c SingleCallBackend missing usage` | second call usage_unknown, old usage not reused, third call not sent | first=completed second=usage_unknown second_usage=None third_sent=False generates=2 |
| F08 | 0 | 0 | yes | `/usr/bin/python3 -c BudgetLedger authorize and timeout` | no request when the budget is already spent; timeout row kept; no resend | blocked=budget_stopped/False timeout=timeout after_sent=False generates=1 |
| F09 | 0 | 0 | yes | `/usr/bin/python3 -c metrics.regressions` | pass 1 PASS and pass 2 FAIL is a regression, not only the final | [{"task_id": "T01", "arm": "A"}] |
| F10 | 0 | 0 | yes | `/usr/bin/python3 -c revision_prompt gate off versus gate on` | gate-off prompt uses the fixed sentence; gate-on includes the checker line | off_has_fixed=True off_leaked=False on_has_line=True |
| F11 | 0 | 0 | yes | `/usr/bin/python3 -c stage2_metrics incomplete reviews` | denominator stays 6 and 48; missing reviews and failed cells are listed, not dropped | rows=48 denom=6 adopt=None missing=['T01', 'T02', 'T03', 'T04', 'T05', 'T06'] failed=['T06:A:p2'] |
| F12 | 0 | 0 | yes | `/usr/bin/python3 -m vacant_network.personal fixture-run` | 36 unique calls, 48 row identities, 6 first drafts per representation, blind bundle may dedupe | rows=48 calls=36 summary_drafts=6 structured_drafts=6 blind_display=6 blind_rows=48 |

Failed: none
