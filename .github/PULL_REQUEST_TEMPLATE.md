<!-- Thanks for the PR.

Read CONTRIBUTING.md before opening if you haven't.
For PRs touching identity / reputation / registry / composite / protocol,
include an adversarial review (see dispatch/Padv_review.md).
-->

## Summary

<!-- One paragraph: what this PR does and why. -->

## Spec citations

- THEORY_V5: §
- Component spec: `architecture/components/P*.md` §
- ADR (if applicable): `architecture/decisions/D###_*.md`

## Changes

- [ ] Code change in `src/vacant/<area>/`
- [ ] Tests added in `tests/{unit,property,integration,adversarial}/`
- [ ] CONSTANTS.md updated (if any new numeric threshold)
- [ ] CLAUDE.md updated (if conventions or commands changed)
- [ ] CHANGELOG.md updated under `[Unreleased]`

## Theory invariant compliance

<!-- Confirm none of the 8 load-bearing decisions in CLAUDE.md is violated.
     If one is, link the ADR that authorizes the change. -->

- [ ] D-series remains primary birth path; Path A still not implemented
- [ ] Registry remains per-vacant (no central routing component)
- [ ] Sunk vacants still cannot review
- [ ] Lineage remains the evolution unit (individual reputation does not inherit)
- [ ] Same-* detection remains cost-raising (not preventing)
- [ ] LOCAL state remains fully runnable
- [ ] Closed children keep keypair through graduation
- [ ] No central LLM / judge / oracle introduced

## Adversarial review (if applicable)

If this PR touches one of the load-bearing surfaces (identity / reputation / registry / composite / replay protect), enumerate ≥ 3 attacks the change might enable and link the regression tests:

1. <!-- attack scenario 1 → test path -->
2.
3.

## Test results

```
uv run ruff check . && uv run ruff format --check .
uv run mypy src/
uv run pytest --cov=vacant --cov-fail-under=90
uv run pytest -m slow
```

Paste the relevant outputs (or "all green").

## Demo / screenshots (if user-facing)

<!-- For dashboard, CLI, or spec changes that change the user experience. -->

## Follow-ups

<!-- Anything intentionally out of scope, with rationale. -->
