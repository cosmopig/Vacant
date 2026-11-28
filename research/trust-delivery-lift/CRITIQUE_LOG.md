# CRITIQUE_LOG — `research/trust-delivery-lift`

Record of external (Gemini) critiques and responses.

| Time (UTC) | Critique | Response |
|------------|----------|----------|
| 2026-11-28 13:20 | *(awaiting first relay)* | Initial push: typed scorer + synthetic controls; equal 2-call arms; pilot v1 complete. Documented known design gap (non-paired call1 per arm) before v2 fix. |
| 2026-11-28 13:35 | *(self-review / expected)* Speed over scale; 0.5B only | Confirmed no 7–9B; Colab notebook uses 0.5B CPU path only. |
| 2026-11-28 13:35 | *(self-review)* Pairing & visible grader | v2 `freeze_drafts.py`, visible currency/city/source-digit checks; confirmatory held-out null. |
| 2026-11-28 21:23 | **Gemini** (upload `ideas-20261128-2123`): (1) n=12 no power—need n≥120–200; (2) 8% Pass@1 floor—not accountability; (3) separate visible vs oracle 2×2; no credit for abstention; (4) 0.5B in-context editing paralysis—use harness merge not full JSON rewrite; (5) BLIND weak baseline—use Maj@3/logprob Bo3 matched CPU+tokens | **Pilot 1 kept as honest null.** Round 2: `PREREG_ROUND2.md`, invoice 8-field bank, field-locked VACANT + STITCH, Maj3/LPB3 baselines, n≥150 holdout, gating secondary Rank 4. |

## Anticipated critic targets (pre-buttress)

1. **Non-paired drafts in pilot v1** — Fixed in v2: `freeze_drafts.py` + `harness.py --drafts`.
2. **Visible grader too weak (EVR starved)** — Added currency-required visible rule, hq_city comma rule, digit-in-source check (no gold).
3. **Scale / big models** — Scope locked to Qwen2.5-0.5B CPU only; Colab notebook deferred / 0.5B only.