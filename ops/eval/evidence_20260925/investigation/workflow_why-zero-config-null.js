export const meta = {
  name: 'why-zero-config-null',
  description: 'Precise investigation: past Vacant results vs the zero-config null, failure taxonomy, literature',
  phases: [
    { title: 'Investigate', detail: 'three targeted readers in parallel' },
  ],
}

const REPO = '/home/user/Vacant'
const S = '/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad'

const OUT = {
  type: 'object',
  properties: {
    summary: { type: 'string', description: 'Traditional Chinese, plain language, 10-25 sentences' },
    table: { type: 'array', items: { type: 'object', additionalProperties: true } },
    citations: { type: 'array', items: { type: 'string' }, description: 'file:line or paper reference for every number/claim' },
    caveats: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary', 'table', 'citations', 'caveats'],
}

const RULES = `Rules: read-only (do not modify any file); every number you report must be quoted exactly from a file you opened, with file:line; if two sources disagree, report both; do not invent results; write the summary in Traditional Chinese plain language (the reader is the project owner, not a statistician).`

const results = await parallel([
  () => agent(`${RULES}

Task: build a precise table of PAST Vacant experiments (before 2026-09-25) that measured whether Vacant improved delivered results. Sources to read: ${REPO}/docs/JOURNEY_2026-09-13.md (sections 5 and 6), ${REPO}/docs/VACANT_ARCHITECTURE_AND_RESULTS_2026-09-07.md (section 2.2 arms, section 3), ${REPO}/decisions/conclusions/CONCLUSION_20260830_G_EXPERIMENT.md, CONCLUSION_20260904_R445_CONFORM_SETTLEMENT.md, CONCLUSION_20260904_R446_EQUAL_BUDGET.md, ${REPO}/docs/paper_2026-09-14/manuscript.md (abstract, methods, results), and the decisions they cite for R460, R460R, R529 (under ${REPO}/decisions/). Also check whether retry-channel / localized-feedback experiments (R535, R536) were run or only preregistered (grep decisions/ and runs/INDEX.md).
For each experiment row give: id, date, benchmark and n, model, arms compared, WHO CONTROLLED GENERATION (did Vacant itself call the model / resample / select / refuse, or was it a passive checker inside another agent?), VERIFIER TYPE (executable visible tests, hidden tests only for scoring, majority vote, model judge, none), budget per task (calls), effect size (pp), CI/p, replication status, and the exact wording the project's own decision files allow.
Then answer precisely: (1) in which configurations did Vacant produce measurably better delivery, and which ingredient carried the gain according to the project's own analysis? (2) which configurations produced no gain (e.g. committee ON vs OFF5, revision H-MIX vs CONFORM)? (3) how does the 2026-09-25 zero-config design (a passive Stop-hook checker inside pi with no executable tests, pushing back at most twice within pi's 15-turn budget; see ${REPO}/decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md) map onto these configurations — which past configuration is it closest to?`,
    { label: 'past-results', phase: 'Investigate', schema: OUT }),
  () => agent(`${RULES}

Task: failure taxonomy of the 2026-09-25 formal DABstep batch, to find the CEILING of what any zero-config Vacant check could have caught. Raw data: ${S}/formal/jobs/<model>-on-<arm>/<job>/dabstep-<task>__<rand>/ (models g4 = gemma-4-26b, q38 = qwen3.8-27b; arms A = without Vacant, C = with). Use the LATEST job dir per (model, arm, task). Each trial: result.json (verifier_result.rewards.reward), verifier/test-stdout.txt (Expected:/Got: lines or 'answer.txt not found'), agent/pi/sessions/*.jsonl (full pi transcript: user/assistant/toolResult messages), agent/trajectory.json. Task instructions and expected answers: ${S}/dabstep_pinned/formal/dabstep-<task>/instruction.md and tests/test.sh. Data files are described in the instruction (payments.csv, fees.json, manual.md, merchant_data.json ...).
For EVERY failed run (reward 0) in both arms and both models (excluding tasks 5 and 70 from the headline counts but listing them), classify the failure into one of: (a) no answer written because the 15-turn/15-request cap was hit; (b) no answer written for another reason; (c) empty or malformed answer (format/guideline violation); (d) wrong answer after reading the relevant data — reasoning/interpretation error (say which: misread manual rule, wrong filter/join, wrong time window, arithmetic, rounding, etc.); (e) wrong answer with an unsourced/fabricated value; (f) other. Read the transcripts for the wrong-answer runs (d/e) carefully enough to name the specific mistake; it is fine to sample if there are too many, but say how many you read.
Then for each class say which verification signal could have caught it BEFORE delivery: (1) the current five zero-config checks (missing output file, failed step skipped, test-claim mismatch, unsourced value, named file unopened); (2) a cheap format/emptiness check; (3) an independent recomputation of the answer (i.e. a second solver / verifier model); (4) nothing short of a correct solution. Give counts per model and arm. Conclude: of all wrong/missing answers, how many could a zero-config process-evidence checker possibly have fixed, and how many need an independent solver or oracle?`,
    { label: 'failure-taxonomy', phase: 'Investigate', schema: OUT }),
  () => agent(`${RULES}

Task: what the literature predicts for this result. Read ${REPO}/docs/LITERATURE_GAP_2026-09-18.md (it contains per-paper summaries with verification level; use ONLY papers listed there, and quote which claim each supports) and ${REPO}/docs/paper_2026-09-14/manuscript.md section 2 (related work). Also see ${REPO}/decisions/DECISION_20260925_ZERO_CONFIG_EVAL.md for how the evaluation cited prior work (e.g. Kamoi budget-matching).
Answer precisely, citing papers from those files: (1) Does published evidence predict that a feedback/critique loop WITHOUT an external correctness signal (no tests, no ground truth) improves task accuracy? (self-correction literature: Huang 2023, Kamoi 2024, Stechly/Valmeekam, Olausson self-repair, Tyen 'can correct given error location', Self-Refine/Reflexion as counter-claims — with their caveats). (2) What ingredients does the literature say ARE needed for gains (external verifier strength, execution feedback, repeated sampling + verifier, test-time compute)? (3) Is there evidence about systems that sit OUTSIDE the agent loop (monitors/hooks that only see the trace) improving outcomes, versus systems that own generation? If the repo's literature files do not cover a point, say 'not covered in the verified literature' rather than guessing. (4) Given (1)-(3), is 'Vacant must become an agent' the right conclusion, or is the needed ingredient something narrower (a verifier with real information about correctness + control over resampling/selection)? Keep claims at the strength the sources support.`,
    { label: 'literature', phase: 'Investigate', schema: OUT }),
])

return { past: results[0], failures: results[1], literature: results[2] }
