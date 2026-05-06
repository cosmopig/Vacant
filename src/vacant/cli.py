"""`vacant` console-script entrypoint.

Each subcommand is a stub returning exit code 0 in P0; later component PRs
replace the body. Built with Typer (CLAUDE.md says pick one and stick).
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="vacant",
    help="Vacant — responsibility-layer residency form for AI agents.",
    add_completion=False,
    no_args_is_help=True,
)


_NOT_YET = "Not yet implemented ({owner})."


@app.command("init")
def init_cmd(name: str) -> None:
    """Create a fresh keypair + seed logbook for `name`. (P2)"""
    typer.echo(_NOT_YET.format(owner="P2"))


@app.command("status")
def status_cmd(
    all_: bool = typer.Option(False, "--all", help="Show every local vacant."),
) -> None:
    """Show local vacants and their lifecycle states. (P1)"""
    _ = all_
    typer.echo(_NOT_YET.format(owner="P1"))


@app.command("heartbeat")
def heartbeat_cmd() -> None:
    """Manually trigger a heartbeat tick. (P1)"""
    typer.echo(_NOT_YET.format(owner="P1"))


@app.command("call")
def call_cmd(vid: str, capability: str) -> None:
    """Send a request to a remote vacant. (P6)"""
    _ = (vid, capability)
    typer.echo(_NOT_YET.format(owner="P6"))


@app.command("publish")
def publish_cmd() -> None:
    """Flip LOCAL → ACTIVE (publish halo to registry). (P4)"""
    typer.echo(_NOT_YET.format(owner="P4"))


@app.command("unpublish")
def unpublish_cmd() -> None:
    """Flip ACTIVE → LOCAL (withdraw from registry). (P4)"""
    typer.echo(_NOT_YET.format(owner="P4"))


@app.command("lineage")
def lineage_cmd(vid: str) -> None:
    """Print the parent_id chain for `vid`. (P4)"""
    _ = vid
    typer.echo(_NOT_YET.format(owner="P4"))


@app.command("attest")
def attest_cmd(target_vid: str, claim: str) -> None:
    """Issue a peer attestation about `target_vid`. (P2)"""
    _ = (target_vid, claim)
    typer.echo(_NOT_YET.format(owner="P2"))


@app.command("demo")
def demo_cmd(
    scenario: str,
    substrate: str = typer.Option(
        "mock", "--substrate", "-s", help="mock | deterministic | anthropic | ollama"
    ),
    seed: int | None = typer.Option(None, "--seed", help="override default seed"),
) -> None:
    """Run a demo scenario end-to-end. (P7)

    Examples:
      vacant demo law_firm
      vacant demo law-firm --seed=42                # hyphen accepted
      vacant demo self_replication --substrate=anthropic
    """
    from vacant.mvp.demo import main as demo_main

    # Normalize hyphenated forms to underscore (scenarios are registered
    # under underscore names in DEFAULT_SEEDS).
    argv = ["--scenario", scenario.replace("-", "_"), "--substrate", substrate]
    if seed is not None:
        argv += ["--seed", str(seed)]
    raise SystemExit(demo_main(argv))


def main() -> None:
    """Console-script entrypoint declared in `pyproject.toml`."""
    app()


if __name__ == "__main__":
    main()
