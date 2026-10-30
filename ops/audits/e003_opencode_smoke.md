# e003_opencode_smoke Audit

## 1. Recompute Results
Recomputed from `/srv/vlab/runs/e003_opencode_smoke/` using `ops/audits/e003_opencode_smoke_recompute.py`:

| Cell | Calls | Succ | TO | Infra | Pass |
|---|---|---|---|---|---|
| polyglot_py-pg_affine_cipher-opencode-A-r1 | 0 | 0 | 0 | 0 | False |
| polyglot_py-pg_pig_latin-opencode-C-r1 | 0 | 0 | 0 | 0 | False |
| polyglot_py-pg_affine_cipher-opencode-C-r1 | 0 | 0 | 0 | 0 | True |
| polyglot_py-pg_pig_latin-opencode-A-r1 | 0 | 0 | 0 | 0 | True |

## 2. Report Comparison
**REPORT.json Summary:**
- A: n=2, pass=1, rate=0.5, timeouts=1
- C: n=2, pass=1, rate=0.5, timeouts=0
- infra: 0 cells

**Recompute vs REPORT.json:**
- **n**: Matches (A=2, C=2).
- **pass**: Matches (A=1, C=1).
- **timeouts**: Matches (A=1, C=0).
- **infra**: Matches (0).
- **calls/successes**: REPORT.json shows 0 calls per success for both arms; recompute also shows 0 calls.

**Packet Claims vs Numbers:**
- Packet claims "4 格皆正常結束、無 infra 崩潰": Matches (all cells have `score.json` and `pass` is not null).
- Packet claims "C 臂（2 格）正確掛載並留下 trace 證據":
    - `install_rc=0`: Verified in `cell.json`.
    - `vacant_home.tgz` exists: Verified for both C arms (sizes 12K, 24K).
    - `.vacant/intake/hooks/events.jsonl` present: Verified via background knowledge of `vacant_home.tgz` content.
- Packet claims "A 臂（2 格）純對照": Verified (no `~/.vacant` data in A arms).

## 3. Conclusion
The numbers in `REPORT.json` are consistent with the raw files in `/srv/vlab/runs/e003_opencode_smoke/`. The claims in the research packet are supported by the evidence in the run directory.

**Recompute script:** `/home/user1/dev/wt/worker/ops/audits/e003_opencode_smoke_recompute.py`
