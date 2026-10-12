export const meta = {
  name: 'zero-config-v3-design',
  description: 'Research pi mechanics, Vacant code, and batch data; three design proposals; judge a build spec for zero-config v3',
  phases: [
    { title: 'Research', detail: 'pi 0.87.1 mechanics, Vacant code map, nudge/rerun simulation on the paid batch' },
    { title: 'Design', detail: 'three independent proposals from different angles' },
    { title: 'Judge', detail: 'score and synthesize one build spec' },
  ],
}

const REPO = '/home/user/Vacant'
const S = '/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad'
const PI = `${S}/agents/node_modules/@earendil-works/pi-coding-agent`
const HARBOR_PI = `${S}/study/src/harbor/src/harbor/agents/installed/pi.py`

const RULES = `Rules: do NOT modify any file under ${REPO} (read-only). You may write scratch scripts/outputs only under ${S}/design/. Every factual claim needs file:line (or a script you ran + its output). Say plainly when something is unknown. Be concise and precise.`

const CONTEXT = `Background (read ${REPO}/docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md sections 零, 七, 十, 十一 first; and CLAUDE.md product principle).
Vacant zero-config = a pi extension (source text in ${REPO}/vacant_network/adapters/agents.py PI_EXTENSION) that forwards pi events to \`vacant hook pi <event>\`; at agent_before_settle it runs evidence checks (${REPO}/vacant_network/trace/evidence.py, zerostop.py, review.py) and may push back (≤2 rounds). A paid DABstep batch showed no difference; root causes: (1) timing: 55/82 failures never delivered an answer because a 15-turn cap (Harbor pi max_turns extension, ${HARBOR_PI} _build_max_turns_extension, which also appends "You have a hard budget of N model turns" to the system prompt) aborts pi and pi skips agent_before_settle; 15-19 of them had already stated a correct answer; (2) the remaining wrong answers had grounded steps, wrong decisions; (3) push-back in the same session is the weakest past lever. Now the human wants the product improved and tested on their local gemma-4-12b (non-thinking) machines, where compute is free.`

const R1 = agent(`${RULES}
${CONTEXT}
Task (pi mechanics, pi version 0.87.1 installed at ${PI}; read dist/*.js and dist/core/extensions/types.d.ts):
1. turn_end handler result (TurnEndEventResult = BoundaryResult): exactly what happens when an extension returns {entries:[{type:"custom_message",...}], continue:true} at turn_end? Is the custom message sent to the model on the next request (as which role), and does it add a turn? What if another extension (Harbor's max-turns) calls ctx.abort() in its own turn_end handler for the same turn — ordering of extension handlers (load order: -e flags vs extensions dir), and does abort win over continue? Can an injected message still be delivered if abort is called?
2. agent_before_settle: confirm it is skipped after abort (cite the loop code). Is there ANY event an extension receives after an abort (agent_end? agent_settled with outcome 'aborted'?) and can it do anything useful there (e.g. start a new prompt / sendUserMessage / followUp)? Check ExtensionAPI methods (pi.sendUserMessage? pi.sendMessage? ctx.* ) and their semantics in print mode (-p) — would pi -p process a follow-up after the first prompt finished or aborted?
3. In the turn_end event, what does the extension see: turnIndex, the assistant message incl. thinking/text/toolCalls, toolResults? Can it see the system prompt text (e.g. the 'hard budget of N model turns' line) anywhere (before_agent_start event.systemPrompt)?
4. Can an extension handler at agent_before_settle run for up to ~10 minutes (spawn a child process) without pi timing out? Any timeout in pi around extension handlers?
5. Would a child 'pi -p <prompt>' spawned from inside the extension (same PI_CODING_AGENT_DIR / models.json / env) work in Harbor's container, and how would Vacant's own extension in the child know it is a nested run (see VACANT_PI_PARENT mark in PI_EXTENSION)?
Return findings with file:line.`, { label: 'pi-mechanics', phase: 'Research' })

