# v4 selection and preregistration

The selector freezes a bank and a 12-ID calibration subset; the native builder
below prepares the kit incrementally without launching agents. The owner approved 62 instances, two
samples per arm, and the widened reference-fraction rule `0 <= f <= 0.5`.

Run from the repository root with the existing v3 harness environment
(`swebench==3.0.17`, Docker and dataset/YAML dependencies):

```sh
<harness-python> -m ops.sandbox.v4.select \
  --experiments /path/to/pinned/swe-bench-experiments \
  --dataset-json /path/to/verified.jsonl \
  --work-dir /persistent/path/to/v4-validation --jobs 2
```

The selector verifies the dataset content hash and reuses the pinned v3 public
reference ranking and `validate_instance` gold/base checks. All twelve v3 IDs
and `>4 hours` instances are excluded before shuffling sorted eligible IDs with
seed 20261124. The first feasible instances under cap 12 are retained. Only if
the entire draw cannot fill the target does the cap increase, one at a time,
reusing validation evidence. If fewer than 62 instances are feasible at any
cap, every feasible instance is retained, with actual bank size and exact power
reported. The calibration subset is a seeded sample of 12 sorted bank IDs,
seed 20261125; it is not selected using agent outcomes.

Validation uses separate worker processes because v3's harness adapter changes
its working directory. A small speculative batch can validate additional
instances beyond the final draw prefix; all such results remain in the report.
Results are consumed in draw order, never completion order. Per-instance caches
bind dataset row bytes, validator source hash, harness version, experiments
revision and timeout; cached official report bytes are rechecked before reuse.
Pull rate limits (including HTTP 429) retry the same instance indefinitely with
15, 30, then 60-minute capped backoff. They never become task rejections. Other
infrastructure failures stop selection instead of silently becoming task skips.
After writing or reusing a verified validation cache, the worker removes that
instance's image by ID with non-forced `docker rmi`; unrelated images are not
pruned and Docker retains layers still referenced by other images. The v3
validator also removes newly pulled instance tags in its own cleanup. Workers
stop before new validation if disk usage reaches 85% (and retain v3's 20 GiB
free-space guard). Two workers limit transient concurrent image storage.
Missing instance images and valid gold/base feasibility failures are recorded.
An SDK `ImageNotFound` after pulling is not proof of registry absence: SDK 7.2
discards streamed pull errors and may emit a local-inspect 404 instead. Such
unverified unavailable results retry with the same backoff and are never cached
as rejections; legacy unavailable caches are invalidated automatically.

## Incremental local kit preparation

`python -m ops.sandbox.v4.kit --dataset-json VERIFIED.jsonl --root BUILD_ROOT
--micromamba BUILD_ROOT/tooling/bin/micromamba --jobs 2` polls the selector without
modifying or restarting it. It retains every selected ID while building
history-free `sandbox-v4/<id>` refs, byte-exact root prompts, native recipes,
measured and confirmed base-passing P2P nodes/timeouts, v4 controls, and leak
checks. SymPy instances are prepared first to exercise the pure-Python path.
Failures remain recorded by instance and phase. The subsequent owner policy
allows replacement after one honest repair attempt, using the next feasible
candidate in the original seeded order and raising the cap minimally only after
exhaustion. `select.replacement_candidates` implements the retained-bank/cap
filter; `SELECTION.json` records every attempted candidate and actual replacement.
Redraw calibration with the original seed only if a calibration ID was removed.
Replay the recorded replacement decisions offline, without Docker or agents:

```sh
python -c 'import json; from ops.sandbox.v4.select import replay_replacements; s=json.load(open("ops/sandbox/v4/SELECTION.json")); assert replay_replacements(s)==s["final_instance_ids"]'
```

Preparation uses GitHub, PyPI and conda-forge, never Docker pulls. Environments
are removed after measurement to reserve disk for the selector; source snapshots,
recipes, evidence and checksums remain. `BUILD_ROOT/KIT.json` records progress,
`first-10.json` records the first milestone, and `BLOCKERS.json` records failures
by instance and phase. The process automatically picks up further selected IDs.
No push is implemented. Only after all 62 are ready does a full-bank leak audit
create the local `sandbox-devin-kit-v4` commit and copy final KIT.json here.
The shared v3 validator uses a neutral marker-only base-control patch; it does
not modify source or tests. Its registry image digests and official reports are
recorded in `SELECTION.json`; full logs stay in the persistent validation folder.

