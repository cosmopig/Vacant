# Changelog

## 0.7.0 — 2026-09-18

**Breaking: this is not an upgrade of 0.6.0, it is a different codebase.**
Anything that imported `vacant.core`, `vacant.protocol`, `vacant.runtime`, `vacant.mvp`,
`vacant.client` or `vacant.composite` will not work. Those modules are gone. Pin `0.6.0`
if you depend on them.

### Packaging

- Distribution renamed to **`vacant-network`** on PyPI. The import name is still `vacant`.
  (`vacant` on PyPI belongs to an unrelated DNS tool by another author; the repository's
  own `pyproject.toml` previously declared that name and could never have been published.)
- Runtime dependencies cut from a declared `fastapi` / `anthropic` / `streamlit` /
  `sqlmodel` / `alembic` set — 63 packages on a clean install — to the three that are
  actually imported: `cryptography`, `mcp`, `jsonschema`. A clean install is now 30 packages.
- `jsonschema` promoted from "used if present" to a declared dependency. The previous
  fallback (`vacant/checks.py::_mini_validate`) is **looser** than the real validator, so
  the same `json_schema` check could return different verdicts on two machines. A system
  whose claim is that verdicts can be recomputed cannot have its criterion drift with the
  environment.
- `requires-python`, classifiers, `project.urls`, SPDX license metadata and a
  `py3-none-any` wheel + sdist that pass `twine check`.
- Version has a single source of truth: `vacant.__version__`, read by setuptools.

### Fixed — two defects that only bit at call time

- `vacant/peerexec.py::sandbox_probe` and `vacant/suitegauge.py::default_runner` imported
  `ops.gain.gain_run` inside the function body. `ops/` is not part of the distribution, so
  importing `vacant` succeeded and **calling** these raised a bare
  `ModuleNotFoundError: No module named 'ops'`. They now raise
  `vacant.suitegauge.OpsRunnerUnavailable` with a message that names the two supported
  injection points (`gauge_suite(runner=...)`, `Executor.new(probe=...)`) and the
  `CheckRunner` signature. **The acceptance criterion was not copied into the library** —
  a second copy is exactly the drift both docstrings forbid, and the experiment's sandbox
  import allow-list is not a policy the library should assert on a user's behalf.
- The build no longer warns about `vacant/web`, and the dashboard assets are confirmed
  present in the wheel.

### Fixed — three blockers found by a clean-room verification (2026-09-18)

An external agent was given the wheel and the READMEs only — no source — and ran 0.7.0 on
Ubuntu. Three defects, all of the same shape: **the failure looks exactly like a normal
output.**

- **`vacant bench` reported a comparison it had never measured.** With every model call
  failing (endpoint down), all calls were silently counted as wrong answers and rendered as
  "plain 0%, vacant 0%, +0%", exit 0. That violates the project's own `infra_void` rule
  (09 §3.5; already enforced by `ops/gain/r530/acceptance.py` and by `vacant record check`):
  **a cell that was not measured is not a cell that measured zero.** `bench` now separates
  right / wrong / **not measured**, refuses to print any comparison number when either arm
  has zero measured cells (exit 2, with the endpoint, the per-arm denominators and the first
  error verbatim), and prints the `infra_void` count separately when the failure is partial.
  `Vacant.bench` gained `plain_void` / `vacant_void` / `plain_measured` / `vacant_measured` /
  `paired_measured` / `infra_void` / `first_error`; the three rates are `None`, not `0.0`,
  when their denominator is zero. `SolveResult` gained `ok_calls` / `failed_calls` /
  `first_error` and the `infra_void` / `measured` properties.
