"""Subprocess entrypoint for MCP integration tests.

Loads a local vacant by name (env `VACANT_HOME` selects the directory)
and runs the FastMCP server on stdio. Separate from `vacant serve --mcp`
because that command also boots uvicorn — for the MCP-only acceptance
test we want a stdio-pure subprocess so the official MCP client SDK can
attach without first having to drain HTTP startup output.

Invoke as: `python -m vacant.cli.mcp_serve_test_runner <name>`
"""

from __future__ import annotations

import sys

from vacant.cli import local_store as ls
from vacant.cli.mcp_server import run_mcp_stdio_server
from vacant.cli.server import build_serve_app
from vacant.core.types import Logbook


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m vacant.cli.mcp_serve_test_runner <name>", file=sys.stderr)
        return 2
    name = args[0]
    bundle = build_serve_app(name)
    # Pfix3 B7: persist sampling-driven SUBSTRATE_BORROWED + INFERENCE_EVENT
    # entries to disk so integration tests can read them back after the
    # subprocess exits. The vacant's existing logbook is the load-bearing
    # audit chain; we re-load it (rather than reuse bundle.form.logbook,
    # which build_serve_app may have replaced with an empty Logbook when
    # the original was empty) so any genesis entry is preserved.
    persistent_lb: Logbook = ls.load_logbook(name)

    def _save(lb: Logbook) -> None:
        ls.save_logbook(name, lb)

    run_mcp_stdio_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        logbook=persistent_lb,
        on_logbook_change=_save,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
