# Local real-agent experiment preregistration — v1

Question: does installing Vacant improve hidden-test pass rate on the twelve
frozen synthetic Python tasks in this directory? This file is committed before
any sandbox batch, including the billing wiring smoke. No task/model selection
will be based on the batch outcomes. Earlier runtime calc smokes are development,
not experimental evidence. Step 1 reference solutions and hidden tests are frozen.

Runtime: CPU-only Ollama, qwen3:8b (digest/version recorded in meta.json),
@earendil-works/pi-coding-agent 0.87.1, OpenAI completions via the tagged local
proxy, think=false / reasoning_effort=none, 32768 context, 4096 max output.
Vacant version and repository SHA, Python and model digest are recorded per run.

Unit: (task, sample). Default one sample; any larger sample count must be chosen
before launching that batch. All 12 tasks are included in the full experiment.
The billing-only smoke is explicitly a wiring check, not evidence of gain.
Each cell has fresh workspace, HOME, agent config and VACANT_HOME. Arms:

- A: ordinary pi with no Vacant installation.
- A2: identical independent rerun; noise-floor control.
- C: same pi argv, after exactly `vacant install --agents pi` in isolated HOME.
- G: visible-test gate, `vacant run --retry revise --max-attempts 3
  --feedback-into both`, relaunching pi with visible failures, not hidden tests.

G is a separate intervention with up to three process attempts; it is not the
zero-config installation effect. A/C/A2 have one process launch, with C's native
Stop feedback inside that session. Same task prompt and pi flags in all arms;
no --no-extensions in any arm. Arm order is shuffled per task/sample using the
batch seed. Default process/cell timeout is 900 seconds. No manual repairs.

Primary outcome: hidden_pass from the independent original-test scorer.
Primary comparisons: C−A and G−A, paired two-sided exact McNemar p-values and
paired percentile-bootstrap 95% CIs (10,000 resamples of task/sample units,
fixed batch seed). Both comparisons reported without multiplicity adjustment;
these are small exploratory synthetic-task comparisons, not general proof.
A−A2 uses the same paired units and is reported as a noise floor.

Decision for each intervention: "gain" only if paired delta > 0, exact p < .05,
and delta > abs(A−A2). Without an A2 floor the decision is not evaluable and
must be "no measurable gain". Otherwise report "no measurable gain".

Infra failures (timeout, model error, harness/install/score crash) are infra_void,
retained in arm denominators and listed separately; primary intention-to-treat
outcome for those cells is failure, irrespective of partial workspace tests.
Only units with both scheduled arms present enter a paired comparison; missing
cells are listed, never imputed. An A2 floor must cover the same paired units.

Secondary: visible pass; false-success heuristic (final assistant text claims
done/tests pass but hidden fails; heuristic, not a semantic judgment); wall time;
model calls and prompt/completion tokens by run_tag; Vacant feedback rounds;
VACANT_HOME/trace bytes; leftover workspace bytes (pytest caches, logs, other).
No proxy rows means UNKNOWN, never zero; missing usage means UNKNOWN tokens.
Costs include all G attempts. Per-task outcomes and infra reasons are published.
Archive workspace, raw stdout/stderr/events, final text, diff, score and progress;
do not give hidden tests or solution overlays to the agent or its feedback.

External Devin arms are documented separately and never pooled with pi arms.
This harness is not an OS security boundary; run only these trusted task fixtures
on this isolated VM. Real model runs require internet only for prior installation.

## External Devin arm (amendment, before any Devin run) — 2026-11-22

Arms are devin-plain, devin-plain2 (A/A2 noise floor), and devin-vacant
(manual visible-gate loop), on 12 tasks × 1 sample. The primary outcome,
paired exact two-sided McNemar test, bootstrap delta interval and gain decision
rule are the same as for the pi arms. External Devin results are never pooled
with pi results.

The 12 devin-plain sessions run first. If devin-plain passes ≥11/12 on hidden
tests, devin-plain2 and devin-vacant are not launched on this task bank; report
"ceiling, not evaluable; harder tasks needed".

## v2 bank (amendment, before any v2 run) — 2026-11-22

Bank: all twelve tasks in `tasks_v2/`, frozen by the per-task SHA256 digests and
reproducible directory-hash recipe in `tasks_v2/FROZEN.json`. Verify those digests
before use. There is no per-task selection, ever: the whole bank is used or the
whole bank is rejected. The existing task contents are frozen without changes.

Calibration: twelve fresh plain Devin sessions, one per task, handing back
`sandbox-devin-cal/<task>-plain`. Calibration outcomes are used **only** for the
bank gate and are never part of any comparison; their workspaces and sessions
must not be reused in comparison arms. Apply the gate only after all twelve
calibration submissions have outcomes; list missing branches, never impute them.

