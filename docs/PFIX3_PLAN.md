# Pfix3 — Codex round-3 review response

**Date opened:** 2026-05-08
**Trigger:** Codex round-3 review identified 8 substantive issues despite green CI, mypy, ruff, bandit, pip-audit, full test suite (854 passed, 90.80% coverage). Issues span deployment correctness, responsibility-chain integrity, and external-facing claims.
**Scope:** Implementation repo (`cosmopig/Vacant`). Thesis-side documentation untouched unless an issue claim mismatches THEORY V5.
**Strategy:** Land issues batch-by-batch. Each batch ends with `ruff check` + `ruff format --check` + `mypy src` + `pytest` (incl. `-m slow`) + a single conventional commit. No batch starts until the previous one is green.

This document is **the source of truth for what we decided and why** — not the commit messages.

---

## Issue inventory

### #1 — Alembic migration cannot reach `head`

- **Cited:** `alembic/versions/0001_initial_p4_tables.py:29`, `alembic/versions/0002_event_actor_seq_unique.py:33`
- **Finding:** `0001` uses `SQLModel.metadata.create_all()` (not the alembic way) which already creates the `uq_event_actor_seq` unique constraint via the model definition. `0002` then tries to add the same constraint via `op.create_unique_constraint()`. SQLite rejects: `No support for ALTER of constraints in SQLite dialect`. So `alembic upgrade head` fails on a fresh SQLite database.
- **Decision:**
  - Rewrite `0001` to use explicit `op.create_table(...)` calls for every model in `vacant/registry/models.py`. Generate the schema by reading the SQLModel metadata once, snapshotted into the migration file. The migration becomes a fixed schema artifact, not a live `metadata.create_all()` redirect.
  - Rewrite `0002` to use `with op.batch_alter_table("event") as batch_op: batch_op.create_unique_constraint(...)` so the SQLite recreate path is taken.
- **Verification:** Add a fast CI step (or a `tests/migration/test_alembic_upgrade_head.py`) that runs `alembic upgrade head` against an in-memory SQLite and asserts it returns non-zero only on real failure.

### #2 — A2A response validation incomplete

- **Cited:** `src/vacant/protocol/dispatch.py:197`–`198`
- **Finding:** After `from_a2a_jsonrpc(wrapped)` returns a `VacantEnvelope`, only `verify_or_raise(target_card.vacant_id.verify_key())` is called. Three things missing:
  1. `response_env.from_vacant_id == target_card.vacant_id` — caller-side: response really comes from the vacant we called.
  2. `response_env.to_vacant_id == requester.identity` — caller-side: response is addressed to us.
  3. Caller-side response replay store — duplicate response envelopes (same `(actor, seq)` or same `envelope_id`) must be rejected.
- **Decision:**
  - Add the two identity checks unconditionally before `return DispatchResult(...)`. Failure raises `EnvelopeFormatError` (mismatched routing) or a new `ResponseSpoofingError` if we want a tighter taxonomy. Pick `EnvelopeFormatError` — it already exists and the meaning fits.
  - Add an optional `caller_replay_store: ReplayStore | None = None` parameter to `call_local()` (default `None` keeps existing unit tests green). When provided, the response envelope is checked against it before return; on success the seq is recorded.
  - The CLI passes a file-backed replay store keyed by `(target_vid)`.
- **Trade-off:** Default-`None` rather than mandatory because lots of unit tests pass synthetic transports. CLI/server paths inject the real store.

### #3 — CLI second call to same target replayed-out

