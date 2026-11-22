# W5 (a + c) Notes — Restart-Mode Receipts & Capacity Governance

Worktree: `~/dev/wt/w5ac` (branched from W1 multi-acceptance work).
Scope: `vacant_network/adapters/restart.py`, `vacant_network/adapters/cli.py`, `vacant_network/trace/recorder.py`, `vacant_network/trace/cli.py`, `vacant_network/retention.py`, `tests/test_restart_receipts.py`, `tests/test_restart_gc.py`.

---

## Part (a): Signed Offline-Verifiable Receipts

### Storage Location & Justification

Each restart-mode run (`vacant do` without a contract, or `restart.run()`) appends **one** signed `restart_receipt` entry into the project's existing trace chain:

```
$VACANT_HOME/trace/projects/<project_key(project)>/chain.ndjson
$VACANT_HOME/trace/projects/<project_key(project)>/head.json
```

while continuing to write `result.json` under `$VACANT_WORK/restart-<ts>-<pid>-<hex>/result.json` (now including a `receipt` reference `{recorded, schema, project_key, chain_path, seq, hash}`).

**Why the project's trace chain instead of a separate `restart` chain:**
1. **Zero new crypto / chain format**: reuses `Recorder(project)` -> `Logbook.append()` -> Ed25519 (`$VACANT_HOME/intake/keys/verifier`) + `trust.json` verifier whitelist + canonical JSON + `stream_id`/`branch_id`/`seq`/`prev_hash`/`sig` + file locking (`lock`) + atomic `head.json` + `MixedSignerRefused` guard + volume sealing.
2. **Existing verification & CLI work immediately**:
   - `vacant trace verify` in the project directory verifies the chain offline (signatures, sequence continuity, hash links, `trace_genesis`, `head.json`, `trust.json`).
   - `vacant trace show` renders `restart_receipt` entries cleanly alongside any trace events.
   - `vacant gc --verify` (`retention.verify_trace_chains()`) automatically verifies restart receipts.
3. **Zero workspace blob pollution**: `Recorder(project).append("restart_receipt", payload)` acquires the lock and appends only the receipt entry (plus `trace_genesis` if this is the first entry for the project); it does **not** scan the workspace or write files into `$VACANT_HOME/trace/objects/`.
4. **Envelope accounting compatibility**: `$VACANT_HOME/trace/projects/` is already registered in `retention.ENVELOPE_COMPONENTS` and bounded by `SUBDIR_TOTAL_CAPS["trace/projects"] = 32 MiB`, and `compact_trace` never deletes `chain.ndjson` or `head.json`.
5. **Cross-location tail-truncation anchor**: `result.json` (stored in `$VACANT_WORK`) records `{seq, hash}` of the receipt entry, so `restart.verify_receipts(project, expected_head=result["receipt"])` catches tail truncation even if an attacker deletes or edits `head.json` inside `$VACANT_HOME`.

### Receipt Schema (`vacant-restart-receipt/1`)

Stored as `type: "restart_receipt"` in `LogEntry` (`Logbook` wire format). Payload fields:

```json
{
  "schema": "vacant-trace/1",
  "receipt_schema": "vacant-restart-receipt/1",
  "run_id": "restart-20261120T073000-12345-abcdef",
  "request_sha256": "<64-hex sha256 of prompt UTF-8>",
  "agent": "pi | claude | codex | opencode | generic | <argv0 basename>",
  "argv": ["<redacted argv tokens>"],
  "env": {"<KEY>": "<value or [REDACTED]>"},
  "project_path_sha256": "<64-hex sha256 of resolved project path>",
  "project_key": "<first 16 hex chars of project_path_sha256>",
  "acceptance": {
    "kind": "check | python_unittest | python_pytest | python_bare | npm | cargo | go | none",
    "command": "<command or null>",
    "protected": ["<sorted protected test relpaths>"],
    "reason": "<reason or null>"
  },
  "max_attempts": 3,
  "attempts": [
    {
      "attempt": 1,
      "wall_s": 0.4,
      "rc": 0,
      "timed_out": false,
      "accept": false,
      "passed": 0,
      "run": 2,
      "status": "ok",
      "tests_tampered": ["sol_test.py"],
      "snapshot_tree_sha256": "<deterministic sha256 over snapshot tree or null>"
    }
  ],
  "delivered_attempt": 2,
  "accepted": true,
  "written_back": [
    {"path": "extra.txt", "op": "added", "sha256": "<file sha256>"},
    {"path": "sol.py", "op": "modified", "sha256": "<file sha256>"}
  ],
  "deleted": ["dropme.txt"],
  "skipped": ["link/evil.txt"],
  "agent_wall_s": 0.8,
  "total_wall_s": 1.1
}
```

