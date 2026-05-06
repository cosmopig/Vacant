"""CLI scaffolding smoke tests. Each component PR adds richer tests."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from vacant.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_help_lists_all_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "init",
        "status",
        "heartbeat",
        "call",
        "publish",
        "unpublish",
        "lineage",
        "attest",
        "demo",
    ):
        assert cmd in result.stdout


@pytest.mark.parametrize(
    ("argv", "owner"),
    [
        (["init", "alice"], "P2"),
        (["status"], "P1"),
        (["heartbeat"], "P1"),
        (["call", "vid:abc", "translate"], "P6"),
        (["publish"], "P4"),
        (["unpublish"], "P4"),
        (["lineage", "vid:abc"], "P4"),
        (["attest", "vid:abc", "is-honest"], "P2"),
        (["demo", "law-firm"], "P7"),
    ],
)
def test_stub_commands_print_owner(runner: CliRunner, argv: list[str], owner: str) -> None:
    result = runner.invoke(app, argv)
    assert result.exit_code == 0
    assert owner in result.stdout
