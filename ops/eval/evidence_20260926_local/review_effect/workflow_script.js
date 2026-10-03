export const meta = {
  name: 'review-bigger-effect',
  description: 'Review how zero-config Vacant could get a clearly bigger effect, design a one-hour screening suite and a within-budget API pilot',
  phases: [
    { title: 'Research', detail: 'past gains, headroom in current data, fast screening suite, mechanism designs' },
    { title: 'Synthesize', detail: 'ranked plan: suite, mechanisms to screen, API pilot within budget, go/no-go rules' },
    { title: 'Critique', detail: 'product-principle critic and evidence/statistics critic' },
  ],
}
const S = args.scratch
const CONTEXT = `
Repo: /home/user/Vacant (read CLAUDE.md there first: product principle, 口徑 rules, the zero-config section). Scratch: ${S}.
READ-ONLY research: do NOT modify the repo or anything under ${S}/local; do NOT touch docker, the proxy on port 18900, or the running held-out batch; do NOT read ${S}/local/heldout_v34 (a preregistered batch is running there; its outcomes must not be looked at). Do not read credential files. Use /tmp/claude-0/review_effect/<your-label>/ for your own scripts.

Situation (2026-09-26):
- Product: zero-config Vacant installed into pi (and other agents). With no contract it records every step; at "done" it checks grounds (5 send-back kinds) and sends back what must be redone (≤2 rounds per request); v3 adds a turn-budget reminder at 2/1 turns left when a requested output file is missing (only when the agent's system prompt states a turn cap); v3.2–v3.4 only change the person-facing delivery note.
- Paid batch 2026-09-25 (OpenRouter, gemma-4-26b and qwen, thinking on, DABstep 77 tasks, pi 0.87.1, 15-turn cap): no measurable difference (p=0.21/0.29). Report: docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md; evidence ops/eval/evidence_20260925/ (INDEX.md). That report says past gains came when Vacant held generation (executable acceptance + resampling + refusal); what is missing is "real signal + right timing + power to redo".
- Local formal batch 2026-09-26 (human's LM Studio gemma-4-12b, thinking off, same 77 tasks, 3 samples, arms A / C1 current zero-config / C2 v3): C2 vs A +7.4 pp (51.9%→59.3%), exact Wilcoxon p=0.021 — thin, concentrated in 6 tasks, mechanism = reminder harvesting answers already computed but not written (63 reminder writes: 25 right, 38 wrong); C1 vs A no difference. Conclusion: decisions/conclusions/CONCLUSION_20260926_ZERO_CONFIG_V3_LOCAL.md. Raw: ${S}/local/formal_v3 (711 runs; Harbor trial dirs with agent/pi.txt event streams, verifier/, agent/vacant_check.json, C arms agent/vacant_home/). Attribution scripts: ops/eval/evidence_20260926_local/formal/verify/scripts/. Research on 12B failure modes: ops/eval/evidence_20260926_local/research_12b/ (README + transcripts).
- The human (2026-09-26, paraphrased from Chinese): "Keep testing, but also review whether we can get a clearly better effect — we have seen gains before; what we have now is within the margin of error. We need a task set that can produce an A-vs-C comparison within one hour before running big batches. After the review, run small tests on the API; only if they work, schedule tests on local compute after the current run, and re-run those."
- Constraints: API (OpenRouter via the recording proxy ops/eval/orproxy.py) budget left ≈ $1.40, no top-up assumed; the paid batch cost $3.40 for 3324 requests / 32.9M prompt tokens (≈ $0.10 per M prompt tokens with deepinfra gemma-4-26b fp8; configured models in ops/eval/evidence_20260925/proxy_config.json: qwen/qwen3.5-9b, google/gemma-3-12b-it, google/gemma-4-26b-a4b-it, openai/gpt-oss-20b). Local compute (2 LM Studio machines, gemma-4-12b, ~55 DABstep runs/hour total, thinking off) is busy until ~03:00–04:00 UTC 2026-09-27. Harbor is at ${S}/study/src/harbor; pinned DABstep at ${S}/dabstep_pinned; other benchmark sources under ${S}/study/src (LiveCodeBench, SpreadsheetBench, terminal-bench-2-0-sample, aider-official, polyglot-benchmark) and study notes ${S}/study/deep-*. Past experiment index: runs/INDEX.md; conclusions: decisions/conclusions/; G experiment: decisions/conclusions/CONCLUSION_20260830_G_EXPERIMENT.md, ops/gain/SPEC_GAIN.md.
- Product principle (non-negotiable): install once, use your agent as usual, zero config; Vacant checks whether each step had grounds and sends back what must be redone before delivery; it never judges correctness itself and never picks an answer; KS-1 wording; nothing sent to the model when nothing is wrong (byte-identical requests).
Be concrete; cite files, counts and run ids. Say "unclear" when unclear.`

