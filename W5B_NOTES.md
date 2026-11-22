# W5(b) Notes: Normalized Audit Record Schema (`vacant-audit-record/1`) & `vacant audit`

## Deliverables

- Schema specification: [`docs/AUDIT_RECORD_V1.md`](docs/AUDIT_RECORD_V1.md) (`vacant-audit-record/1`)
- Exporter & CLI implementation: [`vacant_network/audit_export.py`](vacant_network/audit_export.py)
- Top-level CLI wiring: [`vacant_network/cli.py`](vacant_network/cli.py)
- Synthetic test suite (0 model calls): [`tests/test_audit_export.py`](tests/test_audit_export.py)

## Design Summary

### 1. Unified Read-Only Normalization Across All Five Sources

No existing writer was modified. `vacant_network/audit_export.py` reads all five on-disk sources read-only and normalizes each into a `vacant-audit-record/1` JSON object:

| `kind` | Source | Verification |
|---|---|---|
| `trace` | `$VACANT_HOME/trace/projects/*/chain.ndjson` (+ sealed volumes, `head.json`, `state.json`, `delivery.json`) | Raw torn-line/malformed-entry check + `Recorder.verify(trust, anchor)` cross-checked against any intake ledger `trace_head`/`trace_broken` anchor |
| `intake_ledger` | `$VACANT_HOME/intake/ledger/*.ndjson` | Raw torn-line/malformed-entry check + `Ledger.verify(trust)` against `$VACANT_HOME/intake/trust.json` |
| `vrun` | `<vrun_root>/*/receipts_*.ndjson` (+ `.pub.json`, `rows.jsonl`, `run_*.json`, `possess.json`, `NOT_CERTIFIED.json`) | Raw torn-line/malformed-entry check + `verify_receipts.verify_chain_detailed` & `Logbook.verify_chain` + `rows.jsonl`/`verdict_hash`/`attestation_sha256` reconciliation (or `unsigned` when `infra_void`/`RUN-OFF`/`NOT_CERTIFIED`) |
| `restart` | `work_root()/restart-*/result.json` | Unsigned (`signature.verified = null`, `status = "unsigned"`, `unsigned_source` gap) |
| `possess_wire` | `$VACANT_POSSESS_HOME/proxyd/wire/index.jsonl` (when present) | Unsigned (`signature.verified = null`, `status = "unsigned"`, `unsigned_source` & `unattributed_source` gaps) |

### 2. Three-State / Unknown Discipline

- Missing or unmeasured data is strictly `null` (`None`), `"unknown"`, `"unchecked"`, or `"unreadable"` — never `0`, `false`, or `""`.
- Booleans are explicitly rejected in integer count helpers (`isinstance(v, bool)` check).
- Corrupt, edited, truncated, missing-pubkey, or untrusted chains are **never dropped**: they are emitted with `signature.verified = false`, a concrete `signature.reason`, and a `chain_truncated`, `signature_failed`, or `chain_unverifiable` entry in `gaps`.
- In particular, raw NDJSON inspection catches mid-line torn tails and malformed JSON lines in `trace` chains before calling `Recorder.verify()` (which otherwise treats torn tail bytes as a warning note and skips malformed lines in `_book()`).

### 3. CLI & Backwards Compatibility

- Command: `vacant audit list | show <record_id> | export --jsonl` (consistent with `vacant trace` and `vacant usage`).
- Filters: `--agent`, `--project`, `--since` (ISO-8601 date/datetime, relative duration like `24h`/`7d`, or unix epoch s/ms), `--kind`, `--result`, plus path overrides (`--vacant-home`, `--work-root`, `--vrun-dir`, `--possess-home`).
- Legacy compatibility: `vacant [--root DIR] audit <name>` continues to dispatch to `cmd_audit` unchanged (`tests/test_cli_audit_honesty.py` passes as-is).

### 4. Wording & Accountability Boundaries

- All docs, CLI help, and output footers state that signed records are **tamper-evident** and **re-verifiable** offline, and **never claim they are complete**.
- No banned terms (`信任`, `trust layer`, `trusted layer`, `信任層`) appear in CLI help or docs.
- Unanchored chains explicitly report `signature.anchor_checked = false` and an `unanchored_chain` info gap (clean tail truncation cannot be detected without an external anchor).
- `vrun` ephemeral-key chains explicitly report `scheme = "ed25519_ephemeral_chain"` and an `ephemeral_signer` info gap (post-write tamper-evidence, not signer identity).

## Verification

Ran with `TMPDIR=$HOME/dev/ops/tmp_test PYTHONPATH=$PWD ~/dev/Vacant/.venv/bin/python -m pytest ... -q -p no:cacheprovider`:

- `tests/test_audit_export.py`
- `tests/test_cli_audit_honesty.py`
- `tests/test_cli_top_help.py`
- `tests/test_cleanroom_blockers.py`
- `tests/test_cli_run_help_shows_both_modes.py`