The exact-power calculation calls the repository's `mcnemar_power`, enumerating
discordant-pair counts and binomial rejection probabilities. It assumes
independent paired units, discordance 8/24, and target gain +0.15. These are
planning assumptions, not a guarantee of the v4 discordance or achieved power.
See `../PREREG.md` for the frozen design and the agent-test red/green gate.

The selector itself creates no workspaces or v4 dispatch sessions.
Completed outputs with calibration and power recorded are frozen: rerunning the
default command refuses before validation or writes. Completed checkpoints
missing either final field resume offline: saved IDs, validation and replacement
records stay intact, and only missing calibration/power metadata is added atomically.
Initial selection, offline resume and replacement replay share the same calibration
policy: seed 20261125 on the original bank, redrawn from the final bank only when
a replacement removed an original calibration ID. Missing original-bank provenance
for replacements is an error, not permission to silently redraw.
Use a different `--out` for an independent reconstruction;
`--overwrite-frozen` explicitly permits replacing a completed bank and calibration.

## Bank-independent gate template

`gate.write_suite(kit_root, instance_id, frozen_v3_style_config)` writes only
`gates/<id>/`, not task branches or a full kit. The config supplies the frozen
`django`, `selectors`, `interpreter`, `timeout_s`, and `environment.commands`
fields. P2P measurements/selectors must be finalized before exporting real
bank suites. The exported suite is standalone and does not import `ops/`.

From a workspace with history-free base HEAD and its environment installed:

```sh
TIMEOUT=$(../.venv/bin/python -c 'import json; print(json.load(open("../gates/<id>/selection.json"))["timeout_s"])')
../.venv/bin/vacant run --workspace . --suite ../gates/<id> \
  --run-dir ../receipts/<id>-N --test-timeout "$TIMEOUT" \
  --sandbox none --retry none -- true
```

The agent supplies root `VACANT_TESTS.txt`, one explicit node ID per line.
As in v3, put receipts under the kit root. Vacant verifies a frozen candidate
without `.git`; the wrapper locates the kit from that receipts path and reads
the original workspace's git HEAD and tracked-file inventory. Manifest/test
overlays and all candidate checks come from the frozen tree, never live edits.
The kit-Python coordinator archives git HEAD, normalizes tracked setup edits,
and overlays only the listed test files plus owner-approved untracked `.so`/
`.pyd` build artifacts and generated version files. If compiled sources differ,
it rebuilds extensions in the pristine base with `base_rebuild_commands` instead
of borrowing candidate binaries. The instance Python and existing gate deadline
apply to this rebuild too. Step A requires an actual test-body
failure on that base; Step B requires every listed node green on the candidate;
Step C uses the unmodified v3 P2P runner. One per-instance timeout covers all
three steps. Refusals identify the step and nodes. At most three submissions
are allowed by the dispatch protocol, not by this stateless suite itself.
A/B/C subprocesses prepend the instance interpreter's bin directory to PATH,
including under Vacant's sanitized environment, so recipe-installed tools such
as Graphviz resolve exactly as they did during native preparation.

Do not commit candidate implementation changes over the base HEAD before
submitting. New test helpers/conftest files are not overlaid unless themselves
listed test files. Native artifact copying is exercised by compiled-package kit
controls. Rebuild dispatch, pristine-source use and failure refusal are covered
by fixture tests; these are not a full native compiled-source handoff test.
Rebuild commands are recorded in KIT.json, exported gate
configuration and the instance README section; rebuilding does not reinstall
the candidate or repoint the environment's editable install at a temporary tree.
Artifact reuse is not independent proof that a binary matches its source.

`v4.patch.derive_patch` preserves source/test edits, even in official-test paths
or matching base ignore rules. Only root `VACANT_TESTS.txt` is dropped as gate
metadata; the shared binary/build/cache exclusions and setup normalization
remain. The original hidden test patch is applied independently by the future
scorer. Gate/patch helpers do not perform official scoring; `kit.py` assembles
the bank-specific native kit separately. Harness-version pins remain setup
authority. Xarray disables the user site during setup and gating; pytest sets
its SCM version to the harness version key in both places. Approved base-failing
P2P omissions and supplied-prompt exceptions are explicit in KIT.json and PREREG.

## Official scoring and incremental collection

The v4 adapter reuses v3's safe Git export, official SWE-bench 3.0.17 harness,
review views and paired analyzer. It uses v4 patch derivation: agent tests stay,
root `VACANT_TESTS.txt` is dropped. Its presence is recorded from the original
pushed tree, separately from the scored patch. No gate result is a hidden-test
outcome. Calibration schedules only the frozen twelve-ID subset; comparison
schedules exactly 62 × 3 × 2 = 372 distinct cells, never calibration cells.

