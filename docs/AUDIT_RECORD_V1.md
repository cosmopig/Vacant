# AUDIT_RECORD_V1 — Normalized Audit Record Schema (`vacant-audit-record/1`)

> Machine- and human-facing specification for cross-project audit records exported by
> `vacant audit list|show|export` (`vacant_network/audit_export.py`).
>
> **Accountability boundary (read first):**
> Signed records are **tamper-evident** and **re-verifiable** offline against their signing
> key (and against external anchors when present). They are **never guaranteed to be complete**:
>
> - Unsigned sources (legacy/fallback `restart` runs with only `result.json`, `possess_wire`,
>   or `vrun` runs with no receipt chain) provide no cryptographic integrity guarantee.
> - A signed hash chain without an external anchor (such as `head.json` or a receiver-held
>   ledger head) detects edits and interior deletions, **not** clean truncation from the tail
>   (Ma & Tsudik 2009: integrity != completeness).
> - Activity that bypassed Vacant (direct agent execution without hooks/controller, deleted
>   files, or runs stored outside scanned directories) is absent from this export.
> - Do not describe these records as complete or tamper-proof; use **accountability** rather
  than trust.

---

## 1. Purpose

Vacant writes accountability evidence in five separate on-disk formats without changing any
existing writer:

| `kind` | Source on disk | Writer module(s) | Signature mechanism |
|---|---|---|---|
| `trace` | `$VACANT_HOME/trace/projects/<key>/chain.ndjson` (+ sealed volumes `chain-NNNNNN.ndjson[.gz]`, `state.json`, `head.json`, `delivery.json`) | `vacant_network/trace/recorder.py`, `zerostop.py`, `stopcheck.py` | Ed25519 hash chain verified against `$VACANT_HOME/intake/trust.json` (`verifier` role), `head.json`, and any intake ledger `trace_head`/`trace_broken` anchor |
| `intake_ledger` | `$VACANT_HOME/intake/ledger/<task_id>.ndjson` | `vacant_network/intake/ledger.py`, `flow.py`, `adapters/run.py` | Ed25519 hash chain verified against `$VACANT_HOME/intake/trust.json` (`verifier` role) |
| `vrun` | `<vrun_root>/<run_id>/receipts_<ARM>.ndjson` (+ `.pub.json`, `rows.jsonl`, `run_<ARM>.json`, `possess.json`, `NOT_CERTIFIED.json`) | `vacant_network/vrun/launcher.py`, `receipts.py`, `attest.py`, `gateshim.py` | Per-run ephemeral Ed25519 hash chain verified via `verify_receipts` against sibling `.pub.json`, `rows.jsonl`, `verdict_hash`, and `attestation_sha256` (or unsigned when `infra_void` / `RUN-OFF` / `NOT_CERTIFIED`) |
| `restart` | Signed `restart_receipt` entries in `$VACANT_HOME/trace/projects/<key>/chain.ndjson` joined by `run_id` with `$VACANT_WORK/restart-*/result.json` (fallback to unsigned `result.json` only for legacy runs or missing chains) | `vacant_network/adapters/restart.py` | Ed25519 hash chain verified against `$VACANT_HOME/intake/trust.json` (`verifier` role), `head.json`, and companion `result.json["receipt"]` anchor (or `none` when falling back to unsigned `result.json`) |
| `possess_wire` | `$VACANT_POSSESS_HOME/proxyd/wire/index.jsonl` (default `$VACANT_HOME/possess/proxyd/wire/index.jsonl`) | `vacant_network/vrun/wireproxy.py`, `possess.py` | None (unsigned JSONL file) |

`vacant-audit-record/1` normalizes all five into one versioned JSON object per record (exported
one record per line in JSONL) so humans, scripts, and agents can answer six questions uniformly:

1. **Which agent** (`agent`, `agents`)
2. **Which task** (`task`)
3. **How many attempts** (`attempts`)
4. **Acceptance result** (`acceptance`)
5. **What was sent back** (`sent_back`)
6. **Which accountability gaps exist** (`gaps`, `signature`)

---

