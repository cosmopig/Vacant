# scout-selfcheck — self-correction/self-verification papers, fair-comparison protocols

Read 2026-09-25. All dates below are "read 2026-09-25" unless noted. Sources are primary
(arXiv / ACL Anthology / official blog) unless marked otherwise.

## Note on scope
This is a literature scouting pass only. No model calls were made (per instructions,
research agents in this study must not call OpenRouter). Nothing here proposes touching
Vacant's model routing/proxy; it is input for the lead's arm design (A/B/C).

---

## 1. Reflexion (Shinn et al., NeurIPS 2023)
- Source: https://arxiv.org/abs/2303.11366 (v3), code https://github.com/noahshinn/reflexion
- What it is: agent keeps an episodic memory of *verbal* self-reflections after a trial
  fails, conditioned on an **external binary/scalar signal** (env reward, unit-test
  pass/fail, or a separate evaluator) — not pure intrinsic self-talk. Multiple trials
  per task (e.g., up to ~10 for HumanEval-style coding, fewer for ALFWorld/HotpotQA).
- Relevance to fair comparison: Reflexion is *not* an apples-to-apples "same budget"
  baseline out of the box — it burns N trials × 1 model call each, vs 1 call for a
  vanilla agent. Kamoi et al. 2024 (below) flags this exact class of paper for using
  unequal resources between baseline and treatment.
- Pitfall reported: works best when the external signal is trustworthy (unit tests,
  env reward); degrades when the only signal is the model's own judgment of success.

## 2. Self-Refine (Madaan et al., NeurIPS 2023)
- Source: https://arxiv.org/abs/2303.17651
- Protocol: single LLM plays generator + feedback-giver + refiner, iterative loop,
  no external verifier, no training. 7 tasks (dialogue, code opt, math, acronym gen,
  sentiment reversal, constrained gen, PIE code readability). Iterates until
  feedback says "it's good" or a max iteration count.
- Kamoi et al. 2024 critique of this line of work directly names Self-Refine as an
  example of an **"unfair" framework**: it gives the *initial* generation a weaker
  prompt/fewer few-shot examples than the *refinement* step gets, which inflates the
  apparent gain from refinement — the improvement partly comes from the asymmetric
  prompt, not from "self-correction" per se.
- Relevant number: no external grounding signal → same failure mode as Huang et al.'s
  "intrinsic self-correction" (see #4): works on some generation-style tasks (text
  quality), not shown to work on verifiable reasoning without added signal.

## 3. CRITIC (Gou et al., ICLR 2024)
- Source: https://arxiv.org/abs/2305.11738 (v1 read via arXiv HTML/PDF)
- Protocol (exact, this matters for budget-matching):
  - QA: max 3 correction rounds, up to 7 tool (web search) calls per round; stops
    early if the answer is unchanged for 2 consecutive rounds.
  - Math program synthesis: max 4 correction rounds; stops if execution result
    unchanged for 2 consecutive rounds.
  - Toxicity: max 4 iterations; stops once toxicity score < 10% (Perspective API).
  - Benchmarks: AmbigNQ/TriviaQA/HotpotQA (500 sampled each, EM/F1), GSM8K/SVAMP/TabMWP
    (official test splits, exact match), RealToxicityPrompts (1k prompts, Perspective
    API). Models: text-davinci-003, ChatGPT (gpt-3.5-turbo), LLaMA-2 7B/13B/70B.
  - Baselines it compares against, at matched or larger budget: rejection sampling
    (N new full generations, no critique), self-consistency (vote over N samples),
    and an oracle variant CRITIC* that only "corrects" samples known to be wrong
    (upper bound, explicitly flagged as unrealistic/oracle).
- **Key finding directly relevant to Vacant's design**: CRITIC *without* tools
  ("CRITIC w/o Tool", i.e. self-critique with no external grounding) gave "-0.03 to
  +2.33 F1" on QA — essentially a wash or slight loss — and the paper states plainly
  that intrinsic self-correction "may yield modest improvements or even deteriorate
  performance." The gains (TabMWP: 7B +4.7%, 13B +9.4%, 70B +16.0%) come specifically
  from **tool-grounded** critique (code execution, search results), and gains scale
  *up* with model size — smaller/weaker models get smaller absolute lift from the
  same tool-grounded critique loop.
