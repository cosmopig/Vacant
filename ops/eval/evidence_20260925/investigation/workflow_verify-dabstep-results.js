export const meta = {
  name: 'verify-dabstep-results',
  description: 'Independently recompute the formal DABstep A/C results from raw data before presenting them',
  phases: [
    { title: 'Recompute', detail: 'three independent recomputations from raw files' },
    { title: 'Critic', detail: 'compare against the reported numbers and look for gaps' },
  ],
}

const S = '/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad'
const REPO = '/home/user/Vacant'

const COMMON = `Context: a preregistered benchmark compared pi (a coding agent) WITHOUT Vacant (arm A) vs WITH Vacant installed (arm C) on DABstep tasks, via the Harbor framework.
Raw Harbor trial dirs: ${S}/formal/jobs/<model>-on-<arm>/<job-timestamp>/dabstep-<task>__<rand>/ (model is g4 = gemma-4-26b or q38 = qwen3.8-27b; arm A or C). Each trial has result.json (verifier_result.rewards.reward, exception_info), verifier/test-stdout.txt, agent/pi.txt, and for arm C agent/vacant_check.json and agent/vacant_home/trace/projects/*/chain.ndjson.
When a (model, arm, task) has more than one trial dir, the one with the LATEST job-timestamp directory name counts (two gemma C runs were re-run after infrastructure failures: tasks 43 and 50).
The primary analysis excludes tasks 5 and 70 (77 tasks); tasks 5 and 70 are reported separately.
Do NOT read ${REPO}/ops/eval/evidence_20260925/formal/result.json or runs.json or any CONCLUSION file — recompute independently from the raw files with your own Python (use /usr/bin/python3; read-only; do not modify anything).
Exact McNemar two-sided p for discordant counts b,c: n=b+c; k=min(b,c); p=min(1, 2*sum(comb(n,i) for i<=k)*0.5**n).`

const RECOMPUTE = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    numbers: { type: 'object', additionalProperties: true },
    anomalies: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary', 'numbers', 'anomalies'],
}

phase('Recompute')
const [scores, costs, mech] = await parallel([
  () => agent(`${COMMON}

Task: recompute the SCORES. For each model (g4, q38): count trial dirs per arm, identify void runs (no reward or exception), then on the 77 tasks (excluding 5 and 70) using the latest trial per (model, arm, task): A correct, C correct, both, neither, only-A, only-C, McNemar p. List the task ids of every flip (only-A and only-C). Also report tasks 5 and 70 separately. Report all numbers in 'numbers' (keys like g4_A_correct, g4_C_correct, g4_onlyA, g4_onlyC, g4_p, g4_flips_onlyA, g4_flips_onlyC, same for q38, and void runs found). Put anything odd in 'anomalies'.`,
    { label: 'recompute:scores', phase: 'Recompute', schema: RECOMPUTE }),
  () => agent(`${COMMON}

Task: recompute COST and TOKENS from the per-request ledger ${REPO}/ops/eval/evidence_20260925/formal/ledger_formal.jsonl (one JSON per model request; fields tag like formal-<model>-on-<arm>-<task>[-r2], status, usage{prompt_tokens,completion_tokens,reasoning_tokens}, cost, stream_error, retried_stream_errors). Also read ${S}/evalrun/ledger/summary.json field spent_usd (total spent across the whole evaluation). For each model and arm: number of requests, prompt/completion/reasoning tokens, total USD, count of non-200 or stream_error rows, and the percentage extra cost of C over A. Also the grand total for all formal rows. Report in 'numbers'; anomalies in 'anomalies'.`,
    { label: 'recompute:costs', phase: 'Recompute', schema: RECOMPUTE }),
  () => agent(`${COMMON}

Task: recompute what VACANT DID in arm C. For each arm-C trial (latest per task), read agent/vacant_check.json (reviews, review_actions, stop_reached) and the chain.ndjson 'review' events (payload.action 'continue' = sent back, 'allow' = let through; payload.findings with kind; payload.sent = finding ids actually sent back). Per model report: how many C runs reached Vacant's stop check at all, how many were sent back at least once, and the finding kinds sent back. For each sent-back run: the answer the model had written at the first stop (reconstruct if possible, else say unknown), the final answer (verifier/test-stdout.txt 'Got:' and 'Expected:' lines) and whether it was correct before and after. Then: for each flip task (C and A disagree on reward), was the C run ever sent back? Also count how many runs in each arm hit 15 model requests (from the ledger ${REPO}/ops/eval/evidence_20260925/formal/ledger_formal.jsonl, requests per tag) — the agent's turn limit. Report in 'numbers'; anomalies in 'anomalies'.`,
    { label: 'recompute:vacant-behaviour', phase: 'Recompute', schema: RECOMPUTE }),
])

phase('Critic')
const reported = `REPORTED (what the lead told the user):
- gemma think-on, 77 tasks: A 50/77 (64.9%), C 44/77 (57.1%), only-A 11, only-C 5, McNemar p=0.21. Flips only-A: 12,21,23,28,32,40,44,59,61,68,1871; only-C: 15,18,62,65,66.
- qwen think-on, 77 tasks: A 68/77 (88.3%), C 64/77 (83.1%), only-A 6, only-C 2, p=0.29. Flips only-A: 17,36,47,61,1753,1871; only-C: 19,1464.
- tasks 5 and 70: each model A 1/2 and C 1/2, no flips.
- void: 2 gemma C runs (43, 50) re-run once, both scored; 0 pairs dropped.
- harm (correct at first stop then wrong after push-back) = 0; push-back turned wrong into right = 0.
- gemma C reached stop check 41/81 runs, sent back 7 (unsourced 6, failed_step 1); qwen C reached 78/79, sent back 1 (failed_step). 7 of 8 push-backs were on answers already correct.
- all qwen flips and 15/16 gemma flips were C runs never sent back; the one sent back (gemma 62) was C correct, A wrong, answer unchanged.
- gemma runs hitting 15 requests: A 35/77, C 44/77.
- cost: gemma A $0.9174 (974 req), C $1.0068 (1038 req, +9.7%); qwen A $0.6186 (557 req), C $0.6577 (547 req, +6.3%). Provider errors 0. Whole evaluation spent $3.40 of $4.80.`

const critic = await agent(`You are checking a results summary against three independent recomputations. Be adversarial: any number that does not match exactly, or any claim not supported, must be listed.

${reported}

RECOMPUTATION 1 (scores): ${JSON.stringify(scores)}
RECOMPUTATION 2 (costs): ${JSON.stringify(costs)}
RECOMPUTATION 3 (Vacant behaviour): ${JSON.stringify(mech)}

Return: mismatches (reported vs recomputed, with both values), unsupported claims, and anything important for a person deciding what to do next that the reported summary leaves out (e.g. caveats, confounds, sample-size limits). If a recomputation itself looks wrong or incomplete, say so instead of trusting it.`,
  { label: 'critic', phase: 'Critic', schema: {
    type: 'object',
    properties: {
      mismatches: { type: 'array', items: { type: 'string' } },
      unsupported: { type: 'array', items: { type: 'string' } },
      missing_for_decision: { type: 'array', items: { type: 'string' } },
      verdict: { type: 'string' },
    },
    required: ['mismatches', 'unsupported', 'missing_for_decision', 'verdict'],
  } })

return { scores, costs, mech, critic }
