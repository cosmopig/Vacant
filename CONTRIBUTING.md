# Contributing to Vacant

Thanks for considering a contribution. Vacant is a capstone project that doubles as a research artifact, so the bar for changes is somewhat higher than a typical hobby OSS project — but the path is well-trodden.

## TL;DR

```bash
git clone https://github.com/cosmopig/Vacant.git && cd Vacant
uv sync --all-extras
uv run pre-commit install
uv run pytest                                          # all green
uv run pytest --cov=vacant --cov-fail-under=90         # coverage gate
uv run ruff check . && uv run ruff format --check .    # lint
uv run mypy src/                                       # types
```

If those four commands pass, you're set up.

## Before opening a PR

1. **Read [CLAUDE.md](CLAUDE.md)** — especially the "Load-bearing theory decisions" section. Eight invariants are encoded as both code-level enforcement and ADRs (`architecture/decisions/D###_*.md`). Reversing any of them silently breaks the correctness chain — open an ADR first if you must change one.

2. **Check the spec** — the contract for the implementation lives in `architecture/`. `THEORY_V5.md` is canonical (V3 / V4 are kept for history). Component specs in `architecture/components/P*.md` define each module's surface area.

3. **Update [`architecture/CONSTANTS.md`](architecture/CONSTANTS.md) before adding a magic number.** Every threshold, period, weight, etc. has a single source of truth there. PRs introducing magic numbers without a row in CONSTANTS.md will be asked to update it first.

4. **Test what you ship.** Coverage gate is 90% on the project. Per-module ≥ 90% on core paths is encouraged. Property tests (hypothesis) are required for any new cryptographic / state-machine / chain invariant. Adversarial tests are required for any new identity / reputation / registry / composite / protocol surface.

5. **Format + types must pass.** `ruff` (lint+format), `mypy --strict`. `mypy --strict` is non-negotiable; `Any` requires a `# type: ignore[reason]` with a real reason.

## PR sequence

Most non-trivial PRs follow this loop:

1. Branch off `main` (linear history is preferred, no force-push to `main`).
2. Implement + test locally until all four checks pass.
3. Push and open a PR. Use the PR template.
4. CI runs (ruff + mypy + pytest with coverage gate). Wait for green.
5. PR review. Reviewer checks: spec citation, theory invariant compliance, test coverage of attack surfaces (if applicable), ADR for any spec-ambiguous decision.
6. Squash or rebase merge to `main`. (We don't use merge-commits except for big multi-PR integrations.)

## Adversarial review

Any PR touching:

- `src/vacant/identity/`
- `src/vacant/reputation/`
- `src/vacant/registry/`
- `src/vacant/composite/graduation.py`
- `src/vacant/protocol/replay_protect.py`

requires an adversarial review pass: enumerate ≥ 3 attacks the change might enable, write them as `pytest` tests that assert the defense detects/raises. See [`dispatch/Padv_review.md`](dispatch/Padv_review.md) for the full protocol.

## File a good issue

Use the issue templates in `.github/ISSUE_TEMPLATE/`. Three flavors:

- **Bug** — actual broken behavior. Include reproduction steps + expected vs. actual.
- **Theory inconsistency** — something in `architecture/` that contradicts another part of `architecture/`. Cite both sections.
- **Defense gap** — an attack scenario the current code doesn't defend against. Treat this like a security report (see [SECURITY.md](SECURITY.md) for sensitive cases).

For new features: open a Discussion first (GitHub → Discussions → Ideas) before opening an issue. The cost of saying "no" to a feature is high once code exists.

## Commit messages

```
<area>: <imperative summary>

<why this matters — what changed and why, not what the diff already shows>

<spec citation if relevant: THEORY_V5 §X.Y / CLAUDE.md §Z>
<ADR cited if applicable: architecture/decisions/D###>
```

Examples in `git log` history.

## Where humans review

- **Spec changes** (`architecture/THEORY_V5.md`, component specs): need a heads-up in Discussions before the PR — you don't want to discover after writing code that the maintainer disagrees with the direction.
- **ADRs** (`architecture/decisions/`): the ADR text itself is a form of disagreement-resolution. If you propose a new ADR, expect discussion in the PR.
- **Theory invariant changes**: highest scrutiny. Open a draft PR with the ADR + minimal code change demonstrating the new behavior, *then* discuss.

## What we won't merge

- Reverses to "Path A" (human-written vacant) — Path A is permanently deprecated. If you have a use case, propose a *new* path (D6, D7…) via ADR.
- Anything that reintroduces a "central judge" — no central LLM, no central oracle, no central arbiter. Verification is signed-logbook + peer-review only.
- Anything that makes Sunk vacants reviewable.
- Magic numbers without an entry in `CONSTANTS.md`.
- `# type: ignore` without a documented reason.
- Code that bypasses pre-commit / CI hooks.

## Project decision-makers

This is a single-maintainer project (cosmopig) for now. Decisions go through the maintainer; reasoning is recorded in ADRs.

After the capstone defense, the project may transition to a multi-maintainer governance model (see `GOVERNANCE.md` once it exists).

## License

MIT. By contributing you agree that your contributions are licensed under the same terms (see [LICENSE](LICENSE)).
