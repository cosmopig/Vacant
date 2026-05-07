# Publishing `vacant-network` to PyPI

This project distributes on PyPI as `vacant-network` while keeping `vacant` as the importable Python module name (see `pyproject.toml`'s comment for the rationale). Same shape as `python-dotenv` / `discord.py`.

## What runs automatically

`.github/workflows/publish.yml` fires on **GitHub Release publication**. It:

1. Builds sdist + wheel via `uv build`.
2. Runs `twine check dist/*`.
3. Smoke-installs the wheel into a fresh venv and asserts `vacant --help` + `import vacant` work.
4. Publishes to PyPI via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — no API token in the repo.
5. Attaches the wheel + sdist to the GitHub Release page so users can download without going through PyPI.

`release-please` automatically cuts a GitHub Release per merged release-PR, so the only manual step is the **one-time** PyPI Trusted Publisher setup below.

## One-time setup (maintainer only)

### 1. Reserve `vacant-network` on PyPI

Log into https://pypi.org with the maintainer account, then:

1. Go to https://pypi.org/manage/account/publishing/ → "Add a new pending publisher".
2. Fill in:
   - **PyPI Project Name**: `vacant-network`
   - **Owner**: `cosmopig`
   - **Repository name**: `Vacant`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
3. Save. PyPI will accept the next OIDC-authenticated upload from the matching GitHub Actions workflow and **claim the project name in the same step** — no separate "first upload via password" needed.

### 2. Create the `pypi` GitHub Environment

Repo Settings → Environments → "New environment" → name: `pypi`. Optionally:

- Add a deployment branch rule restricting deploys to `main`.
- Require manual approval for the first run if you want a human-in-the-loop on the very first publish.

That's it. From this commit forward, every `release-please` release-PR merged to `main` triggers `publish.yml` automatically.

## Manual fallback

If the automated path fails (e.g. PyPI outage, OIDC issue), you can publish manually:

```bash
uv build
uv run --with twine twine upload dist/*
```

This uses your `~/.pypirc` API token. Document the failure mode in an issue afterward so we can fix the workflow.

## Verifying after a publish

```bash
# in any clean venv
pip install vacant-network
vacant --help
python -c "import vacant; print(vacant)"
```

Or via uvx (no install needed):

```bash
uvx --from vacant-network vacant --help
```

## What the package on PyPI will look like

```
Name:        vacant-network
Version:     0.2.0
Summary:     Responsibility-layer residency form for AI agents (atop A2A / MCP).
Home-page:   https://github.com/cosmopig/Vacant
License:     MIT
Author:      cosmopig
Requires:    pydantic, pynacl, cryptography, httpx, fastapi,
             sqlmodel, aiosqlite, alembic, structlog, anthropic,
             typer, python-dotenv, mcp, uvicorn, greenlet, keyring
```

The `vacant` import name and `vacant` console-script name are preserved.

## If you need to rename the project later

The `name = ...` line in `pyproject.toml` is the only required change for a *distribution* rename. PyPI does not support free-form renames; you'd need to:

1. Reserve the new name on PyPI (Trusted Publisher again).
2. Bump the version in this repo.
3. Publish the new name.
4. Mark the old name as deprecated on PyPI (form on the project's settings page).
5. Add a "moved to ..." note in this file.

The Python module name (`vacant`) and CLI script name (`vacant`) are independent of the PyPI rename and don't change.
