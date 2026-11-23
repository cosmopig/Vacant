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

## Visible kit and branch handbacks

Clone only `sandbox-devin-kit`. It contains twelve task directories, exact user
prompts in `prompts/<task>.txt`, visible gates and no hidden tests or solutions.
Use a fresh session for each task/arm. `devin-plain2` repeats the plain protocol
with the same prompt; follow the ceiling stopping rule in `PREREG.md` before
launching plain2 or vacant. At the kit root, install the gate environment with:

```bash
python -m venv .venv
. .venv/bin/activate
pip install git+https://github.com/cosmopig/Vacant pytest
```

From `<task>/`, each manual submission uses a new receipts directory (N=1..3):

```bash
vacant run --workspace . --suite ../gates/<task> --run-dir ../receipts/<task>-N --sandbox none --retry none -- true
```

The kit ignores `/receipts/`. Gate scripts explicitly use `<kit>/.venv/bin/python`:
main's vrun verifier runs system `python3` with a cleaned PATH, not the activated
venv. The wrapper searches workspace ancestors because vrun checks a frozen copy
under `receipts/`. pytest is a separate prerequisite, not a Vacant runtime dependency. Hand back
only the task workspace at the **tree root** of branch
`sandbox-devin/<task>-plain`, `-plain2`, or `-vacant`, not the full kit tree.
Do not commit receipts or gates into the task workspace.

On the operator's private PR checkout, score an explicit list of handbacks:

```bash
.venv/bin/python ops/sandbox/score_devin.py --out ~/sandbox-runs/devin1 \
  sandbox-devin/billing-plain sandbox-devin/billing-plain2 sandbox-devin/billing-vacant
.venv/bin/python ops/sandbox/analyze.py ~/sandbox-runs/devin1
```

The scorer fetches from `origin` (override `--repo`/`--remote` for a local bare
repository), records commit identities, archives and scores each branch tree,
and scans the diff against the kit's original task subtree for contamination.
Only submitted branches have cells; all 36 planned task/arm slots remain in the
metadata so unsubmitted branches are listed as missing, never imputed. Costs
and feedback counts are UNKNOWN; final-message claims are not assessed. This
is a separate `external-devin` run, never pooled with the pi experiment.

## Frozen v2 bank: calibration before comparisons

Use only branch `sandbox-devin-kit-v2`, never the full Vacant repository. The
operator verifies all twelve digests in `tasks_v2/FROZEN.json` before use. The
whole bank is used or rejected: no per-task selection. Follow the dated v2 bank
section in `PREREG.md`; the older v1 ceiling rule above does not govern v2.

Run twelve fresh plain calibration sessions first, one per task, handing back
`sandbox-devin-cal/<task>-plain`. Calibration is used only for the bank gate,
never in comparisons. Do not proceed with missing calibration submissions. If
calibration hidden-pass is above 8/12, report "ceiling, v2 rejected" and build and
pre-register a new bank. If it is ≤8/12, launch all three comparison arms fresh,
two samples per task: `sandbox-devin/v2/<task>-<arm>-s<k>` with arm
`plain|plain2|vacant` and k `1|2`. Never reuse calibration sessions, solutions or
workspaces. Never pool calibration, v1, pi or v2 comparison outcomes.

### V2 calibration / devin-plain / devin-plain2 session prompt

Substitute TASK and HANDBACK_BRANCH before starting the session. Use the same
prompt for calibration, plain and plain2; only the handback branch differs.

> Work only on TASK in this visible-only kit. First read `prompts/TASK.txt` at
> the **kit root** and follow that exact task request and `TASK/SPEC.md`.
> `prompts/` is not inside the task directory. Work in `TASK/`, preserve the
> existing public APIs required by SPEC.md, and run the visible tests there.
> Do not invoke the Vacant gate for this arm. Do not read another session's work,
> external task-bank files, hidden tests or reference solutions, and do not alter
> the gates. Deliver only the task workspace at the tree root of
> HANDBACK_BRANCH, not the whole kit. Include your final explanation and actual
> test output; do not include `.venv/`, gates or receipts in the workspace.

### V2 devin-vacant session prompt

> Work only on TASK in this visible-only kit. First read `prompts/TASK.txt` at
> the **kit root** and follow that exact task request and `TASK/SPEC.md`.
> `prompts/` is not inside the task directory. Work in `TASK/`, preserve the
> existing public APIs required by SPEC.md, and run the visible tests there.
> Before delivery, use the README's kit-root `.venv` recipe, then from `TASK/`
> submit through `vacant run --workspace . --suite ../gates/TASK --run-dir
> ../receipts/TASK-N --sandbox none --retry none -- true`. Read failure feedback,
> repair and submit again if needed, using fresh N=1..3 receipts directories;
> stop after at most three submissions. Do not read another session's work,
> external task-bank files, hidden tests or reference solutions, and do not alter
> the gates. Deliver only the task workspace at the tree root of
> HANDBACK_BRANCH, not the whole kit. Provide your final explanation, actual
> test output, raw gate outputs and receipts separately from the workspace.

