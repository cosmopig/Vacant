# Conventional Commits — accepted PR title patterns

The `lint-pr-title` CI check enforces [Conventional Commits](https://www.conventionalcommits.org/) for every PR title (so `release-please` can build a clean changelog and pick the right semver bump). This page lists the patterns the check accepts and the ones that get rejected.

## TL;DR

A valid PR title is `<type>(<optional-scope>): <imperative summary>` where the summary starts with a lowercase letter and is at least 5 characters. The accepted types are:

| Type | When to use | Triggers release? |
|---|---|---|
| `feat` | New user-visible feature | ✅ minor bump |
| `fix` | Bug fix | ✅ patch bump |
| `perf` | Performance improvement (no behavior change) | ✅ patch bump |
| `docs` | Documentation only | ✅ patch bump (visible in changelog) |
| `deps` | Dependency bump (Dependabot uses this) | ✅ patch bump |
| `refactor` | Code restructure with no behavior change | ✅ patch bump |
| `test` | Add or modify tests only | ❌ hidden in changelog |
| `ci` | CI / build pipeline change | ❌ hidden |
| `chore` | Bookkeeping (not user-visible) | ❌ hidden |
| `build` | Build system / packaging change | ❌ hidden |
| `revert` | Revert a prior commit | ✅ patch bump |
| `style` | Formatting / whitespace only | ❌ hidden |

A breaking change is signalled by appending `!` after the type: `feat!: drop Python 3.11 support`. That triggers a major bump regardless of which type was used.

## Accepted patterns (✅ pass)

```
feat: add OpenClaw plugin bundle
feat(cli): vacant mcp stdio entry point
feat(registry)!: rename vacant_id to actor_id (BREAKING)
fix(replay-protect): handle (from, to, seq) collision atomically
fix: macOS CI failing on uv python autoselect
docs: add INTEGRATION.zh-TW.md
docs(faq): clarify same-controller detection cost
deps: bump pydantic to 2.13
deps(crypto): bump pynacl to 1.6
perf(reputation): cache STYLO drift across record_review
refactor: extract _submit_event_in_session helper
test(adversarial): cover halo TOCTOU rollback path
ci: pin uv python in matrix
ci(docs): publish mkdocs to gh-pages on push
chore: bump version to 0.2.0 in CHANGELOG
build: add Dockerfile + .dockerignore
revert: temporarily disable macOS CI gate
style: ruff format pass on tests/
```

## Rejected patterns (❌ fail) and why

```
Add OpenClaw plugin                     # missing type
feat OpenClaw plugin                    # missing colon
feat:Add OpenClaw plugin                # subject starts with capital
feat:add op                             # subject too short (<5 chars)
[feat] add OpenClaw plugin              # bracket prefix is not Conventional Commits
WIP: ...                                # WIP is not a recognised type
hotfix: ...                             # use `fix` instead
```

If you're tempted to write something that doesn't fit, the answer is almost always one of `feat`, `fix`, `docs`, `refactor`, or `chore`. Pick the one that best describes user-facing impact.

## Bot-generated titles

Dependabot already produces Conventional-Commits-compatible titles by default (`build(deps)` / `deps`). Release-please titles itself `chore(main): release X.Y.Z`. Both pass the check.

If you write a custom GitHub Action that opens PRs, set its title to a Conventional Commits prefix or `lint-pr-title` will fail.

## Edge cases the regex handles

The exact `subjectPattern` is `^[a-z].{4,}$` — applied to the part *after* the `:` (and optional scope). It accepts:

- Subjects with embedded uppercase: `feat: add OpenClaw bundle` ✅ (regex only looks at the first character; `O` later in the line is fine)
- Subjects with non-ASCII: `feat: 加入 OpenClaw bundle` ❌ (CJK first char is not `[a-z]`)
- Subjects with leading punctuation: `feat: '<>' is not a valid type` ❌ (first char must be lowercase letter)

Submitter intent is more important than regex sport — if a reviewer agrees the title is fine, override the check via PR conversation rather than rewriting to satisfy a quirk.

## How `release-please` consumes these

Each merged PR contributes exactly one Conventional Commit message to the running changelog. Squash-merging is recommended; the squash commit message defaults to `<PR title> (#<number>)`. Multiple commits in a PR are collapsed to that one title. If you want individual commits cited in the changelog, use a merge commit (less common; we currently squash).

The release PR appears as `chore(main): release X.Y.Z` and includes the auto-generated changelog. Reviewing it requires only checking that the version bump matches your expectation — a `feat` since last tag = minor bump, `fix`-only = patch bump, `feat!` or `BREAKING CHANGE:` in body = major bump.
