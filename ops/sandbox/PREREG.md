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

V3 amendment — 2026-11-23: replace the three DEVIN_ARMS.md comparison templates with the exact validated calibration-form dispatch texts; this amendment is committed before any comparison session.

## v4 bank — 2026-11-23 (pre-run)

This preregistration is frozen before **any v4 agent session** and is not launch
approval. The final IDs, feasibility evidence, replacements and cap history are
recorded in `v4/SELECTION.json`. Only gold/base feasibility and native kit
controls have run; no calibration or comparison has been launched.

### Bank and calibration

Target: **62 instances × 2 samples = 124 scheduled paired units**. The bank
is exactly the following seeded, feasibility-qualified IDs:

```text
django__django-11400
sphinx-doc__sphinx-10614
matplotlib__matplotlib-23299
sympy__sympy-13974
django__django-11141
matplotlib__matplotlib-26466
django__django-15973
django__django-16256
sympy__sympy-23950
sympy__sympy-20916
sphinx-doc__sphinx-9461
sphinx-doc__sphinx-8595
django__django-15916
sympy__sympy-16597
matplotlib__matplotlib-26208
django__django-13513
django__django-14140
django__django-15957
django__django-16502
sympy__sympy-13798
sympy__sympy-17630
django__django-11820
astropy__astropy-8872
sphinx-doc__sphinx-8638
sympy__sympy-21596
django__django-15022
pydata__xarray-7229
django__django-11477
django__django-11734
django__django-14034
matplotlib__matplotlib-21568
django__django-15695
sympy__sympy-18763
pytest-dev__pytest-5840
astropy__astropy-13977
pytest-dev__pytest-10356
matplotlib__matplotlib-25479
sympy__sympy-20438
pylint-dev__pylint-7080
sympy__sympy-13852
matplotlib__matplotlib-23476
pylint-dev__pylint-8898
matplotlib__matplotlib-20676
sphinx-doc__sphinx-7748
sympy__sympy-17318
scikit-learn__scikit-learn-26194
scikit-learn__scikit-learn-25102
sphinx-doc__sphinx-9602
sphinx-doc__sphinx-10435
astropy__astropy-14182
sphinx-doc__sphinx-11510
sphinx-doc__sphinx-8265
sympy__sympy-21930
sphinx-doc__sphinx-7462
mwaskom__seaborn-3187
psf__requests-6028
pylint-dev__pylint-4970
sphinx-doc__sphinx-9229
sympy__sympy-20428
sympy__sympy-22080
astropy__astropy-8707
sympy__sympy-18199
```

The twelve seeded calibration IDs are:

```text
sympy__sympy-18763
sympy__sympy-21596
astropy__astropy-13977
matplotlib__matplotlib-21568
pydata__xarray-7229
scikit-learn__scikit-learn-26194
django__django-15957
astropy__astropy-8707
pytest-dev__pytest-5840
matplotlib__matplotlib-26466
django__django-14140
sphinx-doc__sphinx-8595
```

Initial feasibility exhausted the seeded draw at cap 12 with 59 instances and
cap 13 with 61. Cap 14 first reached 62. After the approved single repair attempt,
two instances remained unready and were replaced in seeded order:

| Outgoing | Incoming | Reason after one repair attempt |
|---|---|---|
| `astropy__astropy-13398` | `django__django-15695` | Harness pins and approved P2P omissions applied; frozen confirmation still failed `test_cirs_to_hadec` with `TypeError: unsupported operand type(s) for -: 'Time' and 'float'`, preventing a passing gate control. |
| `pydata__xarray-6599` | `sympy__sympy-18199` | Isolated setup and exceptiongroup repaired; discovery still could not collect the pre-existing `test_polyval[timedelta-True]` selector. |

The retained bank had 60 ready instances. The next officially feasible candidate
under cap 14, `astropy__astropy-13033`, failed native base P2P at `test_fold` and
was not admitted. Other visited candidates failed recorded official feasibility
criteria. Exhausting cap 14 left 60 ready; **15** is the smallest final cap
filling 62 while preserving ready instances. Both incoming instances independently
passed gold/base official controls and native A/B/C and regression controls.
Docker 429s delayed validation but were retried, never counted as rejections.
Every visited outcome, outgoing/incoming pair and exhausted cap is recorded in
SELECTION.json. The two outgoing IDs were calibration members, so the twelve
IDs above were recomputed from the final sorted bank with seed 20261125.
Use the same pinned Verified revision, experiments commit and ten ranked public
reference submissions as v3. Widen the reference solve-fraction rule to
**0 ≤ f ≤ 0.5**: the strict v3 rule `0 < f < 0.5` leaves only **35** eligible
instances after removing the twelve v3 IDs, insufficient for the new bank.
Continue excluding `>4 hours` and all twelve v3 instances. The widened pool
has 95 eligible instances: 49 at f=0, 35 at f=0.1–0.4, and 11 at f=0.5.

