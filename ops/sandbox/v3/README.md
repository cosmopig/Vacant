# V3 public-result selection and external-session kit

Selection reads no Vacant/pi/Devin experiment outcomes. No agents or calibration
have been run for v3; gate controls are not agent-performance or gain evidence.
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

`KIT.json` records the published branch SHAs, upstream base commits/tree IDs,
file-size checks and leak-check counts. Each `sandbox-v3/<instance_id>` branch
has one parentless commit whose tree is exactly that upstream base tree. No
patch, added test, dataset file, custom prompt or other metadata is inserted.
The small, independently rooted `sandbox-devin-kit-v3` branch contains only
exact problem statements, gates, README and the two ignore rules; it contains
no hints, reference fixes, new acceptance tests or repository workspaces.

`kit.py` maps PASS_TO_PASS parser labels to existing base test modules. Module
scope for labels without a filename comes from the original harness's test
file paths, intersected with files present in base; no test-patch code is
exported. Short labels can represent tests in multiple modules or inherited/
parameterized cases; the runner selects those labels only, never whole files.
Newly introduced functions are omitted even if labelled PASS_TO_PASS. The
Sphinx 8548 list has one such omitted function; its four pre-existing labels
remain. Missing runtime labels fail closed instead of running extra tests.

The kit README defaults to **Python 3.11** (Vacant requires >=3.11), pytest 7
and setuptools for legacy compatibility. Python 3.12 was not suitable for the
SymPy 21612 base P2P control. Sessions must install their project's own
dependencies; only the SymPy 21612 gate has been VM-verified here, with mpmath
1.3.0 and public Vacant main `c097899e768fe049f0b96f6724b219e8530acc10`.
Its unchanged base was accepted; changing only the Catalan printer to return
an incorrect value was refused by `test_Catalan`. No reference overlay was used.
The other eleven gates still require repository-specific environment preflight.

Leak checks cover introduced FAIL_TO_PASS function names and **all nonblank
gold-added lines**, including short fixes. Every kit branch has zero matches
not already present in base. Raw generic-line/name matches are recorded as
base exceptions, not misreported as a literal zero grep count. Prompt bytes
preserve the original CRLF, trailing whitespace and ending exactly, despite
`git diff --check` warnings in the isolated kit checkout. Full control logs
and private match evidence remain under `/home/ubuntu/sandbox-v3-build/`.
