# Cost parity audit (exploratory — pilot_excluded rows only)

**Source:** `hold_000`–`hold_021`, broken-checker era (`rows.jsonl` pilot slice). **Not** confirmatory. Numbers in `COST_PARITY_AUDIT.json`.

## Findings (no “equal cost” claim)

| Arm | mean `n_calls` | call histogram | mean tokens | mean CPU-s | mechanism |
|-----|----------------|----------------|-------------|------------|-----------|
| BLIND | 2 | always 2 | ~572 | ~11.3 (median ~6.8; one outlier ~100s) | 2× full JSON, `max_new_tokens=220`, call-2 is delivery |
| MAJ3 | 3 | always 3 | ~855 | ~11.4 | 3× full JSON + merge |
| LPB3 | 3 | always 3 | ~866 | ~11.9 | 3× full JSON + logprob pick |
| VACANT | 2 | always 2 | ~471 | ~3.3 | 1× full JSON + **1× micro** (`max_new_tokens=48`) — stopped early while visible-all-fail under broken checker |

**VACANT is cheaper because it issued fewer tokens and wall time**, not because of a shared cross-arm draft cache: each arm constructs its own `SmallLM.generate` sequence in `harness_r2.py` (no cross-arm KV reuse; single process only amortizes **model weight load once** per harness).

## RNG / decoding parity

- **BLIND / MAJ3:** `temperature=0.7` on extra samples; harness `rng` passed but only used by those arms.
- **VACANT:** micro calls `temperature=0.3`; first call greedy (`temperature=0` default).
- **LPB3:** `with_logprob=True`, `temperature=0.7` on three samples.
- **Budget:** VACANT up to **1 + 4 micro** = 5 calls when visible fails persist; pilot era always stopped at **2** calls (all fields still failing visible under `vendor` bug).

## Reporting rule

Report **per-arm distributions** (means/medians in JSON); do **not** assert matched-cost comparison without paired design.