# Project governance

This document explains *who decides what* on Vacant. It is short on
purpose: the project is small, the rules should fit in your head.

For *how to contribute* (PR flow, branch naming, the adversarial-review
protocol) see [`CONTRIBUTING.md`](CONTRIBUTING.md). For *what is
in-scope* see [`CLAUDE.md`](CLAUDE.md).

## Current model — single maintainer (capstone phase)

Vacant is a 2026 undergraduate capstone in its post-MVP, pre-1.0
phase. Decisions are made by the project's sole maintainer:

- **Maintainer:** cosmopig — `cosmo20050801@gmail.com`
- **Decision style:** BDFL during the capstone phase. The path to a
  multi-maintainer model is described below.

You should expect:

- The maintainer reviews **every** PR. Small docs/test fixes can land
  on green CI alone; substantive changes get discussion.
- Triage is best-effort; don't expect a 24-hour SLA. If a PR has been
  open more than ~2 weeks with no response, ping the maintainer in a
  Discussion.
- Decisions are made in writing — in PR threads, ADRs, or
  Discussions. There is no private channel where the call gets made.

## Decision record — ADRs

Every non-trivial design decision lives as an **Architecture Decision
Record** under
[`architecture/decisions/`](architecture/decisions/) named
`D###_<slug>.md`. ADRs are the single canonical record; PR
descriptions reference them, code comments cite them, this file
points at the index.

Conventions:

- **ADRs are immutable once merged.** A change of mind ships a new
  ADR that supersedes the old one (and explains why). The old one
  stays in the tree as history.
- **Theory invariants are protected by ADR.** The 9 load-bearing
  decisions in [`CLAUDE.md`](CLAUDE.md) §"Load-bearing theory
  decisions" cannot be silently reversed; a PR that violates one
  without an accompanying ADR is grounds for closing the PR. The
  enforcement points (file:line per invariant) are pinned in
  [`architecture/ENFORCEMENT_POINTS.md`](architecture/ENFORCEMENT_POINTS.md).
- **Anyone can propose an ADR.** Open a PR adding
  `architecture/decisions/D###_<slug>.md`; the maintainer accepts,
  requests changes, or rejects with reasons. There is no separate
  "ADR review" step beyond the PR review.

## Decision matrix — who needs an ADR for what

| Scope | Path | Needs ADR? |
|---|---|---|
| **Theory invariant** (one of the 9 in CLAUDE.md) | High-scrutiny review; ADR required before code lands. | ✅ |
| **Component spec change** (`architecture/components/P*.md`) | Open a Discussion before the PR; maintainer drafts the ADR if the change lands. | ✅ |
| **New attack/defense framing** (changes the defense level P/D/C of a mechanism) | Adversarial review per [`dispatch/Padv_review.md`](dispatch/Padv_review.md); ADR records the residual risk. | ✅ |
| **Numeric threshold** | Update [`architecture/CONSTANTS.md`](architecture/CONSTANTS.md) — that row IS the change record. ADR only if the *meaning* changes. | ⚠️ Sometimes |
| **Implementation detail** within an existing spec | Plain PR with tests + spec citation. | ❌ |
| **Documentation / runbook / READMEs** | Plain PR. Substantive content goes through review; small fixes can self-merge on green CI. | ❌ |
| **Dependencies** | Dependabot opens grouped PRs weekly; new deps need a one-line justification in the PR description. | ❌ |
| **Security-sensitive bug** | Report via [`SECURITY.md`](SECURITY.md), **not** a public issue. ADR if the fix changes a defense level. | ⚠️ Sometimes |
| **Defense-gap report** (non-sensitive) | Use the GitHub Issue → "Defense gap" template. ADR if the response changes a defense. | ⚠️ Sometimes |
| **`GOVERNANCE.md` itself** | Plain PR; same review process. | ❌ |

## Adversarial review

Code that touches a defense surface (reputation aggregator, registry
anti-tamper, federation, runtime state machine, dispatch, composite
sealing) must include an **adversarial review** pass — enumerate ≥ 3
attacks the change might enable and add `pytest` tests that assert
the defense detects/raises/downweights. Full protocol in
[`dispatch/Padv_review.md`](dispatch/Padv_review.md). The maintainer
verifies the pass before merge.

## Path to multi-maintainer governance

The single-maintainer phase is **temporary**. After the capstone
defense and once 1.0 ships, governance may transition to a small core
team **if and only if** there are sustained external contributors.
Hard triggers:

- ≥ 3 distinct external contributors with ≥ 5 merged PRs each, OR
- ≥ 1 long-running ADR proposal that the sole maintainer cannot
  adjudicate alone (e.g. due to bus-factor concerns).

When either trigger fires, the transition is marked by a
`D-MAINTAINERS_<date>.md` ADR listing:

- the initial core team
- the decision-making rule (lazy consensus / formal RFC / vote)
- escalation path
- removal/addition process

Until that ADR is merged, this document is the entire governance.

## Code of Conduct

[Contributor Covenant 2.1](CODE_OF_CONDUCT.md) applies to all
project spaces — issues, PRs, Discussions, security reports.
Enforcement is by the maintainer.

## Trademark / naming

"Vacant" is the project name; the cryptographic concept of a *vacant*
(a residency form) is described in
[`architecture/THEORY_V5.md`](architecture/THEORY_V5.md). There is no
registered trademark; forks may use the name with attribution. If the
project ever applies for trademark protection, this section will be
revised.

## Funding

The project receives no funding. There is no plan to monetize the
codebase. The
[`.github/FUNDING.yml`](.github/FUNDING.yml) file is a placeholder
for future sponsor channels; until any are wired up, code, time, and
review are the only forms of support that matter.

## Escalation

If you disagree with a maintainer decision:

1. Open a Discussion linking to the original PR/issue. Argue the
   technical case in writing.
2. If the maintainer doesn't change their mind, the decision stands.
3. The MIT license guarantees the right to fork. That is the
   ultimate appeals body.

There is no steering committee, trustee body, or external arbiter.
This is intentional for a single-maintainer capstone-stage project,
and will be revisited at the multi-maintainer transition.

## Changes to this document

Changes to `GOVERNANCE.md` itself go through a normal PR. The
maintainer is the final arbiter; non-trivial governance changes
(e.g. adding a new co-maintainer, changing the decision matrix) ship
alongside an ADR.
