# Three paired losses: patch and official-log diagnosis

These are the three (instance, sample) pairs where plain resolved and vacant did
not. No official scoring was rerun or changed for this investigation. Gate use
comes from exported assistant messages/pasted stdout; correctness comes from
the already archived official harness. These are different evidence sources.

## Classification

| Vacant cell | Reported gate exits | Official FAIL_TO_PASS | Official PASS_TO_PASS | Classification |
|---|---|---|---|---|
| scikit-learn-25747 s1 | 0 | 0/1 passed | 14/14 passed | Accepted on visible P2P; new behavior not fixed |
| scikit-learn-25747 s2 | 0 | 0/1 passed | 14/14 passed | Accepted on visible P2P; new behavior not fixed |
| matplotlib-24870 s1 | 20, then 0 | 0/1 passed | 65/65 passed | Initial environment refusal, then visible acceptance; new behavior not fixed |

All three patches applied successfully; `infra_void=false`. None is classified
as an official P2P regression or a never-run gate. `loss-evidence.json` contains
their full handback SHAs, image digests, official test statuses, source log paths,
log hashes and line-numbered failure excerpts. `gate-evidence.json` contains the
separate reply evidence. Receipt integrity, completeness of execution history,
and binding of a gate workspace hash to the final handback remain UNKNOWN.

## Scikit-learn: both patches preserve only the row-count-changing case

Final vacant SHAs:

- s1: `e1e47d1e03647a903d3d19779169bf90560ff2ae`
- s2: `c4d53a2e0931c25ea29723a34fefbc55be724a7e`

Both canonical patches make the same functional change in
`sklearn/utils/_set_output.py::_wrap_in_pandas_container`:

```python
if index is not None and len(index) == len(data_to_wrap):
    data_to_wrap.index = index
```

That avoids forcing a 96-row input index onto a 4-row aggregation. It still
overwrites a transformer's own labels whenever output and input lengths match.
The higher-level `_wrap_data_with_container` remains unchanged in both vacant
handbacks: it supplies `getattr(original_input, "index", None)` to this helper.

### The failing path actually executes

The official added test constructs a two-row input indexed `[0, 1]`, enables
`set_output(transform="pandas")`, and uses an estimator whose transform returns
a DataFrame indexed `["s0", "s1"]`. The mixin wraps that transform through
`_wrap_data_with_container`. Both lengths are 2, so the new condition is true:
the old input labels overwrite the returned labels.

From s1's official `test_output.txt:10023–10032`:

```text
10023:         X_trans = est.transform(X)
10024: >       assert_array_equal(X_trans.index, ["s0", "s1"])
10029: E        x: array([0, 1])
10030: E        y: array(['s0', 's1'], dtype='<U2')
10032: sklearn/utils/tests/test_set_output.py:294: AssertionError
```

s2 executes the same failure, at `test_output.txt:10018–10027`:

```text
10018:         X_trans = est.transform(X)
10019: >       assert_array_equal(X_trans.index, ["s0", "s1"])
10024: E        x: array([0, 1])
10025: E        y: array(['s0', 's1'], dtype='<U2')
10027: sklearn/utils/tests/test_set_output.py:294: AssertionError
```

The failed F2P node in both reports is
`sklearn/utils/tests/test_set_output.py::test_set_output_pandas_keep_index`.
s1's log concludes `1 failed, 14 passed, 1 warning in 0.22s` (line 10050).
Both reports have an empty P2P failure list. This is an executed assertion about
incorrect labels, not an import failure, missing pandas, timeout or Docker void.
The sys.prefix warnings in s1's *gate reply* are not this official failure.

### How the successful plain patches differ

- **plain s1:** changes `_wrap_data_with_container` instead. If the output is
  pandas-like (`hasattr(data_to_wrap, "iloc")`), it passes the output's own
  `data_to_wrap.index` down. The low-level helper can retain its old explicit
  index-override behavior, but the automatic wrapping no longer destroys labels.
- **plain s2:** removes the DataFrame index assignment from the low-level helper
  entirely, preserving a DataFrame's own labels regardless of row count.

Both plain official reports resolve: F2P passes and all 14 P2P nodes pass.

### Could the gate have encouraged the narrower fix?

There is a **verified legacy-test constraint and a plausible selection pressure**,
not proof of agent-level causation:

1. KIT.json's `sandbox-v3/scikit-learn__scikit-learn-25747` entry retains
   `test__wrap_in_pandas_container_dense_update_columns_and_index` in its concrete
   gate targets. The frozen base test explicitly asserts
   `assert_array_equal(new_df.index, new_index)` with `new_index=[10, 12]`.
   Both vacant handbacks leave that old test assertion intact.
2. A separate, offline diagnostic probe ran that **unchanged base test**, without
   `test_patch`, against each of the four canonical patches in the same pinned
   official sklearn image (network disabled, BLAS thread counts 1). It did not
   rerun the official handback scorer or modify any primary outcome:

   | Canonical patch | Old P2P test |
   |---|---|
   | plain s1 | PASS, exit 0 |
   | plain s2 | FAIL, exit 1 |
   | vacant s1 | PASS, exit 0 |
   | vacant s2 | PASS, exit 0 |

   The plain-s2 failure is `test_set_output.py:36`, specifically the old index
   assertion: actual `[0, 1]`, expected `[10, 12]`. It is not an environment error.
   Inputs, digest, stdout/stderr and exits are in `sklearn-base-p2p-probe.json`.
