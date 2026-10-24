# sb_qwen27_freshhint — fresh_hint vs resample vs none, real acceptance gate

Small-batch efficacy run for the small-model context (qwen3.8-27b, local LM
Studio). The gate is the **visible** executable test suite, run by
`vacant run` at the moment the agent process exits. Hidden tests are used
**only afterwards** by `grade.py`, never in the gate, prompt, or feedback.

## Design

- **Tasks**: the first 6 rows of `ops/gain/data/lcb_bank_v2.jsonl`
  (deterministic, no cherry-picking). Bank sha256 pinned in `meta.json`
  and `bank_sha256.txt`.
- **Arms** (identical agent for all; the only arm-specific input is
  `VACANT_FEEDBACK.md`, which only the `fresh_hint` arm receives on attempt 2):
  - `none` — 1 attempt (pass@1 baseline)
  - `resample` — up to 2 attempts, workspace reset, no hint
  - `fresh_hint` — up to 2 attempts, workspace reset + ≤400-byte key-failure hint
- **Retry trigger**: the visible suite failing at acceptance time.
- **Mediation**: the agent calls `$OPENAI_BASE_URL` (the `vacant run` tee
  proxy); upstream pinned to `http://100.119.113.56:1234`, model
  `qwen/qwen3.8-27b`, temperature 0. Every request/response is wire-captured
  in `cells/<name>/wire_RUN-ON/`.
- **Agent**: `agent_qwen.py`, deliberately minimal. Reads `TASK.md`
  (+ `VACANT_FEEDBACK.md` if present), asks the model for the full content
  of `solution.py` in one code block, writes it, exits 0. Exit 3 =
  infrastructure failure (no deliverable).

## Harness versions

- **v1** — `max_tokens=8192`. 9 cells run. `lcb_3026` × 3 arms all
  **accepted** (1/1 attempts, visible 3/3). `lcb_3485` and `lcb_3487`
  × 3 arms all produced **no deliverable**: the model used the whole budget
  on `reasoning_content` (`finish_reason=length`, `content` empty). This is a
  budget incident of the harness, not a model or gate failure — those 6 cells
  were never measured. Wire evidence archived in `cells_v1_8192/`.
- **v2** — `max_tokens=32768` (thinking is always on in this build and cannot
  be disabled; the budget must cover thinking + answer). The 6 void cells are
  being re-run under v2 (`rerun_v2.log`). Per-cell harness is recorded in
  `harness.json` and each cell's `make_batch_log.json` (agent sha256 +
  max_tokens).

## Status (as of round 11, 2026-10-24) — all 6 tasks complete

| task | none | resample | fresh_hint |
|---|---|---|---|
| lcb_3026 | accepted a1, full=True | accepted a1, full=True | accepted a1, full=True |
| lcb_3485 | accepted a1, full=True | accepted a1, full=True | accepted a1, full=True |
| lcb_3487 | refused (rc=3, no deliverable) | refused ×2 (rc=3) | refused a1 (rc=3) → **accepted a2**, full=True |
| lcb_3495 | accepted a1, full=True | accepted a1, full=True | accepted a1, full=True |
| lcb_3496 | accepted a1, full=True | accepted a1, full=True | accepted a1, full=True |
| lcb_3502 | accepted a1, full=True | accepted a1, full=True | accepted a1, full=True |

## What can and cannot be concluded from this batch

- The full 6-task batch is complete: 16/18 cells delivered and passed
  visible+hidden; 2/18 (lcb_3487 none + resample) are no-deliverable
  infra-voids. **Zero false-accepts** (no "visible pass, hidden fail").
- The **only** arm difference across all 6 tasks is lcb_3487 (fresh_hint
  rescued on a2; none/resample no-deliverable). fresh_hint 6/6 vs
  none/resample 5/6 — the whole gap is one task.
- `RULED_OUT` / `EFFECTIVE` framing does **not** apply at n=6 tasks with the
  gap concentrated in one task; this is a directional smoke of the mechanism,
  not a significance claim. Not comparable with R532 (thinking-on here).
