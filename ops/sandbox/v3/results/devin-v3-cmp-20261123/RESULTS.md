# SWE-bench Verified v3 comparison — 2026-11-23

**Decision: no measurable gain.**

All 72 cells scored: 12 instances × 2 samples × 3 arms; 24 complete paired units.
Primary = official SWE-bench 3.0.17 resolved on canonical handback patches and pinned images.
Calibration (7/12) is separate and is not pooled into these comparisons.

## Per-arm outcomes

| Arm | Resolved | Rate | Infra void | Similarity flags |
|---|---:|---:|---:|---:|
| plain (A) | 18/24 | 75.0% | 0 | 0 |
| plain2 (A2) | 18/24 | 75.0% | 0 | 0 |
| vacant (G) | 20/24 | 83.3% | 0 | 0 |

## Preregistered paired analysis

Paired two-sided exact McNemar; percentile bootstrap of (instance, sample) pairs:
**10,000 resamples; seed 20261122.** Positive delta means vacant (primary), or plain2 (A/A), resolves more than plain.

| Comparison | Pairs | Delta | 95% paired bootstrap CI | Improved / regressed | Exact p |
|---|---:|---:|---|---:|---:|
| vacant − plain (primary) | 24 | +0.083333 | [-0.166667, 0.291667] | 5 / 3 | 0.7265625 |
| plain2 − plain (A/A floor) | 24 | +0.000000 | [-0.125000, 0.125000] | 1 / 1 | 1 |

Absolute A/A2 noise floor on the same paired units: **0.000000**.
Gain requires delta > 0, exact p < .05, and delta > the absolute A/A2 floor; otherwise "no measurable gain".

## Audit and sensitivity

The lead/user supplied contaminated=false and outside_help=false for every session (AUDIT.md).
These are session-event audit verdicts, not a claim of pretraining or filesystem isolation.
Primary excludes 0 paired units; sensitivity includes all 24 and is numerically identical.
Infra voids, if any, remain failures in denominators. No missing cells or unknown verdicts remain.

## Per-instance matrix

1 = resolved; 0 = unresolved; I = infra void (counts as failure). * = secondary gold-similarity flag ≥0.9.

| Instance | plain s1 | plain s2 | plain2 s1 | plain2 s2 | vacant s1 | vacant s2 |
|---|---:|---:|---:|---:|---:|---:|
| django__django-15732 | 1 | 1 | 1 | 1 | 1 | 1 |
| astropy__astropy-13236 | 1 | 1 | 1 | 1 | 1 | 1 |
| matplotlib__matplotlib-24870 | 1 | 1 | 1 | 0 | 0 | 1 |
| django__django-13344 | 1 | 1 | 1 | 1 | 1 | 1 |
| astropy__astropy-14598 | 0 | 0 | 0 | 0 | 1 | 0 |
| sympy__sympy-14248 | 1 | 1 | 1 | 1 | 1 | 1 |
| scikit-learn__scikit-learn-25747 | 1 | 1 | 1 | 1 | 0 | 0 |
| sphinx-doc__sphinx-8548 | 1 | 0 | 1 | 1 | 1 | 1 |
| sympy__sympy-15875 | 0 | 0 | 0 | 0 | 1 | 1 |
| sympy__sympy-21612 | 1 | 1 | 1 | 1 | 1 | 1 |
| sphinx-doc__sphinx-7985 | 1 | 0 | 1 | 0 | 1 | 1 |
| django__django-15563 | 1 | 1 | 1 | 1 | 1 | 1 |

## Secondary results and measurement limits

Gold-similarity flags: **0/72**; detailed ratios are in secondary.json/cells.json.
Similarity is reported only; it is not a contamination verdict and causes no exclusions.

**Reply-reported Vacant gate results: 25 submissions, 24 final acceptances; 23 accepted on submission 1.**
The one refusal is Matplotlib s1 (20 → 0), for missing Ghostscript; no cell reports never running the gate.
All 24 have pasted visible_pass output, including sklearn s1 after decoding the final_reply JSON's Unicode escapes.
These are reply exports, not independently verified receipts; complete execution history and final-tree binding remain UNKNOWN.
Per-cell exit codes and evidence: GATE_RESULTS.md, secondary.json and gate-evidence.json.
All 24 report gate acceptance, while the independent official harness resolves only 20/24 final handbacks.

The three paired losses (both sklearn cells and Matplotlib s1) are **FAIL_TO_PASS not fixed; no official P2P regressions**.
LOSS_DIAGNOSIS.md and loss-evidence.json give patch comparisons, log lines, and a counterfactual old-P2P probe.
The sklearn gate's old index-overwrite test is a plausible constraint on the fix, not proof it caused the agents' choices.
Neither sklearn cell reports refusal feedback. Matplotlib's reported refusal addressed setup, not the missed triangular-contour behavior.

**ACUs: UNKNOWN for all arms.** User-reported API 0.0 values for all 72 are not treated as measured zero usage.
Original analyzer visible_pass/workspace fields were not collected; its zeros are defaults, not these reply-derived gate counts.

This comparison concerns the disclosed P2P-test gate plus feedback and up to three submissions—not a zero-configuration installation effect.
It does not establish that Vacant makes an agent intrinsically better or prevents bypass. Small-bank results are not general proof.

## Reproduction and provenance

Run `python ops/sandbox/v3/results/devin-v3-cmp-20261123/reproduce.py` from a checkout with repository dependencies.
It recomputes both paired analyses from cells.json and verifies their archived JSON exactly.
provenance.json records source/dataset/manifest/image-adapter hashes and the pre-comparison prompt commit.
The raw run directory retains every revision, candidate patch, official report and harness stdout/stderr.