Bank gate: proceed only if calibration plain hidden-pass is **≤8/12**. If it is
above 8/12, report **"ceiling, v2 rejected"**. A new bank must then be built and
pre-registered; do not salvage a subset, modify this bank or change the threshold
after seeing calibration outcomes.

If the bank proceeds, run all three arms fresh: devin-plain, devin-plain2 and
devin-vacant, with **two independent samples per task per arm** (72 sessions;
24 paired task/sample units per comparison). Handback branches are
`sandbox-devin/v2/<task>-<arm>-s<k>`, where arm is `plain`, `plain2` or `vacant`,
and k is 1 or 2. devin-plain2 repeats the plain protocol as the A/A2 noise floor;
devin-vacant uses the same manual visible-gate loop, at most three submissions.

Primary outcome remains independently scored hidden_pass. The **primary
comparison is vacant vs plain**; plain2 is the noise floor. Use the same paired,
two-sided exact McNemar test and paired percentile-bootstrap 95% delta interval
(10,000 resamples, seed 20261122) as before. Report a gain only if delta > 0,
p < .05 and delta > |plain − plain2| on the same paired units. Otherwise report
"no measurable gain"; without the matching plain2 floor the gain is not
evaluable. Never pool v2 comparison results with calibration, v1 or pi results.

Infra and missing-branch handling is unchanged: infra_void cells remain in the
arm denominator and count as primary failures, with reasons reported separately.
Missing branches are listed, never imputed; only units with both scheduled arms
present enter a paired comparison. Report incomplete coverage explicitly rather
than presenting it as the full 24-pair comparison.

Power note: with 24 units, p < .05 needs at least six discordant pairs when none
are against the intervention (six improvements, zero regressions gives two-sided
exact p = 0.03125; five gives p = 0.0625).

## v3 bank (SWE-bench Verified; before any v3 session) — 2026-11-22

Bank: the twelve instance IDs in `v3/SELECTION.json`. Reference submissions and
candidate solve fractions are determined only by the pinned public experiments
results recorded there (experiments commit
`40f164d5b8f1d249bf95a6df8b74b577fd8e519d`, Verified dataset revision
`c104f840cc67f8b6eec6f759ebc8b2693d585d4a`); the outcome-independent gold/base
validation and repository cap are as recorded in that selection. No Vacant,
Devin or pi outcomes enter selection. The whole bank is used or rejected;
there is no subsequent per-instance selection or repair after calibration.

Calibration: twelve fresh plain sessions, one per instance, used only for the
bank gate and never for comparisons. Apply the gate only when all twelve
submissions have outcomes; list missing branches and never impute them.
Proceed only if calibration resolved count is **≤8/12**. Contaminated calibration
cells count as **resolved** for this gate, regardless of their harness outcome,
conservatively toward rejection. Otherwise report **"ceiling, v3 rejected"**;
build and pre-register a new bank rather than salvage a subset.

If the bank proceeds, run plain, plain2 and vacant fresh, with two independent
samples per instance per arm (72 sessions; 24 scheduled paired units). Do not
reuse calibration sessions or workspaces. The primary comparison is vacant vs
plain; plain2 is the A/A2 noise floor. Use paired two-sided exact McNemar and
paired percentile-bootstrap 95% delta intervals (10,000 resamples, seed
20261122), as before. A gain requires delta > 0, p < .05 and
delta > |plain − plain2| on the same paired units; otherwise report "no
measurable gain". Without the matching plain2 floor it is not evaluable.
Never pool v3 comparisons with calibration, v1, v2 or pi outcomes.

Primary outcome: **resolved according to the official SWE-bench harness
3.0.17**, using the per-instance image registry digests pinned in
`v3/SELECTION.json`, on the patch derived from the handback. Derive that patch
by diffing the handback tree against its exact base snapshot. Drop all changes
to every file touched by that instance's `test_patch` before applying the
independent original `test_patch`. Exclude binary files and build, egg-info and
cache artifacts (including build/dist, *.egg-info, __pycache__, *.pyc, pytest,
mypy and ruff caches). A derived patch that fails to apply is **unresolved**,
not infra_void. Harness or Docker failures, including timeouts, are infra_void,
kept in denominators and counted as primary failures, with reasons reported.
Missing submissions are listed, never synthesized; paired comparisons use
only units with all required scheduled outcomes and a matching plain2 floor.
Report any incomplete coverage instead of describing it as a full 24-pair run.

