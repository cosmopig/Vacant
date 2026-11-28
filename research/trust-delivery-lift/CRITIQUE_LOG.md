# CRITIQUE_LOG — `research/trust-delivery-lift`

Record of external (Gemini) critiques and responses.

| Time (UTC) | Critique | Response |
|------------|----------|----------|
| 2026-11-28 13:20 | *(awaiting first relay)* | Initial push: typed scorer + synthetic controls; equal 2-call arms; pilot v1 complete. Documented known design gap (non-paired call1 per arm) before v2 fix. |

## Anticipated critic targets (pre-buttress)

1. **Non-paired drafts in pilot v1** — Fixed in v2: `freeze_drafts.py` + `harness.py --drafts`.
2. **Visible grader too weak (EVR starved)** — Added currency-required visible rule, hq_city comma rule, digit-in-source check (no gold).
3. **Scale / big models** — Scope locked to Qwen2.5-0.5B CPU only; Colab notebook deferred / 0.5B only.