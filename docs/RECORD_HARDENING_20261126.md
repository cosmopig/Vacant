# Accountable Trace Record Hardening (2026-11-26)

This note documents four product-layer hardening changes to the accountable trace record
(`vacant_network/trace/`, `vacant_network/retention.py`, `vacant_network/intake/keys.py`,
`vacant_network/adapters/`, `vacant_network/statusboard.py`, `vacant_network/cli.py`),
addressing findings from the independent D2 audit.

---

## 1. Model-call counts and token usage in the signed chain (`model_usage`)

### What changed
- Added `"model_usage"` to `vacant_network/trace/recorder.py` (`EVENT_TYPES`).
- Added best-effort, non-blocking usage extraction in `vacant_network/trace/capture.py`:
  - `usage_from_transcript(agent, data)` for Claude Code JSONL transcripts (deduplicating
    streaming chunks sharing the same `message.id`, extracting `input_tokens`, `output_tokens`,
    `cache_read_input_tokens`, `cache_creation_input_tokens`, and claimed `model` IDs), Codex
    rollout JSONL (`turn_context` + `event_msg/token_count` with duplicate-snapshot dedup, and
    `codex exec --json` `turn.completed`), and pi JSONL transcripts.
  - `usage_from_payload(agent, payload)` for native hook payloads (`model_usage`, `usage`,
    pi `turn_end` `message.usage`, and fallback `turn`-only counts marked `complete=False`).
  - `record_model_usage(...)` called on `stop`, `turn_end`, `subagent_stop`, and `session_end`
    (recorded before `session_closed` so `session_closed` remains the session's tail event).
    Transcript reading on `Stop` is capped at `MAX_USAGE_STOP_BYTES` (16 MiB) and all errors
    are fail-open so hooks never block or break.
  - Every `model_usage` event records `source`, `observed_by="agent_claim"`, `complete`
    (`True`/`False`), `calls`, `input_tokens`, `output_tokens`, optional cache/total tokens,
    `models_claimed`, and `note` when incomplete.
- Updated `PI_EXTENSION` and `OPENCODE_PLUGIN` in `vacant_network/adapters/agents.py` to
  accumulate `turn_end` / assistant-message usage in memory (O(1), zero extra RPCs) and attach
  `model_usage` to `stop` and `session_end` hook payloads.
- Updated `vacant_network/adapters/hook.py` (`pi` `turn_end`) and `vacant_network/trace/cli.py`
  (`vacant trace show` and `--session` filtering) to recognize `model_usage`.

### Tests
- `tests/test_record_hardening_usage.py`: recorded fixtures for Claude Code (`Stop`/`SessionEnd`,
  streaming `message.id` dedup, partial/malformed transcripts, oversized-Stop guard), Codex
  (rollout `token_count` dedup + `turn.completed`), pi (`turn_end`/`stop`/`session_end`,
  turn-only fallback, and live Node execution of `PI_EXTENSION`), and OpenCode.

### What is still not possible
- **Self-reported, not wire-observed**: counts and model IDs come from agent transcripts or
  extension callbacks (`observed_by="agent_claim"`). An agent or modified client can misreport
  token counts or model IDs, or drop/bypass hooks. Independent model-call counting requires a
  separate network/proxy boundary (e.g. `vacant possess` / `vrun` enclosure).
- **Incomplete sources**: OpenCode 2.x plugin events do not uniformly expose per-call token
  usage across all versions; Codex hooks without a rollout `transcript_path` or `token_count`
  events cannot provide token totals and are honestly marked `complete=False` (or omitted when
  no usage data exists at all).

---

## 2. Retention/GC preserves chain-referenced objects + missing-object verification

### What changed
- Added exhaustive reference collection in `vacant_network/retention.py`:
  - `collect_project_blob_refs(pdir, blobs)` and `referenced_trace_blobs(root)` walk all chain
    volumes (`chain-*.ndjson[.gz]` + `chain.ndjson`), `state.json`, and un-ingested `egress.jsonl`,
    collecting `input_blob`, `output_blob`, `reads[*].blob`, `writes[*].{before,after}`,
    `changes[*].{before,after}`, `prompt` `text_blob`, `transcript` `sha256`/`blob`/`transcript_blob`,
    `source_snapshot` `pages`, `source_fetch` `sha256`, `source_check` refs, `coverage`
    `baseline.index` and `rescanned.index`, `session_closed` `final_index`, `checkpoint_restore`
    `target_index`, spilled `payload_blob`/`writes_blob`/`reads_blob`/`changes_blob` (unpacked
    recursively), all index files + delta `base` indexes, and file blobs referenced inside indexes.
- Hardened `compact_trace()`, `gc_all()`, `auto_gc()`, and `vacant gc` so **no chain-referenced
  object is ever deleted by default**:
  - By default (`allow_breaking_chain_references=False`, including `auto_gc`, `gc_all`, `vacant gc`,
    and even when `VACANT_TRACE_BUDGET_BYTES` / `--target-bytes`, `--keep-steps`, or `--aggressive`
    is set), **every** object referenced by any chain event (directly or through an index file the
    chain references) is treated as hard-keep and never deleted.
  - Under budget pressure, default GC may only evict truly unreferenced orphan objects. If the
    budget still cannot be met because referenced objects exceed `target_bytes`, GC does not delete
    them; instead it reports `budget_unmet: true`, `referenced_bytes_held`, and a clear human note.
- Added explicit destructive opt-in with signed chain accountability:
  - `vacant gc --allow-breaking-chain-references` (`allow_breaking_chain_references=True` in
    `compact_trace()` / `gc_all()`; forbidden with `--auto`, exiting `2`).
  - Before deleting any referenced object under this opt-in, GC appends a signed `"objects_evicted"`
    event (`EVENT_TYPES` in `vacant_network/trace/recorder.py`, chunked at 400 sha256s per event to
    stay inline) to every affected project chain listing every evicted sha256. Signing failure
    (e.g. `MixedSignerRefused`) is fail-closed and blocks deletion of that project's objects.
  - Even under `--allow-breaking-chain-references`, structural objects (indices, delta bases,
    `source_snapshot` `pages`, `source_fetch` `sha256`, `source_check`, `egress.jsonl`, and spilled
    structure blobs) remain protected as hard floor under `--target-bytes`.
- Added referenced-object verification distinguishing **evicted by explicit GC** vs **missing**:
  - `retention.verify_trace_objects(root, *, project_dir=None, objects_root=None, verify_hashes=False)`
  - `Recorder.verify_objects(verify_hashes=False)`
  - `vacant trace verify --objects` (and `--verify-hashes`, `--json`) and `vacant gc --verify-objects`:
    - Unexplained absent objects are reported under `missing` (`ok=False`, exit `1`).
    - Tampered objects (`--verify-hashes`) are reported under `corrupt` (`ok=False`, exit `1`).
    - Objects accounted for by a signed `"objects_evicted"` chain event are reported separately under
      `evicted` with `status: "evicted by explicit GC"` and `evicted_at_seq` (`OBJECTS PARTIAL`
      when `evicted_count > 0` and `missing_count == 0`, never silently merged into `missing` or
      falsely reported as `OBJECTS OK`).

### Tests
- `tests/test_record_hardening_gc.py`:
  - Default GC over >55 steps + `source_snapshot` + `source_fetch` + `prompt` + `transcript` +
    `egress.jsonl` + `rescan` + unreferenced orphans (deletes only orphans, keeps all referenced objects).
  - Referenced objects (including `input_blob`, `output_blob`, `prompt`, `transcript`, and
    index-referenced file blobs) survive tight `target_bytes` / `VACANT_TRACE_BUDGET_BYTES` /
    `auto_gc` / `--keep-steps` / `--aggressive`, reporting `budget_unmet: true` and
    `referenced_bytes_held` with a clear CLI note; `--auto --allow-breaking-chain-references` is refused.
  - Explicit `--allow-breaking-chain-references` dry-run writes nothing, real run appends signed
    `objects_evicted` events verifiable offline, fail-closed blocks deletion if signing fails, and
    `vacant trace verify --objects` / `vacant gc --verify-objects` cleanly distinguish
    `evicted by explicit GC` vs unexplained `missing` vs `--verify-hashes` `corrupt`.

### What is still not possible
- **Unbounded growth when chains keep growing**: because default GC refuses to delete
  chain-referenced objects, `trace/objects/` can exceed `VACANT_TRACE_BUDGET_BYTES` (64 MiB
  default) on long-lived workspaces; Vacant reports `budget_unmet: true` with `referenced_bytes_held`
  and leaves space reclamation to an explicit operator decision (`--allow-breaking-chain-references`,
  archiving old projects, or raising `VACANT_TRACE_BUDGET_BYTES`).
- **Store-on-change initial `before` versions**: unmodified workspace files are not copied into
  `objects/` by `workspace.scan(store=False)`; if such a file is later modified outside Vacant
  or overwritten for the first time, its original pre-change bytes were never stored and are
  reported separately under `unmaterializable_index_entries` (defined `UNKNOWN`).
- **Already-deleted objects**: this fix prevents future GC deletion of referenced objects and
  detects missing ones; it cannot recover objects deleted before this change.

---

## 3. Configurable signing key path, permission checks, and same-user warnings

### Default location
- By default, the Ed25519 trace signing key (`verifier` role) is stored at:
  `$VACANT_HOME/intake/keys/verifier/identity.key` (mode `0600`, directory `0700`).
  Because `$VACANT_HOME` is owned by the same OS user that runs the agent, the agent process
  can read this key directly.

### What changed
- Added configurable signing key resolution in `vacant_network/intake/keys.py` (precedence):
  1. `VACANT_SIGNING_KEY_PATH` env var (for `verifier`: file path or directory containing `identity.key`)
  2. `VACANT_KEYS_DIR` env var (all roles: `<dir>/<role>/identity.key`)
  3. `$VACANT_HOME/intake/config.json` (`{"signing_key_path": "...", "keys_dir": "..."}`)
  4. Default: `$VACANT_HOME/intake/keys/<role>/identity.key`
- New keys created at an external path are written with `0600` file mode and `0700` parent dir
  mode, and registered in `trust.json` so `vacant trace verify` works seamlessly.
- Added read-only `keys.signing_key_posture(role="verifier", workspace=...)` checking key
  location (inside `VACANT_HOME` / workspace), file and directory permissions (`0600`/`0700`),
  and whether the key is readable by the current OS user (`os.access(..., os.R_OK)`).
- Surfaced warnings in:
  - `vacant trace verify` (human `WARNING:` lines and `--json` `signing_key` object)
  - `vacant dashboard` (`statusboard.install_status()["signing_key"]`, strictly read-only)
- Extended `vacant_network/adapters/hookpolicy.py` `_protected()` so the hook's string-level
  guard also refuses tool reads/writes to configured external key paths.

### Tests
- `tests/test_record_hardening_keys.py`: default key posture warnings in `vacant trace verify`
  and `statusboard`, strict read-only behavior, `VACANT_SIGNING_KEY_PATH` outside `VACANT_HOME`
  and workspace (mode 0600/0700, hook deny, still warns about same-user readability),
  `VACANT_KEYS_DIR`, `intake/config.json`, overly broad permission warnings (`0644`/`0755`),
  and workspace-key warning.

### What is still not possible
- **Separate-account signing helper is not implemented**: moving the key outside `VACANT_HOME`
  and the workspace prevents accidental inclusion in workspace backups/copies and stops naive
  `VACANT_HOME` scans, **but if the agent and the signing hook run under the same OS user**,
  the agent can still read the private key file directly (and bypass/remove hooks). True key
  isolation requires running a dedicated signing daemon/helper under a separate OS account (e.g.,
  a Unix socket or setuid/sudo helper whose private key is unreadable by the agent's UID) or a
  hardware/KMS signer. Until that is implemented, `signing_key_posture()` reports `isolated=False`
  and emits an explicit warning whenever the current OS user can read the key.

---

## 4. External chain-head anchoring (`vacant trace anchor`)

### What changed
- Added `vacant_network/trace/anchor.py` and CLI command `vacant trace anchor` (registered in
  `vacant_network/trace/cli.py` and `vacant_network/cli.py`):
  - `vacant trace anchor [--output FILE] [--file EXTRA ...] [--git REPO_DIR] [--json]`:
    verifies the current project's chain (fail-closed on empty/broken chains) and writes a
    `vacant-trace-anchor/1` JSON containing `project_key`, `workspace`, `chain_length`,
    `last_seq`, `head_hash`, `genesis_hash`, `signer`, `timestamp`, `ts_ms`, `chain_sha256`,
    `sealed_volumes`, and optional `extra_files` sha256 + byte sizes. With `--git <repo>`,
    stages and commits only the anchor file inside that local git repository (`shell=False`,
    never pushes).
  - `vacant trace anchor --check <file> [--check-files] [--json]`:
    verifies the current chain still passes cryptographic verification, matches `project_key`,
    `signer`, and `genesis_hash`, and extends the anchored head (`current_seq >= anchor_seq`
    with exact `head_hash` match at `anchor_seq`). Optional `--check-files` also fails if any
    recorded extra file's sha256 changed.

### Tests
- `tests/test_record_hardening_anchor.py`: writing anchor JSON + extra file hashes, committing
  to a local `--git` repo without sweeping unrelated files, verifying extension after appending
  new steps, detecting truncation (even with forged `head.json`), detecting rewritten/forked
  tails re-signed with the same key, `--check-files` mismatch detection, wrong-project rejection,
  and fail-closed refusal on empty/broken chains.

### What is still not possible
- **No automatic remote push / external transparency log**: `--git` only creates a local commit.
  If the same attacker controls both the machine and the local anchor git repo, they can rewrite
  both. Real external immutability requires pushing the anchor repo to an independent remote
  (protected branch / separate credentials) or submitting the anchor hash to an external
  timestamping / transparency service.
- **No pre-anchor omission proof**: anchoring proves the chain has not been truncated, forked,
  or replaced *since* the anchor was written; it cannot detect actions that happened outside
  hooks before anchoring or between two anchors.
