"""`vacant` console-script entrypoint.

Each subcommand is wired to real functionality via `vacant.cli.commands`.
The Typer app is exposed at module level (`app`, `main`) for the
`pyproject.toml` console_script and for `typer.testing.CliRunner` use
in unit tests.
"""

from __future__ import annotations

from vacant.cli.commands import app, main

__all__ = ["app", "main"]
