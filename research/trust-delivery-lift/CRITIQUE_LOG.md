# CRITIQUE_LOG — `research/trust-delivery-lift`

Record of external (Gemini) critiques and responses.

| Time (UTC) | Critique | Response |
|------------|----------|----------|
| 2026-11-28 13:20 | *(awaiting first relay)* | Initial push: typed scorer + synthetic controls; equal 2-call arms; pilot v1 complete. Documented known design gap (non-paired call1 per arm) before v2 fix. |
| 2026-11-28 13:35 | *(self-review / expected)* Speed over scale; 0.5B only | Confirmed no 7–9B; Colab notebook uses 0.5B CPU path only. |
| 2026-11-28 13:35 | *(self-review)* Pairing & visible grader | v2 `freeze_drafts.py`, visible currency/city/source-digit checks; confirmatory held-out null. |
| 2026-11-28 21:23 | **Gemini** (upload `ideas-20261128-2123`): (1) n=12 no power—need n≥120–200; (2) 8% Pass@1 floor—not accountability; (3) separate visible vs oracle 2×2; no credit for abstention; (4) 0.5B in-context editing paralysis—use harness merge not full JSON rewrite; (5) BLIND weak baseline—use Maj@3/logprob Bo3 matched CPU+tokens | **Pilot 1 kept as honest null.** Round 2: `PREREG_ROUND2.md`, invoice 8-field bank, field-locked VACANT + STITCH, Maj3/LPB3 baselines, n≥150 holdout, gating secondary Rank 4. |
| 2026-11-28 ~17:30 UTC | **User + GAP_MAP** (`GAP_MAP_94bb.md`, `LINKS_5e63.md`): P0 typed extraction controls; round-2 primary = field-lock + **BLIND** as key baseline (Maj/BoN not contribution); Filing-Evidence offline typed audit + stop rule; binding avoid list §4; milestone ~06:00 Taipei = P0 + one real result | **Done:** `validate_controls.py` → 15/15 controls; **Filing offline** on HF qwen3.5-9b C1: catch **74.3%** on quote-pass-wrong (n=101), false reject **4.8%** (n=724), stop rule **pass** → online filing arms allowed. `PREREG_ROUND2.md` rewritten. Maj3 demoted to non-contribution baseline in prereg. |

## Anticipated critic targets (pre-buttress)

1. **Non-paired drafts in pilot v1** — Fixed in v2: `freeze_drafts.py` + `harness.py --drafts`.
2. **Visible grader too weak (EVR starved)** — Added currency-required visible rule, hq_city comma rule, digit-in-source check (no gold).
3. **Scale / big models** — Scope locked to Qwen2.5-0.5B CPU only; Colab notebook deferred / 0.5B only.