# Pi + GPT-5.6-Luna × Vacant bridge: paired six-task smoke (2026-09-28)

This is an actual agent run, distinct from the R534 score-only replay. The result is **6/6 versus 6/6, no measured correctness gain**. Its small, easy sample has a ceiling and does not estimate the 920-task effect.

> **Correction (2026-10-01, review W4): the "Vacant" arm below is gate-equivalent, not `repair`.** The protocol bullet that says
> "Mode `repair` … one feedback round planned on rejection" names the bridge's *contract mode*, but this run used the external
> `prepare → judge → release` harness and **no Pi extension or Stop hook was loaded** (`PI_PLUGIN_PUBLIC_BENCH_20260928.md` says the same, and
> records that Pi 0.73.1, the version used here, lacked a stop-hook event). Nothing could deliver feedback, so the arm was one judge followed by release
> or refusal. The saved results JSON has no hook, feedback or mode field. The numbers and the sentence "no task exercised repair" below were already
> correct; only the mode label was misleading. This run says nothing about the REPAIR arm and must not be pooled with the real-extension runs.

## Protocol

- Source: the already pinned R534 task templates and separate scoring checks in `ops/gain/r534/`. Select the four shortest `goal.md` files by character length and, after observing 4/4 in each arm, add the two longest by that same rule. IDs below are in run order. The latter addition is exploratory.
- Both arms: independent Pi 0.73.1 sessions, `gpt-5.6-luna` through a local codex2api, low thinking, identical initial prompt: `Read goal.md. Implement solution.py with the requested top-level function. You may use the visible tests and run_tests.sh. Finish with the file saved.` Both see the same R534 template files. No hidden check enters either agent workspace or feedback.
- Native: score the saved `solution.py` directly. Vacant: `prepare` before starting Pi, receiver-pin `tests_visible`, judge the saved file, and score only the released `solution.py`. Contract mode label `repair` (but no hook was loaded; see the correction above, the arm was gate-equivalent), two maximum attempts, one feedback round "planned" on rejection that no component could have delivered. All six first judges accepted, so no second attempt happened.
- Grader: run all `check_*` functions in each task's `hidden/lcb_*/test_hidden.py` in a separate grading directory containing a copy of the actual handed-off solution. The check is a conjunction, not a count of passed cases. The Vacant release reported `readback_ok: true` in each row.
- Local limitations: one OS account (`insecure_same_account=True`) and `sandbox=none`. This does not test isolation or hostile agent bypass. Sessions are independent stochastic runs, not matched deterministic seeds.
- Proxy compatibility: codex2api client version advertised as `0.158.0` so this account exposes `gpt-5.6-luna`; the local proxy was adapted to omit `max_output_tokens`, which the Codex subscription backend rejects. That adaptation is in the temporary proxy checkout, not in Vacant.

## Results

| Task | Native hidden | Vacant first judge | Vacant release/hidden | Native Pi seconds | Vacant Pi seconds |
| --- | --- | --- | --- | ---: | ---: |
| lcb_3686 | PASS | accept | released / PASS | 48.11 | 66.87 |
| lcb_3715 | PASS | accept | released / PASS | 31.78 | 64.10 |
| lcb_3548 | PASS | accept | released / PASS | 29.27 | 30.93 |
| lcb_3522 | PASS | accept | released / PASS | 21.44 | 22.76 |
| lcb_3794 | PASS | accept | released / PASS | 58.32 | 32.71 |
| lcb_3657 | PASS | accept | released / PASS | 27.17 | 32.69 |
| **Total** | **6/6** | **6 accept** | **6/6** | **216.09** | **250.06** |

Model usage reported by Pi: native 101,975 input / 6,815 output tokens; Vacant 106,285 input / 7,076 output tokens. Times sum only Pi invocations, excluding receiver judge/release, and vary between independent generations. No task exercised repair, so this run cannot measure the mechanism most likely to improve correctness. Passing visible acceptance also does not imply passing hidden checks; the fact that all six passed hidden is an empirical result for these six submissions only.

Machine-readable per-arm record: [`PI_LUNA_PAIR_SMOKE_RESULTS.json`](PI_LUNA_PAIR_SMOKE_RESULTS.json). It includes Pi usage, first judge results, release readback, and hidden scoring outcome; no secrets or hidden test bodies are embedded.