Each session starts from a fresh kit clone; `.venv/` and `receipts/` are ignored
at the kit root. The README's venv recipe requires Python ≥3.11 and allows an
explicit `PYTHON` interpreter path; the VM's system Python 3.10 is too old.
Use a separate operator copy for independent hidden scoring.
The visible gate is a manual submission protocol, not a resumable Devin command
or native Stop hook. Gate acceptance is not the independent primary outcome.

### Operator scoring (not session commands)

The scorer recognizes v1, calibration and v2 comparison branch names automatically
and rejects mixed protocols in one run. V1 defaults are unchanged. V2 protocols
select `tasks_v2/` and `sandbox-devin-kit-v2` and verify every frozen task digest.
Use a fresh output directory for each run; calibration and comparison evidence
cannot share a run directory. Scoring never launches an agent.

```bash
# With no branch arguments, request the complete preregistered schedule.
.venv/bin/python ops/sandbox/score_devin.py --protocol calibration \
  --out ~/sandbox-runs/devin-v2-calibration
# Only after the bank proceeds, and after fresh comparison sessions return:
.venv/bin/python ops/sandbox/score_devin.py --protocol v2 \
  --out ~/sandbox-runs/devin-v2-comparison
.venv/bin/python ops/sandbox/analyze.py ~/sandbox-runs/devin-v2-comparison
```

Calibration writes `calibration.json` and `calibration.md` and prints its scored
hidden-pass count against the ≤8/12 gate. Its evidence and `calibration-plain`
arm are separate from A/A2/G. A missing calibration submission makes the gate
incomplete, never a pass or rejection inferred from a partial denominator.
Infra-void submissions count as primary failures and remain in the denominator.
The report is "proceed" at ≤8/12 only with all twelve outcomes, otherwise
"ceiling, v2 rejected" above 8/12. Calibration is never a comparison input.

Explicit branch arguments score only those submissions; the metadata still
declares the whole twelve-task schedule (72 comparison cells). `missing_branches`
lists every scheduled branch absent from the run, including branches not
requested; `unrequested_branches` distinguishes those from requested-but-absent
remote refs. No missing cells are synthesized. Comparison samples stay distinct
as sample indices 1 and 2, with plain/plain2/vacant mapped to A/A2/G. Record
incomplete coverage; do not present partial paired results as a full 24-pair run.
The operator, not an automatic launch mechanism, applies the calibration gate.

## V3 SWE-bench comparison dispatch — 2026-11-23 amendment

Use only the whole selected bank and only after the v3 calibration gate proceeds.
Each comparison is fresh, with two samples per instance; never reuse calibration
work. This amendment adopts the validated calibration prompt form before any
comparison session. Placeholders: `<id>` instance, `<arm>` plain|plain2|vacant,
`<k>` 1|2. Title: `Sandbox v3 <id> <arm> s<k>`.

### V3 plain