- Implication for our arms: this is essentially the paper-level version of "Arm B vs
  Arm C" — CRITIC-w/o-tool ≈ our Arm B (persona/self-check, no grounding), full CRITIC
  ≈ our Arm C (grounded evidence). The effect-size gap between those two conditions in
  CRITIC's own numbers (near-zero vs positive-and-size-scaling) is our best existing
  empirical anchor for why Arm C should beat Arm B, and a warning that on a 9-12B
  model the C-vs-B gap may be *smaller* than on GPT-3.5/70B.

## 4. Huang et al., "Large Language Models Cannot Self-Correct Reasoning Yet" (ICLR 2024)
- Source: https://arxiv.org/abs/2310.01798 (v1 Oct 2023, v2 Mar 2024), read via arXiv HTML.
- Protocol (exact):
  - "Intrinsic self-correction": no external feedback, model told only "review your
    previous answer and find problems," must decide *itself* when to stop (no oracle
    label used to gate stopping). Max 2 rounds.
  - Model-call accounting: standard prompting = 1 call; round-1 self-correction = 3
    calls (generate, critique, revise); round-2 = 5 calls total. This is the paper's
    own explicit call-budget bookkeeping — directly reusable for our "match model
    calls across arms" requirement.
  - Separately runs an **oracle-gated** condition (uses the ground-truth label just to
    decide *whether* to keep the self-corrected answer or revert) to show the upper
    bound of what self-correction *could* achieve if you had a perfect stopping rule —
    explicitly labeled as unrealistic/not a real deployment setting.
  - Benchmarks: GSM8K, CommonSenseQA, HotpotQA (with GPT-3.5/GPT-4).
- **Effect sizes (intrinsic, no oracle), from GPT-3.5-class model, our own extraction**:
  - GSM8K: 75.9% → 75.1% (round 1) → 74.7% (round 2) — monotonic *decline*.
  - CommonSenseQA: 75.8% → 38.1% → 41.8% — catastrophic decline then partial recovery,
    still far below baseline.
  - HotpotQA: 26.0% → 25.0% → 25.0% — flat/slightly negative.
- **Pitfall, stated directly and highly relevant to our KS-1 wording concerns**: "the
  model is more likely to modify a correct answer to an incorrect one than to revise
  an incorrect answer to a correct one" — on GSM8K the model kept its original answer
  74.7% of the time and *introduced new errors* in most of the cases where it changed
  its answer. This is the canonical citation for "self-correction without a real
  external signal can make things worse, not better" and squarely motivates why Arm B
  (self-check, no evidence) is a *necessary control*, not a strawman — it might
  actually underperform Arm A on some tasks, which is itself a finding worth reporting.
- Also: multi-agent debate (6 agents) scored *below* plain self-consistency voting on
  the same call budget (83.2% vs 85.3%), i.e. debate ≈ an expensive re-branding of
  self-consistency, not real error-finding. Relevant if we're tempted to make Arm B
  fancier (e.g. multi-persona debate) — cite this to justify keeping Arm B simple/cheap.

## 5. Tyen et al., "LLMs cannot find reasoning errors, but can correct them given the
   error location" (ACL Findings 2024) — BIG-Bench Mistake
- Source: https://aclanthology.org/2024.findings-acl.826/ ; arXiv 2311.08516v3 (read
  via arXiv HTML).
- Dataset: BIG-Bench Mistake, 2186 CoT-style traces across 5 tasks (word sorting,
  tracking shuffled objects, logical deduction, multistep arithmetic, Dyck languages);
  the first four tasks: 300 traces each, ~85% incorrect / 15% correct by design;
  Dyck languages: 986 traces. Human-annotated ground-truth mistake step location,
  inter-annotator Krippendorff's α = 0.979–0.998 (very high — the "ground truth error
  location" is trustworthy).