- **Our own banned terminology appeared in our own CLI output.** `llms.txt` says "do not
  describe Vacant as a trust layer" and the `AGENTS.md` facts block carries a `never_use`
  list, yet `vacant demo`
  printed 「信任性質」/「信任層淨貢獻」, `vacant init` printed 「信任庫」and `vacant up`
  printed 「信任機制」. Every user-visible string is now accountability-phrased. **Only
  strings changed**: `trust_dir`, `trust_card`, `trust_on`, the `--trust` flag and the
  `trust/` directory name are API surface and are untouched (the path is still spelled
  `trust/` in the output, now glossed as "金鑰與究責紀錄"). The `never_use` list itself was
  incomplete — it listed only the two English phrasings — so 「信任」／「信任層」 were added
  to it, together with the scope (output and prose, never identifiers) and the test that
  now enforces it. The MCP tool docstrings in
  `vacant/mcp_server.py` were deliberately **not** touched — that text enters an agent's
  prompt, so editing it changes behaviour and breaks comparability with existing runs.
- **Three "follow the docs and it breaks" gaps**, one of which disguised itself as a
  refusal: `select_by_quorum`'s `drafts` is `Sequence[tuple[str, str]]` and the order was
  documented nowhere. Passing `(worker_id, code)` is not a type error — every "draft" fails
  the suite, the panel agrees unanimously, and you get `refused=True` with three chains that
  all verify, which is indistinguishable from the mechanism correctly rejecting bad work.
  `select_by_quorum` now applies a cheap **heuristic** shape check and raises
  `peerexec.DraftOrderError`; the heuristic has false negatives and says so, in the
  docstring, in the exception text and in a test that pins one. `SuiteSpec` mappings require
  `"v": 1` and the old message (`bad_version:None`) named neither the field nor its legal
  value; `Executor.attest` requires `task["entry_point"]` and reported
  `entry_point_unbound` even when the `SuiteSpec` passed in did declare one. Both messages
  now say what to fix. `SuiteSpecError` was split into `.code` (machine-readable — this is
  what goes on the chain and into `Selection.refusal_reason`, and it is **byte-for-byte
  unchanged**) and `.hint` (human-readable, `str(exc)` only).

### Documentation

- `README.md` / `README.en.md` / `README.ja.md` rewritten: a short human part
  (one sentence, a 30-second quickstart, current results with their denominators) followed
  by a large machine-facing part.
- New `AGENTS.md` — the integration contract for coding agents: API surface with
  signatures, the four deployment shapes and which of them are actually binding,
  falsifiable invariants, honest boundaries, common mistakes, and a stable
  machine-readable facts block.
- New `llms.txt` following the llmstxt.org convention.
- **The outward positioning was corrected.** Vacant used to be described as a layer that
  wraps an agent. It is not: as a library or an MCP tool it is *voluntary*. The accurate
  description, now the first line of all three READMEs, is a **receiving desk** — a delivery
  without a verifiable receipt is not accepted. Enforcement is at acceptance time, and that
  check cannot be routed around; making Vacant a machine's single exit is the deployment
  layer's job. In reference-monitor terms (Saltzer & Schroeder 1975) it is tamper-proof and
  small enough to verify, and does **not** satisfy complete mediation.
- **Three boundaries that had never been written down are now written down**: the chain gives
  integrity but not completeness (a truncated tail verifies — a truncation/omission attack,
  Ma & Tsudik 2009; `vacant/checkpoint.py:144-155` has the same hole; signing the entry count
  into each entry does not help, because `seq` already is the count); the acceptance gate
  still admitted 14.8% false deliveries in R532; and the reconciliation in
  `ops/gain/replay/verify_run_receipts.py` is same-origin, so it catches bugs and not malice.
- `vacant/__init__.py`'s summary line no longer says "強制信任" (mandatory trust). It said
  two wrong things at once: the project's terminology is *accountability*, not trust, and
  "mandatory" is more optimistic than `vacant/controller.py:7-8`, which states that the
  guarantee covers only the subprocess the controller spawns itself.

### Not changed

No experiment code. The acceptance sandbox, the chain format, the gauge, the arbiter and
every recorded run are byte-for-byte what they were. The clean-room fixes above changed
runtime behaviour in exactly two places, both of them refusals that used to be silent:
`vacant bench` now exits non-zero instead of printing an unmeasured comparison, and
`select_by_quorum` raises on a reversed `drafts` argument. Every wire-facing string
(`refusal_reason`, `SuiteSpecError.code`, attestation payloads) is unchanged.
