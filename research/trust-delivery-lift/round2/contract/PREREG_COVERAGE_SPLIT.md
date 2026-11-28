# PREREG — uncontested vs contested coverage split

**Frozen:** 2026-11-28T13:55:00Z (before small-model delivery analysis beyond interim row counts)

## Definitions (structural, no outcomes)

For each task, compile authors `A_primary`, `B_independent`, `C_question_only`.  
Execute all three; let aggregate be `PASS` / `FAIL` / `ESCALATE`.

- **Uncontested region:** all three aggregates **identical** AND equal to each other.
- **Contested region:** otherwise → runtime policy **ESCALATE** to `owner_escalate` (no auto-ship).

## Delivery under split policy

- **Uncontested:** ship iff unanimous aggregate is `PASS` (else hold/fail as unanimous).
- **Contested:** **no delivery** (ESCALATE only); excluded from auto-delivery denominator.

## Metrics (report together)

1. **Coverage:** `n_uncontested / n_tasks`, `n_auto_pass_eligible / n_tasks`
2. **On uncontested auto-PASS only:** false-release rate (oracle wrong among shipped), catch among oracle-wrong in uncontested
3. **On full qwen9b / small-model:** same split on **contract executor** applied to model answers
4. **Cost:** mean calls/tokens per arm (small-model arms only)

## Main claim candidate (falsifiable)

**Accountability = honest coverage:** On uncontested region, auto-delivered answers meet bounded false-release; contested volume explicitly owned by human reviewer — **not** “higher catch” from blocking 72% of correct rows.

## Falsifiers

- Uncontested coverage **&lt; 5%**
- False-release on uncontested auto-PASS **≥** primary contract false-release (3.6% on qwen9b baseline)
- Small-model: **0.5B** filing zero-wrong **0** and uncontested false-release ≥ BLIND → mechanism does not beat blind on **shippable** subset

## Small-model priority

If **0.5B** filing zero-wrong rate at floor (interim **0/6** filings), **prioritize 1.5B** arm comparison: **false-release** (delivered PASS & oracle wrong) **vs BLIND** at **field/question** level with **cost** table.