- Protocol (exact — this is THE paper for "given the location, can you fix it"):
  1. Generate CoT trace at temperature 0.
  2. Locate the mistake step — three conditions compared: (a) **oracle/human-annotated
     location**, (b) **random location** (control, isolates "does location help vs.
     doing something"), (c) **model/classifier-found location**.
  3. Regenerate the erroneous step at temperature 1, resampling up to 8 times until
     it differs from the original.
  4. Regenerate all subsequent steps at temperature 0 (deterministic replay forward).
- **Effect sizes**: with **oracle** location, accuracy on originally-*incorrect* traces
  improved by +18.04 pp (multistep arithmetic) to +43.92 pp (tracking shuffled
  objects); loss on originally-*correct* traces (false "fixes") was small, 0 to
  -11.43 pp depending on task. Random-location control gave much smaller gains —
  i.e., the lift is specifically from *knowing where* the error is, not from merely
  re-rolling a step.
- **Separately, and this is the paper's headline finding**: LLMs prompted to *find*
  their own mistake are bad at it (their own few-shot/zero-shot mistake-finding
  accuracy is low and inconsistent across tasks — the paper contrasts this with the
  strong correction numbers above). A small trained classifier ("Unicorn"/PaLM-2
  Otter, out-of-domain trained) beat prompted mistake-finding on 4/5 tasks, but its
  absolute accuracy (6.00%–37.67%, task-dependent) is still well below the ~60-70%
  the authors estimate is needed for backtracking to reliably pay off. No seeds/
  multiple-trial reporting was found in the extracted text (flagging as unverified
  whether they ran repeated trials; only single-pass numbers were surfaced by our
  read — check appendix if this matters for our stats).
- **This is the single most load-bearing paper for Vacant's Arm C design**: it is
  direct evidence that "tell the model *where* the problem is" (which is exactly what
  Vacant's trace/locate/blame layer does — file, line, step, first-write) is the
  intervention that works, while "ask the model to find its own error" (= Arm B) is
  the intervention shown *not* to work well. Cite this paper explicitly when
  justifying why Arm C gives localized (file:line:step) feedback and Arm B does not.

## 6. Kamoi et al., "When Can LLMs Actually Correct Their Own Mistakes? A Critical
   Survey of Self-Correction of LLMs" (TACL 2024, vol. 12, pp. 1417–1440)
- Source: https://aclanthology.org/2024.tacl-1.78/ ; arXiv 2406.01297v3 (read via HTML).
- This is the paper to build our experimental design against; it is explicitly a
  meta-critique of exactly the methodological problems we need to avoid.
- **Taxonomy** (useful vocabulary for our writeup): intrinsic self-correction (prompt
  only) vs. external-feedback self-correction (tools/knowledge/training); and
  fair / unfair / unrealistic evaluation settings.
- **Named failure modes in prior papers, with the exact critique**:
  - *Oracle leakage*: e.g. RCI Prompting uses the ground-truth label to *decide
    whether to run* self-correction (skips it when already correct) — this leaks
    test-time-unavailable information and inflates the observed gain.
  - *Asymmetric initial response quality*: Self-Refine (named explicitly) uses a
    weaker prompt/fewer few-shot examples for the *initial* generation than for the
    *refinement* step, so part of the "self-correction gain" is really "we just gave
    it a better prompt the second time."
  - *Inconsistent resource allocation*: methods that only bring in external
    knowledge/tools during the refine step (e.g. RARR) should be compared against a
    baseline that gets to use those same tools on the *first* pass too — otherwise
    you're comparing "no tools" vs. "tools," not "no self-correction" vs.
    "self-correction."
- **Their stated required conditions for self-correction to actually help**:
  1. Feedback generation must be reliable — "the bottleneck is in feedback
     generation," not in the ability to act on good feedback once given (this
     directly echoes Tyen et al.'s finding).
  2. The task should be decomposable such that *verification* is easier than
     *generation* (e.g., checking a calculation is easier than solving it), or an
     external, objective tool exists (code execution, calculator, search).
  3. For trained/fine-tuned feedback models: reported cases needed 100K+ training
     instances — not a zero-config option for us.
- **Concrete fair-comparison checklist we should copy** (their Tables 7–8, our
  paraphrase):
  - State the exact research question and which category (intrinsic/external,
    fair/unfair/unrealistic) the experiment falls into, explicitly, in the writeup.
  - No oracle information anywhere in the loop (including "whether to run
    correction at all").
  - Use the *same, strong* prompt for the initial response as you would use if you
    were not doing self-correction at all — never intentionally weaken pass 1.
  - Compare against self-consistency / generate-and-rerank as an equal-extra-compute
    baseline, not just against "1-shot, no correction."
  - If resources genuinely differ between conditions (e.g. our Arm C's trace data
    didn't exist for Arm A), say so explicitly rather than calling it "fair."
- **Direct implication for Vacant's three arms**: this survey is essentially asking us
  to pre-register exactly what our arms mean before running: Arm A = intrinsic,
  no-correction baseline (1 pass, strong prompt); Arm B = intrinsic self-correction,
  reviewer persona, no external grounding, best-effort *equal* wall-clock/model-call
  budget to Arm C; Arm C = external-feedback self-correction using Vacant's trace
  evidence, which is real "external" information Arm A/B structurally cannot have
  (the paper says: that's fine, just don't call it a like-for-like ablation of the
  *same* information — it is an ablation of *having evidence at all*, which is our
  actual research question, so we should state it that way rather than claim "fair
  in the Kamoi sense" — we're doing an evidence-ablation, not a resource-matched
  self-correction ablation, and the writeup should say exactly that).

## 7. Agent-as-a-Judge (Zhuge et al., 2024)
- Source: https://arxiv.org/abs/2410.10934 (v2)
- What it is: uses an *agentic* judge (itself takes actions/reads intermediate
  trajectory artifacts, not just the final output) to evaluate another agent's run,
  vs. plain LLM-as-a-Judge (final output only) and vs. human evaluation. Benchmarked
  on 3 existing agentic coding systems; reported as close to human-eval reliability
  and clearly ahead of output-only LLM-as-a-Judge.
- Relevance: this is the closest prior work to "give it a persona and send it to
  re-check" (our Arm B/C reviewer step) — but their judge gets to *inspect the
  trajectory* (intermediate steps), which is structurally the same category of
  intervention as Vacant's trace evidence (external/grounded), not intrinsic
  self-talk. Strengthens the case that a reviewer persona is only as good as what it
  is allowed to look at — an ungrounded persona (pure text critique of the final
  output, our Arm B) is a materially weaker condition than a trajectory-grounded
  judge (closer to our Arm C).
- Caveat: could not verify exact model-call budget/cost accounting from search
  snippets alone (unverified — would need to pull the PDF/HTML directly if this
  number matters for our writeup; flagging rather than guessing).

## 8. OpenHands "verification stack" / critic model (2025–2026, industry, not
   peer-reviewed — treat as an engineering report, not a controlled study)
- Sources: https://www.openhands.dev/blog/20260506-the-verification-stack (read
  2026-09-25); referenced arXiv paper on their critic, arxiv.org/abs/2603.03800
  (title/contents not directly verified in this pass — unverified, flagging).
  OpenHands' April 2025 SWE-bench-Verified SOTA announcement ("inference-time
  scaling and critic models") reported by multiple secondary sources; primary
  post not independently re-fetched — treat the SOTA number itself as unverified
  from this pass (search snippets only).
- What it is architecturally: two-layer verification — (1) an agent-level *critic*
  model (separate, smaller model) scores the full trajectory (not just final diff)
  and can trigger "iterative refinement" (send the agent back with a score below
  threshold) before the change is proposed; (2) a repo-level verifier that reviews
  the resulting PR inside normal review flow. The critic is trained on "real
  production traces" (supervised, not prompted self-critique).
- **Could not extract** (this pass): exact retry-count/threshold defaults, exact
  compute-budget parity vs. no-critic baseline, or model size of the critic —
  their public blog defers those to a separate post/paper we did not fully parse.
  Mark as unverified/needs follow-up if we want to cite specific numbers.
- Relevance: structurally this is Vacant's own architecture already (trajectory-
  grounded critic + localized send-back before delivery), which is reassuring as
  an existence proof at industry scale, but we cannot borrow their numbers without
  re-reading the underlying arXiv paper directly (next pass, if useful).

## 9. When Agents go Astray: Course-Correcting SWE Agents with PRMs (Gandhi et al.,
   arXiv 2509.02360, NeurIPS 2025)
