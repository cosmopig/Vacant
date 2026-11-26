# `ops/fl/` — Fast-Lane Single-Round Code Runner & Zero-Answer Judge Comparison

Fast-lane experiment harness for single-round functional LeetCode tasks (`ops/gain/data/lcb_bank_v3.jsonl`) using Claude Code (Haiku) inside E1′'s isolated sandbox (`--unshare-net` allowlist proxy, read-only credentials, `--unshare-net` evaluation sandbox).

## Goal

Compare home-made acceptance criteria ("judges") that use **NO bank hidden tests and NO answers** against:
- `B0`: single-attempt baseline
- `B0x3`: same-budget (3-attempt) baseline without any test/gate signal
- `GT`: oracle upper bound (gated on `gate_hidden`)

## Bank & Deterministic Split

- Bank: `ops/gain/data/lcb_bank_v3.jsonl` (189 LeetCode functional tasks: 135 medium, 54 hard).
- **SHA-256 verification**: verified against `runs/INDEX.json` (`banks.lcb.v3.sha256`) before running; refuses on mismatch.
- **Deterministic 50/50 split**: per task, `hidden_tests` is split 50/50 using a deterministic seed derived from `(plan.seed, task_id)` into `gate_hidden` and `eval_hidden`. Tasks with `< 4` hidden tests are skipped and logged.
- **Strict evaluation separation**: EVERY arm is scored **only** on `eval_hidden` (and nothing else). All arms share the exact same `eval_hidden` set.
- **Literal parsing**: test specifications (including TF/XM `tests_spec.py`) are parsed strictly via `ast.parse` + `ast.literal_eval` (never `eval`/`exec`).
- **LeetCode `class Solution` normalization**: candidates may define either a top-level `<entry_point>` function or `class Solution` with method `<entry_point>`; the evaluator normalizes `Solution().<entry_point>` automatically if no top-level function exists.

## Arms (Max 3 Attempts; `B0` = 1)

All arms receive the identical base task text: `<prompt>\n\nWrite the function \`<entry_point>\` in /work/solution.py.`
All gated retries use a fresh workspace with NO feedback text (same as E1′ `B2`).

| Arm | Role | Gate / Selection | Notes |
|---|---|---|---|
| `B0` | Baseline (1x) | None | 1 attempt, deliver it. |
| `B0x3` | Main same-budget baseline (3x) | None | 3 attempts; attempts 2–3 carry previous workspace + `"Review your solution.py and improve it if needed."` Deliver last. |
| `GT` | Oracle upper bound | `gate_hidden` | Fresh attempt up to 3; pass ⇒ deliver; all fail ⇒ deliver last. |
| `EX` | Judge 1: spec examples | `visible_tests` | **Note:** on this bank (`lcb_bank_v3`), `EX` is the conventional "visible test gate" (the problem statement's own examples). Same retry policy as `GT`. |
| `TF` | Judge 2: tests-first (same agent) | Frozen `/work/tests_spec.py` | Step 1: separate session sees only task text, writes `/work/tests_spec.py` (5–15 literal cases, no solution). Host hashes & copies it out; coding sessions mount it read-only at `/work/tests_spec.py` (kernel EROFS/EBUSY) and gate uses host's frozen copy. Parse failure or 0 cases ⇒ `undetermined`, deliver attempt 1 ungated. |
| `XM` | Judge 3: separate exam | Hidden `/work/tests_spec.py` | Like `TF`, but exam session uses `exam_model` (default Haiku; recorded in `RUN.json`/records so later 9B-coder/Haiku-exam is a config change) and its tests are **NOT** shown to the coder. |
| `MV` | Judge 4: majority agreement (3 solutions) | Output clustering on generated inputs + `visible_tests` args | 3 independent fresh attempts. Separate session writes `gen_inputs.py` (20 arg tuples, no outputs); visible test args (without expected outputs) are included. Run all 3 solutions in `--unshare-net` eval sandbox; cluster by identical outputs (exceptions/timeouts count as distinct output `"ERR"`). Deliver earliest solution in largest cluster if size ≥ 2; else `undetermined`, deliver attempt 1. |
| `CT` | Judge 5: CodeT-style dual agreement | `(#agreeing solutions on inputs) × (#XM tests passed)` | Reuses `MV`'s 3 solutions + inputs and `XM`'s generated tests (or generates its own if run standalone). Delivers highest-scoring solution; true ties across distinct clusters ⇒ attempt 1; 0 tests or all scores 0 ⇒ `undetermined`, deliver attempt 1. |

## Pre-Written Read-Out Criterion

> A judge **qualifies for local 9B confirmation** if and only if:
> 1. **Gain share** $\ge 0.5$, where $\text{gain\_share} = \dfrac{\text{rate}(\text{arm}) - \text{rate}(\text{B0x3})}{\text{rate}(\text{GT}) - \text{rate}(\text{B0x3})}$, **AND**
> 2. **False-accept rate** $\le 2 \times \text{false\_accept\_rate}(\text{GT})$.

Primary statistical comparison: paired exact two-tailed McNemar vs `B0x3` (same-budget baseline); secondary comparison: paired McNemar vs `B0`.

## Usage

```bash
# Calibration mode: B0 only on N tasks (sampled with plan seed from medium+hard)
python3 ops/fl/run_fl.py --plan ops/fl/plans/fl_smoke_haiku.json --root /tmp/fl_cal --calibrate 20

# Full run (plan and ops/fl/ + ops/e1/ must be committed in git; resume-safe)
python3 ops/fl/run_fl.py --plan ops/fl/plans/fl_smoke_haiku.json --root /tmp/fl_run

# Analyze results (markdown table, or --json for machine-readable output)
python3 ops/fl/analyze_fl.py /tmp/fl_run
python3 ops/fl/analyze_fl.py /tmp/fl_run --json
python3 ops/fl/analyze_fl.py /tmp/fl_run --json /tmp/fl_run/summary.json
```

## Reuse & Honest Boundaries

- **Reuse**: Imports `ops.e1.sandbox`, `ops.e1.netproxy`, `ops.e1.negative_controls`, `ops.e1.evaluate`, `ops.e1.run_e1`, and `ops.e1.analyze_e1` directly (no copied sandbox/proxy/eval code).
- **Isolation**: Worker runs in `bwrap --unshare-net` with allowlist UNIX proxy (`api.anthropic.com:443` only) and read-only single-file `.credentials.json`. Preflight `run_claude_negative_controls` explicitly verifies `lcb_bank_v3.jsonl`, run root, other-arm workspace, `~/dev/ops`, and host `~/.claude` non-credential files are unreadable before any worker starts.
- **Cost accounting for `CT`**: When `CT` reuses `MV`'s solutions/inputs and `XM`'s tests, `cost_usd` records the full standalone cost of running `CT` (so per-arm cost/task is fair), while `incremental_cost_usd` records actual additional spend (`0` when fully reused, so total run spend is not double-counted).
- **Smoke runs**: Small 2-task smokes validate the end-to-end pipeline and cost accounting only, not statistical evidence of judge quality.
