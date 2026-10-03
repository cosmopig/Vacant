# Design review: step-level accountability for one person using one agent

Reviewer stance: I read the thesis chapters 03/06/07/08, the 2026-09-24 universal-intake decision, the R535 prereg, and the load-bearing modules (`reputation.py`, `router.py`, `registry.route`, `auditor.py`, `intake/{contract,policy,verifiers}.py`, `adapters/{hook,hookpolicy,agents,run}.py`, `vrun/{attest,hookcli}.py`, `ops/intake/{mock_model,e2e_four_agents}.py`). Every recommendation below is tied to something that already exists or to a measured result. Where I disagree with the draft I say so and give the cost of being wrong.

## 0. The one-paragraph verdict

The draft is right on the spine: deterministic blame over an event-sourced write history, graded confidence, localized KS-1-clean feedback, and an open-issues report the user cannot miss. It is wrong, or at least too ambitious for v1, on three things: (1) it treats "what the actor had read" as observable, when the hook layer gives you a lower bound on reads and no view of model context at all; (2) it lets heuristic attribution touch reputation, which is exactly where the 0/368 permanent-exclusion result and the Who&When accuracy numbers say you will hurt honest actors; (3) it plans to show routing advice to the agent, which reintroduces the KS-1 problem through the back door. Fix those three and the design is defensible tonight with the mock model, and testable with the 12B model next week.

The single most important reframing: **blame is a product feature for the human; reputation is a side-effect that must be starved of noise.** The user's stated goal is "the problem is raised instead of drowned" and "output converges to requirement". Both are served by localized findings delivered to the right place. Neither requires reputation to be accurate on day one.

---

## Q1. Who decides "wrong" for general tasks

### Recommendation

Three sources, strictly ordered by authority, and only the first two can gate:

1. **Contract claims** (existing `intake/verifiers.py`: exists, forbid_paths, sha256_pin, text, json_schema, csv_total, citations_resolve, python_checks, command, review) — the only thing that produces `reject`. Keep `policy.decide` untouched.
2. **Human pointing** — a new primitive `vacant point <path>[:<start>-<end>] "<what is wrong>"` that writes a signed finding bound to `artifact_sha256` + location. It is a `review`-class object (already exists as a verifier with signature binding), so it can gate if the human says `--required`. This is the honest oracle for open-ended tasks; the thesis already concedes there is no free judge (test-oracle problem, 7.1).
3. **Proactive deterministic consistency checks** — produce **advisory findings** that go into the open-issues report and into blame, but **never** into `policy.decide`. They are a separate object (`Finding`, not `ClaimResult`) so the accept/reject rule is not changed by adding them.

Do **not** add any model-judged "is this wrong" step. The team's own number kills it: same-pool review accuracy 0.7552 vs 0.7522 for always-pass; 145/147 review votes on failing items said pass. A model judge for general tasks will be a constant "looks fine" with a 14% miss rate on the things that matter, and it will be blamed on Vacant.

### Which proactive checks are deterministic enough to build

Build these two first; both produce locations, both are cheap, both hit the user's own example ("cross-checking numbers against sources read"):

