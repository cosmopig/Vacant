"""PR3: `vacant serve --public --tls-cert/--tls-key` flag behaviour.

We can't actually start uvicorn in a unit test, but we can verify:
- The CLI surface advertises the new flags.
- `--public` flips the displayed bind host to `0.0.0.0`.
- `--tls-cert` without `--tls-key` (or vice versa) exits with error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vacant.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    monkeypatch.delenv("VACANT_NAME", raising=False)
    return home


def _init_alice(runner: CliRunner) -> None:
    res = runner.invoke(app, ["init", "alice"])
    assert res.exit_code == 0, res.stdout


def test_serve_help_lists_public_and_tls_flags(runner: CliRunner) -> None:
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    for flag in ("--public", "--tls-cert", "--tls-key"):
        assert flag in result.stdout


def test_serve_rejects_tls_cert_without_key(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_alice(runner)
    cert = tmp_path / "cert.pem"
    cert.write_text("dummy", encoding="utf-8")
    # Patch uvicorn.run so we don't actually serve. If validation passes,
    # we'd hit the run call; the test verifies it never gets there.

    def _no_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("uvicorn.run should not be reached when args are invalid")

    monkeypatch.setattr("uvicorn.run", _no_run)
    res = runner.invoke(
        app,
        ["serve", "--name", "alice", "--tls-cert", str(cert)],
    )
    assert res.exit_code != 0
    assert "tls-cert" in res.output.lower() or "tls" in res.output.lower()


def test_serve_rejects_tls_key_without_cert(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_alice(runner)
    key = tmp_path / "key.pem"
    key.write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(
        "uvicorn.run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run")),
    )
    res = runner.invoke(app, ["serve", "--name", "alice", "--tls-key", str(key)])
    assert res.exit_code != 0


def test_serve_public_flag_flips_host_to_0_0_0_0(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The JSON banner printed before uvicorn.run should show
    `0.0.0.0` when --public is passed."""
    _init_alice(runner)

    captured: dict[str, object] = {}

    def _fake_run(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", _fake_run)
    res = runner.invoke(app, ["serve", "--name", "alice", "--public", "--port", "8443"])
    assert res.exit_code == 0, res.output
    # First line of output is the JSON banner from typer.echo(...).
    banner = json.loads(res.output.splitlines()[0])
    assert banner["host"] == "0.0.0.0"  # noqa: S104 — operator-opt-in via --public
    assert banner["public"] is True
    assert banner["tls"] is False
    # Uvicorn was called with the same bind host.
    assert captured.get("host") == "0.0.0.0"  # noqa: S104


def test_serve_tls_flags_pass_through_to_uvicorn(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_alice(runner)
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("dummy-cert", encoding="utf-8")
    key.write_text("dummy-key", encoding="utf-8")

    captured: dict[str, object] = {}

    def _fake_run(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", _fake_run)
    res = runner.invoke(
        app,
        [
            "serve",
            "--name",
            "alice",
            "--tls-cert",
            str(cert),
            "--tls-key",
            str(key),
        ],
    )
    assert res.exit_code == 0, res.output
    assert captured.get("ssl_certfile") == str(cert)
    assert captured.get("ssl_keyfile") == str(key)
    banner = json.loads(res.output.splitlines()[0])
    assert banner["tls"] is True