## 2. Three-State / Unknown Discipline

**Missing or unmeasured data is NEVER filled with `0`, `false`, `""`, or `[]`.**

| Value | Meaning |
|---|---|
| `null` | **Unknown / not recorded / not measured / not applicable** for this source (or source was unreadable). |
| `0` / `false` / `[]` | **Explicitly observed** zero, false, or empty result from a readable source that actually tracks that dimension. |
| `"unknown"` | Parsed source whose acceptance status field is missing or unrecognized. |
| `"unchecked"` | Source explicitly ran without an executable acceptance check (e.g., restart `no_tests`, vrun `ungated`, trace with no review/consequence, or wire-only proxy log). |
| `"unreadable"` | Source file exists on disk but could not be parsed (corrupt JSON, invalid encoding, I/O error). Unreadable sources are **never silently dropped**. |

Type strictness: Python `bool` is a subclass of `int`, so integer count fields explicitly reject
booleans (`true`/`false` in a count field is treated as invalid/unknown, never as `1`/`0`).

### 2.1 Non-UTF-8 Filesystem Paths

POSIX filesystems allow arbitrary non-UTF-8 byte sequences in filenames (which Python surfaces via
`surrogateescape` code points `U+DC80..U+DCFF`). Raw surrogates cannot be serialized into strict
UTF-8 JSON or Ed25519 canonical bytes (`canonical_bytes()`).

To guarantee that signed receipts, `result.json`, CLI summaries, and `vacant audit` exports never
crash or silently drop a run when a non-UTF-8 filename exists:

- Valid UTF-8 path strings are emitted unchanged.
- Any path string containing surrogateescape code points is converted deterministically by encoding
  back to raw OS bytes with `os.fsencode(p)` and decoding as UTF-8 with `errors="backslashreplace"`
  (e.g. raw byte `0xff` becomes the four-character sequence `\xff`).
- The same representation is applied consistently across `result.json`, the signed
  `restart_receipt` payload, CLI summaries, and `vacant audit` exports so companion reconciliation
  agrees without false mismatches.
- When any path in a restart run required backslashreplace escaping, both `result.json` and the
  signed `restart_receipt` set `"non_utf8_paths": true` and
  `"path_encoding": "utf-8-backslashreplace"` (propagated to `details` in `vacant-audit-record/1`).
- Snapshot tree hashes (`snapshot_tree_sha256`) continue to hash the raw OS filename bytes
  (`os.fsencode(rel)`), which is byte-identical to UTF-8 encoding for all valid UTF-8 paths.

---

## 3. Top-Level Record Schema (`vacant-audit-record/1`)

Every JSONL line is one JSON object with the exact top-level keys below.