Key design details:
- **Deterministic `snapshot_tree_sha256`**: computed over sorted `snap.files` (`relpath -> sha256`) as:
  `sha256(b"".join(rel.encode("utf-8") + b"\x00" + sha.encode("ascii") + b"\n" for rel in sorted(snap.files)))`.
  Reuses digests already computed by `_snapshot_workspace` (zero extra disk reads).
- **Secret redaction**: `_redact_env` and `_redact_argv` operate strictly on copies captured for the receipt after the fact; `Launch.env` and `Launch.argv` passed to `run_agent` are never mutated. Redacts secret-named env keys (`*_API_KEY`, `*_SECRET*`, `*_TOKEN*`, `*_PASSWORD*`, `*_AUTH*`, `*_COOKIE*`, `*_CREDENTIAL*`, `*_PRIVATE*`, `*_JWT*`, `*_DSN*`, etc. — preserving non-secret `PWD`), secret value patterns (`sk-*`, `ghp_*`, `github_pat_*`, `glpat-*`, `xox*-*`, `AKIA*`, `Bearer ...`, `Basic ...`, PEM private keys, `user:pass@host` URLs), and secret CLI flags (`--api-key`, `--token`, `--secret`, `--password`, etc.). Long argv elements (>512 chars) are truncated with a sha256 prefix.
- **Self-contained size bound**: `_bound_receipt_payload` caps receipt payload size at `48 KiB` (safely below `Logbook.MAX_PAYLOAD_BYTES = 64 KiB`) by summarizing oversized file lists with `{key}_count`, `{key}_sha256`, `{key}_truncated: true` so receipts are never offloaded into GC-able `trace/objects/` blobs.
- **Hard rule preservation**: policy, attempt loop, budget timing (`total_wall_s` is computed before receipt signing), prompt, workspace contents, and agent environment are completely unchanged. Recording is fail-open (e.g., on `MixedSignerRefused` or read-only `$VACANT_HOME`, delivery still succeeds and `result.json["receipt"]["recorded"]` is `false` with the error).

### Offline Verification & Tamper Detection

Both `vacant trace verify` and `vacant_network.adapters.restart.verify_receipts(project, state_root=..., trust=..., expected_head=...)` detect:
- **Edited receipt**: fails Ed25519 signature and subsequent `prev_hash` check.
- **Truncated chain**:
  - Tail truncation (last entry removed): caught by `head.json` vs `last.seq`/`last.hash()`, and also by `expected_head=result["receipt"]` even if `head.json` was deleted.
  - Mid-line truncation (torn EOF): caught by `head.json` in `vacant trace verify`, and unconditionally rejected by strict raw-line check in `verify_receipts()`.
  - Head/middle deletion: caught by `trace_genesis` / `seq` continuity / `prev_hash`.
- **Reordered entries**: caught by `seq` continuity, `prev_hash`, and signatures.
- **Wrong signer**: caught by `trust.json` `verifier` whitelist (`trace signer is not on the accepted-signer list`) and Ed25519 signature verification.

Honest boundary: by default the `verifier` private key lives on the same OS account as the agent; if an attacker with full local account access rewrites both `chain.ndjson` and `head.json` using the stolen key, only an off-host key/anchor prevents forgery.

---

## Part (c): Capacity Governance & Measurements

### Finding on Existing `retention.compact_work()`

Before this change, `compact_work()` assumed a two-level contract-mode layout (`$VACANT_WORK/<task_id>/<run_id>/ws*`):
- It treated each `restart-<ts>-<pid>-<hex>` directory as a `<task_id>` and `attempt_k` as `<run_id>`.
- Because restart attempts store workspaces in `attempt_k/w` and snapshots in `attempt_k/snap-<hex>` (neither matches `ws*`), normal GC (`strip_workspaces_only=True`, used by `vacant gc` and `vacant gc --auto`) freed **0 bytes** from restart runs — workspaces and snapshots accumulated without bound.
- Under `--aggressive` (`strip_workspaces_only=False`), it deleted entire `attempt_k/` directories, destroying `attempt_k/logs/agent_stdout.log` and `agent_stderr.log`.

