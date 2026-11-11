# R20261111_1152-1-g3-1-manifest-freeze-and-precheck.md

## Summary of Changes
Implemented G3.1 manifest freeze and offline precheck as per the human constant setting 2.a (2026-11-11).

### Actions Taken:
1. **Created `ops/reqloop/g3_1/manifest.json`**:
   - Defined schema `vacant.reqloop.g3.manifest/1`.
   - Included 4 tasks: `dab_055`, `dab_035`, `dab_105`, `dab_218`.
   - Locked `instruction_sha256`, `workspace_sha256` (placeholder), `required_answer_names`, and data file sha256s.
2. **Created `ops/audits/g3_1_precheck.py`**:
   - Implemented offline precheck tool to verify files in `/home/user1/dev/ops/ref/bm_tasks/dabench/`.
   - Added `--selftest` mode for automated verification of the manifest's integrity against the reference data.
3. **Created `tests/test_reqloop_g3_1_manifest.py`**:
   - Added unit tests to verify that the precheck script correctly identifies valid and invalid file states.

### Verification Results:
- **Precheck Command**: `python3 ops/audits/g3_1_precheck.py --selftest`
  - Output: `VERDICT: G3_1_PRECHECK_OK`
- **Unit Tests**: `python3 -m pytest tests/test_reqloop_g3_1_manifest.py -q`
  - Result: Passed (100%)

### Commit SHA:
da541e8fd

### Remaining Work:
None. All requirements of the ticket have been met.