| Field | Type | Nullable? | Description |
|---|---|---|---|
| `schema` | `string` | No | Constant `"vacant-audit-record/1"`. |
| `record_id` | `string` | No | Stable deterministic identifier for this record (`trace:<project_key>`, `intake_ledger:<task_id>`, `vrun:<run_name>:<arm>`, `restart:<run_name>`, `possess_wire:proxyd`). |
| `kind` | `string` | No | One of `"trace"`, `"intake_ledger"`, `"vrun"`, `"restart"`, `"possess_wire"`. |
| `source` | `object` | No | On-disk provenance (`path`, `kind`, `auxiliary_paths`). |
| `timestamp_ms` | `integer \| null` | Yes | Canonical epoch-millisecond timestamp for sorting and `--since` filtering (`ended_at_ms` if known, else `started_at_ms`, else parsed run-dir timestamp for `restart`, else `null`). |
| `started_at_ms` | `integer \| null` | Yes | Earliest recorded timestamp in the source (epoch ms), or `null` if unknown. |
| `ended_at_ms` | `integer \| null` | Yes | Latest recorded timestamp in the source (epoch ms), or `null` if unknown. |
| `project` | `string \| null` | Yes | Workspace / project directory path when recorded by the source; `null` if unknown. |
| `project_key` | `string \| null` | Yes | 16-hex trace project key (when source is `trace` or linked to a trace project); `null` otherwise. |
| `agent` | `string \| null` | Yes | Agent/platform label (`"pi"`, `"claude"`, `"codex"`, `"opencode"`, `"hermes"`, or comma-joined sorted list if multiple agents acted in one project chain); `null` if not recorded. |
| `agents` | `list[string] \| null` | Yes | Sorted deduplicated list of observed agents/platforms; `null` if none recorded (never `[]` for unknown). |
| `task` | `string \| null` | Yes | Task identifier (`task_id`) when recorded; `null` if the source has no task identifier. |
| `attempts` | `object` | No | Attempt counts (`count`, `max`, `delivered`). See §3.2. |
| `acceptance` | `object` | No | Normalized acceptance verdict (`result`, `raw_status`, `passed`, `kind`, `checks_passed`, `checks_total`). See §3.3. |
| `sent_back` | `object` | No | What Vacant sent back or refused (`count`, `items`). See §3.4. |
| `gaps` | `list[object]` | No | List of observed accountability gaps (`code`, `severity`, `detail`, `count`). Empty list `[]` means no gaps detected by this reader (never means "complete"). See §3.5 and §5. |
| `signature` | `object` | No | Cryptographic verification result (`verified`, `status`, `scheme`, `reason`, `signer`, `entries_checked`, `chain_head`, `anchor_checked`). See §3.6. |
| `details` | `object` | No | Source-specific normalized supplemental fields (always a JSON object; never overwrites core fields). |

### 3.1 `source`

| Field | Type | Description |
|---|---|---|
| `path` | `string` | Absolute path to the primary source file (`chain.ndjson`, `<task_id>.ndjson`, `receipts_<ARM>.ndjson` or `run_<ARM>.json`, `result.json`, `index.jsonl`). |
| `kind` | `string` | Same as top-level `kind`. |
| `auxiliary_paths` | `list[string]` | Related companion files consulted (e.g. `head.json`, `state.json`, `receipts_<ARM>.pub.json`, `rows.jsonl`, `run_<ARM>.json`, `possess.json`, `NOT_CERTIFIED.json`, sealed volume files). |

### 3.2 `attempts`

| Field | Type | Nullable? | Description |
|---|---|---|---|
| `count` | `integer \| null` | Yes | Number of attempts / check rounds observed. `null` when the source does not track attempts or is unreadable. |
| `max` | `integer \| null` | Yes | Configured maximum attempts budget when recorded; `null` if not recorded. |
| `delivered` | `integer \| null` | Yes | 1-based index of the delivered attempt when recorded (e.g. `restart.delivered_attempt`, or `vrun.attempts_used` when accepted); `null` otherwise. |

### 3.3 `acceptance`

| Field | Type | Nullable? | Description |
|---|---|---|---|
| `result` | `string` | No | Closed normalized enum: `"accepted"`, `"released"`, `"rejected"`, `"held"`, `"escalated"`, `"void"`, `"unchecked"`, `"open"`, `"withdrawn"`, `"release_unconfirmed"`, `"unreadable"`, `"unknown"`. |
| `raw_status` | `string \| null` | Yes | Source-native verdict/status string (e.g. `visible_pass`, `attempts_exhausted`, `no_tests`, `allow`, `continue`, `accept`, `reject`), or `null`. |
| `passed` | `boolean \| null` | Yes | Strictly three-state: `true` for `accepted`/`released`, `false` for `rejected`, `null` for everything else (`held`, `escalated`, `void`, `unchecked`, `open`, `withdrawn`, `release_unconfirmed`, `unreadable`, `unknown`). |
| `kind` | `string \| null` | Yes | Acceptance mechanism identifier (e.g. `"contract"`, `"python_unittest"`, `"python_pytest"`, `"python_bare"`, `"check"`, `"npm"`, `"cargo"`, `"go"`, `"vrun_suite"`, `"zero_config_evidence"`, `"zero_config_block"`), or `null`. |
| `checks_passed` | `integer \| null` | Yes | Count of passing tests/claims when numerically measured; `null` for exit-code-only checks or when unmeasured. |
| `checks_total` | `integer \| null` | Yes | Total count of tests/claims when numerically measured; `null` when unmeasured. |