const RESEARCH = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    findings: { type: 'array', items: { type: 'object', properties: {
      claim: { type: 'string' }, evidence: { type: 'string' }, implication: { type: 'string' },
    }, required: ['claim', 'evidence', 'implication'] } },
    numbers: { type: 'string', description: 'key quantitative results (ceilings, costs, sizes) with how they were computed' },
  },
  required: ['summary', 'findings', 'numbers'],
}

phase('Research')
const research = await parallel([
  () => agent(`${CONTEXT}

ANGLE: past gains archaeology. Find every past experiment in this repo that measured a real gain from Vacant (or its predecessors) on correct deliveries: runs/INDEX.md (real_run entries and headlines), decisions/conclusions/*, decisions/DECISION_*.md about R4xx/R5xx/G/X1, ops/gain/*. For each: benchmark, model, mechanism (e.g. executable acceptance + resample + refuse), arms, effect size, preregistered or not, cost multiplier, and whether it was confirmed. Then say precisely which ingredients produced the gain and which of them could exist in the zero-config product installed into pi/Claude Code/Codex/OpenCode (where Vacant does not hold generation). Identify the single most transferable ingredient.`, { label: 'past-gains', phase: 'Research', schema: RESEARCH }),
  () => agent(`${CONTEXT}

ANGLE: headroom in today's data. Using the local formal batch (711 runs; per-run pi.txt event streams, verifier outputs) and the paid batch evidence, compute ceilings for candidate mechanisms WITHOUT running models:
(a) harvest ceiling: runs (any arm) where the correct value was visible in a tool output or assistant text before the run ended but no answer file / wrong file was delivered — split by when it first appeared (turn number) and whether v3 captured it;
(b) redo/relaunch ceiling: for each task, if the product could relaunch a fresh attempt when the first attempt delivered nothing (or delivered something a check flags), what would accuracy be? Estimate with the other samples of the same arm/task as the "second attempt" (e.g. A s1 no-file → take A s2), and the cost in extra requests;
(c) best-of/consistency ceiling (for reference only; conflicts with 'never picks an answer');
(d) what fraction of wrong answers had a signal Vacant could legitimately observe (failed step ignored, unread named file, value without source, format mismatch with the request's stated format).
Report which mechanism has headroom for a clearly bigger effect (≥ +10–15 pp) and under which conditions.`, { label: 'headroom', phase: 'Research', schema: RESEARCH }),
  () => agent(`${CONTEXT}

ANGLE: a one-hour screening suite. Design a fixed task set that yields an A-vs-C comparison in ≤ 1 hour, usable (1) on the API within a tiny budget and (2) on local compute (~55 DABstep runs/hour total, 4 concurrent). Consider: DABstep subsets (selected by a rule that does NOT use the outcomes you want to test — e.g. stratified random with a fixed seed, or selection on A-arm-only properties with a stated regression-to-the-mean caveat), and coding benchmarks with executable tests where Vacant's checks (test claims, ignored failed steps, missing outputs) have real signal (LiveCodeBench, aider polyglot, terminal-bench sample, SpreadsheetBench — check what is actually available and runnable in Harbor here and how long a run takes). For each option give: tasks, runs per arm, wall time on local and on API, API cost per run (use the paid ledger ops/eval/evidence_20260925/formal/ledger_formal.jsonl and cost fields), and what effect size it can detect (e.g. paired McNemar/Wilcoxon power for +10/+15/+20 pp). Recommend one suite with a concrete task list rule and the exact runner command (ops/eval/local/run_batch.py / run_local.sh or the paid runner used on 2026-09-25 — find it).`, { label: 'fast-suite', phase: 'Research', schema: RESEARCH }),
  () => agent(`${CONTEXT}

ANGLE: mechanism designs that could give a clearly bigger effect while keeping the product principle. Candidates to evaluate (and add your own): (1) harvest earlier — a reminder when a requested output is missing AND the last tool outputs already contain a value of the requested form (still no value quoted); (2) redo power for headless runs: when the agent ends (or is capped) with no deliverable, Vacant relaunches one fresh attempt of the same agent in the same workspace (how, in pi / Claude Code / Codex, without extra user config; cost; cap interaction; what the person sees); (3) making the agent's own verification real — e.g. when the request states an output format, check the delivered file against it; when the agent claims tests passed, run them; (4) a 'grounds' check that the delivered value appears in some step's output (already exists as 'unsourced' — why it rarely fires, can it be made useful); (5) changing where the turn cap bites (e.g. reserving the last turn). For each: principle fit (zero config, never picks an answer, byte-identical when nothing is wrong, KS-1), which failures it reaches (tie to research_12b categories and the local formal data), expected gain range, harms, cost, and implementation size in vacant_network (adapters/agents.py PI_EXTENSION, trace/zerostop.py, trace/budget.py, trace/evidence.py).`, { label: 'mechanisms', phase: 'Research', schema: RESEARCH }),
])
const R = research.filter(Boolean)
log(`research returned ${R.length}/4`)

