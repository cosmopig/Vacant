# v4 calibration operator log

All 12 session/instance bindings were supplied by the lead on 2026-11-23.
Session IDs are recorded in /home/ubuntu/sandbox-v4-scoring/calibration-sessions.json
and bound into scoring metadata. No comparison sessions are launched here.

Session-reported native setup notes (not independently reproduced):
- pydata__xarray-7229 needed PYTHONNOUSERSITE=1. Verified in frozen KIT.json:
  selection.runner_environment.PYTHONNOUSERSITE is "1", and the setup recipe
  contains `export PYTHONNOUSERSITE=1`.
- sphinx-doc__sphinx-8595 pinned docutils==0.16 inside its own environment.
- astropy__astropy-8707 and pytest-dev__pytest-5840 reported pre-existing native
  environment failures.

Official scoring uses the pinned official harness images, not these native
environments; these notes do not alter patch derivation or harness recipes.

The v3 session-event scanner is an external lead/operator operation. This
subagent has no session-event retrieval integration or configured Devin API
credential. Both audit verdicts must remain unknown until exported scanner and
PR/review-before-final-push evidence are supplied. The watcher is configured to
ingest /home/ubuntu/sandbox-v4-scoring/audits.json when available; no hits or
missing exports never imply clean sessions.

## Scorer review/resumption log — 2026-11-23

The initial scorer at 6fa41c908 completed seven official outcomes before the
Astropy 8707 base export encountered its unchanged `astropy_helpers` gitlink.
Both frozen base and handback pin that link to
`32b440b52f4c60592148b3254c7ddbf14df3c6e0`. Revision 8a91f75b1 permits only
unchanged gitlinks, represented as empty directories without fetching them;
changed links are not silently dropped. PID 872019 resumed the existing cache
at 15:20 UTC with that revision. The first seven official results were reused.

The resumed pass reached ten scored outcomes, four resolved and zero
infra_void, before Docker Hub returned 429 for Django 14140 at 15:24:52 UTC.
Its same-image backoff remains active. Old, unused v3 instance image caches
were removed without force to release space (86% to 76% used); calibration
images were protected. Cleanup stopped safely on an already-removed digest
alias, so some old v3 image caches remain.

The running pass loaded 8a91f75b1. Later commits address stale audit ingestion
and per-cell preparation failures. `reload.py` (PID 906814) waits for the pass
lock before replacing the watcher, preserving the current pull backoff and
all completed official results. Its log is
`/home/ubuntu/sandbox-v4-scoring/reload.log`. For this running pass, any
`scorer_git_sha` recorded after a later source commit observes checkout HEAD
at result-write time, not a module reload: execution still uses 8a91f75b1.
The updated scorer instead captures the revision at pass start.

Audit exports remain absent. No clean verdict is inferred and calibration
clearance remains incomplete.

## Reviewed scorer release — 2026-11-23

Final reviewed source: `6a6e26b4da2d8790e7f69ba1c40ea390cb7434f7`.
PR #99 CI: 8 passed, 0 failed, 0 pending, 0 skipped. Focused v3/v4 scoring
tests: 54 passed; repository blueprint Ruff check passed. The reload waiter
was replaced by PID 975315 before the active pass finished, without stopping
PID 872019 or resetting its pull delays. It will load the final source after
the active pass releases the run lock; all existing outcomes remain cached.

All twelve exact calibration handback heads were queried for PRs, state=all,
at 15:47 UTC. Each query returned no matching PRs. Raw outputs and scope are
saved in `/home/ubuntu/sandbox-v4-scoring/calibration-pr-check.json`.
This checks that PR/review route in this repository only; it is not a full
session-access or outside-help audit and does not complete either verdict.
The full v3 scanner/human evidence export is still required at
`/home/ubuntu/sandbox-v4-scoring/audits.json`.

At 16:12:50 UTC the resumed official pass completed all twelve outcomes:
four resolved, zero infra_void. The reload completed and PID 975315 now runs
the final 6a6e26b4d watcher against the existing cache. The active watcher's
stdout/stderr is `/home/ubuntu/sandbox-v4-scoring/reload.log`; the original
pass remains in `scorer.log`. The image warmer completed. Clearance is still
`incomplete`, `complete=false`, `proceed=false`: zero cells have both full
audits completed and the audit export is absent. No comparisons were launched.

## Final calibration snapshot — 2026-11-23

The preceding entries are the chronological run log, not the final gate state.
The lead supplied both completed audits at 16:29 UTC. All twelve reviewed
records were applied, bound to the scored branch, session ID and handback SHA;
no records were rejected. All twelve official outcomes exist: four resolved,
eight unresolved, zero infra_void. No cells were flagged by either audit.
The conservative count is therefore 4/12, within the preregistered ceiling
of 8/12. `calibration.json` records `complete=true`, `proceed=true` and
`decision="proceed"`. This permits the comparison launch; it is not evidence
that Vacant improved an agent or that gate acceptance implies correctness.

This compact snapshot preserves the reviewed verdict export verbatim under
`audit-sources/d295ad171b702c34f0532b338678776db7d826f8174b59e21156d68138a8114d.json`,
the lead's scanner summary as `audit-raw.json`, and all twelve per-cell
`result.json` files, including the official harness report and scored commit.
The scanner summary is selected event evidence, not full session transcripts.
`calibration-pr-check.json` is the earlier exact-head PR query supplement;
the completed verdict export contains the final push/PR-review timing check.

`meta.json` retains the original run fingerprints and initialization revision;
each cell separately records the scorer revision used for that outcome.
`provenance.json` records the final review source, frozen input file hashes,
audit source hashes and a byte/hash inventory of the other snapshot files.
Absolute paths are original evidence locations on the scoring host, not
portable dependencies. Source/handback trees, candidate patches, full harness
logs, environments, lock files and duplicate progress output are omitted.
Secret-token/private-key pattern review found no matches in the selected inputs.

The official scores are not rerun when reproducing the gate: copy this bundle
to a directory outside the repository, then run, from the repository root:

```sh
.venv/bin/python -m ops.sandbox.v4.score review --out /path/to/copied-bundle
```

That command rechecks the twelve cached outcomes and completed audit verdicts
and reproduces `calibration.json` without network access or the Docker harness.
