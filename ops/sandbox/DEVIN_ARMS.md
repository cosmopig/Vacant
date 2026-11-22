# External-agent arms (not pooled with pi)

These arms measure a different agent and intervention. A Devin session is not
a local executable that `vacant run` can resume, so do not claim native Stop
mediation or automatic retries for Devin. Do not give the session hidden tests,
reference overlays, the full repository or previous-arm results. Separate fresh
sessions/workspaces for each task/sample; record session id, time and cost if known.

## devin-plain prompt

> Work only in the attached task workspace. {task.prompt}
> Preserve your final workspace as a tar archive whose root contains the source
> files, and provide your final explanation and actual test output. Do not read
> external task-bank files or change the acceptance harness.

## devin-vacant prompt

> Work only in the attached task workspace. {task.prompt}
> Before delivery, run the supplied visible-only Vacant acceptance command.
> Read any failure feedback and repair the workspace, at most three submissions.
> Deliver the workspace tar, raw command outputs, signed gate receipts and final
> explanation. Do not read hidden tests or reference solutions.

The operator must supply an authoritative visible suite outside the workspace.
The suite must use vrun's `check_*` or `main` protocol, not bare pytest tests.
`run.gate_suite` builds a wrapper that runs the ORIGINAL visible pytest source
against the candidate; no hidden tests are included. Example after preparing it:

```bash
vacant run --workspace /work/task --suite /work/original-visible-wrapper \
  --run-dir /work/receipts/submission-1 --sandbox none \
  --retry revise --max-attempts 3 --feedback-into both -- \
  python -c 'import sys; print(sys.argv[1])' '{VACANT_FEEDBACK}'
```

This launches a no-op delivery command, not Devin. It **cannot repair anything**:
automatic internal retries merely recheck the unchanged workspace. Do not count
them as independent agent attempts. The honest closest equivalent is an external
manual loop: Devin reads the visible feedback, edits, and submits again with a
new receipts directory, up to three submissions. Record that additional protocol
and budget; it is NOT the same treatment as pi-G. A simpler `--retry none` gate
per manual submission is preferable when not demonstrating the literal command.
`--sandbox none` assumes a trusted isolated VM, not malicious-code protection.

Score both delivered archives independently, outside the agent session:

```bash
.venv/bin/python ops/sandbox/score.py TASK_ID /deliveries/workspace.tar.gz
```

Acceptance is a verdict, not an OS write barrier. Do not advertise rejection as
preventing Devin from writing files. Success claims and final tests remain
independent recorded outcomes, not substitutes for the hidden scorer.