Shuffle sorted eligible IDs with seed **20261124** and take the first feasible
instances under repository cap **12**. Feasible means official-harness gold
resolved, base unresolved, and an observed F2P failure in the base control.
Only if that cap cannot fill 62 after feasibility may it increase, one at a
time, to the smallest sufficient cap. Record every exhausted cap and why it
changed. Infrastructure failures are not candidate rejections; Docker pull
rate limits back off and retry the same instance. If fewer than 62 are feasible
at any cap, take every feasible instance and replace the planned count and
power below with the actual count and exact power before preregistration.
No selection may use v4 agent outcomes.

Draw twelve calibration IDs using
`random.Random(20261125).sample(sorted(final_instance_ids), 12)`. Run twelve
fresh plain sessions, branches `sandbox-devin-cal4/<id>-plain`. Calibration
is only the whole-bank gate; it never enters comparisons. Apply it only when
all twelve outcomes and contamination/outside-help audits are available.
Proceed only if the conservative resolved count is **≤8/12**. Contaminated
or outside-help calibration cells count as resolved regardless of their
harness outcome. Unknown audits leave the gate incomplete. Above 8/12 report
**"ceiling, v4 rejected"**; never salvage a subset or change the threshold.

### Comparison, outcome and analysis

After the calibration gate, run all bank IDs fresh in **plain/plain2/vacant ×
s1/s2**: 372 sessions for the target bank, 124 paired (instance, sample) units.
Branches: `sandbox-devin/v4/<id>-<arm>-s<k>`, arm in plain/plain2/vacant,
k in 1/2. Do not reuse calibration workspaces or sessions. Primary comparison
is **vacant vs plain**; plain2 is the identical independent A/A floor.
Never pool with calibration, v1–v3, or pi outcomes.

Primary outcome is **official SWE-bench harness 3.0.17 resolved**, using the
instance image registry digests frozen by selection. Score handback trees
independently, with the original hidden `test_patch`, not gate acceptance or
agent success claims. Derive patches against the exact setup-normalized base.
Unlike v3, **retain agent test edits, including edits to paths also touched by
the official test patch**; do not blanket-strip those paths. The root manifest
`VACANT_TESTS.txt` alone is dropped as gate metadata. No agent test is excluded
because it is an agent test or merely because it matches a base ignore rule.
Normal non-source binary/build/cache exclusions remain. Report apply failures
as unresolved. Harness/Docker failures and timeouts are infra_void, kept in
denominators as primary failures with reasons. List missing branches without
synthesizing results; report incomplete paired coverage explicitly.

Use two-sided exact McNemar and paired percentile-bootstrap 95% delta CIs,
**10,000 resamples, seed 20261122**. Apply the same paired-unit mask to vacant
vs plain and plain2 vs plain. A gain requires **delta > 0, p < .05, and
delta > |plain − plain2|** on those same units; otherwise report **"no measurable
gain"**. Without the matching A/A floor the decision is not evaluable. If null,
report the CI upper endpoint in percentage points as the **largest gain not
ruled out** by that interval, not as evidence of equivalence or zero effect.

### Exact planning power

V3 supplies 8 discordances among 24 paired units, so `q = 8/24`. For target
gain `delta = .15`, set `psi = (q + delta)/(2*q) = .725`, the favorable
direction probability conditional on discordance. Reproduce with:

```python
from vacant_network.research import mcnemar_power
q = 8 / 24
psi = (q + .15) / (2 * q)
power = mcnemar_power(124, q, psi, alpha=.05)
# 0.805571660767604 (80.5571660767604%)
```

The function sums exact rejection probabilities over `K ~ Binomial(124, q)`
and `B | K ~ Binomial(K, psi)` using the two-sided exact McNemar test at .05.
The previously considered 48×2 design gives only `0.6745570062630449` power.
The approved 62×2 design reaches the 80% planning target under these assumptions.
They assume independent paired units and unchanged discordance, not a promise
of achieved v4 power. If selection is undersized, explicitly preregister
`mcnemar_power(2 * actual_bank_size, q, psi, alpha=.05)` and its actual result.

