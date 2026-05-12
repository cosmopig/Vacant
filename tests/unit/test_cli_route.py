"""Unit tests for ``vacant.cli.route`` — the model-agnostic action loop.

The end-to-end behaviour (real LLM + real MCP subprocess) is covered
by ``examples/agent/route.py`` smoke runs against an Ollama endpoint;
these tests pin the parsing + transcript-rendering primitives that
the loop depends on, so a future regression there fails the unit
suite before it ships."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from vacant.cli import app
from vacant.cli import route as route_mod


def test_parse_action_self_closing() -> None:
    out = route_mod.parse_action('<vacant_action name="vacant_describe"/>')
    assert out == ("vacant_describe", "")


def test_parse_action_empty_body() -> None:
    out = route_mod.parse_action('<vacant_action name="vacant_describe"></vacant_action>')
    assert out == ("vacant_describe", "")


def test_parse_action_json_body() -> None:
    out = route_mod.parse_action(
        '<vacant_action name="vacant_spawn">{"policy_mutation": "x", '
        '"child_name_hint": "y"}</vacant_action>'
    )
    assert out is not None
    name, body = out
    assert name == "vacant_spawn"
    assert "policy_mutation" in body


def test_parse_action_handles_prose_padding() -> None:
    """A small LLM may emit prose around the block — we still find it."""
    text = (
        'Here is my action.\n<vacant_action name="final">all done.</vacant_action>\n'
        "Hope this helps."
    )
    out = route_mod.parse_action(text)
    assert out == ("final", "all done.")


def test_parse_action_returns_none_when_absent() -> None:
    assert route_mod.parse_action("no action here") is None


def test_render_transcript_includes_labels() -> None:
    rendered = route_mod.render_transcript(
        [("assistant", "hello"), ("tool:vacant_describe", '{"x": 1}'), ("final", "bye")]
    )
    assert "--- assistant ---" in rendered
    assert "--- tool:vacant_describe ---" in rendered
    assert "--- final ---" in rendered
    assert "bye" in rendered


def test_route_result_holds_fields() -> None:
    r = route_mod.RouteResult(exit_code=0, transcript=[("final", "ok")])
    assert r.exit_code == 0
    assert r.transcript[0] == ("final", "ok")


def test_route_command_requires_base_url() -> None:
    """``vacant route ...`` must surface a clean error when neither
    ``--base-url`` nor any LLM_BASE_URL/OLLAMA_BASE_URL env is set."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["route", "anything"],
        env={"LLM_BASE_URL": "", "OLLAMA_BASE_URL": ""},
    )
    assert result.exit_code == 2
    assert "base-url" in (result.stdout + (result.stderr or ""))


@pytest.mark.parametrize(
    "action_text",
    [
        '<vacant_action name="vacant_spawn">{ "policy_mutation": "x" }</vacant_action>',
        '<vacant_action name="vacant_spawn">\n  {"policy_mutation": "x"}\n</vacant_action>',
    ],
)
def test_parse_action_tolerates_whitespace(action_text: str) -> None:
    out = route_mod.parse_action(action_text)
    assert out is not None
    assert out[0] == "vacant_spawn"