### 3.4 `sent_back`

Captures what Vacant sent back to the agent (review pushbacks, nudges, retry feedback) or refused
back to the submitter (rejected/held/escalated decisions, release refusals, vrun gate refusals).

| Field | Type | Nullable? | Description |
|---|---|---|---|
| `count` | `integer \| null` | Yes | Count of send-back/refusal items. `null` when the source does not observe send-backs (`possess_wire`) or is unreadable. `0` only when a readable source tracks send-backs and observed none (or `restart`, which by policy sends no feedback between attempts). |
| `items` | `list[object] \| null` | Yes | List of send-back items, or `null` when `count` is `null`. |

Each item in `sent_back.items`:

| Field | Type | Nullable? | Description |
|---|---|---|---|
| `round` | `integer \| null` | Yes | 1-based attempt/review round if known, else `null`. |
| `action` | `string` | No | `"continue"`, `"nudge"`, `"retry_feedback"`, `"reject"`, `"hold"`, `"escalate"`, `"release_refused"`, `"refuse"`. |
| `channel` | `string \| null` | Yes | `"hook_review"`, `"prompt_feedback"`, `"file_feedback"`, `"file_and_prompt"`, `"intake_decision"`, `"release_gate"`, `"vrun_gate"`, or `null`. |
| `summary` | `string` | No | Compact human-readable summary of what was sent back or refused. |
| `details` | `list[string]` | No | Specific reasons, finding IDs/kinds, failed claim IDs, or paths (capped for readability). |

### 3.5 `gaps`

Each entry in `gaps` is an object:

| Field | Type | Nullable? | Description |
|---|---|---|---|
| `code` | `string` | No | Stable machine-readable gap code (see §5). |
| `severity` | `string` | No | `"error"` (integrity/verification failure or hard void), `"warning"` (coverage/policy/unsigned gap), or `"info"` (structural boundary such as ephemeral signer or unanchored tail). |
| `detail` | `string` | No | Human-readable explanation naming the specific failure or boundary. |
| `count` | `integer \| null` | Yes | Associated occurrence count when applicable, else `null`. |

### 3.6 `signature`

Every record states whether its source was signature-verified and why.

| Field | Type | Nullable? | Description |
|---|---|---|---|
| `verified` | `boolean \| null` | Yes | `true` = signature chain verified cleanly; `false` = verification failed (edited, truncated, torn tail, broken hash link, bad signature, untrusted signer, missing pubkey, empty/unreadable chain); `null` = source format is unsigned (no signature mechanism exists for this source). |
| `status` | `string` | No | `"verified"`, `"failed"`, `"unverifiable"`, or `"unsigned"`. |
| `scheme` | `string` | No | `"ed25519_trusted_chain"` (`trace`, `intake_ledger`, signed `restart`), `"ed25519_ephemeral_chain"` (`vrun`), or `"none"` (unsigned sources). |
| `reason` | `string` | No | Concrete verification outcome or exact failure reason. |
| `signer` | `string \| null` | Yes | Signer public key hex or `vacant_id` when present, else `null`. |
| `entries_checked` | `integer \| null` | Yes | Number of chain entries parsed/checked, or `null` for unsigned/unreadable chains. |
| `chain_head` | `string \| null` | Yes | Hex hash of the last parsed chain entry, or `null` when unavailable. |
| `anchor_checked` | `boolean \| null` | Yes | `true` if checked against a signed external anchor (e.g. intake ledger `trace_head`) or companion reconciliation (`rows.jsonl` / `verdict_hash` / `result.json["receipt"]`); `false` if only self-contained chain verification ran (tail truncation not detectable); `null` for unsigned sources. |

**Rule on broken/truncated chains:** A truncated, torn, edited, reordered, empty, or untrusted
chain is **never dropped**. It is always emitted with `signature.verified = false`,
`signature.reason` naming the failure, and an explicit `chain_truncated` or `signature_failed`
entry in `gaps`.

---

## 4. Field-by-Source Matrix