const R2 = agent(`${RULES}
${CONTEXT}
Task (Vacant code map for the change): read ${REPO}/vacant_network/adapters/hook.py, hookpolicy.py, agents.py (PI_EXTENSION), trace/zerostop.py, trace/evidence.py (requested_outputs, OUTPUT_* regexes, findings), trace/review.py, trace/recorder.py, trace/capture.py (classify_prompt), adapters/run.py (vacant do: isolated workspace + headless + retry), and tests/test_zero_*.py.
Answer: (a) exact data flow from a pi event to a decision today (which function, which state files: zero_state.json, rounds file), (b) where a new 'turn_end' route would plug in (hook.py dispatch, state needed across turns, how to know the requested output path cheaply at turn end without running the full evidence check), (c) how the delivery note and review events are recorded (so a new intervention is recorded the same way), (d) what 'vacant do' already provides that a 'fresh attempt' / 'independent recompute' could reuse (functions, isolation, headless argv for pi), (e) the invariants the tests enforce that a change must keep (KS-1 text checks, byte-identical requests when no problem, fail-open, rounds per person request), (f) risks: places where adding a mid-run message could break sub-agent handling, rounds counting, or the OpenCode/Claude/Codex adapters. Give file:line for everything.`, { label: 'vacant-code', phase: 'Research' })

const R3 = agent(`${RULES}
${CONTEXT}
Task (offline simulation on the paid formal batch; raw data: ${S}/formal/jobs/<g4|q38>-on-<A|C>/<job>/dabstep-<task>__<rand>/ with agent/pi/sessions/*.jsonl (full pi transcripts), verifier/test-stdout.txt, result.json; per-run metadata in ${REPO}/ops/eval/evidence_20260925/formal/runs.json (use the latest job per model/arm/task; exclude tasks 5 and 70 from headline counts); answer-in-hand list in ${REPO}/ops/eval/evidence_20260925/investigation/failure_taxonomy.json; expected answers in ${S}/dabstep_pinned/formal/dabstep-<task>/tests/test.sh, scorer ${S}/dabstep_pinned/formal/dabstep-<task>/tests/scorer.py (usage: python3 scorer.py <got> <expected>, exit 0 = correct)).
For every run (both models, both arms, 77 tasks), reconstruct per assistant turn: turn index (1-based model request count), whether /app/answer.txt exists at the end of that turn (from write/edit/bash tool calls in the transcript — handle echo > answer.txt, python writes, etc.; say how you detected it), and the first turn at which the model's text or thinking states a candidate final answer that the scorer accepts.
Then simulate a one-time 'write-early' nudge that fires at the end of turn K if answer.txt does not exist yet (K = 4, 6, 8, 10, 12): for each K and model, count (i) runs where it fires, (ii) of those, runs that in reality eventually wrote a correct answer anyway (nudge unnecessary; possible disruption), (iii) runs that never wrote but had a scorer-accepted answer stated at or before turn K (likely rescued if the model obeys), (iv) runs that never wrote and had a correct answer stated only after K, (v) runs that eventually wrote a wrong answer. Also report the distribution of the turn at which answer.txt was first written in successful runs.
Also estimate a 'nudge when a candidate answer is stated but not written' trigger: how reliably can a candidate final answer be detected from the assistant text (not thinking) at turn end (precision/recall vs your scorer-checked labels), since the product cannot read hidden thinking reliably across agents.
Save your script and a JSON of per-run turn data to ${S}/design/nudge_sim/. Return the tables.`, { label: 'nudge-sim', phase: 'Research' })

const research = await parallel([() => R1, () => R2, () => R3])
const [pim, code, sim] = research
const brief = `RESEARCH RESULTS
=== pi mechanics ===
${pim}
=== Vacant code map ===
${code}
=== nudge / timing simulation on the paid batch ===
${sim}`

