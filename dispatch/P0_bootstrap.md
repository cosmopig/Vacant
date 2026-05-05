# P0 — Bootstrap

## Goal

Bootstrap the Vacant Python repo so all subsequent component work has a working CI, package skeleton, shared base types, and zero ambiguity for downstream sessions.

## Read first (in order)

1. `/CLAUDE.md` — full
2. `architecture/ARCHITECTURE.md` — top-level navigation
3. `architecture/THEORY_V5.md` §1–§3 — to ground the core type model

## Repo state at start

- `architecture/` populated
- `CLAUDE.md`, `README.md`, `.gitignore` present
- `dispatch/` populated (this file lives there)
- No `src/`, no `tests/`, no `pyproject.toml`

## Scope

### 1. Project metadata

`pyproject.toml` managed by **uv** (Python 3.12). Declared deps:

- runtime: `pydantic>=2.5`, `pynacl`, `cryptography`, `httpx`, `fastapi`, `sqlmodel`, `aiosqlite`, `alembic`, `structlog`, `anthropic`
- dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `hypothesis`, `ruff`, `mypy`
- demo: `streamlit`, `pandas`, `plotly`

Run `uv lock` and commit `uv.lock`.

`ruff.toml` (or `[tool.ruff]` in pyproject) configured for line-length 100, target-version py312, all default lints + `S` (security), `B` (bugbear), `UP` (pyupgrade), `RUF`.

`mypy.ini` (or `[tool.mypy]`) configured `--strict`, `disallow_any_generics`, `warn_return_any`.

### 2. Package skeleton

Create empty modules per the layout in `CLAUDE.md`:

```
src/vacant/
  __init__.py
  core/        types.py constants.py crypto.py errors.py
  identity/    __init__.py errors.py
  runtime/     __init__.py errors.py
  reputation/  __init__.py errors.py
  registry/    __init__.py errors.py
  composite/   __init__.py errors.py
  protocol/    __init__.py errors.py
  substrate/   __init__.py base.py errors.py
  mvp/         __init__.py
```

Each `errors.py` defines a base `XxxError(Exception)` for that module.

### 3. Core types — `src/vacant/core/types.py`

All Pydantic v2 `BaseModel` (frozen where appropriate). Full strict typing.