| Field | `trace` | `intake_ledger` | `vrun` | `restart` | `possess_wire` |
|---|---|---|---|---|---|
| `project` | `state.json.workspace` or `trace_genesis.workspace` | Parent of `task_opened.contract_path` or `attempt_started.workspace` | `run_<ARM>.json.workspace` or `possess.json.cwd` | `trace_genesis.workspace` (signed receipt), fallback `result.json.project` | `null` (machine-level) |
| `project_key` | Trace directory name (16 hex) | Linked `trace_head.project` if present, else `null` | `null` | Trace project key (16 hex) when backed by chain, else `null` | `null` |
| `agent` / `agents` | Platforms from `step`, `session_seen`, `session_closed`, `review`, `consequence`, `state.json.sessions` | `attempt_started.agent` (fallback: `candidate_frozen.source` prefix) | `possess.json.possess_agent`, `attestation.agent`, `framework_hook.agent`, or `gateshim`/`agentwrap` argv | Signed `restart_receipt.agent` (fallback: `result.json.agent` if present, else `null`) | `null` (proxy cannot attribute per agent) |
| `task` | Linked ledger `task_id` or `consequence.task_id`, else `null` | `task_id` (events or filename stem) | `ws_verdict` / `ws_attempt` / `run_<ARM>.json` `task_id` | `restart_receipt.task_id` / `result.json.task_id` if present, else `null` | `null` |
| `attempts.count` | Count of `review` events (if >= 1), else `null` | Count of `attempt_started` (or `max(candidate_frozen, decisions)` if direct submit); `null` if unreadable | `attempts_used` or count of `ws_attempt`; `null` if unavailable | `len(restart_receipt.attempts)` (fallback: `len(result.json.attempts)`) | `null` |
| `attempts.max` | `null` | `null` | `max_attempts` | `restart_receipt.max_attempts` (fallback: `result.json.max_attempts`) | `null` |
| `attempts.delivered` | `null` | `null` | `attempts_used` when accepted, else `null` | `restart_receipt.delivered_attempt` (fallback: `result.json.delivered_attempt`) | `null` |
| `acceptance.result` | From `consequence.outcome` or last `review` (`allow`+no open -> `accepted`, open/`continue` -> `rejected`), else `unchecked` | `ledger.state_of(events).state` (`accepted`/`released`/`rejected`/`held`/`escalated`/`void`/`open`/`withdrawn`/`release_unconfirmed`/`unreadable`) | From `infra_void` -> `void`, `accepted_is_null`/`ungated` -> `unchecked`, `accepted` -> `accepted`/`rejected` | From signed `restart_receipt.accepted` (fallback: `result.json.accepted`): `true`->`accepted`, `false`->`rejected`, `null`->`unchecked`; missing->`unknown` | `"unchecked"` (`"unreadable"` if unreadable) |
| `acceptance.checks_*` | `null` | Latest `decision.results` PASS / total | `visible_passed` / `visible_total` | Delivered attempt `passed` / `run` from signed receipt (fallback: `result.json`) | `null` |
| `sent_back` | `review(action=continue)`, `nudge`, `prompt(source=vacant_feedback)` | `decision(outcome in reject/hold/escalate)`, `release_refused` | Retry feedback deliveries + gate refusals (`refused=true`) | `count=0, items=[]` (restart policy sends no feedback to agent); `null` if unreadable | `count=null, items=null` |
| `signature.verified` | `true`/`false` (`Recorder.verify` + raw torn-line check + ledger anchor check) | `true`/`false` (`Ledger.verify` + raw torn-line check) | `true`/`false` (`verify_receipts` + raw torn-line + `verdict_hash` + `attestation_sha256`), or `null` if no chain emitted | `true`/`false` (`Recorder.verify` + raw torn-line + companion `result.json["receipt"]` anchor), or `null` (`unsigned`) when falling back to legacy/missing-chain `result.json` | `null` (`unsigned`) |
| `timestamp_ms` | Max `ts_ms` across entries | Max `ts_ms` across entries | Max `ts_ms` across entries (or `attestation.assembled_at`) | Signed `restart_receipt` entry `ts_ms` (fallback: `result.json.timestamp_ms` or parsed `restart-YYYYMMDDTHHMMSS-...` dir name), else `null` | Max `ts * 1000` across valid lines |

