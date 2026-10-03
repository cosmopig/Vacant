export const meta = {
  name: 'local-12b-failure-research',
  description: 'Classify gemma-4-12b failures and reactions to Vacant, then propose and adversarially check the next zero-config change',
  phases: [
    { title: 'Read', detail: 'classify A-arm failures, A-arm successes, and reactions to Vacant in C runs' },
    { title: 'Propose', detail: 'one synthesizer ranks candidate product changes with reach and harm estimates' },
    { title: 'Critique', detail: 'two adversarial critics: product principle and evidence/overfitting' },
  ],
}

const DIR = args.dir
const G = args.groups
const CONTEXT = `
Context (read-only research; do NOT modify any file in /home/user/Vacant, do NOT touch docker, the proxy on port 18900, or anything under ${args.scratch}/local; do NOT read credential files such as ~/.claude*, auth.json, .env, *.key).
Vacant is a zero-config accountability layer installed into a coding agent (here pi 0.87.1). With zero config it records every step, and when the agent says it is done (Stop), it checks whether each step had grounds and sends back only five kinds of problems: a requested output file does not exist, a failed step was ignored, a test claim does not match a test run, a value has no source in the record (only when the request named data), a file the request named was never opened. Vacant never judges whether the answer is right and never picks an answer for the agent; its messages must never say "you are responsible / will be punished" (rule KS-1) and name no actor. v3 adds: when the agent's system prompt states a turn budget (Harbor appends "You have a hard budget of 15 model turns"), and 2 or 1 turns are left, the last turn ran a tool, and the requested output file does not exist, a 3-line reminder rides the next request ("write your current best answer now, you can overwrite it later"); with 1 turn left the Stop check only sends back the missing file. v3.2 (not in these runs) runs the check after a final answer on the capped turn, for the person only.
The runs: DABstep data-analysis questions (answer written to /app/answer.txt, scored by exact-ish match), pi 0.87.1 in Harbor with a 15-turn cap, local model gemma-4-12b-it-qat with thinking OFF. Arms: A = no Vacant; C1 = previous zero-config (v2: Stop check only); C2 = v3 (budget reminder). Each run is rendered as a markdown transcript in ${DIR}/<file> (turns with visible text, tool calls, head of tool results, Vacant messages as "### (vacant-budget|vacant-check message after turn N)", verifier output with Expected/Got, and vacant_check summary). ${DIR}/index.json has per-run metadata (reward, answer_file, turns, stop_reason of last real turn, review actions, nudge turns).
Be concrete and cite run files and turn numbers. Do not speculate beyond what the transcripts show; say "unclear" when unclear.`

const RUN_SCHEMA = {
  type: 'object',
  properties: {
    runs: { type: 'array', items: { type: 'object', properties: {
      file: { type: 'string' },
      outcome: { type: 'string', description: 'no_file_cut_off | no_file_said_done | no_file_other | wrong_answer | correct' },
      category: { type: 'string', description: 'short failure/success category, e.g. loop_same_command, huge_output_flood, never_computed, computed_but_not_written, format_mismatch, wrong_filter, misread_question, guessed_without_computing, tool_error_loop, docs_only, answered_in_text_only' },
      had_candidate_answer_turn: { type: ['integer', 'null'], description: 'first turn where a concrete candidate answer value appears in visible text or tool output that the agent itself computed (null if never)' },
      candidate_matches_expected: { type: ['boolean', 'null'] },
      last_turns_summary: { type: 'string', description: 'what the agent did in its last 4 turns' },
      vacant_observable_signal: { type: 'string', description: 'what a recorder that sees every tool call/result, the request, and the files (but NOT the expected answer) could have noticed, and at which turn' },
      notes: { type: 'string' },
    }, required: ['file', 'outcome', 'category', 'last_turns_summary', 'vacant_observable_signal'] } },
    batch_summary: { type: 'string' },
  },
  required: ['runs', 'batch_summary'],
}

