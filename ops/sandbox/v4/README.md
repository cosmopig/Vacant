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
