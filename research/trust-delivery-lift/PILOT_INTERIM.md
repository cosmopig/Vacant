# Pilot interim — `research/trust-delivery-lift` (v1, superseded)

**Branch:** `research/trust-delivery-lift`  
**Model:** Qwen2.5-0.5B-Instruct CPU  
**Split:** `pilot_ids` (n=12), 5 arms, **non-paired** call1 (design flaw)

## Whole-deliverable success (final)

| Arm | Success | Rate | 95% Wilson CI |
|-----|---------|------|---------------|
| EVR | 2/12 | 16.7% | [4.7%, 44.8%] |
| KEEP/BLIND/BLANKS/RAND | 1/12 each | 8.3% | [1.5%, 35.4%] |

Net gain (draft→final): **0** on all arms — interventions did not flip paired outcomes because visible checks did not flag wrong-but-parseable values (e.g. `240` vs `USD 240 million`).

**Decision:** v2 paired drafts + stronger **visible field contract** (currency, city-only, digit-in-source).

## Pilot v2 (paired, n=12)

| Arm | Success | net_gain_pp |
|-----|---------|-------------|
| BLIND / BLANKS / EVR | 1/12 | 0 |
| KEEP | 0/12 | −8.3 (1× right→wrong) |

Confirmatory: **EVR = BLIND = 1/12** — frozen baseline **BLIND**, null lift.