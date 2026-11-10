# Process baseline (no Vacant) — pi + qwen3.8:27b

**Question.** Vacant aims to make an AI agent work the way *this user* would want — not only
reach an output the user accepts, but follow a *process* the user recognises (ask vs act,
read tests first, small diff vs rewrite, verify before reporting). Outcome-only scoring
hides this. This directory is the **no-Vacant control**: a real coding-agent CLI running the
target model, with every step of its process recorded in a common schema and scored by
process metrics that can later be compared to a user's reference process.

The **with-Vacant** condition plugs into the same harness at one point (see
[`WITH_VACANT.md`](WITH_VACANT.md)), so baseline vs Vacant is a clean A/B: same tasks,
same model, same CLI, same tools and budgets.

Status: v0 harness. The process-metric definitions are deliberately simple; a literature
review on process/trajectory similarity and trust is in progress separately and may
replace or extend them.

## Setup

| piece | choice | why |
|---|---|---|
| agent CLI | [`pi`](https://github.com/badlogic/pi-mono) 0.73.x (`npm i -g @mariozechner/pi-coding-agent`) | one npm install; custom OpenAI-compatible provider via `models.json`; `--mode json` streams every message/tool event; `--append-system-prompt` is a clean injection point for the Vacant condition |
| model | `qwen3.8:27b` on Ollama (Kaggle T4×2), OpenAI-compatible `/v1` | project model choice |
| `proxy.py` | stdlib reverse proxy on 127.0.0.1 | injects `"reasoning_effort":"none"` (without it qwen3.8 spends `max_tokens` on hidden reasoning and returns empty content), adds the upstream bearer token, throttles (default 28 req/min, used 12), logs one line per LLM call (latency, tokens) |
| tools | `read,bash,edit,write,grep,find,ls` | pi built-ins; stock pi system prompt |
| workspace | fresh copy of `tasks/<T>/repo` per run, `git init` + commit, so the diff is exact | isolation |
| `mock_upstream.py` | scripted fake model | **smoke test only** (wiring check while the GPU endpoint was down); runs are labelled `MOCK`, never results |

```bash
source /workspace/ep.sh   # BASE, TOK (not in repo)
UPSTREAM_BASE=$BASE UPSTREAM_TOKEN=$TOK CALL_LOG=/tmp/calls.jsonl RPM=12 python proxy.py --port 18080 &
python run_baseline.py --repeats 2 --upstream-label "kaggle-ollama qwen3.8:27b" --call-log /tmp/calls.jsonl
python analyze.py /workspace/process_baseline/runs --out summary.md
```

Raw runs (events, workspaces) stay outside the repo; only code, synthetic tasks and
synthetic example personas are committed.

## Tasks (synthetic, personally ambiguous)

Each task is small and has a defensible answer, but *different users would want a
different process*. Nothing in the repo resolves the ambiguity, on purpose.

| id | family | prompt | where users differ |
|---|---|---|---|
| T1_bulk_discount | bugfix | "Customers say the bulk discount is wrong for big orders. Please fix it." | ask about the business rule (stacking, `>` vs `>=`) or assume; read/run tests first; minimal diff |
| T2_csv_export | feature | "Add a way to export the weekly report as CSV." | ask about format/CLI vs pick defaults; test-first; explain choices |
| T3_cleanup_utils | refactor | "utils.py is messy. Clean it up." | search call sites before renaming; characterization tests first; small diff vs rewrite |
| T4_funding_memo | deliverable (Vacant plan domain: fixed facts → memo.md + plan.json) | "Read task_facts.json and write memo.md … plus plan.json …" | ask priorities vs assume; verify constraints with a command; memo length |

## Trajectory schema (`trajectory.jsonl`, v0.1)

One object per step: `run_id, task_id, condition, step, t, kind (plan|tool|final),
action, tool, args, text, files_read, files_written, command, is_error, retry_of, usage`.
Raw pi events (`events.jsonl`), `diff.patch`, `metrics.json` and `meta.json` sit next to it.
Token totals come from the proxy call log (`calls.jsonl`), independent of the CLI.

Action alphabet: `R` read · `S` search/explore · `E` edit/write · `X` run other command ·
`T` run tests · `A` ask the user (final message that is a question) · `F` final answer.
In `-p` mode pi has no ask tool, so asking = ending the turn with a question; that is
what a user would see.

## Process metrics v0 (`metrics.py`)

Per run:
- action sequence (e.g. `SSRRETF`) and its run-length-collapsed form (`SRETF`)
- step count, counts per action, tool errors, retries (same call repeated after an error)
- order features: `read_before_first_edit`, `edited_files_were_read_first`,
  `test_before_first_edit`, `test_after_last_edit`, `asked_before_acting`, `made_edit`
- diff size (`+added/-removed`, files)
- LLM calls, tokens in/out, wall time

Against a reference process (pluggable JSON: `{"sequence": "...", "features": {...}}`):
- `edit_sim` = 1 − Levenshtein / max length (also on collapsed sequences)
- `lcs_sim` = 2·LCS / (|a|+|b|)
- `feature_agreement` = share of specified order features that match

Across repeats: within-task self-consistency (mean pairwise collapsed edit similarity).

`personas/examples.json` holds two **hand-written SYNTHETIC example personas**
(`example_cautious`, `example_fast`) purely to demonstrate the metric. They are not a
real user's process. A real user's reference process is a separate file with the same
shape, collected from that user (not stored in this repo).

## Tests

`python -m pytest experiments/process_baseline/tests -q`
