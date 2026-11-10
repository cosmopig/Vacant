# 如何讓 Vacant 有用 — diagnosis + model-free tests (2026-11-10)

All numbers below were produced by the scripts in this directory on Twin-2K-500
(`LLM-Digital-Twin/Twin-2K-500`, `wave_split`, CC BY 4.0) from the local cache
`~/.cache/vacant/twin2k500/rows.jsonl` (2,058 people). No dataset rows are in the repo.
Accuracy = strict accuracy on wave-4 two-option items; Wilson 95% CI; McNemar exact p;
person-cluster bootstrap 95% CI of the paired difference.

## Diagnosis

1. **The holdout is 40/45 grocery purchase decisions at a randomized price**
   (`QID9_1..40`: "product X priced at $Y — would you buy?"). The product per QID is fixed,
   the price is randomized per person (0×…~5× base). Calibration (waves 1–3) has no
   shopping history: cognitive tests (50), economic preferences (18), demographics (14),
   personality (5). Personal data is off-domain, so a careful model is right to be unsure.
2. **The prompt tells the model to abstain** ("Do not invent a preference when the data
   is insufficient" + an `unsure` option). With off-domain data it abstains on 27–79% and
   strict accuracy collapses (0.21–0.43).
3. **The baseline was weak and the price was ignored.** Leave-one-out majority inside
   10 people = 0.520; item-level majority over the other 2,057 people = 0.576 on the same
   450 cells. A population model that reads the price gets 0.680 with no personal data.
4. SUMMARY lines were `W13:QIDxx (block) selected X.` without the question text, so the
   model could not tell what an answer meant.

## Results (same 10 people = 450 cells; 20 people = 900; all 2,058 by 5-fold CV = 92,610)

| Method | personal data used | 10 ppl | 20 ppl | all 2,058 (5-fold) |
|---|---|---|---|---|
| LOO majority within sample (current baseline) | none | 0.520 [0.474–0.566] | 0.481 [0.449–0.514] | – |
| Item majority, population | none | 0.576 [0.529–0.620] | 0.573 [0.541–0.605] | 0.577 [0.574–0.580] |
| kNN CF on wave 1–3 answers (k=50) | wave 1–3 | 0.567 | 0.546 | 0.579 (+0.002 vs item maj., p=0.06) |
| Per-item logistic on wave 1–3 answers | wave 1–3 | 0.551 | 0.557 | 0.572 (−0.005) |
| **Price-aware population prior** (logistic: product + price level) | none | **0.680** [0.636–0.721] | **0.683** [0.652–0.713] | **0.706** [0.703–0.709] |
| + personal residual from K=5 own decisions | 5 other items | 0.698 | 0.701 | 0.722 |
| + personal residual from K=10 | 10 other items | 0.691 | 0.710 | 0.730 |
| + personal residual from K=39 | 39 other items | 0.711 | 0.714 | 0.741 [0.738–0.744] |
| test-retest ceiling (same person, same item, later wave) | – | 0.853 | – | – |

Price-aware prior vs current baseline on the same 10 people: +0.160 (0.680 vs 0.520).
vs item majority: 10 ppl +0.104, McNemar p=3.4e-4, bootstrap [+0.033,+0.171]; all: +0.129.
Personal residual vs price-aware prior (paired): all 2,058 K=5 +0.016 [+0.013,+0.019],
K=10 +0.024 [+0.020,+0.027], K=39 +0.035 [+0.031,+0.039], McNemar p<1e-40 each;
20 ppl K=10 +0.027 (p=0.048, bootstrap [−0.001,+0.057]); 10 ppl not significant (K=39 +0.031, p=0.12).

"Ask when unsure" (abstain on the least-confident fraction, the rest answered),
all 2,058, K=10: ask 0% → 0.730; 10% → 0.752; 20% → 0.771; 30% → 0.790; 50% → 0.828.

Protocol note: the K-decision residual uses the person's answers on *other* wave-4
priced items (online-feedback protocol: Vacant sees accept/reject on earlier tasks of the
same kind). The target item's answer is never used. This differs from the frozen
wave 1–3 → wave 4 protocol of `twin2k.py` and is reported separately.

## Ranked changes

1. Population prior that reads the task facts (here: price) → +13 pp, no LLM, no personal data. Required floor for any personal claim.
2. Collect in-domain accept/reject feedback, model it as a residual on that prior → +1.6 pp (5) … +3.5 pp (39).
3. Replace "unsure" abstention with forced choice + calibrated confidence, and ask the user only below a threshold (20% asks → 0.771 on the rest).
4. Show question text in profile lines; generic off-domain profiles (cognitive/personality) did not help even through CF.
5. Process: inject a process profile (`--append-system-prompt`) — test pending, see below.

## Pending model runs (qwen3.8:27b on Kaggle)

- `llm_forced.py` FORCED_NONE + FORCED_PRECEDENT5 on the 10-person sample: 900 calls, ~35 min at ~2.2 s/call.
- Process with-Vacant arm (PR #92 harness): 4 tasks × 2 synthetic profiles (`process_profiles/`) × 3 repeats = 24 pi runs, ~155 LLM calls, ~30 min (baseline averaged 72 s/run).
  `run_baseline.py --condition vacant --profile experiments/vacant_useful/process_profiles/example_cautious.md --repeats 3 --upstream-label kaggle-qwen3.8:27b --tag cautious` (same for fast).

## Reproduce

```
python extract.py && python price.py && python offline.py && python hier.py && python hier_conf.py
```
