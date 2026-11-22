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
