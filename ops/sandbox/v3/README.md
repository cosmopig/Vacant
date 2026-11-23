# V3 public-result selection and external-session kit

Selection reads no Vacant/pi/Devin experiment outcomes. These tools launch no
agents; gate and synthetic harness controls are not agent-performance or gain evidence.
`SELECTION.json` is a checkpoint:
only `status: complete` with twelve validated IDs is a finished selection. A
partial/blocked checkpoint is not a usable task bank.

## Pinned inputs and deterministic rules

- Experiments: `swe-bench/experiments` commit
  `40f164d5b8f1d249bf95a6df8b74b577fd8e519d`.
- Dataset: `princeton-nlp/SWE-bench_Verified`, test split, revision
  `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, 500 instances. The script checks a
  canonical JSON SHA256 as well as recording the revision. A local JSONL export
  must contain these exact records, in dataset order.
- Rank every submission with `evaluation/verified/<submission>/results/results.json`
  by the number of distinct resolved Verified IDs divided by 500. Absent IDs
  are not resolved. Break equal rates by submission directory ascending. Use
  exactly the first ten, without filtering models, attempts, checked tags,
  organization, dates or metadata availability. Missing result files are not
  inferred. All ranked submissions, source hashes and top-ten resolved lists
  are recorded so the choice can be audited.
- Read names from `metadata.yaml` (or upstream's `.yml` spelling). Where metadata
  has no date, record the directory-prefix date and label that source explicitly.
- Candidate pool: strictly `0 < solved_by_top_ten / 10 < 0.5`, before feasibility.
  Sort IDs ascending, then shuffle with a private `random.Random(20261123)`.
- Walk that fixed order, excluding dataset difficulty exactly `>4 hours`, then
  enforce at most three selected instances per repository. Validate remaining
  instances in order until twelve pass. Record every actual skip and validation;
  the rest of the ordered list remains unvisited, not implicitly failed.

## Environment and invocation

Use a separate Python >=3.11 environment. Plain `pip install swebench` succeeded
here with 5.0.2, but that release requires the new `image`/`eval_script` schema:
`make_test_spec` on this Princeton dataset raises `KeyError: 'image'`. The
compatible official harness is pinned to **swebench 3.0.17** for this procedure.
Do not change the package in the Vacant project environment.

```bash
python3.12 -m venv ~/swebench-venv
~/swebench-venv/bin/python -m pip install swebench==3.0.17
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/swe-bench/experiments.git ~/swebench-experiments
git -C ~/swebench-experiments sparse-checkout set --no-cone \
  '/evaluation/verified/*/results/results.json' \
  '/evaluation/verified/*/metadata.yaml' '/evaluation/verified/*/metadata.yml'
# If upstream has advanced, fetch the pinned SHA before selecting.
git -C ~/swebench-experiments fetch origin 40f164d5b8f1d249bf95a6df8b74b577fd8e519d
~/swebench-venv/bin/python -m ops.sandbox.v3.select \
  --experiments ~/swebench-experiments --work-dir ~/swebench-v3-validation
```

`--dataset-json ~/swebench-data/verified.jsonl` uses the hash-checked local
export instead of downloading the same pinned HF revision. `--out` defaults to
this directory's `SELECTION.json`. Source reads use `git show <pinned SHA>:...`,
not mutable working-tree copies. Sparse clones may lazily fetch missing blobs.

Docker availability is checked before any validation. Without Docker, the script
writes the candidate list/order and stops with no selected IDs (exit 2). Global
infrastructure errors likewise stop and are not disguised as broken instances.
Insufficient eligible instances returns exit 2, rather than relaxing a rule.

## Gold/base validation

The official harness `make_test_spec` and `run_instance` execute against the
published `swebench` instance images. Image IDs and registry digests are recorded
because the upstream tag is `latest`; report JSON hashes and paths preserve the
exact evidence used. Validation is serial, with 1800 seconds per control, and
stops if less than 20 GiB is free before starting an instance. Only images newly
pulled by this validator are removed afterward; pre-existing images are retained.

Gold applies the dataset's gold patch. Base leaves all source and tests unchanged:
it adds only `.swebench_v3_base_control`, an inert dotfile. This is necessary
because 3.0.17 rejects empty predictions/patches before testing. Both controls run
the dataset's test patch through the unmodified official harness. A pass requires
gold resolved=true and base resolved=false **with an actually observed failing
FAIL_TO_PASS test**, not merely a missing result, parser failure or patch error.

Full test/build logs and reports live under the external work directory, not the
repository. Stable input/image/control fingerprints identify reusable harness
reports; a rerun may read these rather than execute unchanged controls again.
The selection procedure itself exports no agent workspace or solution material.

## Preregistration and kit

The dated v3 section in `../PREREG.md` was committed on its own before kit
creation. It fixes the whole-bank calibration gate, fresh comparison arms,
official-harness primary outcome and handback-patch rules, P2P intervention,
event-based contamination exclusions and inclusive sensitivity analysis.
The v3 handback scorer is not implemented by this kit-building step.
`patch.py` is its canonical patch-derivation module/CLI: normalize the base with
the recorded tracked setup edits before comparing with the handback. It does
not execute project code or installation commands. It excludes test-patch
files, binary files and generated artifacts, while retaining agent changes
even in setup files. The official harness image has its own pre-install edits.
Setup-only Sphinx/Astropy handbacks therefore produce empty candidate patches.
New paths ignored by the base snapshot's own `.gitignore` files are omitted too,
including generated Astropy/Matplotlib version modules and generated C sources.
Ignore rules are taken only from base, not from the handback or host settings;
tracked edits and non-ignored new source files remain eligible for scoring.

```bash
.venv/bin/python -m ops.sandbox.v3.patch --base BASE_SNAPSHOT --handback HANDBACK \
  --dataset-json ~/swebench-data/verified.jsonl --instance INSTANCE --out candidate.patch
