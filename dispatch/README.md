# Dispatch — cloud Claude Code prompts

Each `P*_*.md` is a self-contained prompt for one cloud Claude Code session. Each session:

1. clones https://github.com/cosmopig/Vacant
2. reads `/CLAUDE.md` and the prompt's "Read first" list
3. branches `feat/P#-<slug>` off `main`
4. implements per the prompt
5. opens a PR titled per the prompt's "Output" line

You merge sequentially / in parallel per the DAG below.

## Dependency DAG

```
P0 ── P1 ──┐
   ├── P2 ──┴── P5 ──┐
   │       ├── P4 ───┤
   │       │   ├── P3 ┤
   │       │   └── P6 ┤
   │                  └── P7
```

| Stage | Prompt | Depends on | Can parallel with | Weeks |
|---|---|---|---|---|
| 0 | `P0_bootstrap.md` | — | — | 1 |
| 1 | `P1_runtime.md` | P0 | P2 | 2 |
| 1 | `P2_identity.md` | P0 | P1 | 2 |
| 2 | `P4_registry.md` | P2 | — | 2 |
| 3 | `P3_reputation.md` | P4, P1 | P6 | 2 |
| 3 | `P6_protocol.md` | P4, P2, P1 | P3 | 2 |
| 4 | `P5_composite.md` | P1, P2, P4 | — | 2 |
| 5 | `P7_mvp.md` | all above | — | 4 (= W11-14) |

## Companion files

- `HOW_TO_DISPATCH.md` — three modes (claude.ai/code, Agent SDK, GitHub Actions) + secrets + branch protection
- `Padv_review.md` — adversarial review prompt to run after any PR touching identity/reputation/registry/composite/protocol
- `P7_demo_seed.md` — fixed seeds + expected outputs for all 4 demo scenarios + 1 adversarial seed
- `../architecture/CONSTANTS.md` — single source of truth for all numeric thresholds (every prompt cites this)

## How to dispatch

For each stage, copy the prompt content into a new cloud Claude Code session pointed at this repo. Do not paraphrase. Each prompt assumes its predecessor's PR is merged unless explicitly told otherwise. See `HOW_TO_DISPATCH.md` for the three modes available and full operational checklist.

After every merge, pull locally and verify:

```bash
git pull
uv sync
uv run pytest --cov=vacant --cov-report=term-missing
uv run mypy src/
```

If anything regresses, do not start the next stage — fix on the merged branch first.

## Branch protection

Recommended on `main`:
- Require PR review (you = reviewer)
- Require CI green
- Require linear history
- Disallow force push

## When to escalate to you

Cloud Claude Code should open a "blocked" PR and ping you when:
- A spec is genuinely ambiguous (not just unclear — actually contradictory)
- A theory invariant from CLAUDE.md "Load-bearing decisions" appears to need changing
- An external dependency's API has changed since the spec was written
- Test failures persist after 2 attempts at fixing