### Implemented Changes

1. **Restart-shape compaction in `retention.compact_work()`**:
   - Identifies direct children matching `restart-*` separately from contract-mode `<task_id>/` directories.
   - For old runs (beyond `keep_runs_per_task`, default `DEFAULT_KEEP_RUNS = 3`, or older than `max_age_days`, or all runs under `--aggressive`): strips `attempt_k/w`, `attempt_k/snap-*`, and any stray `bkp-*` crash leftovers.
   - **Always preserves**: `result.json`, `attempt_k/logs/*`, delivered project files, and signed receipts in `$VACANT_HOME/trace/projects/`.
2. **Named cap**:
   - `DEFAULT_RESTART_WORK_CAP_BYTES = 16 * 1024 * 1024` (**16 MiB**), overridable via `VACANT_RESTART_WORK_CAP_BYTES` (`0` disables).
   - Enforced in `compact_work()`: if total bytes across all `restart-*` dirs still exceed the cap after stripping old runs, kept recent runs also have `w/` and `snap-*` stripped oldest-first (and as a last resort oversized old logs are tail-truncated), never deleting `result.json` or receipts.
3. **`vacant usage` integration**:
   - Reports `areas.restart_work`, `budget.restart_work` (`bytes`, `runs`, `cap_bytes`, `within_budget`, `override_env`), and includes `restart_work` in `envelope.groups` (so overrun flips `envelope.within_envelope` to `False` and is flagged in human-readable `vacant usage`).
   - Fits strictly inside the 256 MiB steady-state envelope:
     - Existing `state_dir` named caps (`all_caps_sum`): `239,337,472 B` (**228.25 MiB**)
     - New `restart_work` named cap: `16,777,216 B` (**16.00 MiB**)
     - Combined total caps: **`256,114,688 B` (244.25 MiB) <= 268,435,456 B (256.00 MiB)** (11.75 MiB headroom).
4. **Auto-GC trigger at end of `vacant do`**:
   - Both `_do_restart` and contract-mode `cmd_do` in `vacant_network/adapters/cli.py` invoke `_trigger_auto_gc(agent)`, which delegates to existing `adapters/hook.py:_spawn_auto_gc(agent, "do")` (detached `vacant gc --auto --json`, flock-locked, 1-hour rate limit, 30 s budget, fail-open, disabled by `VACANT_HOOK_NO_GC=1`).

### Real Measured Disk Usage (Small Project, Stub Agent, 0 Model Calls)

Measured in an isolated `VACANT_HOME` + `VACANT_WORK` on a small Python project (`1,143 B`: `sol.py`, `sol_test.py`, `README.md`, `util.py`) with a stub agent that fails attempt 1 and passes attempt 2 (2 attempts total):

| State | `work_dir` (`restart-*`) | Breakdown of `work_dir` | `state_dir` (`$VACANT_HOME`) | `trace/` (`chain.ndjson` + `head.json`) | Receipts valid? |
|---|---:|---|---:|---:|---|
| After 1 `vacant do` (2 attempts) | **6,762 B** | `result.json`: 2,220 B; `logs`: 30 B; `attempt_*/w`: 2,256 B; `attempt_*/snap-*`: 2,256 B | **3,732 B** | 2,400 B (chain: 2,314 B, head: 86 B; `intake` keys+trust: 1,332 B; `trace/objects`: 0 B) | Yes |
| After default GC on 1 run (`keep_runs=3`) | **6,762 B** (`0 B` freed) | Within `keep_runs=3` and 16 MiB cap | **3,732 B** | 2,400 B | Yes |
| After `--aggressive` GC on 1 run (`keep_runs=0`) | **2,250 B** (`4,512 B` freed, -66.7%) | `result.json`: 2,220 B; `logs`: 30 B; `w`/`snap-*`: 0 B | **3,732 B** | 2,400 B | Yes (`verify_ok=True`) |
| After 5 runs -> default GC (`keep_runs=3`) | **33,550 B -> 24,526 B** (`9,024 B` freed) | 2 oldest runs stripped to `result.json`+`logs`; 3 newest kept intact | **10,189 B** | 8,857 B (all 5 receipts + genesis) | Yes (`verify_ok=True`) |
| Steady-state cap (`restart_work`) | **16 MiB** (`16,777,216 B`) | Overridable via `VACANT_RESTART_WORK_CAP_BYTES` | **228.25 MiB** (`all_caps_sum`) | `trace/projects` subcap: **32 MiB** | Combined cap **244.25 MiB <= 256 MiB** |