### Agent-supplied-test gate

The vacant arm runs `vacant run --suite ../gates/<id>` with the same v3 manual
feedback loop, **at most three submissions**. It supplies its **own tests**,
not experimenter-provided new acceptance tests. Before submitting, write root
`VACANT_TESTS.txt`, one explicit pytest node ID per line. Missing/empty manifests
are refused with a clear message. Plain/plain2 do not open the gate suites.

1. **A (red):** archive workspace git HEAD, the history-free base snapshot,
   into a pristine temporary copy; apply the same documented tracked setup
   normalization as v3. Vacant strips `.git` from its frozen candidate; read
   HEAD from the original workspace's git metadata, but take the manifest and
   test overlays from the frozen candidate. Overlay **only** the test files named by the
   listed nodes, not candidate implementation, new helper modules or conftest
   files unless they themselves contain listed tests. Use the instance Python.
   At least one listed node must be collected and actually fail by assertion
   or error inside its test body. A test-file collection/import failure, fixture
   or unittest setup failure, skip, deselection, or synthetic strict XPASS is
   not a qualifying red result. Other listed nodes need not fail at A.
2. **B (green):** run the listed nodes on the candidate with the instance Python.
   Every listed node must be collected and pass; none may be skipped,
   deselected, failed or unexecuted.
3. **C (regression):** apply the unchanged v3 frozen pre-existing P2P check.
   Missing, skipped, deselected, failing or unexecuted selected nodes refuse.

Every refusal names the step and node IDs. Keep v3's per-instance timeout
`max(120, ceil(3 * measured_base_P2P_seconds + 30))`; the three steps share that
gate budget with the wrapper's ten-second margin. Freeze concrete P2P node IDs,
label mappings, omissions, environment recipes and measurements before sessions,
as in v3. BLAS/OMP/MKL threads are one in the test runner. No additional F2P IDs
or original `test_patch` content are exported to the agent or used in gate
feedback; the byte-exact supplied-issue exceptions below remain unchanged.
`VACANT_TESTS.txt` is not passed to the official scorer; **the agent's tests are**.
Extra test-writing, visible P2P selection and iterative feedback are all part
of the intervention, not a zero-configuration installation effect. Acceptance
does not establish hidden correctness or prevent bypass; this is not an OS
security boundary. The HEAD base assumption is part of the dispatch contract:
do not commit implementation changes over the history-free base before gating.

### Contamination, outside help and secondary records

**2026-11-23 owner-approved v4 kit exceptions (before agent sessions):**
Sphinx 8595 has no official P2P labels. Step C will instead freeze the existing
base-passing nodes in the explicitly approved existing
`tests/test_ext_autodoc.py`; official scoring is unchanged. The originally
affected `tests/test_ext_autodoc_automodule.py` is new in the official test patch
and is not exported or used for Step C. Matplotlib 23299 freezes only official
P2P nodes that are collected and pass on base. Its four uncollected parameter
labels are recorded as omissions in KIT.json, not silently counted as passing.
For Matplotlib 26466 and compiled packages generally, Step A populates the
pristine base with untracked workspace `.so`/`.pyd` artifacts and generated
version files. If candidate compiled sources change (`.c`, `.cpp`, `.pyx`, `.h`
and other native-source equivalents), do not borrow candidate binaries: rebuild
extensions in the pristine base using the recorded instance recipe instead.
The rebuild shares the existing per-instance gate deadline. Collection/import
errors still do not qualify as red. This artifact reuse is part of the
intervention, not an independent proof that compiled binaries match source.
Setup-generated native sources are registered against the pristine installed
base by digest, canonicalizing kit/environment paths so relocation alone is not
an agent edit. A changed tracked native source always triggers the base rebuild.
Preparation records native parameter-ID translations (absolute paths and pytest
duplicate-ID spelling), preserving official-label provenance; frozen checks
rebase paths when Vacant verifies a frozen tree. Step C still executes the
unmodified v3 runner, with the selected tree on its import path before pytest.
Native Astropy builds use the instance NumPy headers without build isolation
and force a rebuild. The owner subsequently approved the v3 rule for Matplotlib
21568, Sphinx 7462 and Astropy 13398: after reinstating harness version-spec
pins, omit measured base-failing or warning-erroring P2P nodes and list each
omission. At least one red/green control remains mandatory.
Archive-only extension rebuilds recover SCM version metadata from the installed
instance distribution rather than requiring Git history in the pristine copy.
Django 16256 keeps the official problem statement byte-exact, including the
gold-added text already present in that supplied issue. This is a documented
provided-prompt provenance exception, not an exception for any gate or source
file. All arms receive the same unchanged text. All decisions, frozen selections,
omissions, native recipes and provenance exceptions are recorded in v4 `KIT.json`.

