# GitHub Community Standards — checklist

GitHub's "Insights → Community Standards" page renders a checklist that
external visitors implicitly read as a quality-signal. This file
documents which file in the repo satisfies each row, so a maintainer
can verify the page renders 100%-green after a structural change
(refactor, file move, etc.) without having to wait for GitHub to
reindex.

## Required rows

| Standard            | Resolved by                                           | Notes |
|---------------------|-------------------------------------------------------|-------|
| Description         | Repo settings → "About" sidebar (set on cosmopig/Vacant) | Not a tracked file. Confirm string is up to date when the README hero copy changes. |
| README              | `README.md`                                           | English; bilingual link at the top. |
| Code of conduct     | `CODE_OF_CONDUCT.md`                                  | Contributor Covenant 2.1, project-specific contact line. |
| Contributing        | `CONTRIBUTING.md`                                     | 100 lines; covers PR flow + commit style + adversarial-review expectation. |
| License             | `LICENSE`                                             | MIT. |
| Security policy     | `SECURITY.md`                                         | Private reporting via GitHub Security Advisories; SLAs noted. |
| Issue templates     | `.github/ISSUE_TEMPLATE/{bug,feature,defense_gap,theory_inconsistency}.yml` + `config.yml` | `config.yml` disables blank issues. |
| Pull request template | `.github/PULL_REQUEST_TEMPLATE.md`                  | Sections: summary, test plan, ADRs touched, adversarial-review note. |

GitHub renders 100%-green when every row above resolves. As of v0.1.0
all rows resolve.

## Beyond the GitHub-mandated rows

These are not on GitHub's checklist but improve discovery / academic
citation / OSS-bot legibility:

| Signal                    | Resolved by              | Why we ship it |
|---------------------------|--------------------------|----------------|
| Citation metadata         | `CITATION.cff`           | Academic + OSS-citation crawlers (Zenodo, Software Heritage). |
| Changelog                 | `CHANGELOG.md`           | Keep-a-Changelog format; bumped on every release tag. |
| Governance                | `GOVERNANCE.md`          | Single-maintainer model; explicit funding statement. |
| Third-party notices       | `THIRD_PARTY_NOTICES.md` | Per-dep license credit. |
| Sponsor button            | `.github/FUNDING.yml`    | All channels currently commented out; rendered grey. |
| Support routing           | `SUPPORT.md`             | Distinguishes "ask in Discussions" vs "report a bug". |
| Issue routing chips       | `.github/ISSUE_TEMPLATE/config.yml` | Forces structured templates; blank issues off. |
| Dependabot                | `.github/dependabot.yml` | Weekly update window for actions + Python deps. |

## Diagnosing a regression

If GitHub's Community Standards page shows a row red after a refactor:

1. Confirm the file is at the **exact path** in this table — GitHub does NOT search recursively.
2. Confirm the file is non-empty AND committed to the **default branch** (`main`).
3. Force a refresh by pushing a no-op commit; GitHub re-runs the indexer once per push.
4. If the file IS at the right path and committed to `main` but the row is still red, file a GitHub support ticket — that's a GitHub-side indexing bug, not a repo bug.

## Files we deliberately do not ship

- **`.github/CONTRIBUTING.md`** symlink → root `CONTRIBUTING.md`. GitHub finds the root file fine; a symlink would be redundant noise.
- **`AUTHORS` / `CONTRIBUTORS`** — `git shortlog -sn` is the canonical source. Don't ship a stale file that has to be updated manually.
- **`MAINTAINERS.md`** — duplicates `GOVERNANCE.md`; GitHub doesn't read it for the checklist.