Per-run steady-state retention cost after compaction: ~2.25 KiB in `work_dir` (`result.json` + logs) + ~1.6 KiB per receipt entry in `chain.ndjson` + `0 B` in `trace/objects/`.

---

## `COPY_SKIP` Measurement & Proposal (Not Modified)

Current `COPY_SKIP` (`vacant_network/adapters/run.py:47`):
```python
COPY_SKIP = frozenset({".git", "node_modules", "__pycache__", ".venv", ".pytest_cache"})
```
Used by `restart.py` in `shutil.copytree(..., ignore=shutil.ignore_patterns(*COPY_SKIP))` and `_snapshot_workspace()` (`if name in COPY_SKIP: continue`).

### Measured Copy Behavior (100 KiB = 102,400 B payload placed in each dir, 1 attempt)

| Directory | In `COPY_SKIP`? | Source bytes | Copied to `attempt_1/w` | Copied to `attempt_1/snap-*` | Amplification (3 attempts) |
|---|---:|---:|---:|---:|---:|
| `.git` | Yes | 102,400 B | 0 B | 0 B | 0x |
| `node_modules` | Yes | 102,400 B | 0 B | 0 B | 0x |
| `.venv` | Yes | 102,400 B | 0 B | 0 B | 0x |
| `target` | **No** | 102,400 B | **102,400 B** | **102,400 B** | **6x** (2x per attempt) |

### Proposals (Left Unchanged Here Because Altering `COPY_SKIP` Changes Agent Workspace Visibility)

1. **Rust `target/` (currently copied 2x per attempt — 6x over 3 attempts)**:
   - On any real Rust repository, `target/` is commonly 200 MiB–2 GiB. Copying it into every attempt workspace and every snapshot causes multi-gigabyte disk spikes, slows down each attempt's copy + SHA-256 snapshotting (eating into `budget_s`), and immediately triggers the 16 MiB `restart_work` cap.
   - **Proposal**: Add `"target"` to `COPY_SKIP` (or skip `"target"` only when `Cargo.toml` is present at project root), **paired with** setting `CARGO_TARGET_DIR` to an external per-run or shared build-cache dir so `cargo test` does not have to recompile all dependencies from scratch on every attempt. Keep an opt-out flag if a user intentionally commits a directory named `target/`.
2. **JS/TS `node_modules` (already skipped by `COPY_SKIP`)**:
   - Skipping `node_modules` prevents massive disk bloat (often 100–500 MiB and tens of thousands of tiny files).
   - **Trade-off / W1 interaction**: Because `node_modules` is omitted from `attempt_k/w` and acceptance `work`, JS/TS projects whose `npm test` runs local binaries (`node_modules/.bin/jest`, `vitest`, `mocha`, `tsc`) will fail in the isolated workspace unless dependencies are globally installed or resolved outside the workspace.
   - **Proposal**: Keep `node_modules` in `COPY_SKIP` (do **not** copy it), and in a follow-up task expose `project/node_modules` read-only to the workspace/acceptance runner (e.g., via `NODE_PATH` + prepending `project/node_modules/.bin` to `PATH`, or a read-only bind mount where available) so `npm test` works without duplicating `node_modules` or letting the agent mutate the host `node_modules`.
3. **Additional build/cache directories** (`venv`, `.tox`, `.mypy_cache`, `.ruff_cache`, `.next`, `dist`, `build`):
   - Same trade-off as `target/`: skipping saves significant copy/hash time and disk, but can change what an agent or `--check` command sees. Propose making extra skip patterns configurable (e.g., `.vacantignore` or CLI `--copy-skip`) while keeping the default `COPY_SKIP` minimal and documented.
