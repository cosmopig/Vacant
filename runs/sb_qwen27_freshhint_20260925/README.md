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
  non-thinking). The lcb_3487 rescue is real; its attribution to the hint
  *content* was settled by the round-13 neutral control (below): it was not —
  the no-detail file carried the same rescue. One task is not an effect size.
- **Arm split on the full batch**: fresh_hint 6/6, none 5/6, resample 5/6 —
  the entire gap is the single task lcb_3487. The 3 newly-run tasks
  (lcb_3495/3496/3502) were passed by all three arms on attempt 1, so they add
  no arm-difference signal.
- **Rescue mechanism — narrowed by the round-13 neutral control and the
  round-16 presence control**: on lcb_3487 a file with **no failure detail at
  all** (and even a file of seeded random ASCII) rescued exactly as the
  detail file did. What is excluded: the specific error content as a
  necessary condition. What is not isolated: the filename
  `VACANT_FEEDBACK.md` and "a file the agent did not write is present /
  the workspace differs from origin" (a name-neutral control was not run).
  See the sections below.

## Neutral-hint control (round 13, 2026-10-24): the missing arm for lcb_3487

The v2 table confounded two variables that both changed between the failing
attempts and the fresh_hint rescue: (a) a `VACANT_FEEDBACK.md` file was
present at all, and (b) it named the actual failure (`No module named
'solution'`). The control arm adds (a) without (b): clean resample + a
same-shape file whose body is `retry.render_fresh_hint`'s own neutral
fallback sentence, verbatim. `neutral_cell.py`; each attempt is a plain
`vacant run --retry none` invocation, so argv is byte-identical to the other
arms — only the workspace file differs.

| lcb_3487 arm | a1 | a2 | final grade |
|---|---|---|---|
| none | FAIL (no deliverable, `finish_reason=length`) | — | FAIL, no artifact |
| resample | FAIL (no deliverable) | FAIL (clean ws, no file) | FAIL, no artifact |
| **neutral_hint** (175 B, no detail) | FAIL (same signature) | **PASS** (gate rc=0) | **PASS: 4/4 visible, 24/24 hidden** |
| **presence** (175 B, seeded random ASCII) | FAIL (same signature, rc=20) | **PASS** (gate rc=0, 154.9 s) | **PASS: 4/4 visible, 24/24 hidden** |
| fresh_hint (275 B, detail) | FAIL (no deliverable) | **PASS** | **PASS: 4/4 visible, 24/24 hidden** |

- a1 of the neutral cell failed with the identical signature
  (`finish_reason=length`, empty content, no `solution.py`, gate refused,
  rc=20) — same as none/resample/fresh_hint a1.
- a2 with the neutral file wrote a solution (928 chars) that passed the
  visible gate and all 28 graded cases. The a2 solution differs from the
  fresh_hint a2 solution (different DP formulation, both correct) — the input
  difference genuinely changed the model's behavior, so this is not a
  replay artifact.
- **Attribution (n=1 cell, no statistical claim):** the specific error
  content is *not demonstrated* to be the driver; the presence of the
  retry/feedback signal sufficed in this case. Do not quote the round-12
  result as "the hint content fixed it".

## Pure-presence control (round 16, 2026-10-24): the missing arm was run — it rescues

`presence_cell.py` (committed in `3211c28e`): attempt 2 gets a file of the
SAME size as the neutral hint (175 B), same name (`VACANT_FEEDBACK.md`),
same delivery point — but the content is seeded random ASCII
(`noise_sha256=6c9b58cf…`, recorded in the cell log). Nothing task-relevant,
nothing failure-relevant, no words at all.

| lcb_3487 | a1 | a2 | final grade |
|---|---|---|---|
| presence (175 B noise) | FAIL (same signature, rc=20) | **PASS** (gate rc=0, agent wrote 809-char solution) | **PASS: 4/4 visible, 24/24 hidden** (`grade.json`) |

- **Attribution (n=1 cell, no statistical claim):** a file of *meaningless
  noise* broke the deterministic no-delivery loop as well. The demonstrated
  driver is therefore **not** the failure signal's content; it is something
  in "the workspace is not the clean origin at attempt 2" (file present,
  filename, or the state change between attempts). Do not quote any lcb_3487
  result as "the hint content fixed it".
- **Residual confounds, stated (do not over-read):**
  1. ~~the filename is `VACANT_FEEDBACK.md` — not isolated~~ — **corrected in
     round 21**: the filename never reaches the model (the agent embeds content
     only), so the testable factor was the *header label*; see the label-neutral
     control below, which isolated it;
  2. "a file exists" and "the workspace differs from the origin the agent
     saw at attempt 1" are the same event here and not separated;
  3. n=1 cell, one model, one task — mechanism attribution only, no effect
     size, no generalization to other tasks.

Reproduce:

```bash
python3 neutral_cell.py      # default SB_TID=lcb_3487; ~10 min
python3 grade.py lcb_3487__neutral_hint
python3 presence_cell.py     # round 16; ~10 min
python3 grade.py lcb_3487__presence
```

## Label-neutral control (round 21, 2026-10-25): the label is NOT the driver

Design correction (recorded): the round 18 backlog item "name-neutral control:
random file name" targeted the filename, but `agent_qwen.py` passes only the
file's **content** into the model prompt (under the header line "## Acceptance
feedback from the previous attempt"); the filename never reaches the model. The
testable factor is therefore the **header label**, which tells the model a
previous attempt failed acceptance. `name_cell.py` + `agent_qwen_neu.py`
isolate exactly that: attempt 2 gets the SAME 175-byte seeded noise
(byte-identical, imported from `presence_cell.py`; same sha256) under the neutral
header "## Note". `agent_qwen_neu.py` is byte-identical to `agent_qwen.py` except
that one header line (verified by `diff`).

**Single-factor claim verified on the wire, not by assertion**: the a2 request
bodies of both cells are on disk
(`cells/lcb_3487__presence/wire_RUN-ON/78f7054c…req.bin` vs
`cells/lcb_3487__labelneu/wire_RUN-ON/f5e4ec91…req.bin`); their
`messages[0].content` diff to exactly one line (`-## Acceptance feedback from
the previous attempt` / `+## Note`), with `model`, `max_tokens` (32768),
`temperature` (0) and the noise bytes identical.

| attempt | ws state | result | signature |
|---|---|---|---|
| a1 | clean origin | **rc=20, no deliverable** | same signature as presence a1: `finish_reason=length`, empty content, budget consumed by thinking; requests_seen=1 |
| a2 | + 175B seeded noise (same seed/bytes/sha256 as presence) under **"## Note"** | **rc=0, full=True** | visible 4/4, hidden 24/24 (`grade.json`) |

**Reading**: the rescue happens **without** the label "acceptance feedback from
the previous attempt". The model does not need to be told a previous attempt
failed; any extra prompt content (175 B of noise) breaks the deterministic
no-delivery loop on this task. Attribution narrows from "the failure signal"
(round 13) to "the prompt is no longer a clean start" — label-agnostic.

- **caveats (n=1 cell, no statistical claim):** one model (qwen3.8-27b), one
  task, one attempt per arm, temperature 0; the noise content is fixed (seed
  20261024) — "this specific content" vs "any extra content" is still not
  separated (needs a second seed under the same neutral label; 2 more model
calls, not run this round).

Reproduce:

```bash
python3 name_cell.py a1      # ~7 min (model call); expect no-delivery signature
python3 name_cell.py a2      # ~3-4 min; expect rc=0
python3 grade.py lcb_3487__labelneu
```