3. The official dataset's test_patch edits this existing P2P test's index assertion
   to compare with `X_df.index`, and adds the independent equal-length/new-label
   F2P case. Thus the old frozen gate assertion and the official patched test
   are not textually the same contract. The changed assertion aliases the input
   DataFrame; the added F2P test is what exposes these vacant patches' overwrite.
4. s1's reply explicitly says that "the existing test that checks the index gets
   replaced still passes." Both vacant patches preserve that behavior while
   special-casing mismatched lengths. This is consistent with conservative
   preservation of the visible test, but is not a recorded reason for choosing
   the patch over a higher-level fix.

**Attempt to disprove a gate-forced failure:** plain s1 passes the same old P2P
assertion *and* resolves in the official harness. A gate-compatible correct fix
therefore exists; the gate did not make resolution impossible. The visible
constraint does rule out the particular plain-s2 repair, but not every repair.

Neither sklearn session reports a refusal or corrective gate-feedback round:
both show first-submission `visible_pass`, exit 0. There is no observed refusal
feedback that steered a formerly correct patch wrong. Whether the visible test
selection/anticipated acceptance actually caused either choice is **unverified**:
the exported messages are not the full shell/reasoning trajectory or pre-gate
candidate snapshots. The directly supported cause is the same incomplete
row-count-only patch in both final handbacks.

## Matplotlib s1: the triangular-contour caller was omitted

Final vacant SHA: `ad67f25012ffca15a8200f075113500bfb6aa768`.

The canonical patch updates `QuadContourSet._contour_args` to pass the original
Z dtype to `_process_contour_level_args(args, z_dtype=None)`, and supplies boolean
defaults when the dtype is boolean. It does **not** update
`lib/matplotlib/tri/_tricontour.py::TriContourSet._contour_args`, whose final-tree
call is still:

```python
self._process_contour_level_args(args[1:])
```

For this caller `z_dtype` therefore remains `None`; the new bool-specific branch
is skipped and the old default `levels_arg=7` automatic path remains. Both successful
plain patches update this triangular caller to forward the dtype; vacant s2
also updates it and resolves.

### The official failure is the triangular case, not the environment refusal

The independent `test_bool_autolevel` first executes six quad contour/contourf
assertions successfully (`test_output.txt:569–574`). Then:

```text
575:         z = z.ravel()
576: >       assert plt.tricontour(x, y, z.tolist()).levels.tolist() == [.5]
577: E       assert [0.0, 0.15000...00000001, ...] == [0.5]
579: E         At index 0 diff: 0.0 != 0.5
580: E         Left contains 7 more items, first extra item: 0.15000000000000002
583: lib/matplotlib/tests/test_contour.py:709: AssertionError
```

The failed F2P node is
`lib/matplotlib/tests/test_contour.py::test_bool_autolevel`. The log concludes
`1 failed, 65 passed, 1 skipped in 4.31s` (line 653). The report lists 65 P2P
successes and no P2P failures. The separate skipped SVG test needs Inkscape;
it is not the failed F2P or a selected P2P failure.

**Disconfirming the environment explanation:** the same official log explicitly
passes `test_contour_manual_labels[pdf]` (line 603), the test cited in the earlier
gate refusal. The final official failure is a numeric level assertion reached
through `plt.tricontour`, not missing Ghostscript or a patch-application failure.
The six preceding quad checks pass, further localizing the missed caller.

### What the refusal feedback actually shows

Event `event-01a2066322057e618b43ebe45c29eaa9` reports:

```text
Submission 1, EXIT=20
test_gate.py::main — assert: P2P skipped:
lib/matplotlib/tests/test_contour.py::test_contour_manual_labels[pdf]
64 passed, 1 skipped, 2 deselected in 2.99s
```

It then shows submission 2 `交付（visible_pass）`, `EXIT=0` after installing
Ghostscript. The session reports "no code change between submissions"; that
claim cannot be independently verified without the intermediate receipt trees.

The observed feedback refuses a skipped P2P test; the session attributes that
skip to a setup gap. It does not request the wrong contour behavior or explain
the unmodified triangular caller. **No evidence
shows feedback introduced the functional bug.** The before/after source
trajectory and counterfactual effect of time spent on setup remain unverified;
one should not convert that uncertainty into either proven harm or proven
absence of influence.

## Boundaries

- The primary decision remains **no measurable gain**; these diagnoses do not
  change the exclusion mask, scores or preregistered statistics.
- All three are supported examples of reported visible acceptance coexisting
  with an unresolved final handback, not demonstrations of better agents or
  an environment-wide mandatory receiving desk.
- Native gate receipts were not exported or independently verified. Message
  exports can be truncated; only explicitly shown/reported executions are counted.
- API ACU values reported as 0.0 for all 72 remain **UNKNOWN**, not zero cost.