Keep the calibration images, by their feasibility-recorded registry digests:

```sh
nohup .venv/bin/python -u -m ops.sandbox.v4.images > ~/sandbox-v4-images.log 2>&1 < /dev/null &
```

`sessions.json` maps full scheduled branch names to session IDs. For calibration
only, instance-ID keys are also accepted. Partial maps may be extended, but an
existing session binding cannot change. Run outside-repository results under
`results/devin-v4-cal-*` or `results/devin-v4-cmp-*`:

```sh
nohup .venv/bin/python -u -m ops.sandbox.v4.score watch \
  --protocol calibration --sessions ~/sandbox-v4-scoring/calibration-sessions.json \
  --dataset-json ~/swebench-data/verified.jsonl \
  --harness-python ~/swebench-venv/bin/python \
  --out ~/sandbox-runs/results/devin-v4-cal-YYYYMMDD \
  --audit-export ~/sandbox-v4-scoring/audits.json \
  > ~/sandbox-v4-scoring/scorer.log 2>&1 < /dev/null &
```

Use `--protocol comparison` and the 372-cell session map for comparisons.
`score` performs one polling pass; `watch` polls every 300 seconds until all
outcomes and both audits exist. Pull rate limits retry the same pinned image or
candidate at 900, 1800, then 3600 seconds (capped), never as a scored rejection.
Other infrastructure failures remain infra_void failures in the denominator.
Images are retained; the puller pauses at 85% disk use, without deleting any
images. Check disk capacity before the full comparison. Harness attempts and
interrupted cells are archived, not overwritten. Resume checks frozen inputs,
protocol and timeout. A moved or deleted delivered branch makes results
incomplete; it is never silently rescored. Use a fresh results directory to
score a different delivery. `--control-only` cannot clear calibration.

### Session audits and review

The v3 session-event search is an operator/lead operation, not a credentialed
session API client in this repository. Reuse that scanner with the session IDs
from the map, including browser/terminal accesses and received PR/review
messages before the final push. PR creation alone is not outside help. Raw
`browser_events`/`hits` scanner exports can be ingested but never establish
clean verdicts. Missing transcripts or either unknown verdict leave the gate
incomplete; absence of scanner hits is not evidence that an audit is complete.

The audit export is a JSON list, one record per branch, containing `branch`,
`session_id`, and the scanner evidence. To apply reviewed verdicts, also supply:
`handback_sha` equal to the scored commit; `reviewer`; boolean `contaminated`
and `outside_help`; `access_audit_complete: true` and
`outside_help_audit_complete: true`; nonempty `evidence` and
`outside_help_evidence` lists; and nonempty `final_push_evidence` and
`pr_review_evidence` describing the timing/receipt check. Source exports are
archived by SHA256. The watcher ingests this file between scoring passes, or:

```sh
.venv/bin/python -m ops.sandbox.v4.audit --out RUN_DIR --export audits.json
.venv/bin/python -m ops.sandbox.v4.score review --out RUN_DIR
```

Scoring and review use a single nonblocking run lock. If the watcher is scoring,
let it ingest the export after its pass rather than editing state concurrently.
`calibration.json` clears only with all twelve official outcomes and both audits
complete, counting either flagged cell as resolved regardless of harness result.
Above eight reports `ceiling, v4 rejected`. Costs stay UNKNOWN without usage data.

Comparison review writes `analysis-primary.json`, `analysis-sensitivity.json`,
the v3-style verdict-addressed review views, and `secondary.json`. Complete
A/A2/G triples use exact McNemar and the existing 10,000-resample paired
bootstrap (seed 20261122), with the same gain/noise-floor rule. Primary excludes
whole flagged/unreviewed triples; sensitivity includes complete triples.
Incomplete coverage/audits is explicitly provisional. Null comparisons include
the CI upper endpoint as `largest_gain_not_ruled_out`.

For gate evidence, place the v3-format reply export (`branch`, `session_id`,
`messages`, `final_reply`) in `RUN_DIR/gate-export.json`. The v3 parser is reused;
v4 adds A/B/C step verdicts, with sequential-step inferences explicitly labeled.
Unshown steps remain UNKNOWN. `gate-evidence.json` and `secondary.json` preserve
raw excerpts, source hashes, final-branch manifest presence and UNKNOWN receipt
verification/handback binding. Pasted acceptance is not an independently
verified receipt, and `1/1 次` is not a session submission count.