**2026-11-23 subsequent owner decisions, before bank commit or agent runs:**
Astropy 13398, sklearn 26194, Astropy 14182 and Sphinx 7462 receive the same
byte-exact supplied-prompt provenance exception as Django 16256. This includes
code examples already in the issue; every arm receives identical text. No gate,
source-file or official-scoring exception is granted. Astropy 13398 was
subsequently replaced and is not part of the final bank. The harness version specs
(pins, pre-install steps and environment variables) remain the setup authority.
Xarray setup and runners explicitly disable the user site and install
exceptiongroup into the prefix. The xarray specs pin pytest 7.4.0 but do not
directly pin exceptiongroup; the explicit compatible transitive dependency is
frozen at 1.1.3 rather than relying on a package outside the prefix. Pytest setup
and runners set SETUPTOOLS_SCM_PRETEND_VERSION to the instance's harness-version
key (5.1 or 7.2), recovering version identity lost with history-free snapshots.

An instance still unready after one honest repair attempt is replaced, not
silently dropped. Preserve ready instances; scan the original seeded draw for
the next officially feasible, kit-ready candidate under the current repo cap.
Raise the cap minimally only after exhausting that draw under the smaller cap.
Record each outgoing/incoming ID, reason, failed attempts and cap escalation in
SELECTION.json. Recompute the seed-20261125 calibration sample only if a removed
instance belonged to it. No v4 agent outcome may influence replacements.

The full-bank leak audit matches literal gold-line/test-name fingerprints at
identifier boundaries in exported files and base exceptions. This avoids the
substring false positive `a = []` inside the unchanged v3 runner's `extra = []`;
an actual `a = []` export is still flagged unless present at base. No source or
gate-file provenance waiver is granted. Prompt-only exceptions remain as above.

Pre-run review correction: A/B/C subprocesses explicitly prepend the instance
interpreter's bin directory to PATH. Original native preparation already supplied
that PATH; the correction restores it under Vacant's sanitized runner. On frozen
Sphinx 10614, an actual CLI control initially refused C (one pass, four Graphviz
skips) and passed after the correction. Historical native-control runtime hashes
are preserved separately from the updated shipped-runtime digest in KIT.json;
the other 61 native controls were not rerun for this PATH-only correction.

CI portability correction: canonicalize the system temporary directory before
checking archived test paths for symlinks. This permits macOS's `/var` alias
without relaxing refusal of symlinks inside the pristine base. A fixture covers
both a symlinked system temp root and an archived test symlink.

Use the same v3 event-based contamination policy: observed access to this
instance's upstream issue/PR/commit, a fork/mirror of its fix, or SWE-bench data
(including dataset pages, experiments or Hugging Face) flags contamination.
Audit complete browser, shell, search and final-reply records with matched
evidence/source locations. Unavailable evidence is UNKNOWN, not certified clean;
this does not certify absence of pretraining contamination or filesystem access.

Review feedback (Devin Review or human PR comments) reaching a session before
its final push flags **outside_help**, treated identically to contamination.
PR creation alone is not outside help. Every arm's dispatch includes exactly:
**"Do not open a pull request; the pushed branch is the only deliverable."**
Exclude an entire (instance, sample) unit from primary analysis if any of its
plain/plain2/vacant cells is contaminated or outside_help; use the same mask
for the A/A floor. Keep all raw cells. Include flagged units with observed
outcomes in the sensitivity analysis under the same missing/infra rules.
Disclose unknown audits and excluded/remaining sample counts before analysis.

Retain v3's ≥.9 normalized diff-line gold-similarity flag as secondary evidence,
not a contamination verdict or exclusion, using the same v4 manifest/test
handling for both patches. Record submissions, raw gate output, exit codes and
step/node verdicts where available; unshown actions and missing receipts remain
UNKNOWN. Record wall time and valid cost/usage evidence; unavailable usage is
UNKNOWN, not zero. Never describe visible acceptance as proof of a better agent.
