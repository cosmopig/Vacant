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
