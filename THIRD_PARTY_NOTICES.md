# Third-party notices

Vacant is licensed under the [MIT License](LICENSE). It depends on
the following third-party packages at runtime, in development, or
under the `[demo]` extras. Each package is the property of its
respective copyright holders and is governed by its own license; this
file collects attributions and license tags so a downstream consumer
can satisfy their notice obligations without re-running the licence
scanner.

The authoritative version-pinned list of every transitive dependency
lives in [`uv.lock`](uv.lock). This file summarises it and calls out
the licenses that require active attribution (notably **MPL-2.0**).

## How this file is generated

```bash
uv sync --all-extras
uv run --with pip-licenses pip-licenses --format=markdown --order=license
```

If you bump a dependency, regenerate the table below and the
**MPL-2.0 attribution** block. If a *new license family* shows up
(e.g. anything copyleft beyond MPL), open an ADR in
`architecture/decisions/` describing the impact before merging.

## Direct dependencies (`pyproject.toml`)

Runtime (`[project] dependencies`):

| Package | License | Use |
|---|---|---|
| `pydantic` | MIT | Core types, validation. |
| `pynacl` | Apache-2.0 | Ed25519 crypto. |
| `cryptography` | Apache-2.0 OR BSD-3-Clause | Adjacent crypto (Fernet for `FileVault`). |
| `httpx` | BSD-3-Clause | Client + transport for A2A / substrates. |
| `fastapi` | MIT | `vacant serve` HTTP surface. |
| `sqlmodel` | MIT | Registry storage. |
| `aiosqlite` | MIT | Async SQLite driver. |
| `alembic` | MIT | DB migrations. |
| `structlog` | MIT OR Apache-2.0 | JSON-formatted logging. |
| `anthropic` | MIT | `AnthropicSubstrate`. |
| `typer` | MIT | `vacant` CLI. |
| `python-dotenv` | BSD-3-Clause | `.env` auto-load for substrates. |
| `mcp` | MIT | MCP server transport. |
| `uvicorn` | BSD-3-Clause | ASGI server for `vacant serve`. |
| `greenlet` | MIT AND PSF-2.0 | SQLAlchemy async on macOS arm64. |

Dev (`[project.optional-dependencies] dev`):

| Package | License | Use |
|---|---|---|
| `pytest` | MIT | Test runner. |
| `pytest-asyncio` | Apache-2.0 | asyncio support for pytest. |
| `pytest-cov` | MIT | Coverage. |
| `hypothesis` | **MPL-2.0** | Property-based tests. *See attribution below.* |
| `ruff` | MIT | Lint + format. |
| `mypy` | MIT | Type check. |
| `pre-commit` | MIT | Local hooks. |
| `pip-audit` | Apache-2.0 | CVE scan. |
| `bandit` | Apache-2.0 | SAST. |
| `twine` | Apache-2.0 | Package publish. |

Demo + docs (`[project.optional-dependencies] demo`):

| Package | License | Use |
|---|---|---|
| `streamlit` | Apache-2.0 | Demo dashboard. |
| `pandas` | BSD-3-Clause | Dashboard data wrangling. |
| `plotly` | MIT | Dashboard charts. |
| `mkdocs` | BSD-2-Clause | Docs site generator. |
| `mkdocs-material` | MIT | Docs theme. |
| `mkdocstrings[python]` | ISC | Auto-rendered API reference. |

## Transitive dependencies — license-family summary

Computed from a fully-installed `uv sync --all-extras` venv. Counts
include direct dependencies in addition to transitive ones.

| License | Count |
|---|---|
| MIT (in any spelling) | 67 |
| Apache-2.0 (in any spelling) | 24 |
| BSD-3-Clause | 11 |
| BSD-2-Clause / "BSD License" (unspecified) | 8 |
| **MPL-2.0** | 3 |
| PSF-2.0 / Python Software Foundation | 2 |
| ISC | 1 |
| MIT-CMU | 1 |
| Other dual-licensed (e.g. `BSD AND 0BSD AND CC0`) | a few — see `uv.lock` |

No GPL / AGPL / LGPL / SSPL / commercial-restrictive licenses appear
anywhere in the transitive tree as of the lock file at this commit.

## MPL-2.0 attribution

Three packages in the dependency tree are distributed under the
**Mozilla Public License 2.0** ([full text](https://www.mozilla.org/MPL/2.0/)).
MPL-2.0 is *file-level* copyleft: modifications to the MPL-2.0-licensed
*files themselves* must be released under MPL-2.0, but linking or
combining with code under a different license (such as MIT, the
license of Vacant) is explicitly permitted by §3.3.

We do not modify these packages — Vacant uses them as installed via
`uv` from PyPI. The notices below acknowledge upstream authorship.

### `certifi`

- **License:** MPL 2.0
- **Author / maintainer:** Kenneth Reitz
- **Project:** <https://github.com/certifi/python-certifi>
- **Vacant uses it via:** transitive dep of `httpx` / `requests`. We
  ship a Mozilla-curated CA bundle.
- **License file:** distributed inside the wheel; reproduced at
  <https://github.com/certifi/python-certifi/blob/master/LICENSE>.

### `hypothesis`

- **License:** MPL 2.0
- **Authors:** David R. MacIver and Zac Hatfield-Dodds
  (`david@drmaciver.com`)
- **Project:** <https://hypothesis.works>
- **Vacant uses it via:** dev dep — property-based tests live under
  `tests/property/`. Hypothesis is not a runtime requirement.
- **License file:** <https://github.com/HypothesisWorks/hypothesis/blob/master/LICENSE.txt>.

### `pathspec`

- **License:** MPL 2.0
- **Author:** Caleb P. Burns (`cpburnz@gmail.com`)
- **Project:** <https://python-path-specification.readthedocs.io/>
- **Vacant uses it via:** transitive dep of `pip-audit` / `bandit` /
  `mkdocs` (gitignore-style pattern matching).
- **License file:** <https://github.com/cpburnz/python-pathspec/blob/master/LICENSE>.

If you ship Vacant as part of a downstream distribution, you must
preserve these attributions and either include the unmodified MPL-2.0
licensed files (PyPI wheels already do this) or arrange for users to
obtain them. See MPL-2.0 §3 for the full obligations.

## Other notable license families

- **PSF-2.0** (Python Software Foundation License) covers
  `typing_extensions` and `defusedxml`. Compatible with MIT.
- **ISC** (`shellingham`, `mkdocstrings`) — MIT-equivalent permissive.
- **Dual-licensed packages** (e.g. `cryptography` Apache-2.0 OR BSD-3,
  `structlog` MIT OR Apache-2.0) — Vacant accepts under whichever side
  is convenient; both are permissive.
- `numpy` is composite (`BSD-3-Clause AND 0BSD AND MIT AND Zlib AND
  CC0-1.0`); all five are permissive and impose no copyleft
  obligation.

## Reporting an attribution gap

If you find a dependency whose license obligations are not satisfied
by this file (missing notice, missing source link, an upstream
re-license that requires action) please open a security advisory or
file a public issue with the **Defense gap** template — handling is
maintainer-reviewed per
[`GOVERNANCE.md`](GOVERNANCE.md). License gaps are treated as
release-blocking.
