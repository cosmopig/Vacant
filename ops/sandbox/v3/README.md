# V3 feasibility and public-result selection

This is a selection procedure, not a kit, agent run, calibration, or gain claim.
It reads no Vacant/pi/Devin experiment outcomes. `SELECTION.json` is a checkpoint:
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
No source/solution material is exported as an agent workspace in this step.