const REACT_SCHEMA = {
  type: 'object',
  properties: {
    runs: { type: 'array', items: { type: 'object', properties: {
      file: { type: 'string' },
      vacant_actions: { type: 'string', description: 'which messages Vacant sent and after which turns (budget reminder / stop pushback kinds), or none' },
      reaction: { type: 'string', description: 'what the model did next: wrote file / rewrote answer / ignored / looped / said done again / ran out of turns' },
      pushback_was_valid: { type: ['boolean', 'null'], description: 'for stop pushbacks: was the flagged problem real per the transcript (null if no pushback)' },
      effect: { type: 'string', description: 'rescued (would have been 0 without it and scored 1) | harmed (answer was right before, wrong after) | wrote_wrong | no_effect | unclear' },
      final_reward: { type: ['number', 'null'] },
      notes: { type: 'string' },
    }, required: ['file', 'vacant_actions', 'reaction', 'effect'] } },
    batch_summary: { type: 'string' },
  },
  required: ['runs', 'batch_summary'],
}

function chunk(a, n) { const out = []; const k = Math.ceil(a.length / n); for (let i = 0; i < a.length; i += k) out.push(a.slice(i, i + k)); return out }

phase('Read')
const failBatches = chunk(G.a_fail, 3)
const reactBatches = chunk(G.c_acted, 2)
const tasks = [
  ...failBatches.map((b, i) => () => agent(`${CONTEXT}

Your job: classify each of these FAILED runs of arm A (no Vacant), reading each transcript fully: ${b.join(', ')}.
For each run decide the outcome, a short category, whether and when the agent itself had a concrete candidate answer before the end, whether that candidate matches the Expected value in the verifier section, what it did in its last 4 turns, and — most importantly — what a recorder that sees every step, the request text, and the files (but never the expected answer) could have noticed and at which turn (e.g. "turns 9-15 run the same grep with the same output", "turn 11 printed the number 0.58 from its own script and it never wrote the file", "the answer file contains a sentence while the request asks for just a number").`, { label: `fail:${i + 1}`, phase: 'Read', schema: RUN_SCHEMA })),
  () => agent(`${CONTEXT}

Your job: classify each of these SUCCESSFUL runs of arm A (reward 1): ${G.a_succ.join(', ')}.
Same fields. Here the point is the false-positive baseline: for each run note which of these signals are also present (so a Vacant rule based on them would also fire on a correct run): repeated identical commands, many turns spent, file written only in the last 2 turns, answer written then overwritten, answer file containing more than the bare answer, the agent never opening the documentation, huge tool outputs, tool errors.`, { label: 'success-baseline', phase: 'Read', schema: RUN_SCHEMA }),
  ...reactBatches.map((b, i) => () => agent(`${CONTEXT}

Your job: for each of these runs of arms C1/C2 where Vacant sent at least one message (or at least ran its Stop check), read the transcript fully and report what Vacant sent and when, how the model reacted, whether each Stop pushback was valid per the transcript, and the effect (rescued / harmed / wrote_wrong / no_effect / unclear). Files: ${b.join(', ')}.
Be strict about "rescued": only when the transcript shows the model had not written the file (or had written a wrong one) before the message and the final reward is 1 because of what it did after. Be strict about "harmed": only when a correct answer file existed before the message and the final one is wrong, or the message made the model waste its last turns so that a correct candidate was never written.`, { label: `react:${i + 1}`, phase: 'Read', schema: REACT_SCHEMA })),
]
const read = (await parallel(tasks)).filter(Boolean)
log(`read batches returned: ${read.length}/${tasks.length}`)