```

`KIT.json` records the published branch SHAs, upstream base commits/tree IDs,
file-size checks and leak-check counts. Each `sandbox-v3/<instance_id>` branch
has one parentless commit whose tree is exactly that upstream base tree. No
patch, added test, dataset file, custom prompt or other metadata is inserted.
The small, independently rooted `sandbox-devin-kit-v3` branch contains only
exact problem statements, gates, README and ignore rules; it contains
no hints, reference fixes, new acceptance tests or repository workspaces.

`kit.py` maps PASS_TO_PASS parser labels to existing base test modules. Module
scope for labels without a filename comes from the original harness's test
file paths, intersected with files present in base; no test-patch code is
exported. Short labels can represent tests in multiple modules or inherited/
parameterized cases. Before export, `measure.py` freezes concrete base-passing
node IDs, covering every retained label and rejecting every failing baseline
variant. Only ambiguous base-skipped variants are excluded. Newly introduced
functions, methods and parameterizations are omitted even if labelled P2P.
Omissions and label-to-node mappings are recorded in `KIT.json`. Every frozen
node must actually pass: skips, deselection and missing nodes refuse.

Vacant and its wrapper use kit-root `.venv` (Python >=3.11). Tests use the
instance's official harness Python at `.envs/INSTANCE/bin/python`; no stdlib
shim is used. The generated README lists each version and harness environment,
system-provisioning and repository-install commands. Both env directories and
receipts are gitignored. BLAS/OMP/MKL threads are fixed to one in the runner.
Django uses its native database setup and warning policy; other repositories
load their installed pytest plugins. The driver pins compatible pytest versions
and the legacy `py` API for SymPy. Pandas is required for the sklearn tests.

`measure.py` runs in each registry-digest-pinned official image, retaining the
image's built dependencies while restoring tracked files from raw base Git
blobs (image setup may adjust build files). It never applies either patch.
Gate timeouts are `max(120, ceil(3 * measured_base_seconds + 30))`; the README
passes that value to `vacant run --test-timeout`, not merely an inner subprocess.
The inner timeout leaves ten seconds for feedback. Measurements, image and
runner fingerprints, and passing-node reports are retained externally.

```bash
~/swebench-venv/bin/python -m ops.sandbox.v3.measure \
  --dataset-json ~/swebench-data/verified.jsonl \
  --snapshots ~/sandbox-v3-build/snapshots.json --work ~/sandbox-v3-measurements
~/swebench-venv/bin/python -m ops.sandbox.v3.kit \
  --dataset-json ~/swebench-data/verified.jsonl \
  --snapshots ~/sandbox-v3-build/snapshots.json \
  --measurements ~/sandbox-v3-measurements/measurements.json --out NEW_KIT_DIR