- Do **not** cite the round-8 `+15.4pp` (6-task subset, contaminated by the
  last two tasks) as an effect size for this mechanism.

## Reproduce

```bash
python3 make_batch.py setup                       # idempotent
python3 make_batch.py run                         # all cells
python3 make_batch.py run lcb_3485__fresh_hint    # one cell
python3 grade.py                                  # post-hoc visible+hidden grade
```

`grade.py` writes `cells/<name>/grade.json`, `rows.jsonl`, `summary.json`.

## v2 results — full 6-task batch (18 cells, completed round 11, 2026-10-24)

| task | none (1 att.) | resample (≤2) | fresh_hint (≤2) |
|---|---|---|---|
| lcb_3026 | accepted a1, full=True | accepted a1, full=True | accepted a1, full=True |
| lcb_3485 | accepted a1, full=True | accepted a1, full=True | accepted a1, full=True |
| lcb_3487 | refused (rc=3, no deliverable) | refused ×2 (rc=3) | refused a1 (rc=3) → **accepted a2**, full=True |
| lcb_3495 | accepted a1, full=True | accepted a1, full=True | accepted a1, full=True |
| lcb_3496 | accepted a1, full=True | accepted a1, full=True | accepted a1, full=True |
| lcb_3502 | accepted a1, full=True | accepted a1, full=True | accepted a1, full=True |

accepted@budget: **none 5/6, resample 5/6, fresh_hint 6/6**. `full=True` means
visible + hidden all passed (graded by `grade.py`, evaluation only).
16/18 cells delivered and passed visible+hidden; the 2 non-delivered cells are
lcb_3487 none + resample (both infra-void, no deliverable).

Honest reading:

- **All 5 failures are the same mode**: `finish_reason=length` with empty
  `content` — the model spent the whole 32768-token output budget on
  `reasoning_content` and produced no answer, so the agent wrote no
  `solution.py` (rc=3, infra-void), and the gate refused a missing
  deliverable. The gate never accepted a wrong answer in this batch.
- **Deterministic at temp=0**: the four no-hint prompts on lcb_3487
  (none-a1, resample-a1, resample-a2, fresh_hint-a1) all returned
  byte-identical 48541-char reasoning and empty content (wire-captured).
- **The only variable on fresh_hint-a2 is the 275-byte hint in the prompt**
  ("No module named 'solution' … Avoid this failure in your clean
  implementation"); that attempt finished (`finish_reason=stop`), wrote
  `solution.py`, passed visible 4/4 and hidden 24/24.
- The round-2 fix (hint redelivery after reset, `launcher.py`) is validated
  in production receipts: `hint_redelivered` sha256 matches attempt 1's hint
  (88089a25…), and attempt 2's `ws_start_sha256` differs from origin
  (hint file re-placed).
- `requests_seen=1` on every attempt → model channel mediation was measured.
- **This is a smoke-level result, not a measurement**: n=6 tasks (18 cells);
  on 5 of 6 tasks every arm passed on attempt 1 (no differentiating signal);
  only lcb_3487 separates the arms, and it separates on a *no-deliverable*
  failure mode. Not comparable with R532 (all arms thinking-on here; R532 was
  non-thinking). The lcb_3487 rescue is real and attributable to the hint,
  but one task is not an effect size.
- **Arm split on the full batch**: fresh_hint 6/6, none 5/6, resample 5/6 —
  the entire gap is the single task lcb_3487. The 3 newly-run tasks
  (lcb_3495/3496/3502) were passed by all three arms on attempt 1, so they add
  no arm-difference signal.
- **Rescue mechanism boundary**: on lcb_3487 the hint's value is (a) breaking
  the deterministic thinking loop by changing the prompt, and (b) its content
  names the actual failure (missing `solution` module). This batch cannot
  separate (a) from (b) — that would need a control arm (hint = neutral text),
  not run.