- `VacantId(BaseModel)` — wraps Ed25519 public key bytes; `.hex()`, `.short()`, `__str__`. `__eq__` and `__hash__` over the bytes.
- `LogEntry(BaseModel)` — `kind: str`, `ts: datetime`, `payload: dict[str, Any]`, `prev_hash: bytes`, `signature: bytes`. Method `verify(pubkey)` and `compute_hash()`.
- `Logbook(BaseModel)` — `entries: list[LogEntry]`. Methods: `append(kind, payload, signing_key) -> LogEntry`, `verify_chain(pubkey) -> bool`, `latest_hash() -> bytes`.
- `SubstrateSpec(BaseModel)` — `allowed_substrates: list[str]`, `policy: dict[str, Any]`.
- `BehaviorBundle(BaseModel)` — `system_prompt: str`, `policy_dsl: str`, `tool_whitelist: list[str]`, `bundle_hash: bytes` (computed).
- `CapabilityCard(BaseModel)` — `vacant_id: VacantId`, `capability_text: str`, `substrate_spec: SubstrateSpec`, `halo_version: int`, `signature: bytes`. Method `verify() -> bool`.
- `VacantState(StrEnum)` — `ACTIVE`, `LOCAL`, `HIBERNATING`, `STALE`, `SUNK`, `ARCHIVED`. (Note: `LOCAL` is the visibility=none state that runs but isn't published — see CLAUDE.md.)
- `ResidentForm(BaseModel)` — `identity: VacantId`, `logbook: Logbook`, `behavior_bundle: BehaviorBundle`, `substrate_spec: SubstrateSpec`, `runtime_state: VacantState`, `capability_card: CapabilityCard | None`. Method `verify_self() -> bool`.

### 4. Constants — `src/vacant/core/constants.py`

Threshold values cited from `THEORY_V5.md`:

```python
HEARTBEAT_INTERVAL_S: int = ...  # §3.x
HIBERNATING_AFTER_S: int = ...   # §3.x
STALE_AFTER_DAYS: int = 180      # §4.1
SUNK_AFTER_DAYS: int = ...       # §3.x
ARCHIVED_AFTER_DAYS: int = ...   # §3.x
STYLO_DRIFT_THRESHOLD: float = 3.5  # T1: Mahalanobis
DEFAULT_HALO_VERSION: int = 1
```

Each constant has an inline comment with spec section. Read `THEORY_V5.md` for actual values; if a value is not in the spec, raise it as a question in the PR rather than guessing.

### 5. Crypto — `src/vacant/core/crypto.py`

Module functions (pure, no module-level state):

- `keygen() -> tuple[SigningKey, VerifyKey]`
- `sign(key: SigningKey, msg: bytes) -> bytes`
- `verify(pubkey: VerifyKey, msg: bytes, sig: bytes) -> bool`
- `hash_blake2b(data: bytes) -> bytes` (32-byte digest)
- `hex_encode(b: bytes) -> str`, `hex_decode(s: str) -> bytes`

All async-safe. No global RNG state.

### 6. Tests

- `tests/conftest.py` — fixtures: `test_keypair`, `fresh_logbook`, `tmp_db_path`.
- `tests/unit/test_core_crypto.py` — keygen, sign/verify roundtrip, hash determinism.
- `tests/unit/test_core_types.py` — every type's invariants (signature verify, hash chain).
- `tests/property/test_logbook_chain.py` — hypothesis: random-bytes payloads round-trip; tampering any entry fails `verify_chain`.

Coverage target on `src/vacant/core/`: ≥90%.

### 7. CI — `.github/workflows/ci.yml`

```yaml
name: CI
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-extras
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src/
      - run: uv run pytest --cov=vacant --cov-fail-under=90
```

### 8. Pre-commit — `.pre-commit-config.yaml`

ruff + ruff-format + mypy hooks.

### 9. `vacant` CLI scaffolding — `src/vacant/cli.py`

A console_script entrypoint registered in `pyproject.toml` as `vacant = "vacant.cli:main"`.

For P0, only stub the command tree so subsequent components can fill in:

```
vacant init <name>           # P2 will implement: create keypair + seed logbook
vacant status                # P1 will implement: show state of local vacants
vacant heartbeat             # P1
vacant call <vid> <cap>      # P6
vacant publish               # P4: flip LOCAL → ACTIVE
vacant lineage <vid>         # P4: print parent chain
vacant demo <scenario>       # P7
```

For now, each command prints `"Not yet implemented (Px)"` and exits 0. The CLI itself is wired up via `argparse` or `typer` (pick one and stick with it across components).

Acceptance: `uv run vacant --help` prints the command tree.

### 10. README update

Update `README.md` Quick start section to be accurate after this PR.

## Acceptance

- `uv sync` succeeds on a fresh clone.
- `uv run pytest` shows all tests passing with ≥90% coverage on `src/vacant/core/`.
- `uv run ruff check .` clean, `uv run mypy src/` clean.
- CI workflow file is syntactically valid (lint with `actionlint` if available).
- A second cloud Claude session reading just `CLAUDE.md` + your code can extend `vacant.core` types without surprises.

## Output

One PR titled **"P0: bootstrap repo + core types"**.

PR description must list every public type/function added with a one-line contract for each.

## Out of scope (do not touch)

- `runtime/ identity/ reputation/ registry/ composite/ protocol/ mvp/` beyond empty `__init__.py` + `errors.py` stubs
- Real LLM integrations
- Database schema (P4 owns that)
- Anything in `architecture/` (it's the spec — read it, don't edit it unless an ADR demands)