```text
Clone github.com/cosmopig/Vacant branch `sandbox-devin-kit-v3` (this is the kit root). Inside it, clone only branch `sandbox-v3/<id>` into `<id>/` (`git clone --single-branch --depth 1 --branch sandbox-v3/<id> https://github.com/cosmopig/Vacant <id>`). The issue to fix is `prompts/<id>.txt` at the kit root. Set up the test environment exactly as the README's `<id>` section says (its Python version and commands, creating `.envs/<id>/bin/python`). Fix the issue in the `<id>/` source and run whatever tests you think are relevant. Do not open any other branch of this repo or any other session's work. Do not look up this issue's upstream GitHub issue, PR or commit, any fork or mirror of the fix, or any SWE-bench data or leaderboard. Do not open `gates/`. When done, push the contents of `<id>/` as the tree root (no kit, no .envs, .venv, receipts or build artifacts) to a new branch `sandbox-devin/v3/<id>-<arm>-s<k>`. Do not open a pull request; the pushed branch is the only deliverable. Reply with the branch name, your final explanation, and the actual output of the tests you ran.
```

### V3 plain2

```text
Clone github.com/cosmopig/Vacant branch `sandbox-devin-kit-v3` (this is the kit root). Inside it, clone only branch `sandbox-v3/<id>` into `<id>/` (`git clone --single-branch --depth 1 --branch sandbox-v3/<id> https://github.com/cosmopig/Vacant <id>`). The issue to fix is `prompts/<id>.txt` at the kit root. Set up the test environment exactly as the README's `<id>` section says (its Python version and commands, creating `.envs/<id>/bin/python`). Fix the issue in the `<id>/` source and run whatever tests you think are relevant. Do not open any other branch of this repo or any other session's work. Do not look up this issue's upstream GitHub issue, PR or commit, any fork or mirror of the fix, or any SWE-bench data or leaderboard. Do not open `gates/`. When done, push the contents of `<id>/` as the tree root (no kit, no .envs, .venv, receipts or build artifacts) to a new branch `sandbox-devin/v3/<id>-<arm>-s<k>`. Do not open a pull request; the pushed branch is the only deliverable. Reply with the branch name, your final explanation, and the actual output of the tests you ran.
```

### V3 vacant

```text
Clone github.com/cosmopig/Vacant branch `sandbox-devin-kit-v3` (this is the kit root). Inside it, clone only branch `sandbox-v3/<id>` into `<id>/` (`git clone --single-branch --depth 1 --branch sandbox-v3/<id> https://github.com/cosmopig/Vacant <id>`). The issue to fix is `prompts/<id>.txt` at the kit root. Set up the test environment exactly as the README's `<id>` section says (its Python version and commands, creating `.envs/<id>/bin/python`). Fix the issue in the `<id>/` source and run whatever tests you think are relevant. Do not open any other branch of this repo or any other session's work. Do not look up this issue's upstream GitHub issue, PR or commit, any fork or mirror of the fix, or any SWE-bench data or leaderboard. Before delivering, create the kit-root `.venv` with Vacant as the README says, then submit through the gate with the README's `vacant run` command from inside `<id>/` (`--suite ../gates/<id>`, `--run-dir ../receipts/<id>-N`, N = 1, 2, 3, timeout from `../gates/<id>/selection.json`). Exit 0 means accepted. Exit 20 means refused: read its feedback, fix, and submit again, at most 3 submissions. Do not edit `gates/`. Include each submission's raw gate output in your reply. When done, push the contents of `<id>/` as the tree root (no kit, no .envs, .venv, receipts or build artifacts) to a new branch `sandbox-devin/v3/<id>-<arm>-s<k>`. Do not open a pull request; the pushed branch is the only deliverable. Reply with the branch name, your final explanation, and the actual output of the tests you ran.
```

Calibration uses the plain template with handback branch
`sandbox-devin-cal3/<instance_id>-plain`, including the same no-PR instruction.
Platform-default PR instructions must not override this dispatch. If PR review
feedback reached a session before its final push, record `outside_help` and its
evidence: treat it as contamination for primary paired exclusions and as resolved
for the calibration gate. A PR alone is not that flag; check feedback delivery
and timing. Leave unaudited verdicts unknown, including the distinct access-based
contamination verdict, until session-log review is complete.

## V4 SWE-bench calibration and comparison dispatch — 2026-11-23

Use only `sandbox-devin-kit-v4` and the frozen 62-instance v4 bank. Run the 12
fresh plain calibration sessions on the recorded subset before any comparison;
proceed only with all twelve scored and at most 8/12 resolved. Calibration never
enters comparisons. Each comparison session is fresh, with two samples per
instance; never reuse calibration work or pool v4 with earlier versions.
Placeholders: `<id>` instance, `<arm>` plain|plain2|vacant, `<k>` 1|2.
Comparison title: `Sandbox v4 <id> <arm> s<k>`.
The prompts below retain the v3 dispatch text except for v4 paths and the
approved arm instructions. This document does not authorize launching sessions.

### V4 calibration

```text
Clone github.com/cosmopig/Vacant branch `sandbox-devin-kit-v4` (this is the kit root). Inside it, clone only branch `sandbox-v4/<id>` into `<id>/` (`git clone --single-branch --depth 1 --branch sandbox-v4/<id> https://github.com/cosmopig/Vacant <id>`). The issue to fix is `prompts/<id>.txt` at the kit root. Set up the test environment exactly as the README's `<id>` section says (its Python version and commands, creating `.envs/<id>/bin/python`). Fix the issue in the `<id>/` source and run whatever tests you think are relevant. Do not open any other branch of this repo or any other session's work. Do not look up this issue's upstream GitHub issue, PR or commit, any fork or mirror of the fix, or any SWE-bench data or leaderboard. Do not open `gates/`. When done, push the contents of `<id>/` as the tree root (no kit, no .envs, .venv, receipts or build artifacts) to a new branch `sandbox-devin-cal4/<id>-plain`. Do not open a pull request; the pushed branch is the only deliverable. Reply with the branch name, your final explanation, and the actual output of the tests you ran.
```

### V4 plain

```text
Clone github.com/cosmopig/Vacant branch `sandbox-devin-kit-v4` (this is the kit root). Inside it, clone only branch `sandbox-v4/<id>` into `<id>/` (`git clone --single-branch --depth 1 --branch sandbox-v4/<id> https://github.com/cosmopig/Vacant <id>`). The issue to fix is `prompts/<id>.txt` at the kit root. Set up the test environment exactly as the README's `<id>` section says (its Python version and commands, creating `.envs/<id>/bin/python`). Fix the issue in the `<id>/` source and run whatever tests you think are relevant. Do not open any other branch of this repo or any other session's work. Do not look up this issue's upstream GitHub issue, PR or commit, any fork or mirror of the fix, or any SWE-bench data or leaderboard. Do not open `gates/`. When done, push the contents of `<id>/` as the tree root (no kit, no .envs, .venv, receipts or build artifacts) to a new branch `sandbox-devin/v4/<id>-<arm>-s<k>`. Do not open a pull request; the pushed branch is the only deliverable. Reply with the branch name, your final explanation, and the actual output of the tests you ran.
```

### V4 plain2

```text
Clone github.com/cosmopig/Vacant branch `sandbox-devin-kit-v4` (this is the kit root). Inside it, clone only branch `sandbox-v4/<id>` into `<id>/` (`git clone --single-branch --depth 1 --branch sandbox-v4/<id> https://github.com/cosmopig/Vacant <id>`). The issue to fix is `prompts/<id>.txt` at the kit root. Set up the test environment exactly as the README's `<id>` section says (its Python version and commands, creating `.envs/<id>/bin/python`). Fix the issue in the `<id>/` source and run whatever tests you think are relevant. Do not open any other branch of this repo or any other session's work. Do not look up this issue's upstream GitHub issue, PR or commit, any fork or mirror of the fix, or any SWE-bench data or leaderboard. Do not open `gates/`. When done, push the contents of `<id>/` as the tree root (no kit, no .envs, .venv, receipts or build artifacts) to a new branch `sandbox-devin/v4/<id>-<arm>-s<k>`. Do not open a pull request; the pushed branch is the only deliverable. Reply with the branch name, your final explanation, and the actual output of the tests you ran.
```

### V4 vacant

```text
Clone github.com/cosmopig/Vacant branch `sandbox-devin-kit-v4` (this is the kit root). Inside it, clone only branch `sandbox-v4/<id>` into `<id>/` (`git clone --single-branch --depth 1 --branch sandbox-v4/<id> https://github.com/cosmopig/Vacant <id>`). The issue to fix is `prompts/<id>.txt` at the kit root. Set up the test environment exactly as the README's `<id>` section says (its Python version and commands, creating `.envs/<id>/bin/python`). Fix the issue in the `<id>/` source and run whatever tests you think are relevant. Do not open any other branch of this repo or any other session's work. Do not look up this issue's upstream GitHub issue, PR or commit, any fork or mirror of the fix, or any SWE-bench data or leaderboard. Before delivering, write at least one test that reproduces the issue (it must fail on the original code and pass with your fix) inside the `<id>/` test suite, and list its pytest node IDs, one per line, in `<id>/VACANT_TESTS.txt`. Then create the kit-root `.venv` with Vacant as the README says and submit through the gate with the README's `vacant run` command from inside `<id>/` (`--suite ../gates/<id>`, `--run-dir ../receipts/<id>-N`, N = 1, 2, 3, timeout from `../gates/<id>/selection.json`). Exit 0 means accepted. Exit 20 means refused: read its feedback, fix, and submit again, at most 3 submissions. Do not edit `gates/`. Include each submission's raw gate output in your reply. When done, push the contents of `<id>/` as the tree root (no kit, no .envs, .venv, receipts or build artifacts) to a new branch `sandbox-devin/v4/<id>-<arm>-s<k>`. Do not open a pull request; the pushed branch is the only deliverable. Reply with the branch name, your final explanation, and the actual output of the tests you ran.
```

Platform-default PR instructions must not override this dispatch. If PR review
feedback reached a session before its final push, record `outside_help` and its
evidence: treat it as contamination for primary paired exclusions and as resolved
for the calibration gate. A PR alone is not that flag; check feedback delivery
and timing. Leave unaudited verdicts unknown, including the distinct access-based
contamination verdict, until session-log review is complete.