phase('Synthesize')
const PLAN = {
  type: 'object',
  properties: {
    diagnosis: { type: 'string', description: 'why the current effect is small, in plain words' },
    candidates: { type: 'array', items: { type: 'object', properties: {
      name: { type: 'string' }, mechanism: { type: 'string' }, principle_fit: { type: 'string' },
      expected_gain: { type: 'string' }, harms: { type: 'string' }, cost: { type: 'string' },
      implementation: { type: 'string' }, rank: { type: 'integer' },
    }, required: ['name', 'mechanism', 'principle_fit', 'expected_gain', 'rank'] } },
    fast_suite: { type: 'string', description: 'the one-hour screening suite: benchmark, task rule, task list or how to generate it, runs per arm, expected wall time local/API' },
    api_pilot: { type: 'string', description: 'concrete pilot within ≈$1.40: model, arms, tasks, samples, estimated cost with arithmetic, and the go/no-go rule to schedule it on local compute' },
    after_pilot: { type: 'string', description: 'what to schedule on local compute after the held-out batch, and what to re-run' },
    risks: { type: 'string' },
  },
  required: ['diagnosis', 'candidates', 'fast_suite', 'api_pilot', 'after_pilot', 'risks'],
}
const plan = await agent(`${CONTEXT}

Below are four research reports. Synthesize a plan: rank at most 4 candidate mechanisms by (plausible gain − harm) under the product principle; define the one-hour screening suite; design an API pilot that fits the remaining ≈ $1.40 (show the cost arithmetic; if nothing meaningful fits, say so and give the smallest budget that would); and a go/no-go rule for scheduling on local compute after the held-out batch. Be honest if the evidence says the product, as defined, cannot reach a clearly bigger effect on DABstep, and whether another benchmark type is where its mechanism has signal.

REPORTS:
${JSON.stringify(R)}`, { label: 'synthesize', phase: 'Synthesize', schema: PLAN })

phase('Critique')
const CRIT = {
  type: 'object',
  properties: {
    verdicts: { type: 'array', items: { type: 'object', properties: {
      item: { type: 'string' }, holds: { type: 'boolean' }, problems: { type: 'string' }, fix: { type: 'string' },
    }, required: ['item', 'holds', 'problems'] } },
    overall: { type: 'string' },
  },
  required: ['verdicts', 'overall'],
}
const critics = await parallel([
  () => agent(`${CONTEXT}

You are the PRODUCT-PRINCIPLE critic. For each candidate and for the pilot design below, try to show it violates the principle (zero config, minimal install, use your agent as usual, grounds-not-correctness, never picks or hints an answer, KS-1, byte-identical when nothing is wrong, no extra model calls a user did not ask for without saying so), would annoy an interactive user, or only works inside a benchmark harness. Default to holds=false when uncertain.

PLAN:
${JSON.stringify(plan)}`, { label: 'critic:principle', phase: 'Critique', schema: CRIT }),
  () => agent(`${CONTEXT}

You are the EVIDENCE/STATISTICS critic. For each candidate's expected gain, the fast suite, and the API pilot below: check the arithmetic and the data they cite (re-compute where you can), check whether a one-hour suite can detect the claimed effect (power), whether task selection biases it (regression to the mean, selecting on outcomes), whether the pilot budget math holds, and whether the go/no-go rule would let noise through. Default to holds=false when uncertain.

PLAN:
${JSON.stringify(plan)}`, { label: 'critic:evidence', phase: 'Critique', schema: CRIT }),
])
return { research: R, plan, critics: critics.filter(Boolean) }
