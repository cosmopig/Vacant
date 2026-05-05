# P7 demo seeds — reproducible scenario specifications

P7's four demo scenarios MUST be reproducible at fixed seeds so the thesis defense and any later replays produce identical structure (within deterministic substrates) and statistically-similar reputation distributions (within real-LLM substrates).

## Substrate determinism contract

| Substrate | Determinism |
|---|---|
| `MockSubstrate` | Bit-exact reproducible |
| `DeterministicSubstrate` | Bit-exact reproducible (canned responses keyed by prompt hash) |
| `AnthropicSubstrate` (temp=0) | Statistically reproducible — structure stable, exact text varies ±5% |
| `OllamaSubstrate` (temp=0) | Statistically reproducible — same as above |

The integration test `tests/integration/test_mvp_full.py` MUST use `MockSubstrate` so CI is bit-exact.

## Default seeds

Set in `src/vacant/mvp/scenarios/_seeds.py`:

```python
DEFAULT_SEEDS: dict[str, int] = {
    "law_firm": 42,
    "code_review": 137,
    "multilingual_translation": 271,
    "self_replication": 314,
}
```

Override via CLI: `python -m vacant.mvp.demo --scenario=law_firm --seed=999`.

## Expected outputs at default seeds

The integration test asserts the following invariants. Exact numeric values are computed once on `MockSubstrate` and **frozen** as test fixtures. If the values change, that signals either (a) a real bug or (b) a deliberate scenario change requiring fixture update — the PR must call out which.

### Scenario 1 — law_firm (seed=42)

**Setup**: 1 composite parent ("法律問答 vacant"), 2 closed sub-vacants ("專利查詢", "條款草擬"), 1 client.

**Expected end state after 30 simulated calls**:
- Parent reputation: F ≥ 0.7, R ≥ 0.65 (composite earns from successful delegation)
- Sub "專利查詢": F ≥ 0.75 (high factual accuracy on canned legal facts)
- Sub "條款草擬": L ≥ 0.7 (logical structure)
- All sub-call envelopes traced in parent's logbook
- All three vacants' logbook chains verify
- Both subs remain `state=LOCAL` (no graduation triggered in this scenario)

**Failure assertion**: tampering with any sub's logbook entry must cause `verify_chain()` to fail in the test.

### Scenario 2 — code_review (seed=137)

**Setup**: 5 ACTIVE vacants ("code reviewer" capability), 1 PR-shaped query, all 5 race to review.

**Expected**:
- All 5 dispatched concurrently
- Top-3 by UCB get caller_review credit; bottom-2 get peer_review credit only
- After 100 such queries, reputation distribution: top 2 vacants have μ_F ≥ 0.8, bottom 1 has μ_F ≤ 0.4
- Ranking stable across last 20 queries (no flapping)

**Failure assertion**: if all 5 vacants are stamped with same `controller_id`, the same-controller signal fires and reviewer credibility is downweighted by ≥ 0.5.

### Scenario 3 — multilingual_translation (seed=271)

**Setup**: 6 vacants ("translator" capability), each declaring different `substrate_spec.allowed_substrates`:
- 2 prefer `claude-sonnet-4-6`
- 2 prefer `gpt-4o`
- 2 prefer `local-ollama-llama3`

10 queries each in: en→zh, en→ja, en→es, en→fr.

**Expected**:
- Substrate-aware dispatch: queries route to vacants whose substrate matches the runtime's available backends
- `portability_factor` bonus visible: vacants successfully serving across ≥2 substrates get reputation +0.05 across F
- `n_eff` per `(vacant_id, substrate)` is tracked separately — same vacant on different substrates has separate posteriors

**Failure assertion**: a vacant claiming to support a substrate it can't actually run on must be detected via failed call → reputation penalty.

### Scenario 4 — self_replication (seed=314)

**Setup**: 1 root vacant. Over 200 simulated ticks:
- D1 spawn at tick 30
- D2 spawn at tick 50 (closed child)
- D3 spawn at tick 80 (capability fork)
- D5 spawn at tick 120 (cross-substrate)

**Expected**:
- Lineage tree depth = 2 (root → 4 children, no grandchildren in this scenario)
- All 5 vacants share no keypair (each generates fresh)
- All children have `parent_id` correctly pointing to root
- Root's logbook has 4 SPAWN entries
- D2 child remains `state=LOCAL` throughout (closed child default)
- One graduation attempt at tick 180 for D2 child:
  - If parent consents AND same-* signals all below threshold AND rate limit OK → graduates
  - Post-graduation: same keypair, logbook continues (no fork), `state=ACTIVE`, halo published
- STYLO discount: a self-evolving vacant (D1 with mutation each tick) accumulates STYLO drift; its reputation stalls after epoch 5 due to discount rollover
- Lineage-as-evolution: a NEW D1 child spawned from the high-drift parent inherits a fresh posterior — the lineage continues even though the individual parent stalls

**Failure assertion**: the SUNK heartbeat for any vacant in this scenario carries `key_in_custody=true` and `liveness=false`. Removing the custody attestation must cause the lineage attribution test to fail (the line through that vacant becomes orphaned).

## Adversarial seed (seed=666) — for the dashboard's "Adversarial" page

This is NOT a default scenario but is included in the demo dashboard's adversarial page:

**Setup**:
- 10 ACTIVE vacants, of which 4 share `controller_id` (the colluding ring)
- The ring exchanges high reviews
- The other 6 are independent

**Expected**:
- After 200 reviews, same-controller signal fires on the 4-ring with strength ≥ 0.7
- Ring members' reviews count for ≤ 0.5 weight when the target is also in the ring
- The non-ring vacants' reputations correctly outrank the ring under UCB despite the ring's inflated raw scores

**Failure assertion**: dashboard must visualize the detected ring and explain "cost-raising, not preventing" (per CLAUDE.md framing).

## Where to store fixture files

```
tests/integration/fixtures/
├── law_firm_seed42_expected.json
├── code_review_seed137_expected.json
├── multilingual_translation_seed271_expected.json
├── self_replication_seed314_expected.json
└── adversarial_seed666_expected.json
```

Each file: structural assertions (counts, depths, presence/absence) plus tolerance bounds for non-deterministic parts (reputation μ within ±0.05, ranking stable for top-K).

## Updating fixtures

If a scenario's expected output legitimately changes:

1. Run the scenario locally on `MockSubstrate`
2. Inspect the new output against the spec — does it still satisfy the **invariants** (not the exact numbers)?
3. If yes: update the fixture file in the same PR as the code change
4. PR description must explain WHY the fixture changed and which invariants were preserved
5. Reviewer must verify the new fixture against the spec independently

Do NOT update fixtures to make a failing test pass without verifying the invariants. That's how regressions sneak in.
