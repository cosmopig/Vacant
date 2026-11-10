# Plugging in the with-Vacant condition (sketch)

Goal: show Vacant is *effective*, i.e. with Vacant the agent's **process** moves closer to
the user's own reference process (and the user trusts/adopts it more), at the same model,
tasks and budget. Same harness, one switch.

## The single injection point

```
run_baseline.py --condition baseline                 # stock pi system prompt
run_baseline.py --condition vacant --profile P.md    # + pi --append-system-prompt P.md
```

Everything else is identical: fixture repos, prompt text, model (`qwen3.8:27b`), tools,
`reasoning_effort=none`, proxy throttle, timeout, repeats, metric code.

`P.md` is the user's **process profile** produced by Vacant's preference layer
(calibration → structured rules), e.g. (format only, contents must come from the user):

```
When a request is ambiguous about a business rule, ask one question before editing.   [scope: bugfix, feature]
Read the existing tests before changing code; run them before and after.               [scope: code]
Prefer the smallest diff that fixes the issue; do not rename public functions.         [scope: refactor]
Memos: <= 150 words, show the arithmetic for constraints.                              [scope: deliverable]
```

Optional variant (v1): a **pre-step** instead of a system-prompt append — a small call
that selects only the rules relevant to this task (same as the STRUCTURED arm of the
personal-preference pilot) and prepends them, so token cost is matched to a
SUMMARY-profile control.

## Arms for the A/B

| arm | profile | purpose |
|---|---|---|
| BASELINE | none | this directory's current runs |
| SUMMARY | free-text summary of the same calibration data, length-matched | controls for "any personal text helps" |
| VACANT | structured process rules from Vacant | the claim |

## What counts as "effective"

Primary (per user, per task, ≥3 repeats):
1. **Process similarity** to the user's reference process: `edit_sim_collapsed` and
   `feature_agreement` (VACANT − BASELINE, paired by task; bootstrap CI over tasks×repeats).
2. **Self-consistency**: the process should be stable across repeats.

Secondary:
3. Outcome still OK (tests pass / checker accept) — process gains must not cost correctness.
4. Cost: LLM calls, tokens, wall time (from the proxy log).
5. Human: the user blind-rates two trajectories (same task, arms hidden) on
   "this is how I'd want it done" and "I'd trust this agent with the next task"; this is
   the trust link that process similarity is meant to predict.

## Where the reference process comes from

Not invented. Options: (a) the user does the same task themselves in pi/an editor while
we log the same action alphabet; (b) the user picks/edits the step list they'd want;
(c) for multi-person studies, a public dataset of human coding trajectories if one fits
(lit review in progress). Synthetic personas in `personas/examples.json` only demo the metric.