| Check | Rule | Output | Known false positives |
|---|---|---|---|
| **Unsourced number** | For every numeric token in the deliverable with ≥3 significant digits or a unit/percent sign, look for the same value (normalized: thousands separators, ±1 ulp at the reported precision) in the observed read-set (pinned inputs + command stdout + fetched pages recorded by hooks). Not found ⇒ finding `unsourced_number` at `file:line:col`. | location + value + read-set coverage | Derived numbers (sums, ratios). v1 mitigation: if the deliverable contains a table, also try column sums / row sums of pinned CSVs (reuse `csv_total`'s normalizer). Report as "no source observed", never as "wrong". |
| **Unhandled failed command** | A tool step ran a shell command with exit≠0 (or stdout matching a traceback/`error:` pattern) and no later step re-ran an equivalent command (same normalized argv) with exit 0, yet the deliverable claims the corresponding thing (tests pass, build ok, file generated). | step id + command sha + deliverable location that makes the claim (text match on "pass", "success", "generated", configurable) | Agent legitimately abandoned that path. Mitigation: only fire when the deliverable text asserts success. |

Second tier, worth it but not tonight: **quote provenance** (quoted spans ≥8 words must appear verbatim in the read-set; `citations_resolve` already does this for citations), **dangling reference** (deliverable names a file/column/section that does not exist in inputs or workspace).

Do not build: "consistency between report and inputs" in the general semantic sense. That is a model judge with a different name.

### Cost and how you know you chose wrong

- Cost: the read-set must be recorded (Q8 #1). Number-provenance is O(tokens × read-set size) — index the read-set by normalized numeric value once per session; it is fine.
- Wrong if: on real sessions, >30% of `unsourced_number` findings are derived numbers the user considers obviously fine. Measure: user dismiss rate per finding type (the `vacant point --dismiss <finding_id>` action gives you this for free).
- Wrong the other way if: planted wrong numbers that *do* appear nowhere in the inputs are missed >10% of the time. Measure with the planted-fault bank tonight.

---

## Q2. Actor granularity and reputation keys

### Recommendation: three actor classes, but only one gets a Beta cell

Record everything as an actor in the trace (agent, sub-agent, model, tool, input file, web page, MCP server, command) because blame needs the full lineage graph. But only **(platform, agent-definition, model, family)** gets a reputation cell. Information sources get a **tally**, not a reputation.

Why not reputation for tools/sources: `reputation.py` is five-dimensional (factual/logical/relevance/honesty/adoption) with decay, slash and UCB. None of that means anything for `sales.csv` or `example.com`. What the user actually needs about a source is a count: "this input contradicted the deliverable 3 times in 2 sessions". A count with a link to the evidence is more useful than a posterior mean and cannot be mis-read as "we distrust this file".

### Key mapping in the single-user, single-agent setting

The thesis rule is "credit follows memory, not body" and the code makes stream_id = genesis hash so that wipe ⇒ new triple ⇒ credit resets. In the single-agent setting the thing that plays the role of "memory" is the **instruction bundle that defines the actor** — a sub-agent's definition file, a custom agent's system prompt, the skills it is given. That is what persists across sessions, what the human edits, and what should reset credit when it changes.

| Key slot | Meaning in this setting | Notes |
|---|---|---|
| `stream_id` | sha256 of the actor's definition bundle (sub-agent `.md`, custom agent config). Main agent with no definition file ⇒ `"main"` | Editing a sub-agent's instructions ⇒ new stream ⇒ fresh cell. This is exactly the existing wipe semantics and it is *right*: the thing you were rating no longer exists. |
| `branch_id` | platform + major version (`claude/2.1`, `codex/0.156`, `opencode/1.18`, `pi/0.87`) | The same definition behaves differently across platforms (feedback reached the model on 3/4 platforms in the E2E run); that difference must not be averaged away. |
| `substrate` | model id, **tri-state provenance**: `observed` (proxy saw it), `claimed` (transcript says so), `unknown` | Keep substrate in the key (the docstring's "brain A bad, brain B launders" argument still holds). A `claimed` substrate is labeled as such in any display. |
| `family` | task family from the contract: the sorted set of verifier kinds used (`csv_total+text`, `python_checks`, …) unless the owner sets `family` explicitly | Cheap, deterministic, and it is what actually predicts whether a (definition, model) pair will do well. |

Honest boundary to write into the docstring: in this setting every cell will have n in the single digits for a long time. `reputation.py` already warns that family-splitting drops per-cell n by 1/N. So the product must **display counts and the interval, never a bare score**, and must never take an action from a cell with n < 5. (Q6 and Q8 #5.)

### Cost and how you know you chose wrong

- Cost: one extra field on the trace actor record (`definition_sha256`), and a `tally` table beside `Reputation`.
- Wrong if: users edit sub-agent definitions so often that no cell ever reaches n=5. Measure: median n per cell after 30 days of dogfooding. If it is <3, collapse `stream_id` to "definition path" instead of "definition hash" and accept the laundering hole (document it as raises-cost-not-prevents).

---

## Q3. What routing means when one person uses one agent

### Recommendation: build (ii) first, then (iii); build (i) only as a non-text channel, and possibly never

When a person is driving one agent, "routing" collapses to three very different things:

| | What it is | Who receives the signal | KS-1 exposure | Heterogeneity available |
|---|---|---|---|---|
| (ii) recommend agent/model for next time | Advice to the **human** | human | none — KS-1 is about text shown to the model | real: 4 platforms × several models, and the E2E run already shows platform-level differences |
| (iii) `vacant do --agent auto` | Vacant picks the platform/model for a headless run | nobody (non-text opportunity channel) | none | same as (ii) |
| (i) which sub-agent the agent should delegate to | Advice shown to the **model** | model | full — "sub-agent X has a bad record" is prompt engineering by the thesis's own definition | low: usually one main agent and a handful of sub-agents on the same model |

(ii) is the only one that is both honest and cheap. It is a leaderboard per family with counts, rendered in the session-end report: "For `csv_total+text` tasks: claude/2.1+gemma-12b 4/5 accepted; codex/0.156+gemma-12b 2/5; n is small." That is literally `registry.leaderboard(niche, substrate, family=…)` with counts attached.

(iii) is (ii) plus `Router.pick` and is the one real non-text consequence channel you have. It is also the only place where the thesis's routing evidence (E10, 20→11, p=0.093) has a chance to reproduce with real heterogeneity, because the candidates are different platforms/models rather than personas of one model.

(i) as text is a KS-1 violation waiting to happen. If you want (i) at all, do it the way the thesis says consequences must work: through opportunity, not text. Concretely, a `pre_tool` deny on `Task`/`spawn` for a sub-agent definition whose cell is below a floor **with n≥5 and provable faults only**, with a KS-1-clean reason ("this sub-agent is not available in this session"). I would not ship that in v1 either: with n that small you will block the wrong sub-agent, and there is no measurement that this channel helps anyone.

How to keep KS-1 if any routing information leaks into agent-facing text: it does not, by construction. The feedback renderer (Q4) has no actor field. Attribution lives in the ledger and the human report. Add an executable guard: `feedback_ks1_clean(text)` = `memory.assert_ks1_clean` plus a rejection of any actor identifier (sub-agent names, model ids, `definition_sha256`) in agent-facing text. Do not extend `KS1_FORBIDDEN` itself — it is frozen for experiment comparability.

### Cost and how you know you chose wrong

- Cost of (ii): near zero. Cost of (iii): `vacant do` already exists; add candidate discovery over installed agents.
- Wrong if: users never use (iii) because they have one agent and one model. Measure: (iii) invocations vs `vacant do <explicit agent>` after a month. If <10%, stop investing and keep (ii) as a report line.

---

## Q4. Intervene during the work or only at the end

### Recommendation: detect at the step, deliver at the turn boundary, escalate to per-step only for regressions

The R535 lesson is not "intervene early"; it is "the channel decides whether the model ever sees the text" (file: 1/46; argv: +86 pp). The E2E run then showed the Stop channel reaches the model on pi/Claude Code/Codex but not on `opencode run`. So the channel question dominates the timing question. Design accordingly:

1. **Detection is continuous and cheap.** After every tool step that writes to a file matched by `deliverable.include`, re-run the cheap required claims (`exists`, `text`, `json_schema`, `csv_total`, `citations_resolve` — all sub-second) and the two proactive checks. Record the result against the step id. This is what makes blame exact later: you know the first step after which claim X went PASS→FAIL without any bisection.
2. **Delivery is at the turn boundary by default** (existing `decide_stop` → `continue` + text), one consolidated message, deduplicated by finding id, with a "since last time" diff so the agent is not re-told what it already fixed. This is the measured channel. Keep the existing `max_feedback_rounds` and the `not_agent_fixable` short-circuit.
3. **Per-step interruption only for a regression on a required claim** (a claim that was PASS and is now FAIL after this exact step). That is the one case where the value of a message is highest and the false-positive risk is lowest. Even then, do not deny the tool; deliver the finding through the platform's next available measured channel. Where a platform has a `post_tool` context channel that you have *measured* reaching the model, use it; where not, queue it for Stop. Do not assume a channel works because the docs say so — the repo's own convention is [RUN] vs [DOC].

What not to do: per-step feedback for every finding. Three reasons: (a) a mid-refactor workspace legitimately fails checks; (b) each message costs context and the thesis already found that the agent reads filenames and skips contents when the signal is weak; (c) PreToolUse hooks have a 30 s budget and any expensive check there will time out and silently skip the hook — a gap you then have to report.

### Feedback text shape (KS-1-clean, localized)

```
The task contract's checks do not pass yet (feedback from `vacant check`, not a final decision):
- totals_recomputed: FAIL — report.md:12 says "Total revenue: 999".
  The pinned input data/sales.csv sums to 60 (column "amount", 6 rows).
  This value first appeared at step 7 (write to report.md).
- unsourced_number (advisory): report.md:18 "23.5%" was not found in any input or command output this session.
Run `vacant check` to re-check before finishing.
```

Facts, locations, sources. No "you", no actor names, no consequence language. The step number is a fact about the workspace history and is useful to the agent (it can look at what it did at step 7); the actor behind step 7 is not in this text.

### Cost and how you know you chose wrong

- Cost: continuous detection adds one verifier pass per deliverable write. With the cheap verifiers that is tens of milliseconds. `python_checks`/`command` are excluded from continuous mode (run at Stop only).
- Wrong if: attempts-to-accept does not drop vs the current generic `feedback_text`, or M7 (feedback text present in the next model request) is <0.9 on the platforms where Stop is known to work. Both are measurable tonight with `MOCK_LOG` and next week with the proxy.
- Also wrong if: per-step regression messages fire more than ~1 per 20 tool calls on real sessions. That means "regression" is catching transient states; raise the threshold to "regression that survives the next N steps".

---

## Q5. Keep the intake gate as the judge?

### Recommendation: keep it, extend results with locations, add a separate `Finding` object, add a one-line contract path

Keep because: it is the only part of the system that survived a 60-item adversarial review with a red test per item, it already has the four-state semantics you need (FAIL vs UNKNOWN is exactly "agent fault vs cannot tell"), `authority=fact` already encodes "the agent cannot prove a fact with its own files", and `hidden` claims give you a place for owner-reserved acceptance. Restructuring would throw away the hardening for no user-visible gain.

Three surgical extensions:

1. **`ClaimResult.evidence.locations: [{path, start_line, end_line, kind, value}]`** populated by every verifier that can (text, csv_total, citations_resolve, json_schema, python_checks with tracebacks). `results_digest` does not include evidence, so signatures and archived runs are unaffected.
2. **`Finding`** — a new object for human pointing and proactive checks: `{finding_id, kind, severity: gate|advisory, locations, value, source_locations, step_id?, actor?, confidence: provable|lineage|heuristic|gap, dismissed_by?}`. Stored in the ledger alongside the decision; rendered in the report; consumed by blame. Gate-severity findings only come from a signed human `point --required`; they enter `decide` as a `review` claim so the decision rule stays the same.
3. **`vacant contract quick`** — the minimal contract a normal user will actually write for a general task. Today's scaffold (`exists` + `forbid_paths`) checks nothing the user cares about. The minimum that makes accountability possible is: what the deliverable is, what the inputs are (pinned), and one thing that must be true.

```
vacant contract quick \
  --deliverable report.md \
  --input data/sales.csv \
  --must "Total revenue" \
  --objective "Summarize Q3 sales and recommend one action"
```

which generates: `deliverable.include=[report.md]`, `inputs.sales` pinned, claims = `exists(report.md)`, `text(must_contain=["Total revenue"])`, `forbid_paths(secrets)`, and — because a CSV input exists — a `csv_total` claim scaffolded with `authority=fact` that the user can fill or delete. Anything the user did not write is marked `required:false` so the scaffold cannot reject on its own guesses. The open-issues report tells the user what was and was not checkable ("1 required claim, 2 advisory, 0 human review").

The user's earlier rejection ("several local verifiers + a release gate is not accountability") is not an argument against the gate; it is an argument that the gate alone does not say *where* or *who*. Locations + findings + trace answer that. The gate stays the judge; the trace becomes the witness.

### Cost and how you know you chose wrong

- Cost: verifier changes are additive; `Finding` is a new table; `quick` is CLI sugar.
- Wrong if: real users still do not write contracts. Measure: fraction of `vacant do`/hooked sessions with a contract beyond the scaffold after two weeks of dogfooding. If <50%, the next move is inferring a draft contract from the first user prompt (deliverable file names, mentioned inputs) and asking the user to confirm — still human-signed, still no model judge.

---

## Q6. Penalties per confidence grade

### Recommendation

| Grade | What it means | Reputation update | Ledger |
|---|---|---|---|
| **provable** | Deterministic re-run of the failing claim on the reconstructed workspace flips at exactly this step, and the offending value is not present in any pinned input | `record_review(score=0, weight=1.0)` on the matching dim (factual for values, logical for code/tests, honesty only if the step's own output claimed success while its command failed). **No `slash`** in the single-user product path. | full finding + evidence hashes |
| **lineage-exact** | Offending value appears verbatim in content the step observably read, and that content is a pinned input or a recorded external source | **No update to the agent.** Increment the *source* tally. Record `input_fault` with the input's pinned sha256 and the source location. | full finding |
| **lineage-internal** | Offending value came from an earlier step's output (sub-agent reply, command stdout) | Propagate: re-run the grading on the producing step. The writing step gets nothing. | chain of steps |
| **heuristic** | Blame by line-history only, or value matched by containment without a deterministic flip | **No reputation update.** Report only, with the grade shown. | finding, marked heuristic |
| **gap** | Unexplained workspace change, hooks absent for part of the session, transcript missing | **No reputation update to any actor.** Increment the session's `coverage` gap counter (a property of the platform integration, shown in the report). | finding of kind `gap` |

Why no `slash` at all in this path: the thesis measured that the current slash shape (λ=1) excludes permanently (0/368 returned), that the harm to honest actors misjudged by blind spots was never measured, and CLAUDE.md freezes the λ change because it would require re-running the B-layer six scenarios. In a single-user setting with n<10 per cell, one wrong provable fault (verifier bug, flaky command, non-hermetic sandbox) would end a sub-agent's usefulness forever with no appeal. A weight-1.0 negative review plus decay does the honest thing: the cell's mean drops, it recovers with evidence, and the human can see the count that caused it. If you later want teeth for a multi-actor deployment, that is the frozen experiment, not this product.

Should input faults or gaps touch anyone's reputation, including the human who wrote the requirement? **No.** Humans do not get Beta cells: Raji's point is that accountability chains must end at a human, not that humans are one more agent in the table; and rating your only user is user-hostile with n=1. What input faults *should* do is show up prominently in the report in the user's own words: "report.md:12 repeats data/sales.csv row 4, which says 999; if that is wrong, the input is wrong." That is the "distinguish input fault from agent fault" requirement, satisfied without a score.

One more rule: **a dispute wins.** `vacant point --dismiss <finding_id>` (human-signed) reverses the reputation effect of a provable finding. Provable means "the verifier flipped", and the verifier can be wrong (7.4: passing a check ≠ meeting the requirement; the converse is also true). The ledger keeps both the finding and the dismissal.

### Cost and how you know you chose wrong

- Cost: none beyond what `record_review` already does; the tally table from Q2.
- Wrong if: honest sub-agents' cells still drift to the floor because verifier false positives are frequent. Measure: rate of dismissed provable findings. If >10%, the `provable` bar is too low — require the flip to reproduce on two independent re-runs (hermetic sandbox each time).

---

## Q7. Tonight's demo and the preregistered real-model experiment

### Tonight (mock model, four real agents): "one symptom, three causes, one blind spot"

The most convincing thing you can show without a model is that the same wrong deliverable is attributed differently depending on where the error entered, with evidence that re-runs. Use the existing `e2e_four_agents.py` lab (mock provider, hooks, ledger) and add four scripted scenarios on the same report-from-CSV task:

| Scenario | Plant | Expected verdict | Expected grade | Evidence shown |
|---|---|---|---|---|
| A input fault | `sales.csv` row 4 is 999 (pinned that way); script writes "Total 999" faithfully | `totals_recomputed` FAIL (fact claim), `input_fault` | lineage-exact → source | value found at `sales.csv:4`; agent cell untouched |
| B agent fault | inputs sum to 60; script writes "Total 999" from nowhere | FAIL | provable (flip at write step; value not in read-set) | re-run of `csv_total` on state before/after step k |
| C code-step fault | sub-step runs `python calc.py` whose stdout says 999 because `calc.py` (written at step j) sums the wrong column; report copies it | FAIL | lineage-internal → step j (the script write), not the report write | chain: report write ← command stdout ← calc.py write |
| D blind spot (negative control) | Same as B, but the hooks are disabled for the middle of the session (simulate `--bare` or a hook error) | FAIL | **gap**, not agent fault | report says "steps 4–8 unobserved; cannot attribute" |

Run each on all four agents. The result table is: 16 cells, expected 16/16 correct grades, with D producing a `gap` and not a false blame. Add the M7 analog from `MOCK_LOG`: does the localized feedback text appear in the next model request on pi/Claude Code/Codex (expect yes) and not on `opencode run` (expect no, known). That last line matters: it is the honest boundary that the demo carries the R535 lesson forward.

What this proves and what it does not (say it on the slide): it proves the mechanism attributes correctly when the plant is clean and the recorder saw everything; it does not prove anything about a real model's convergence. That is the next experiment.

### Next: the preregistered real-model experiment (team, local 12B)

Name it whatever the next R number is; the design matters more than the name.

**Question:** does trace-localized feedback converge outputs to requirements better than generic failure feedback, at equal attempt budget, and is either better than equal-budget resampling?

**Arms** (all: max 3 draws, same argv, same model, `reasoning_effort` fixed as in R535, feedback via the prompt channel only — the file channel is already ruled out):
- **RS** — 3 independent draws, no feedback (the R535 control).
- **RF** — generic feedback: today's `feedback_text` (claim id + verifier detail).
- **RL** — localized feedback: claim id + location + offending value + source excerpt + first-appearance step, rendered by the Q4 template, KS-1-guarded.
- Optional and only if budget allows: **RL−src** — RL without the source excerpt, to separate "location" from "where the right value is".

**Bank** (two layers, reported separately, never merged — the R535 rule):
- **L1 general tasks (n=50)**: report-from-CSV/JSON with `csv_total`/`json_schema`/`text` claims and hidden checks; half the items carry a **decoy** in the inputs (a plausible wrong number in a column the task does not ask for) so that lineage has something to say. This is where RL should win if it wins anywhere.
- **L2 code tasks (n=40)**: LCB-style with visible/hidden split; here "localized" is mostly the traceback the verifier already gives, so RL ≈ RF is the honest prior.

**Primary outcome:** M1 = `accepted ∧ hidden checks pass` (reject counts as 0), paired McNemar, RL vs RF, one confirmatory test per layer, Holm across the two layers. **Secondary (descriptive):** RL vs RS, RF vs RS, false delivery (visible pass ∧ hidden fail), tokens per correct delivery, M7 (feedback in next request; predict ≥0.95 for both feedback arms or the run is NOT_TRIGGERED), and a **convergence curve**: number of failing required claims after draw 1, 2, 3 per arm — this is the closest measurable proxy for the user's "felt convergence".

**Budget matching:** attempts-matched by design (3 draws each). Token cost reported per arm; if RL's tokens exceed RF's by >20% (longer prompts), add a token-matched sensitivity analysis but do not let it replace the primary.

**Pre-written predictions:** L1: RL − RF ≥ +10 pp on decoy items, ~0 on non-decoy items; L2: |RL − RF| < 5 pp. State table copied from R535 §六 with the same order (INVALID → NOT_TRIGGERED → CEILING_TOO_LOW → CONFIRMED_POSITIVE → CONFIRMED_NEGATIVE → RULED_OUT → INCONCLUSIVE) and the same direction guards.

**Power:** n=50 gives ~0.89 power for +30 pp and roughly 0.4–0.6 for +10 pp (the R460 numbers). Write down in advance that RULED_OUT/INCONCLUSIVE is the likely landing for a +10 pp true effect and that you will not add n after seeing data.

**If RL ≈ RF everywhere:** that is a real result: localization adds nothing beyond what the verifier's detail already carries, and the blame machinery is justified only as a human-facing report, not as a convergence lever. Say that in the prereg so nobody can call it a failure later.

---

## Q8. Top five ways this fails in practice, and the cheapest mitigation

1. **The read-set is a lower bound and you will mis-grade absence as agent fault.** Reads via `cat`/`sed`/`python open()` are only inferable from command strings; sub-agent contexts and everything the model already had in context are invisible to hooks; web pages fetched by the agent's own tools are visible only if the tool reports them. Mitigation: never emit "agent fault" from absence of a read. The grade for "value not found in observed reads" is `heuristic` unless the flip is provable. Every report carries `read_coverage: {observed_reads, inferred_reads, unobservable: true|false|null}` in tri-state. Test tonight: scenario A′ where the input is read via `cat` in bash, not the Read tool; the grade must still be lineage-exact (command-string inference) or degrade gracefully to heuristic, never to provable-agent-fault.

2. **Snapshotting the workspace on every tool call blows the hook budget, hooks time out, and you get silent gaps.** PreToolUse has a 30 s budget; an agent that touches a `node_modules` tree will make a full-tree hash exceed it. Mitigation: hash only paths matched by `deliverable.include` + contract `inputs` + files the tool call names; short-circuit on (size, mtime, inode); store content in a local content-addressed store under `$VACANT_HOME` (the chain carries hashes only, preserving `hookcli` boundary 1 — no payloads in the chain); do everything else asynchronously at Stop. Measure p95 hook wall time; if >200 ms, the design is wrong for that platform.

3. **Feedback drowns or is ignored.** Mitigation is structural: one message per turn boundary, ≤12 lines, stable finding ids, "since last time" diff, no per-finding messages except regressions. Measure M7 and attempts-to-accept; if attempts do not fall vs generic feedback in the real-model run, cut the message to the single highest-severity finding.

4. **Confidently wrong blame destroys the user's trust in Vacant faster than no blame.** A verifier false positive or a flaky command produces a "provable" agent fault that the user knows is wrong. Mitigation: the confidence grade is mandatory in every rendering; "show evidence" re-runs the flip live; `point --dismiss` exists from day one and reverses the reputation effect. Before shipping, attribution precision on the planted bank must be ≥0.9 for the provable grade and the negative control must produce `gap`, not blame. Also: archive the Who&When paper (Zhang et al., ICML 2025) in `參考文獻/_引用備份/` before citing it anywhere — it is not in the thesis literature chapter and CLAUDE.md requires archived citations.

5. **Reputation in a single-user setting has no n, so advice is noise or, worse, punitive after one bad run.** Mitigation: no exclusion anywhere in this path (Q6); never render a score without its count and interval; no action below n=5; decay as configured. Measure instability: the fraction of (ii) recommendations that flip after one more observation. If >30% at n=5, raise the floor to n=10 or drop (ii) to a plain history table.

Two more that are cheap to state and cheap to fix:

6. **Hooks removed or `--bare` ⇒ no trace at all, and the report looks the same as a clean one.** Mitigation: `coverage` is a first-class tri-state line on every report and in the ledger (`recorder: full|partial|absent`); `vacant do` records without hooks; the ledger records `submit_on_end` origin. The thesis's five-tier vocabulary already exists for exactly this; reuse the words.

7. **Transcript ingestion is self-report.** Model ids and sub-agent turns read from the agent's own session files are `claimed`, not `observed` (Figuera's structural weakness). Mitigation: label them; the optional proxy (tier A) upgrades them to `observed`; never let a `claimed` model id be the substrate key for a reputation update without saying so in the cell's metadata.

---

## Appendix: the finding object (proposed shape)

```json
{
  "finding_id": "f_3b9c…",
  "kind": "totals_recomputed | unsourced_number | unhandled_failed_command | human_point | gap",
  "severity": "gate | advisory",
  "status": "FAIL | ADVISORY | DISMISSED",
  "locations": [{"path": "report.md", "start_line": 12, "end_line": 12, "value": "999"}],
  "source_locations": [{"kind": "input", "name": "sales", "sha256": "…", "path": "data/sales.csv", "line": 4}],
  "step_id": "s7",
  "first_failing_step": "s7",
  "actor": {"platform": "claude/2.1", "definition_sha256": null, "substrate": "gemma-4-12b", "substrate_provenance": "claimed"},
  "confidence": "provable | lineage_exact | lineage_internal | heuristic | gap",
  "evidence": {"rerun": {"before": "PASS", "after": "FAIL", "verifier": "csv_total", "version": "2"}},
  "read_coverage": {"observed": 5, "inferred": 2, "unobservable": null},
  "dismissed_by": null
}
```

`actor` is rendered for the human and written to the ledger; it is never included in text sent to the agent.