---

## 5. Accountability Gap Codes

| Code | Typical Severity | Meaning |
|---|---|---|
| `signature_failed` | `error` | Ed25519 signature, hash link, sequence continuity, volume seal, or signer list verification failed. |
| `chain_truncated` | `error` | Torn/partial trailing line, malformed entry line, `head.json` ahead of chain tail, ledger `trace_head` ahead of chain tail, or `rows.jsonl`/`verdict_hash` missing verdict. |
| `chain_unverifiable` | `error` | Signed chain exists, but verification key/metadata (e.g. `.pub.json`) is missing or unreadable. |
| `unreadable_source` | `error` | Source file could not be read or parsed as valid JSON/JSONL. |
| `unsigned_source` | `warning` | Source format has no cryptographic signature (`restart`, `possess_wire`, or `vrun` without chain). |
| `unanchored_chain` | `info` | Signed chain verified internally, but no external anchor was checked; clean tail truncation cannot be detected. |
| `ephemeral_signer` | `info` | Signed with a per-run ephemeral key (`vrun`); proves post-write tamper-evidence, not signer identity. |
| `unrecorded_change` | `warning` | Trace recorded workspace modifications outside any observed tool step. |
| `scan_disabled` | `warning` | Trace file-change observation was disabled (subsequent writes unattributable until rescan). |
| `post_missing` | `warning` | One or more trace steps missed their post-tool hook event. |
| `pre_missing` | `warning` | One or more trace steps missed their pre-tool hook event. |
| `writes_unknown` | `warning` | One or more trace steps could not observe workspace writes. |
| `open_flags` | `warning` | Unresolved human-flagged findings (`vacant flag`) remain open. |
| `trace_broken` | `error` | Intake ledger recorded that the project's trace stopped verifying. |
| `trace_error` | `warning` | Intake ledger recorded a tracing error. |
| `workspace_escape` | `error` | Agent modified files in the original project outside its isolated workspace. |
| `infra_void` | `error` | Infrastructure failure prevented valid measurement (`infra_void`, timeout, or spawn failure). |
| `release_unconfirmed` | `error` | Release was attempted, but destination readback failed. |
| `contract_unlocked` | `info` | Intake task has no owner-signed `contract_locked` event. |
| `tests_tampered` | `warning` | Restart mode detected edits to protected test files (restored before check, not written back). |
| `skipped_writeback` | `warning` | Restart mode skipped unsafe paths (symlink, conflict, unreadable) during write-back. |
| `result_json_mismatch` | `warning` | Companion unsigned `result.json` disagreed with the signed `restart_receipt` in `chain.ndjson`; the signed receipt was preferred and discrepancies are listed in `details.mismatches`. |
| `unchecked` | `warning` / `info` | No executable acceptance check ran (`no_tests`, `no_tests_collected`, `runner_unavailable`, `ungated`, or wire-only log). |
| `unmediated` | `error` | `vrun` receipt recorded `requests_seen == 0` (model channel mediation not observed). |
| `unattested` | `warning` | `vrun` attestation tier is below `"A"` (`B`, `B'`, `C`, or `NOT_CERTIFIED.json`). |
| `unexplained_calls` | `warning` | `vrun` reconciliation found relay calls not matched to a turn-opening hook event. |
| `wire_not_quiesced` | `warning` | `vrun` proxy timed out draining in-flight calls; `requests_seen` is a lower bound. |
| `wire_blocked` | `warning` | Wire proxy blocked call(s) to an unspecified upstream sink. |
| `wire_refused_path` | `warning` | Wire proxy refused non-model API path(s). |
| `unattributed_source` | `info` | Source format does not record agent, project, and/or task identity. |
| `malformed_entries` | `warning` | One or more lines in an unsigned JSONL log could not be parsed. |
| `missing_fields` | `warning` | Expected fields were absent or wrong type in the source payload. |

