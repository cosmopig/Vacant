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
    # Single-Logbook invariant: bundle.form.logbook *is* the loaded
    # on-disk logbook (build_serve_app already calls ls.load_logbook).
    # Don't pass `logbook=` separately — the sampling tool's appends and
    # spawn tool's appends both go to form.logbook, so one save callback
    # persists both. The earlier double-load split the chain.

    def _save(lb: Logbook) -> None:
        ls.save_logbook(name, lb)

    def _persist_child(result: object, child_name: str, _parent_name: str) -> None:
        # `result` is a SpawnResult from vacant.runtime.spawn; we keep the
        # signature broad here so test_runner doesn't import composite-runtime
        # types it doesn't otherwise touch.
        ls.persist_spawned_child(
            child_name,
            child_vacant_id=result.child.identity,  # type: ignore[attr-defined]
            child_signing_key=result.child_signing_key,  # type: ignore[attr-defined]
            child_logbook=result.child.logbook,  # type: ignore[attr-defined]
            parent_vacant_id=result.child.parent_id,  # type: ignore[attr-defined]
            state=result.child.runtime_state.value,  # type: ignore[attr-defined]
        )

    run_mcp_stdio_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        on_logbook_change=_save,
        parent_local_name=name,
        persist_spawned_child=_persist_child,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