- Source: https://arxiv.org/abs/2509.02360
- What it is: an inference-time Process Reward Model (PRM) that watches an agent's
  SWE-bench trajectory *during* execution (not just at the end) and intervenes on
  specific inefficiency patterns (redundant exploration, looping, failure to
  terminate once solved) — trained on a taxonomy of trajectory-level error types.
- **Effect size**: on SWE-bench Verified, closed-source PRM improved resolution rate
  from 40.0% → 50.6% (+10.6 pp), with the largest gains concentrated on medium/hard
  difficulty tasks (i.e., gains are not uniform — easy tasks the agent already solves
  don't benefit, consistent with our expectation that Vacant's lift should show up
  most on tasks where evidence genuinely disambiguates something).
- Relevance: strongest available large-scale numeric anchor for "external process-
  level verification measurably improves SWE-bench-class coding agent outcomes,"
  and it is a *step-level*, not just outcome-level, intervention — same shape as
  Vacant's step-located feedback. Good citation for justifying that step-level >
  outcome-level verification, independent of the self-correction literature above.
- Caveat: PRM here is a trained model requiring its own training data/infra, not a
  zero-config evidence-based check — different mechanism from Vacant's rule-based
  trace/locate, but same causal claim (localized signal beats none).

## 10. When Small Models Are Right for Wrong Reasons: Process Verification for
    Trustworthy Agents (arXiv 2601.00513, read as 2026 preprint)