---

## 6. CLI Interface (`vacant audit`)

Consistent with `vacant trace` and `vacant usage`:

```bash
# List normalized records across all projects and sources
vacant audit list [--agent NAME] [--project PATH_OR_SUBSTR] [--since SPEC] \
                  [--kind KIND] [--result RESULT] [--limit N] [--json | --jsonl]

# Show full normalized details for one record (exact or unique prefix of record_id)
vacant audit show <record_id> [--json]

# Export normalized records as JSONL (stdout or --out FILE)
vacant audit export --jsonl [--agent NAME] [--project PATH_OR_SUBSTR] [--since SPEC] \
                    [--kind KIND] [--result RESULT] [--out FILE]
```

Filter semantics:
- `--agent`: case-insensitive match against `agent` or `agents` entries (exact match or `<agent>:*` prefix). Records with `agent: null` do not match.
- `--project`: case-insensitive substring match against `project` or exact/prefix match against `project_key`. Records with both `null` do not match.
- `--since`: accepts ISO-8601 date (`2026-11-01`), ISO-8601 datetime (`2026-11-01T12:00:00Z`), relative duration (`24h`, `7d`, `30m`, `60s`), or Unix epoch seconds/ms. Keeps records with `timestamp_ms >= since_ms`; records with `timestamp_ms: null` do not match.
- `--kind`: repeatable or comma-separated subset of `trace,intake_ledger,vrun,restart,possess_wire`.
- `--result`: repeatable or comma-separated subset of `acceptance.result` values.

Optional path overrides (useful for inspecting archived directories or custom homes):
- `--vacant-home DIR` (default: `$VACANT_HOME` or `~/.vacant`)
- `--work-root DIR` (default: `$VACANT_WORK` or `<vacant_home>-work`)
- `--vrun-dir DIR` (repeatable; default: `$VACANT_RUN_DIR` or `<vacant_home>-run`)
- `--possess-home DIR` (default: `$VACANT_POSSESS_HOME` or `<vacant_home>/possess`)

Legacy single-body verification (`vacant [--root DIR] audit <name>`) remains unchanged when
the argument is not one of `list`, `show`, `export`, or a flag.

---

## 7. Honest Boundaries

1. **Read-only:** `vacant audit` never modifies chains, ledgers, keys, `trust.json`, or workspaces.
2. **Tamper-evident and re-verifiable, not complete:** Verification checks every recorded entry
   against its signing key and available anchors. It cannot prove that no separate run happened
   outside Vacant or that an unanchored chain was never truncated from its tail.
3. **Same-account key boundary:** When signing keys live in plaintext under the same OS account
   as the agent, a hostile process in that account can read them. Stronger separation requires
   moving the receiver and signing keys to another OS account or machine.
4. **Deduplication boundary:**
   - **Restart mode (joined):** A `vacant do` restart run writes a signed `restart_receipt`
     into the project's trace chain (`chain.ndjson`) and a companion `result.json` under
     `$VACANT_WORK/restart-*`. These are joined by `run_id` (falling back to `(project_key,
     seq, hash)` for older receipts without `run_id`) into **one** `restart:<run_id>` record
     whose fields come from the signed receipt (including `agent`, `argv`, `acceptance`,
     `attempts`, `delivered_attempt`, `snapshot_hashes`, and `written_back` in `details`).
     Restart-only trace chains (containing only `trace_genesis` + `restart_receipt` entries)
     do not emit a duplicate empty `trace:<project_key>` record. If `result.json` disagrees
     with the signed receipt, the signed receipt is preferred and `result_json_mismatch` is
     flagged. Unsigned `result.json` is used as a fallback only for legacy runs (before
     receipts existed) or when the referenced trace chain is missing, in which case the record
     remains `unsigned` with an `unsigned_source` gap.
   - **Contract mode (distinct records):** A single `vacant do` run with a task contract writes
     both an `intake_ledger` record and a `trace` chain; both are exported as distinct records
     linked by `task` and `project_key` so each source's verification status remains
     independently visible.
