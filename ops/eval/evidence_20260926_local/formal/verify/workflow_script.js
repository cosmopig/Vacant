export const meta = {
  name: 'verify-local-formal-result',
  description: 'Adversarially verify the preregistered local formal result (C2 v3 vs A, p=0.019) before it is reported',
  phases: [
    { title: 'Refute', detail: 'three independent attempts to break the result: data integrity, attribution, statistics' },
  ],
}
const S = args.scratch
const CONTEXT = `
Read-only verification. Do NOT modify anything under /home/user/Vacant or ${S}/local; do not touch docker, the proxy on port 18900, or the running held-out batch (${S}/local/heldout_v34). Do not read credential files. Use scratch space under /tmp/claude-0/verify_formal/ for your own scripts.

Preregistration: /home/user/Vacant/decisions/prereg/PREREG_20260926_ZERO_CONFIG_V3_LOCAL.md (frozen at commit 769022a3). Run log: /home/user/Vacant/ops/eval/evidence_20260926_local/RUNLOG.md (sections 7 and 11: a session restart at 14:32 UTC interrupted 3 runs, which were re-run per the infra_void rule).
Raw data: ${S}/local/formal_v3/g12-off-<ARM>-s<k>/v3local-g12-off-<ARM>-<task>-s<k>/dabstep-<task>__<id>/ (result.json, verifier/, agent/pi.txt, agent/vacant_check.json, agent/vacant_home/ for C arms); ${S}/local/formal_v3/_void_first/ (the 3 interrupted originals); progress.jsonl; logs/. Proxy ledger: ${S}/local/ledger/ (ledger.jsonl per request with tag and upstream; io.jsonl full bodies, ~0.6 GB — stream it, do not load whole).
Analysis output (preregistered tool): ${S}/local/analysis_formal/summary.json, cells.json, split_ended_C2.json, exceptions.json.
Reported result: primary C2 (Vacant v3, wheel sha256 0dcd5d68…42a2) vs A (no Vacant): per-task mean correct over 3 complete samples, 77 tasks (5 and 70 excluded), exact Wilcoxon p=0.0189 (frozen function; an independent midrank recomputation with tolerance for float ties gives p=0.0207), mean diff +0.0736, 15 tasks better / 7 worse. Secondary: C1 vs A p=0.46; C2 vs C1 p=0.118 (Holm 0.237). A arm correct 41/38/41, C2 45/47/45. C2 cut 'no answer file' from 26-30 to 4-8 per sample while wrong answers rose from 9-10 to 24-26.
Your job is to try to REFUTE or weaken the reported result from your angle. Report what you checked, what you found, and whether the result survives. Be concrete (file paths, counts).`

const SCHEMA = {
  type: 'object',
  properties: {
    survives: { type: 'boolean', description: 'does the reported primary result survive your checks' },
    checks: { type: 'array', items: { type: 'object', properties: {
      check: { type: 'string' }, method: { type: 'string' }, finding: { type: 'string' }, problem: { type: 'boolean' },
    }, required: ['check', 'finding', 'problem'] } },
    caveats_to_report: { type: 'string', description: 'caveats that must accompany the result when reported' },
  },
  required: ['survives', 'checks', 'caveats_to_report'],
}

phase('Refute')
const out = await parallel([
  () => agent(`${CONTEXT}

ANGLE: data integrity and protocol. Check: every (task, sample) triple of A/C1/C2 ran on the same upstream machine and close in time (ledger tags and 'upstream'); every C2 run installed the frozen C2 wheel and every C1 run the C1 wheel (look in agent setup logs / vacant_check.json install_json, and any wheel hash evidence), no A run had Vacant installed; the 'latest run per cell' logic picked the re-runs for the 3 interrupted cells and nothing else was duplicated; the prereg's order and stopping rule were followed (samples 1..3 in order, no reward-based stopping); rewards in cells.json match verifier/reward.txt; tasks 5 and 70 excluded; thinking was off for all requests (reasoning_effort=none forced by the proxy; spot-check io.jsonl bodies for a few tags of each arm).`, { label: 'refute:integrity', phase: 'Refute', schema: SCHEMA }),
  () => agent(`${CONTEXT}

ANGLE: attribution — is the gain caused by what Vacant v3 does (budget reminder at 2/1 turns left; last-turn narrowing; the stop check) or by something else (noise, machine, the install changing the environment, time of day, a few tasks)? For each of the 15 better and 7 worse tasks (per-task means C2 vs A), look at the C2 runs: was there a nudge (vacant_check.json nudge_turns), did the answer file get written after the nudge (compare turn of the write in agent/pi.txt with the nudge turn), was there a stop pushback? Estimate how many of the net extra correct C2 runs are explained by writes after a reminder vs stop pushbacks vs neither. Compare with A's own between-sample noise (A flips 8-15 between samples). Also check whether any C2 gain comes from runs where Vacant did nothing (that would be noise).`, { label: 'refute:attribution', phase: 'Refute', schema: SCHEMA }),
  () => agent(`${CONTEXT}

ANGLE: statistics and robustness. Recompute from raw result.json (not cells.json) the per-task means and the paired tests: exact Wilcoxon with correct tie handling, sign test, a paired permutation test on the mean difference, a bootstrap CI over tasks for the mean difference, per-sample McNemar; sensitivity: include tasks 5 and 70; use only samples 1-2; drop the 3 re-run cells; per machine. Check whether the result hinges on a handful of tasks (leave-one-task-out on the Wilcoxon p). Report honestly if the sign test (p≈0.13) disagreeing with Wilcoxon matters and how to word it.`, { label: 'refute:stats', phase: 'Refute', schema: SCHEMA }),
])
return { verdicts: out.filter(Boolean) }