- Source: https://arxiv.org/html/2601.00513 — **directly on-point for our model
  size regime** (7–9B open models: Llama-3-8B, Mistral-7B, Qwen-2.5-7B).
- Protocol notes: greedy decoding (temperature=0) throughout for consistency; their
  RAG condition uses **oracle retrieval**, which they themselves flag as an upper
  bound / potential leakage — a caution to us if any Vacant-evidence condition
  resembles "perfect retrieval" (we should make sure Vacant's evidence is the
  *actual* trace, not a curated/cherry-picked excerpt, to avoid the same critique).
- **Central, alarming finding for small models specifically**: 50–69% of *correct*
  final answers from these 7-9B models were reached via reasoning the authors
  characterize as fundamentally flawed ("right for wrong reasons") — i.e., outcome-
  only correctness is a weak signal of process quality at this scale, which is
  exactly the accountability-not-correctness framing the project owner wants
  ("checks whether each step was justified," not whether the final answer is right).
- **Effect sizes (Cohen's d)**:
  - External grounding (RAG) on fact-grounded tasks: d = +0.23 to +0.93 (positive,
    sometimes large).
  - Self-critique/verification **without** external grounding: d = **-0.14 to -0.33**
    — i.e. at 7-9B scale, ungrounded self-critique measurably *hurts*.
- **Named failure mode**: "pseudo-reflection" — small models produce text that has
  the surface form of critique/introspection without actually re-examining anything,
  and can actively "invent incorrect justifications" that make a correct step look
  wrong or vice versa. This is a strong, size-matched warning for our Arm B design:
  at the ~9-12B scale we're targeting, a reviewer-persona-without-evidence arm may
  not just fail to help, it may actively degrade some outputs — which should be
  explicitly reported as a possible/expected outcome, not treated as a bug in our
  harness if it happens.
- A distilled verifier they trained got F1 0.86, but again under oracle context —
  same caveat as above; not a zero-config claim.

## 11. HaluAgent / "Small Agent Can Also Rock!" (Cheng et al., EMNLP 2024)
- Source: https://arxiv.org/abs/2406.11277 ; code https://github.com/RUCAIBox/HaluAgent
- What it is: a 7B model (Baichuan2-Chat-7B) fine-tuned on ~2K examples, given a
  multi-functional toolbox (not pure prompting) and a 3-stage detect-locate-verify
  framework with memory, to detect hallucinations in text/code/math outputs.
- Reported result: comparable to or exceeding GPT-4-without-tools on both in-domain
  and out-of-domain hallucination-detection datasets, at 7B scale.
- Relevance: counter-example showing a **small model *can* do useful verification
  work IF given tools/structure** (toolbox + staged pipeline), not pure intrinsic
  self-talk — consistent with the CRITIC/Tyen/#10 pattern: small models fail at
  *unstructured* self-critique but can succeed at *structured, tool-grounded*
  verification. Reinforces that Arm C's advantage should come from structure +
  evidence (Vacant's trace), not from asking a small model to "think about whether
  it's right" unaided (Arm B).
- Caveat: needs 2K fine-tuning examples — not literally zero-config/zero-shot;
  relevant only as an existence proof that small+structured beats small+unstructured,
  not as a technique we can port directly without training.

---

## Cross-cutting pitfalls, collected

1. **Self-correction can turn correct answers into wrong ones.** Huang et al. 2024:
   GPT-3.5-class model on GSM8K/CommonSenseQA got *worse* after 1-2 rounds of
   ungrounded self-correction; more likely to break a correct answer than fix a wrong
   one. Confirmed at small-model scale by #10 (Cohen's d negative for self-critique
   without grounding). **Design implication: our Arm B must be reported honestly even
   if it underperforms Arm A — that is itself a citable, expected finding, not a bug.**
2. **Budget confounds are the single most common methodological flaw** (per Kamoi et
   al.'s survey): more model calls, better prompts on the "improved" condition, or an
   oracle used to decide whether/when to stop, all inflate apparent gains. Huang et
   al. explicitly counted calls (1 / 3 / 5) — we should do the same for A/B/C.
3. **Verification-without-grounding fails; verification-with-grounding/localization
   works**, consistently across scales and papers: CRITIC (w/o tool ≈ flat, w/ tool
   positive and size-scaling), Tyen et al. (prompted self-location bad, given-location
   correction strong), #10 (self-critique negative d, RAG-grounding positive d).
   This is the single strongest piece of evidence FOR Vacant's core bet (evidence-
   grounded, localized feedback should beat ungrounded reviewer-persona self-check).
4. **"Pseudo-reflection" at small scale** (#10): watch for the reviewer persona in
   Arm B producing confident-sounding but non-substantive critique text; if we can
   afford it, a manual/LLM-judge spot-check of *whether Arm B's critique references
   anything specific* (vs. generic hedging) would strengthen the writeup, though this
   adds judge-model calls to budget.
5. **Multi-agent debate ≈ expensive self-consistency**, not real error-finding (Huang
   et al.): if we're tempted to make Arm B more elaborate (multiple reviewer personas
   debating), the literature says this likely just re-buys self-consistency at N×
   cost, not a qualitatively different signal — an argument for keeping Arm B simple
   and cheap rather than "beefing it up to be fair."
6. **Task-decomposability matters** (Kamoi et al.): self-correction/verification works
   best where checking is structurally easier than generating (code execution, exact-
   match facts, calculator). For an exhibition-facing task, prefer tasks where Vacant's
   evidence gives an objective yes/no (a file was or wasn't opened; a number in the
   output does or doesn't match a number in the source data) over tasks needing
   subjective judgment — this maximizes the chance our effect replicates the
   literature's positive cases rather than its negative ones.

---

## Recommendations for our three arms (A / B / C)

**Framing**: per Kamoi et al., call this explicitly an *evidence ablation*
(does having Vacant's grounded trace evidence at delivery time change the outcome?),
not a resource-matched "self-correction ablation" — A and B structurally cannot have
Vacant's evidence, so don't claim the comparison is "fair" in the strict sense the
survey defines; state plainly what varies between arms.

- **Arm A — no Vacant, single pass.** Agent runs the task once, delivers immediately,
  no self-review step at all. This is the true zero-intervention baseline. Record:
  1 model call sequence (whatever the task naturally takes), no extra review calls.

- **Arm B — reviewer-persona self-check, no Vacant evidence.** After Arm-A-equivalent
  output is produced, run one additional review pass: give the model a reviewer
  persona/prompt asking it to check its own work, **with no access to Vacant's trace,
  unread-file list, or unsourced-specifics flags** — i.e., exactly CRITIC's
  "w/o tool" condition / Huang et al.'s "intrinsic self-correction" condition. Budget:
  match Arm C's *number of extra review-and-possible-redo calls*, not necessarily
  wall-clock, since Arm C's evidence-gathering (trace read, locate) is cheap/free
  (no model calls — it's static analysis of the recorded trace) while the redo pass
  is the comparable unit. Concretely: Arm B gets exactly the same max-redo-round
  budget as Arm C (their target: reuse Huang et al.'s explicit 1/3/5-call accounting
  style — report exact call counts per arm per task).
  **Expected outcome per literature: Arm B may not beat Arm A, and could be worse on
  some tasks (#10, Huang et al.) — report this as a real finding, don't tune Arm B
  until it "works," that would reintroduce exactly the asymmetric-effort bias Kamoi
  et al. calls out in Self-Refine.**

- **Arm C — Vacant evidence, localized redo.** Same reviewer-persona framing as Arm B
  (so the *prompt style* is held constant — same persona, same "check your work"
  instruction), but the persona is additionally given Vacant's grounded findings:
  unread-but-relevant files, unsourced numbers/dates with their trace-verified
  provenance (or lack of it), any test/claim mismatches the trace can prove. This
  mirrors Tyen et al.'s "given the error location" condition, which is the one paper
  in this set with the cleanest, largest, most replicated positive effect. Feedback
  text must stay KS-1-clean (no "you are responsible/will be punished," no actor ids)
  — consistent with Vacant's existing constraint and with the research finding that
  *what* helps is the location/evidence, not blame framing.

- **Budget-matching, concretely** (borrowing Huang et al.'s bookkeeping style):
  report, per arm per task: total model calls, total input+output tokens, wall-clock
  seconds, and — since we are on a metered OpenRouter key — cost in USD from the
  ledger. Because Arm C's *evidence gathering* is free (trace/locate is deterministic
  code, not model calls), the fair thing to match is **max redo rounds and max review
  calls**, not total wall-clock; call out anywhere Arm C ends up cheaper (fewer wasted
  redo rounds because feedback is localized) as a *result*, not a discarded confound —
  Tyen et al.'s framing (oracle location → fewer, more effective correction attempts)
  supports reporting "calls to reach an accepted result" as a headline metric, not
  just pass/fail.

- **What to report, minimum set** (synthesizing Kamoi et al.'s checklist + Huang et
  al.'s call-accounting + #10's effect-size framing): per arm — task-level pass/fail
  (or rubric score) with the exact rubric, model calls, tokens, cost, wall-clock;
  aggregate: proportion of tasks changed from fail→pass and from pass→fail (the
  Huang et al. "does self-correction ever break a correct answer" check applies
  directly to Arm B and Arm C both — track both directions, not just net accuracy);
  if feasible, effect size (not just raw % — Cohen's d or similar) given our expected
  small sample count (task budget will be small given the 50-call/day and $5 cap
  constraints per MODELS.md); explicitly flag any oracle-like leakage if it turns out
  our task rubric was written after seeing model outputs (write rubrics before running
  Arm A, per Kamoi et al.'s "no oracle information anywhere in the loop").

- **Seeds/trials**: none of the papers here reliably reported multi-seed self-
  correction numbers (Tyen et al.'s were not found; Huang et al./CRITIC report
  single-run benchmark accuracy). Given our tiny compute/call budget (50 free calls/
  day; a few-dollar paid cap), multi-seed replication is likely infeasible for more
  than a couple of exemplar tasks — if so, say "demo, not proof" explicitly (this
  matches the project's own KS rule 5: "demo can say visible improvement; proven
  improvement needs a pre-registered batch run").

---

## Sources index (for citation)
- Shinn et al., Reflexion, NeurIPS 2023: https://arxiv.org/abs/2303.11366
- Madaan et al., Self-Refine, NeurIPS 2023: https://arxiv.org/abs/2303.17651
- Gou et al., CRITIC, ICLR 2024: https://arxiv.org/abs/2305.11738
- Huang et al., LLMs Cannot Self-Correct Reasoning Yet, ICLR 2024: https://arxiv.org/abs/2310.01798
- Tyen et al., LLMs cannot find reasoning errors but can correct given location, ACL
  Findings 2024: https://aclanthology.org/2024.findings-acl.826/ (arXiv 2311.08516)
- Kamoi et al., When Can LLMs Actually Correct Their Own Mistakes?, TACL 2024 vol.12:
  https://aclanthology.org/2024.tacl-1.78/ (arXiv 2406.01297)
- Zhuge et al., Agent-as-a-Judge, 2024: https://arxiv.org/abs/2410.10934
- OpenHands, "The Verification Stack," blog, 2026-06-22 (page timestamp):
  https://www.openhands.dev/blog/20260506-the-verification-stack (protocol details
  largely deferred to a linked paper we did not re-verify this pass — unverified)
- Gandhi et al., When Agents go Astray: SWE-PRM, arXiv 2509.02360 (NeurIPS 2025):
  https://arxiv.org/abs/2509.02360
- "When Small Models Are Right for Wrong Reasons," arXiv 2601.00513:
  https://arxiv.org/html/2601.00513
- Cheng et al., HaluAgent / "Small Agent Can Also Rock!", EMNLP 2024:
  https://arxiv.org/abs/2406.11277

## Explicitly unverified / needs follow-up if it matters later
- OpenHands critic model size, exact retry-threshold defaults, compute-budget parity
  claim, and the April 2025 SWE-bench-Verified SOTA number: only seen via search
  snippets / a blog that defers to another post; did not independently re-fetch the
  underlying arXiv paper (arxiv.org/abs/2603.03800) in this pass.
- Agent-as-a-Judge's exact model-call budget vs. LLM-as-a-Judge baseline: not found
  in the snippets pulled; would need the PDF.
- Whether Tyen et al. ran multiple seeds/trials: not found in the extracted text;
  possibly in an appendix we did not fetch.