phase('Propose')
const PROPOSAL_SCHEMA = {
  type: 'object',
  properties: {
    failure_profile: { type: 'string', description: 'counts by outcome/category across the 27 A failures, and what the 19 successes look like' },
    reaction_profile: { type: 'string', description: 'counts of rescued / harmed / wrote_wrong / no_effect in C runs, and pushback validity' },
    candidates: { type: 'array', items: { type: 'object', properties: {
      name: { type: 'string' },
      mechanism: { type: 'string', description: 'exactly what Vacant observes, when it acts, what it sends (or writes for the person), within which limits' },
      principle_fit: { type: 'string', description: 'how it fits zero-config / grounds-not-correctness / no answer picking / KS-1 / only-when-budget-stated if it acts mid-run' },
      reach_failures: { type: 'string', description: 'which of the 27 A failures it would plausibly touch (list files), and how many could plausibly flip to correct' },
      false_positive_risk: { type: 'string', description: 'which of the 19 A successes it would also fire on (list files) and what could go wrong there' },
      needs_measurement: { type: 'string' },
      effort: { type: 'string' },
    }, required: ['name', 'mechanism', 'principle_fit', 'reach_failures', 'false_positive_risk'] } },
    recommendation: { type: 'string', description: 'which one (or none) to build next and why; what a held-out test on other DABstep tasks would need to show' },
    not_worth_it: { type: 'string', description: 'ideas considered and rejected, with reasons' },
  },
  required: ['failure_profile', 'reaction_profile', 'candidates', 'recommendation', 'not_worth_it'],
}
const proposal = await agent(`${CONTEXT}

Below are structured classifications of every run (A-arm failures, A-arm successes as a false-positive baseline, and C-arm reactions to Vacant). Spot-check at least 5 of them against the transcripts before relying on them.
Then propose up to 4 concrete candidate product changes for Vacant's zero-config mode that would plausibly raise the share of correct deliveries for this kind of model without breaking the product principle ("install once, use your agent as usual; Vacant checks at 'done' whether each step had grounds and sends back what must be redone before delivery; never judges correctness, never picks an answer"). Mid-run actions are only acceptable inside a stated turn budget (v3 precedent) and must never exceed the budget. Rank by (plausible rescues) minus (plausible harms), and be honest when the evidence is thin (these are small samples; the same 79 tasks are in the running preregistered batch, so any new version must be tested on held-out DABstep tasks).
Also consider changes to the existing v3 reminder (timing, wording, conditions) and to the Stop check's five kinds, based on the reaction data.

CLASSIFICATIONS:
${JSON.stringify(read)}`, { label: 'propose', phase: 'Propose', schema: PROPOSAL_SCHEMA })

phase('Critique')
const CRIT_SCHEMA = {
  type: 'object',
  properties: {
    verdicts: { type: 'array', items: { type: 'object', properties: {
      candidate: { type: 'string' },
      holds: { type: 'boolean' },
      problems: { type: 'string' },
      evidence_checked: { type: 'string', description: 'which transcripts you re-read and what they showed' },
      fix_or_condition: { type: 'string' },
    }, required: ['candidate', 'holds', 'problems', 'evidence_checked'] } },
    overall: { type: 'string' },
  },
  required: ['verdicts', 'overall'],
}
const critics = await parallel([
  () => agent(`${CONTEXT}

You are an adversarial critic from the PRODUCT PRINCIPLE side. For each candidate below, try to show it violates the principle (zero config, minimal install, Vacant judges grounds not correctness, never picks or hints an answer, KS-1 wording, no actor named, mid-run only within a stated budget and never beyond it, byte-identical requests when nothing is wrong), would annoy a real interactive user of pi / Claude Code / Codex / OpenCode who has no turn budget, or would fire wrongly outside DABstep. Re-read transcripts where relevant. Default to holds=false when uncertain.

PROPOSAL:
${JSON.stringify(proposal)}`, { label: 'critic:principle', phase: 'Critique', schema: CRIT_SCHEMA }),
  () => agent(`${CONTEXT}

You are an adversarial critic from the EVIDENCE side. For each candidate below, re-read the transcripts it cites and try to refute its reach and harm estimates: are the "plausible rescues" real (did the agent actually have the right value in hand? would a message at that turn have been acted on, given how the model reacted to Vacant messages in the C runs)? Are there successes it would break? Is it overfitted to these specific 79 tasks or to DABstep's answer-file convention? Default to holds=false when uncertain.

PROPOSAL:
${JSON.stringify(proposal)}`, { label: 'critic:evidence', phase: 'Critique', schema: CRIT_SCHEMA }),
])
return { read, proposal, critics: critics.filter(Boolean) }
