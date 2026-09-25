All strings below are the constants and templates of trace/review.py. They were checked by running the repo's own `memory.assert_ks1_clean` over the whole texts file (clean), the second-person regex `\byou (ignored|failed|forgot|should have)\b` (0 matches; in fact no "you" token at all), and a scan for reputation/score/trust/responsib/punish/accountable in the templates (none). Every rendered line additionally passes `feedback.feedback_ks1_clean(line, actor_tokens)` and the path guard at runtime, or is replaced by the substitute line.

FIXED HEADER (HEADER; also registered in capture.prompt_source as a vacant_feedback prefix):
Before delivery: a review of the recorded steps of this task.

REVIEWER PERSONA (PERSONA; decision §4.2 verbatim; one line):
Take the role of a careful reviewer who reads a draft against the materials given for the task. Check that every specific number, date and name in the deliverable can be traced to a given file, the task message, or a computation done in this task; that every file named in the task was actually opened; and that any claim of testing or verification matches a step that ran. Redo only the parts that do not hold. Anything that remains unverified goes under a heading "Unverified" in the final message.

EVIDENCE LINE TEMPLATES (one "- " line each; quotes ≤ 80 chars, JSON-escaped; at most 10 evidence lines):

unread_material (grouped; one line per prompt-named set):
- Not opened in the recorded steps: {m1}, {m2}, {m3} (the task named {dir_or_files}). Action: open the ones the deliverable depends on and redo those parts; if one is not needed, no change.
  e.g. - Not opened in the recorded steps: materials/brand.md, materials/schedule.md, materials/sales_2025.csv, materials/logo.png (the task named materials/). Action: open the ones the deliverable depends on and redo those parts; if one is not needed, no change.

unsourced_value (per file, ≤ 5 locators per line; each locator repeats the path so "plan.md line 5" is a literal substring):
- {path} line {n} "{value}"; {path} line {m} "{value2}", "{value3}": no source found in the recorded steps. Action: open the given files or compute the value in a command and redo these lines, or label each value as an assumption.
  e.g. - plan.md line 4 "October 1, 2026"; plan.md line 5 "2026-09-20"; plan.md line 8 "$50,000"; plan.md line 11 "$1.2M", "25%": no source found in the recorded steps. Action: open the given files or compute the value in a command and redo these lines, or label each value as an assumption.
  e.g. - answer.txt line 1 "0.61": no source found in the recorded steps. Action: open the given files or compute the value in a command and redo these lines, or label each value as an assumption.
  e.g. - summary.md line 3 "38"; summary.md line 4 "$2,145.50": no source found in the recorded steps. Action: open the given files or compute the value in a command and redo these lines, or label each value as an assumption.

write_before_read:
- {deliverable} was written at step {w}, before {material} was opened at step {o}, and not rewritten since. Action: redo the parts of {deliverable} that depend on it.

unbacked_test_claim, no runner ran:
- Final message says "{claim}"; no test command ran in this task. Action: run `{discovered_command}` and report the result.
  (no discovered command: … Action: run the project's tests and report the result.)
  e.g. - Final message says "All tests pass"; no test command ran in this task. Action: run `python3 -m unittest` and report the result.

unbacked_test_claim, last run failed:
- Final message says "{claim}"; the last test run at step {r} (`{command}`) printed "{excerpt}". Action: fix, re-run the tests, and report the result.
  e.g. - Final message says "tests pass"; the last test run at step 4 (`python3 -m unittest 2>&1 | tail -5`) printed "FAILED (failures=2)". Action: fix, re-run the tests, and report the result.

unbacked_test_claim, edit after the last green run:
- {file} changed after the last passing test run (step {r}; the change is step {w}). Action: re-run the tests and report the result.
  e.g. - textstats/core.py changed after the last passing test run (step 3; the change is step 4). Action: re-run the tests and report the result.

failed_step_ignored:
- step {n} `{command}` failed: "{last_error_line}"; no later step re-ran it or changed {script_or_file}. Action: fix and re-run, or say in the final message that it failed.
  e.g. - step 3 `python3 summarize.py` failed: "KeyError: 'amount'"; no later step re-ran it or changed summarize.py. Action: fix and re-run, or say in the final message that it failed.

dropped_values:
- {path}{ column X}: {M} of the {N} values printed at step {n} are in the file; missing {t1}, {t2}, {t3}, {t4}{ and k more}. Action: write all of them or state why some are left out.
  e.g. - output.xlsx column E: 5 of the 9 values printed at step 1 are in the file; missing PK03/P812203390, PK04/P813300015, PK04/P813300071, PK05/P814400120. Action: write all of them or state why some are left out.

date_outside_data:
- {path} line {n}: sentence ties {stem} to {D}; rows of {csv} are dated {min}..{max}. Action: check the sentence against the data, or state the difference.
  e.g. - report.md line 28: sentence ties sales to 2026-11-15; rows of inputs/sales.csv are dated 2026-07-01..2026-07-05. Action: check the sentence against the data, or state the difference.

project_check:
- Project check `{command}` (run by Vacant on a copy of the project): passed before this task's changes; now {k} tests fail: {id1}, {id2}. Action: fix and re-run.

CONTROL LINES:
- a repeated finding gets the suffix " (still open)" on its line
- Resolved since the last review: {k}.   (only when k > 0)
- overflow: - … and {N} more points of the same kinds.
- substitute when a line fails a guard: - {path} line {n}: finding withheld (wording check)   — or, when the path itself fails the guard: - a finding was withheld (wording check)

FIXED FOOTER (FOOTER; carries the delivery-note request):
This note lists what the record shows; it does not say whether the final answer is right. When done, end your message with three headings: Checked, Fixed, Unverified.

PERSONA-ONLY RENDER (arm B, VACANT_MODE=persona, not run now): HEADER + "\n" + PERSONA + "\n" + FOOTER — byte-identical to the evidence render minus the evidence block and control lines.

NEVER SENT TO THE MODEL: the delivery note, delivery.md/json, report.md, any path under $VACANT_HOME, any actor/model/session id, any consequence or reputation wording.