- **Cited:** `src/vacant/cli/commands.py:519` (call site of `call_local`)
- **Finding:** `call_local()` defaults `sequence_no=1` and `prev_envelope_hash=EMPTY_PREV_HASH`. The CLI never reads or writes per-pair chain state. Server-side replay store advances after first call → second CLI call to same target is rejected as replay. This is a smoke-test-passes-once-then-fails footgun.
- **Decision:**
  - Add a single sidecar file `~/.vacant/<name>/envelope_state.json` (codex's suggestion — one file per local vacant, keyed by target). Schema:
    ```json
    {
      "<target_vid_hex>": {
        "request": {"last_seq": 1, "last_envelope_id_hex": "..."},
        "response": {"last_seq": 1, "last_envelope_id_hex": "..."}
      }
    }
    ```
  - `call_cmd` flow: load → derive next request seq + prev hash → call → on success, update both `request` and `response` blocks → atomic write (`tempfile + os.replace`).
  - Encapsulate as `cli/local_store.py::load_envelope_state(name)` / `save_envelope_state(name, state)`.
  - The same file backs the caller-side response replay store from #2 — single source of truth.
- **Trade-off vs. per-pair files:** Single file is simpler, and CLI calls aren't concurrent in practice. If the user later needs concurrency we move to SQLite; the JSON shape above maps trivially.

### #4 — MCP `vacant_call_with_sampling` bypasses responsibility chain

- **Cited:** `src/vacant/cli/mcp_server.py:131`
- **Finding:** Tool accepts `user_prompt: str` + `caller_vacant_id_hex: str` directly. No signed envelope. No envelope verification. No logbook append. No response signing. README claims "the vacant signs the resulting logbook entry" — code does not.
- **Decision:** Take the **fallback path** (not the `BehaviorHandler` ctx-injection refactor we considered).
  - Tool signature changes to: `vacant_call_with_sampling(envelope: dict[str, Any], model_hint: str = "client-default", max_tokens: int = 256)`.
  - Server flow per call:
    1. Parse + verify the inbound envelope under the *caller's* pubkey (extracted from `envelope.from`). Replay-check via the existing `replay_store`.
    2. Treat the envelope's payload text as the user prompt. Run sampling via `ctx.session.create_message()`.
    3. Wrap the inference through `ClientInheritedSubstrate` so the substrate identity becomes `client-inherited:<caller_vid>:<model_hint>`.
    4. Append a signed `INFERENCE_EVENT` (kind: `"INFERENCE_EVENT"`) to the vacant's logbook with payload `{ "caller": <hex>, "substrate": "...", "model_id": "...", "prompt_hash": "...", "response_hash": "...", "proof": "..." }`. Also emit a `SUBSTRATE_BORROWED` companion event so external auditors can index borrows independently.
    5. Build a *signed response envelope* and return it as the tool result (mirrors `vacant_call`'s return shape).
  - `caller_vacant_id_hex` parameter is **removed** — caller identity comes from the verified envelope, not from a self-declared string.
- **Why fallback, not the clean refactor:** Folding sampling into the regular `vacant_call` path requires `BehaviorHandler` to take a per-call `Context`. Doable but reaches into many tests and into the HTTP path which never had a ctx. The fallback gets the responsibility-chain claim honest with a much smaller blast radius.
- **README impact:** §"For non-MCP deployments" wording stands; no change beyond #5.
- **Test impact:** `tests/integration/test_mcp_external_client.py` needs to construct + sign an envelope before calling the tool. Update the fixture, not the assertion.

### #5 — README HTTP `/mcp` claim wrong

- **Cited:** `README.md:183`
- **Finding:** README tells users to point Claude Desktop at `http://localhost:8443/mcp`. Implementation only spawns a stdio MCP thread. No `/mcp` route on the FastAPI app.
- **Decision:** Fix the README. Do **not** add an HTTP `/mcp` route — sampling callbacks over HTTP would mean implementing the streamable-http MCP transport and that's out of scope.
  - Replace the `http://localhost:8443/mcp` paragraph with a stdio config example (`command/args` mcp.json snippet pointing at `vacant mcp` or `vacant serve --mcp`).
  - Cross-reference the existing plugin manifest section at `README.md:99-104` as the recommended path for Claude Desktop users.
  - Also update `README.zh-TW.md` to match.

### #6 — `publish_halo` republish doesn't update the card

- **Cited:** `src/vacant/registry/halo.py:60-168` and `src/vacant/registry/store.py::submit_register_event_atomic`
- **Finding:** When `existing is not None`, `publish_halo()` builds `vacant_to_insert = None` and only passes `new_visibility` to `submit_register_event_atomic`. The audit event captures the new `card_hash`, but the registry row keeps the old `capability_card_hash/sig/blob`, old `declared_capabilities_json`, old `version`, old `base_model`. Lookups serve stale cards while the audit chain claims fresh.
- **Decision:** Allow republish; overwrite all card-derived fields. Reject only on identity-violating changes.
  - Extend `submit_register_event_atomic` with `vacant_field_updates: Mapping[str, Any] | None = None`. When non-`None` and `vacant_id_to_update` is set, the in-transaction update path applies these fields onto the existing row.
  - `publish_halo` and `publish_halo_signed` populate `vacant_field_updates` from the *new* card on the existing-vacant branch. Fields written: `capability_card_hash`, `capability_card_sig`, `capability_card_blob`, `declared_capabilities_json`, `base_model`, `base_model_family`, `owner_org`, `version`, `visibility`.
  - Three invariants enforced (raise `RegistryWriteError` on violation, before submitting the event):
    1. **`parent_id` is immutable.** If the new card carries a different `parent_id`, reject. Identity custody.
    2. **`halo_version` monotonic.** New `card.halo_version` must be ≥ existing. Prevents accidental replay of an older signed card.
    3. **Public key match.** `card.vacant_id.pubkey_bytes == existing.public_key`. Theoretically tautological since `vacant_id` is derived from the pubkey, but cheap defense in depth.
- **Why no `--republish` flag:** The audit chain already records the change as a new `register` event with new `card_hash` and a new `actor_seq`. That is the explicit history. Adding a flag is API surface without a security gain.

### #7 — `record_review` not atomic; audit silent-skip

- **Cited:** `src/vacant/reputation/aggregator.py:248` (audit append) vs `:271` (rate-limit check)
- **Finding (a):** Audit append runs before rate-limit check. If rate-limit fires, the reviewer's logbook has a `REVIEW_EVENT` but no posterior change. Logbook diverges from observable reputation state.
- **Finding (b):** Lines 246–248 say the audit step is mandatory only on mutation; line 248 silently skips the append when audit isn't registered. README says "record_review first appends signed REVIEW_EVENT". Code disagrees.
- **Decision:**
  - **Reorder under one lock.** New sequence inside a single `async with self._lock:`:
    1. Validate (reviewer/target/source/dim/range).
    2. Rate-limit check + tentative timestamp append.
    3. Signed `REVIEW_EVENT` append. On failure, pop the timestamp.
    4. Posterior update.
  - **Fail-closed audit on mutation.** If `_audit_enabled_for(reviewer)` is `False` and we're in `record_review` (mutation), raise a new `MisconfiguredAuditError`. Read paths (`get_reputation`, `score`, `get_ranked`) keep tolerating missing registration.
  - Update test fixtures that relied on silent-skip to call `register_audit(reviewer, logbook=lb, signing_key=sk)` first. Initial grep: 7 test files reference `record_review`. If updates exceed ~10 fixture sites, pause and raise.
- **Note on README claim alignment:** Once these land, the README's "record_review first appends signed REVIEW_EVENT" is technically accurate again, modulo "first" being ambiguous. The aggregator docstring will spell out the new ordering.

### #8 — Version + typed metadata + plugin manifest drift

- **Cited:** `pyproject.toml:11` (0.3.0) vs `src/vacant/__init__.py:3` (0.2.0). `pyproject.toml:29` declares `Typing :: Typed` but no `src/vacant/py.typed` marker. Codex also flagged `.claude-plugin/plugin.json` (v0.1.0) and `.github/workflows/publish.yml:42`'s `getattr(vacant, '__version__', '0.2.0')` fallback.
- **Decision:**
  - `src/vacant/__init__.py`: `__version__ = "0.3.0"`.
  - Create empty file `src/vacant/py.typed`.
  - `.claude-plugin/plugin.json`: bump `version` to `0.3.0`. Verify `manifest-validation.yml` still passes.
  - `.github/workflows/publish.yml:42`: drop the `'0.2.0'` fallback. If `__version__` is missing on a published wheel, that's a bug worth surfacing — do `getattr(vacant, '__version__')` or `vacant.__version__` and let it AttributeError.

---

## Execution batches

Order is risk-ascending and dependency-respecting.

| Batch | Issues | Touches | Risk |
|---|---|---|---|
| **B1** Metadata sync | #8 | `__init__.py`, `py.typed`, `plugin.json`, `publish.yml` | None — verifiable by string match |
| **B2** README correction | #5 | `README.md`, `README.zh-TW.md` | None — non-code |
| **B3** Alembic | #1 | `alembic/versions/0001`, `0002`, optional `tests/migration/` | Low — verify with fresh sqlite |
| **B4** Reputation atomicity | #7 | `aggregator.py`, ~7 test files | Medium — test fixture surgery |
| **B5** Halo republish | #6 | `halo.py`, `store.py`, new tests | Medium — new invariants |
| **B6** Response validation + CLI chain state | #2, #3 | `dispatch.py`, `commands.py`, `local_store.py`, integration tests | Medium-high — paired change |
| **B7** MCP sampling responsibility chain | #4 | `mcp_server.py`, `client_inherited.py` (maybe), `tests/integration/test_mcp_external_client.py` | Highest — surgery near "嫁接到客戶端" claim |

Each batch:

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest                # full + slow
git commit                   # conventional commit, single batch
```

If `pytest` regressions exceed the per-batch budget noted above, stop and document instead of pushing through.

---

## Decisions deferred to user, now resolved

| Question | Resolution |
|---|---|
| Batch 5: silent overwrite + invariants vs. explicit `--republish` flag? | **Silent overwrite + 3 invariants** (parent_id immutable, halo_version monotonic, pubkey match). Audit chain is the explicit history. |
| Batch 4: fail-closed audit on missing registration? | **Yes, fail-closed on mutation.** Read paths still tolerant. Up to ~10 fixture updates accepted; over that, pause. |
| Batch 7: refactor `BehaviorHandler` to take `ctx`, vs. keep `vacant_call_with_sampling` and put envelope verification + INFERENCE_EVENT logbook inside it? | **Fallback path: keep the separate tool but make it require a signed envelope, append `INFERENCE_EVENT` + `SUBSTRATE_BORROWED` events, and return a signed response envelope.** Don't refactor `BehaviorHandler`. |

---

## Out of scope for Pfix3

These are real concerns but distinct from the codex round-3 list:

- True HTTP/SSE/streamable MCP route at `/mcp` (would let README `http://localhost:8443/mcp` claim be re-instated). Defer.
- Behavior-side ctx injection so sampling can ride the standard `vacant_call` envelope path. Defer; revisit if/when a second sampling-shaped tool is added.
- Reputation: `audit_enabled_for` symmetry on read paths (currently tolerant, will stay tolerant).
- THEORY V5 has no claim that conflicts with the fallback path chosen for #4 — INFERENCE_EVENT + SUBSTRATE_BORROWED in the logbook is consistent with §responsibility chain wording.

---

## Outcome (closed 2026-05-08)

All seven batches landed.

| Batch | Commit | Tests |
|---|---|---|
| docs | `cb16170` | — |
| B1 metadata | `1346741` | 854 (no test changes) |
| B2 README | `c4b2cd0` | 854 (no code changes) |
| B3 alembic | `1bc106b` | +1 → 855 |
| B4 reputation | `71b99b9` | +3 → 858 |
| B5 halo republish | `bfb0410` | +3 → 861 |
| B6 dispatch + CLI | `5c9c2d8` | +6 → 867 |
| B7 MCP sampling | `da8eca9` | 867 (rewrote 1 integration test, contract change) |

**Final state:** 867 tests pass (52 slow); ruff + ruff format + mypy strict on `src/` all green.

**Carry-over decisions to remember:**

- The aggregator's "audit-aware mode" latch is one-way. Once any reviewer registers, every subsequent `record_review` requires audit registration. If a future caller wants to opt back out, they must construct a fresh aggregator. (Marked `ONE-WAY LATCH` in the source after F4.)
- Halo republish `parent_id` immutability uses **None-as-preserve** semantics (after F2 follow-up): a caller passing `parent_id=None` (or omitting the field) on republish leaves the existing column untouched; a caller passing a *different non-None* parent_id is rejected. To genuinely unset a parent, callers need an explicit revoke flow (out of scope).
- CLI `envelope_state.json` lives alongside the keypair; deleting it forces seq=1 / EMPTY on the next call, which the server will reject as replay until the server's replay store also forgets the pair. Document this as part of the "rotate identity" workflow if/when that ships.
- The fallback path for #4 means `vacant_call_with_sampling` and `vacant_call` share envelope semantics but diverge in one place: sampling's response carries `substrate` + `model_id` + `proof` *alongside* the signed `message`. Clients that consume the sampling tool need to read both keys.

---

## Self-review fixes (F1–F4 + follow-ups, 2026-05-08)

After Pfix3 landed, a PR-style self-review surfaced four risks that
hadn't broken tests but were either smells or latent footguns. Two
also turned out to have residual bugs at adjacent layers, caught on
re-review and fixed.

| Fix | Commit | What |
|---|---|---|
| F1 | `5d6f193` | `InMemoryReplayStore.seed()` public method; CLI no longer pokes `_state` |
| F2 (core) | `5d6f193` | `publish_halo[_signed]` kwargs use `None` defaults; partial-update on republish |
| F2 (rpc) | `f43dbee` | `HaloPublishRequest` schema also uses `None` defaults so HTTP path is consistent |
| F2 (parent_id) | `210d10d` | `parent_id` invariant treats `None` as "preserve" (was firing on legitimate omit-on-republish) |
| F2 (cli) | `4e97515` | `vacant publish` typer flags use `None` defaults + omit from JSON when unset |
| F3 + F4 | `5d6f193` | Drop dead `lb is not None` guard in MCP sampling tool; strengthen audit-mode latch docstring |
| Test coverage | `f72f454` | `seed()` unit tests; HTTP republish-preserves; parent_id-preserves |

**Final test count:** 872 passed (52 slow). All ruff / format / mypy strict checks green.