```

These commands are operator-only: dataset files never enter the kit. The
measurement command requires the pinned images locally and reuses evidence
only when runner, environment, image and selection inputs match. The builder
rejects missing or stale runner/selector SHA256 fingerprints before writing any
kit files. Session hosts
must still install the documented environments and preflight before starting;
the Docker measurements do not certify dependency resolution on every host.

Leak checks cover introduced FAIL_TO_PASS function names and **all nonblank
gold-added lines**, including short fixes. Every kit branch has zero matches
not already present in base. Raw generic-line/name matches are recorded as
base exceptions, not misreported as a literal zero grep count. Prompt bytes
preserve the original CRLF, trailing whitespace and ending exactly, despite
`git diff --check` warnings in the isolated kit checkout. Full control logs
and private match evidence remain under `/home/ubuntu/sandbox-v3-build/`.

## Independent handback scorer (operator only)

The scorer uses the frozen twelve-instance bank, not v1/v2 task scoring. Keep
the dataset and all scorer artifacts off session hosts and out of kit branches.
Use the project venv for collection and a separate Python >=3.11 environment
with `swebench==3.0.17` for the isolated harness worker:

```bash
.venv/bin/python -m ops.sandbox.v3.score score --protocol calibration \
  --dataset-json ~/swebench-data/verified.jsonl \
  --harness-python ~/swebench-venv/bin/python \
  --out ~/sandbox-runs/devin-v3-cal
```

Calibration reads `sandbox-devin-cal3/<instance_id>-plain`. Comparison uses
`--protocol comparison` and `sandbox-devin/v3/<instance_id>-<arm>-s<k>`, where
arms plain/plain2/vacant map to A/A2/G and k is 1 or 2. With no branch arguments,
all scheduled refs are attempted. Explicit arguments restrict collection but
not the whole-bank schedule: all absent/unrequested submissions are listed in
`missing_branches`, never imputed. Output must be fresh and outside the repo;
an existing directory containing only `NOTES.md` is permitted and preserved.

Base refs must match the committed KIT SHA, raw tree and dataset base commit.
Raw Git blobs are exported without archive export-ignore/export-subst effects.
No handback code executes on the collector host. `patch.py` derives the patch;
the harness applies the official test patch and executes in the digest-pinned
official image, never a checked-but-mutable tag. Its report supplies resolved
(`hidden_pass` in the generic analyzer schema). Candidate application failure
is unresolved, not infra. Missing/invalid reports, Docker errors and timeouts
are infra_void, retained as failures. The default official test timeout is
1800 seconds, independent of the visible gate deadline. Canonical empty patches
are submitted unchanged; an empty-patch application refusal is unresolved.
`visible_pass` is null: the scorer does not measure the Vacant gate outcome;
the generic analyzer's visible counter must not be read as a v3 gate pass rate.

`cells/*/` retains the raw base/handback, canonical candidate patch, harness
request, report and logs. Metadata records code/input fingerprints. Agent costs
remain UNKNOWN; harness timing is separate. Gold similarity uses the same
test-file/artifact exclusions and the PREREG whitespace-normalized polarized
diff-line SequenceMatcher rule; ≥0.9 is a secondary flag, never a contamination
verdict. Synthetic e2e controls use `--control-only` and cannot pass calibration.

### Human verdicts and analysis

`contamination.json` has a slot for every scheduled branch. Fill `contaminated`
(access-based) and `outside_help` with JSON true/false, plus `evidence`,
`outside_help_evidence` and reviewer. Null means pending, not clean. For PR help,
audit whether Devin Review or human comments reached the session **before its
final push**; PR creation alone does not establish outside help. The dispatch
instruction prohibiting PRs and the dated amendment are in `DEVIN_ARMS.md` and
`PREREG.md`. Review does not fetch or rerun tests:

```bash
.venv/bin/python -m ops.sandbox.v3.score review ~/sandbox-runs/devin-v3-cal
```

`calibration.json` reports observed resolved and conservative gate counts.
Either positive verdict makes a calibration cell count as resolved even if its
harness outcome failed/was infra. The ≤8/12 gate is incomplete until all twelve
branches and both verdicts per cell are present; otherwise it says proceed or
"ceiling, v3 rejected". Calibration is never a comparison input.

The raw root is analyzer-compatible but **is not the primary comparison view**.
For comparisons, review exports verdict-addressed `primary` and `sensitivity`
views; paths are in `meta.json.analysis_views`. Both use complete A/A2/G triples
so treatment and noise floor share units. Primary excludes the entire unit if
any arm is contaminated, outside-helped or unreviewed; sensitivity retains
complete triples with their observed outcomes. Infra remains failure in both.
Missing and excluded units are explicit; unknown review/coverage is not a full
24-pair result. Run the existing analyzer on the chosen exported view:

```bash
.venv/bin/python -m ops.sandbox.analyze PATH_FROM_META_ANALYSIS_VIEWS
```