Vacant intervention: the gate runs only that instance's **PASS_TO_PASS** test
IDs from pre-existing base tests, through the kit-root `.venv` Python's pytest
via `vacant run`. Never export or run FAIL_TO_PASS IDs or `test_patch` content
in the gate. The vacant arm gets at most **three submissions** and the gate's
feedback between them. This reveals which existing tests must remain green;
that extra test-selection information and the feedback loop are **part of the
intervention**, not a zero-configuration installation effect. Plain/plain2 do
not get the selected gate IDs. Session setup installs each repository's own
dependencies; the small kit documents the Python ≥3.11 venv recipe.

Contamination policy, fixed before sessions: a cell is contaminated if its
session record shows access to the upstream issue, PR or commit for that
instance; any fork or mirror of the fix; or SWE-bench data, including dataset
pages, the experiments repository or Hugging Face. Audit the complete browser,
shell and search events and the final reply, recording matched evidence and
source locations. The rule concerns observed access, not an assumption that
an agent's pretraining or filesystem was isolated. An unavailable session
record is unknown, not certified clean, and must be disclosed before analysis.

The **primary analysis excludes an entire paired (instance, sample) unit if
any of plain, plain2 or vacant is contaminated**. Apply that same exclusion
mask to the treatment comparison and noise floor. A sensitivity analysis
includes contaminated units with their observed harness outcomes, using the
same statistical and missing/infra rules. Report excluded units and remaining
paired sample size explicitly; retain all cells in the published raw records.
Calibration uses the conservative contaminated-as-resolved rule above instead
of exclusions.

Secondary flag, reported but **not an exclusion**: normalized diff-line
similarity to the gold patch ≥0.9. For both the derived candidate patch and
gold patch, apply the same test-file/artifact exclusions, retain added/deleted
content lines with their +/- polarity, discard diff headers/hunks/context and
empty content, trim and collapse whitespace within each line. In sorted-path
diff order, use `difflib.SequenceMatcher(None, gold_lines, candidate_lines,
autojunk=False).ratio()` (2 × matching lines / total lines). Report this
separately from event-based contamination; similarity alone does not establish
that the session accessed a fix.

### v3 pre-run clarification — 2026-11-22

No v3 session has run. Vacant and its wrapper use kit-root Python >=3.11;
pytest uses the instance's own Python and dependencies from its official
SWE-bench 3.0.17 harness specification, at the per-instance interpreter path
recorded in the kit. No stdlib compatibility shim is used. Measure base P2P
wall time inside the pinned official instance image and set each gate timeout
to max(120 seconds, ceil(3 * measured seconds + 30 seconds)).

Before sessions, freeze concrete pre-existing base-passing pytest node IDs.
Every retained P2P label must be covered; no failing-at-base variant may be
dropped. Omit test-patch-introduced tests even if listed as P2P. Record all
omissions and label-to-node mappings in KIT.json. Ambiguous labels may exclude
base-skipped variants only when covered by passing variants. Once frozen,
any selected test skipped, deselected or not collected causes refusal.
Set OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and MKL_NUM_THREADS to 1 inside
the test runner's environment, independently of the caller.

Pre-run clarification — 2026-11-22: derive the handback patch against a base
snapshot with the same documented tracked-file setup recipe edits applied
(Sphinx tox/setup pins and Astropy build pins). Setup-only changes therefore
produce no candidate patch; additional agent edits remain. The official
harness image already applies its own pre-install steps. No v3 session has run.

Pre-run clarification — 2026-11-23: generated untracked setup outputs are
excluded using the base snapshot's own ignore rules, not the handback's;
tracked source edits remain in the patch. No v3 session has run.

### v3 amendment — 2026-11-23: outside help and PR reviews

Recorded after calibration began and before comparisons. Every v3 comparison
arm prompt (plain, plain2, vacant) includes the identical instruction:
"Do not open a pull request; the pushed branch is the only deliverable."
Platform-default instructions otherwise request PRs, whose reviews can provide
outside help. This instruction also applies to subsequent calibration dispatches.

A cell is flagged **outside_help** if a PR review (Devin Review or human
comments) reached its session before its final push. Audit delivery to the
session and the final-push timestamp, not just PR creation or review publication.
Treat outside_help exactly like contamination: exclude its entire paired unit
from primary analysis, retain it in sensitivity analysis, and count a flagged
calibration cell as resolved for the whole-bank gate. Unknown review/access
verdicts remain unknown; calibration cannot proceed until both are reviewed.

PR creation alone is not outside help. The operator records in the calibration
NOTES.md that PRs #101 (SymPy 15875) and #102 (Matplotlib 24870) were closed
without review feedback reaching either session before its final push. These
reports do not certify other contamination criteria as clean.