phase('Design')
const DESIGN_SCHEMA = {
  type: 'object',
  properties: {
    name: { type: 'string' },
    summary: { type: 'string', description: 'Traditional Chinese, plain language, 5-10 sentences' },
    mechanisms: { type: 'array', items: { type: 'object', properties: {
      what: { type: 'string' }, trigger: { type: 'string' }, text_to_agent: { type: 'string', description: 'exact English text sent to the agent, KS-1 clean (no responsibility/punishment words, no actor names)' },
      where_in_code: { type: 'string' }, cost: { type: 'string' }, risk: { type: 'string' },
      l_fake_test: { type: 'string', description: 'how to prove it works with a scripted mock model before real runs' },
      expected_effect: { type: 'string', description: 'grounded in the simulation numbers' },
    }, required: ['what','trigger','text_to_agent','where_in_code','cost','risk','l_fake_test','expected_effect'] } },
    principle_check: { type: 'string', description: 'zero-config, install-minimal, byte-identical when no problem, accountability wording' },
    do_not_do: { type: 'array', items: { type: 'string' } },
    eval_plan: { type: 'string', description: 'how to measure it on the local gemma-4-12b machines (arms, samples, primary metric, analysis)' },
  },
  required: ['name','summary','mechanisms','principle_check','do_not_do','eval_plan'],
}
const ANGLES = [
  ['timing-first', 'Maximize rescued deliveries by acting at the right time (before a budget runs out / when an answer exists but is not written), with the smallest possible change to what the model sees. Prefer mechanisms that stay inside the pi extension and the existing hook/zerostop flow.'],
  ['redo-first', 'Past gains came from the power to redo: fresh attempts and selection with a real signal. Design how zero-config Vacant can own a fresh attempt or an independent recomputation (e.g. reuse vacant do machinery, spawn the same agent headless in an isolated copy) while keeping install-minimal and the user\'s agent unchanged; be explicit about cost multipliers and when NOT to trigger.'],
  ['signal-first', 'Make every intervention carry a real correctness signal, not opinions: requested-output existence/emptiness, the agent\'s own printed tool outputs vs the delivered value (e.g. the delivered value was never printed but a different value was), projects\' own tests, disagreement between independent computations. Minimize false positives (the paid batch had a 16% false-positive rate on correct answers for gemma before the fixes).'],
]
const designs = await parallel(ANGLES.map(([name, angle]) => () => agent(`${RULES}
${CONTEXT}
You are one of three independent designers. Angle: ${angle}
Using the research below, propose a concrete v3 of zero-config Vacant for pi (other agents can follow later). Only propose what the pi 0.87.1 API supports per the research. Quote simulation numbers for expected effects. Keep total code change reasonable (days, not weeks).
${brief}`, { label: `design:${name}`, phase: 'Design', schema: DESIGN_SCHEMA })))

phase('Judge')
const SPEC_SCHEMA = {
  type: 'object',
  properties: {
    summary_zh: { type: 'string', description: 'Traditional Chinese, plain, for the project owner' },
    build_list: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, what: { type: 'string' }, trigger: { type: 'string' }, text_to_agent: { type: 'string' },
      files: { type: 'string' }, tests: { type: 'string' }, l_fake_acceptance: { type: 'string' }, rationale: { type: 'string' },
    }, required: ['id','what','trigger','text_to_agent','files','tests','l_fake_acceptance','rationale'] } },
    rejected: { type: 'array', items: { type: 'object', properties: { idea: { type: 'string' }, why: { type: 'string' } }, required: ['idea','why'] } },
    eval_plan: { type: 'string' },
    risks: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary_zh','build_list','rejected','eval_plan','risks'],
}
const spec = await agent(`${RULES}
${CONTEXT}
You are the judge. Score the three designs below on: expected rescued/corrected deliveries (grounded in the simulation), false-intervention risk on correct runs, product-principle fit (zero-config, install-minimal, 'no problem => model sees exactly what it would without Vacant', KS-1 wording, fail-open), feasibility in pi 0.87.1, cost multiplier, and testability with a scripted mock model. Then synthesize ONE build spec: an ordered build list (smallest high-value first), with exact agent-facing text, triggers, files, tests, and L-fake acceptance for each item; list rejected ideas with reasons; an evaluation plan for the local gemma-4-12b machines (non-thinking; two machines; compute free; A vs current C1 vs new C2; repeated samples; primary metric and analysis to preregister); and risks.
${brief}
=== DESIGNS ===
${designs.filter(Boolean).map((d, i) => `--- design ${i + 1}: ${d.name} ---\n${JSON.stringify(d, null, 1)}`).join('\n')}`,
  { label: 'judge', phase: 'Judge', schema: SPEC_SCHEMA })

return { research: { pim, code, sim }, designs: designs.filter(Boolean), spec }