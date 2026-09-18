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

No experiment code and no runtime behaviour. The acceptance sandbox, the chain format,
the gauge, the arbiter and every recorded run are byte-for-byte what they were.
