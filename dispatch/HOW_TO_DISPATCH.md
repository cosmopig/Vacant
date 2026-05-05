# How to dispatch a prompt to cloud Claude Code

Three modes. Pick whichever you actually have access to.

## Mode A — Cloud Claude Code session at https://claude.ai/code (recommended)

For each stage in `dispatch/README.md`:

1. Open https://claude.ai/code → New session
2. Connect the GitHub repo `cosmopig/Vacant` (Settings → Connect GitHub)
3. Paste the **entire content** of the relevant `dispatch/P*_*.md` into the first message. Do not paraphrase. The prompt is self-contained.
4. Add at the end of your first message:
   ```
   When you finish, open a PR against main. Do not merge it yourself.
   ```
5. The session will: clone → read CLAUDE.md → branch → implement → push branch → open PR.
6. You review the PR on GitHub. If approved, merge. If not, comment with required changes (Claude Code can pick the session back up from the comment thread).

**Cost note**: each session consumes context for the whole prompt + spec reads + code generation + tests. Budget rough estimate: P0 ≈ 200K tokens, P1-P6 ≈ 400-800K each, P7 ≈ 1.5-2M.

**Parallelism**: stage 1 (P1+P2) and stage 3 (P3+P6) can run concurrently — open them in two browser tabs.

## Mode B — Anthropic API + Claude Agent SDK on your machine

If you'd rather run locally (no claude.ai/code) and stream the work into your own terminal:

1. `npm install -g @anthropic-ai/claude-agent-sdk`
2. Set `ANTHROPIC_API_KEY` env
3. Clone the repo locally
4. For each stage:
   ```bash
   claude-agent --workdir /path/to/Vacant \
                --prompt "$(cat dispatch/P0_bootstrap.md)" \
                --commit --push --open-pr
   ```
5. Same review flow as Mode A.

This mode gives you direct stdout streaming and easier interruption, at the cost of running on your machine (not free in tokens, not free in laptop CPU).

## Mode C — GitHub Actions (most automated, least flexible)

For autonomous scheduled runs:

1. Add `.github/workflows/dispatch.yml`:
   ```yaml
   name: Dispatch
   on:
     workflow_dispatch:
       inputs:
         stage:
           description: 'P0/P1/P2/P3/P4/P5/P6/P7'
           required: true
   jobs:
     run:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: anthropics/claude-code-action@v1
           with:
             prompt-file: dispatch/${{ inputs.stage }}_*.md
             open-pr: true
           env:
             ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
   ```
2. Trigger via Actions tab → Run workflow → pick stage.

This mode is best for re-running a stage cleanly after a botched first attempt. Worst for interactive iteration.

## Secret management (all modes)

Add to GitHub repo Settings → Secrets and variables → Actions:

- `ANTHROPIC_API_KEY` — for the substrate backend (P3, P6, P7)
- `CODECOV_TOKEN` (optional) — if you wire up Codecov

For local dev, `cp .env.example .env` then fill in. `.env` is in `.gitignore`.

## Branch protection (set this BEFORE first dispatch)

GitHub repo → Settings → Branches → Add rule for `main`:

- ☑ Require a pull request before merging
- ☑ Require approvals: 1 (you)
- ☑ Dismiss stale pull request approvals when new commits are pushed
- ☑ Require status checks to pass before merging
- ☑ Require branches to be up to date before merging
- ☑ Require linear history
- ☑ Restrict who can push to matching branches → only repo admins
- ☐ Do NOT enable "Allow force pushes"

Without this, cloud Claude Code can push directly to main and bypass your review.

## What to do when a dispatched session goes off the rails

Symptoms:
- Tests failing repeatedly
- PR keeps growing without convergence
- Spec ambiguity Claude is guessing at

Action:
1. Stop the session (don't let it burn more tokens)
2. Read what it produced — the diagnostic is usually in the PR description or last few commits
3. Add an ADR in `architecture/decisions/D###_*.md` resolving the ambiguity
4. Open a fresh session with the SAME prompt + a short addendum: "Read architecture/decisions/D###_*.md before starting"
5. Do not iterate on a stuck session beyond 2 attempts

## Order of operations checklist

1. ☐ Push the bootstrap commit (`git push`) — DONE
2. ☐ Set up branch protection (above)
3. ☐ Add `ANTHROPIC_API_KEY` to repo secrets
4. ☐ Decide license (`README.md` says TBD — pick MIT or Apache-2.0 before the first PR)
5. ☐ Skim `architecture/CONSTANTS.md` and adjust any value that disagrees with your intent
6. ☐ Dispatch P0 → review PR → merge
7. ☐ Dispatch P1 + P2 in parallel → review → merge
8. ☐ Dispatch P4 → review → merge
9. ☐ Dispatch P3 + P6 in parallel → review → merge
10. ☐ Dispatch P5 → review → merge
11. ☐ Run `dispatch/Padv_review.md` against P3/P2/P4 PRs (after they're merged) → fix any findings
12. ☐ Dispatch P7 → 4 weeks of iteration → demo
