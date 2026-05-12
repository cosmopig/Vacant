"""Model-agnostic Vacant agent route (Pfix6+).

Hermes / OpenClaw / Claude Desktop / Cursor all expect the LLM to emit
OpenAI function-call JSON to invoke MCP tools. Models smaller than
~7B (Gemma 4 E2B, Qwen 3 4B, Phi 3 mini, …) emit free-form text
instead, and the framework silently swallows the would-be tool call.

This module exposes a ReAct-style action loop that lets *any* LLM with
an OpenAI-compatible ``/v1/chat/completions`` surface drive Vacant
correctly. Wired as ``vacant route`` so it's reachable straight from
``uvx --from vacant-network vacant route ...`` — no clone required.

The action protocol (taught to the model via the system prompt):

    <vacant_action name="vacant_describe"></vacant_action>
    <vacant_action name="vacant_spawn">{"policy_mutation": "...",
                                         "child_name_hint": "..."}</vacant_action>
    <vacant_action name="final">free-form answer to the user</vacant_action>

The client side parses each assistant turn with a regex, dispatches
the named tool to a ``vacant mcp --name <name>`` subprocess over
stdio, appends the result back into the conversation, and re-prompts
until the model emits ``final`` or ``max_rounds`` runs out.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

__all__ = [
    "DEFAULT_SYSTEM",
    "RouteResult",
    "parse_action",
    "run_route",
]


ACTION_RE = re.compile(
    r'<vacant_action\s+name="([^"]+)"\s*(?:/>|>(.*?)</vacant_action>)',
    re.DOTALL,
)


DEFAULT_SYSTEM = """\
You are an autonomous agent grafted onto a Vacant identity. You CANNOT
call tools through OpenAI function-calls; instead you emit a single
ACTION block per turn and NOTHING ELSE. No commentary, no explanation,
no greetings — just the action block.

Three actions are available. Examples (copy the format exactly):

  Example 1 — describe self (zero arguments, empty body):
  <vacant_action name="vacant_describe"></vacant_action>

  Example 2 — spawn a D1 child (body is JSON):
  <vacant_action name="vacant_spawn">{"policy_mutation": "always cite the source paragraph verbatim", "child_name_hint": "cite"}</vacant_action>

  Example 3 — final answer to the user (body is plain text):
  <vacant_action name="final">After reviewing the task I recommend spawning a specialised translator. Done.</vacant_action>

Rules:
- Exactly one action block per turn.
- Nothing outside the <vacant_action>...</vacant_action> wrapper.
- vacant_describe takes NO arguments — its body MUST be empty.
- vacant_spawn body MUST be a valid JSON object with policy_mutation (and optionally child_name_hint).
- final's body is the answer you want to show the user; pick this when you are done.
"""


class RouteResult:
    """Outcome of a route loop: exit code + transcript."""

    __slots__ = ("exit_code", "transcript")

    def __init__(self, *, exit_code: int, transcript: list[tuple[str, str]]):
        self.exit_code = exit_code
        self.transcript = transcript


def parse_action(text: str) -> tuple[str, str] | None:
    """Extract the first ``<vacant_action name="X">body</vacant_action>``
    block from ``text``, or ``None`` if absent. ``body`` is stripped
    of surrounding whitespace."""
    m = ACTION_RE.search(text)
    if not m:
        return None
    name = m.group(1)
    body = (m.group(2) or "").strip()
    return name, body


async def _llm_complete(  # pragma: no cover -- live HTTP; covered by VM smoke
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
) -> str:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    r = await client.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json={"model": model, "messages": messages, "temperature": temperature},
    )
    r.raise_for_status()
    return str(r.json()["choices"][0]["message"]["content"])


async def run_route(  # pragma: no cover -- spawns vacant mcp; covered by VM smoke
    *,
    prompt: str,
    name: str,
    model: str,
    base_url: str,
    api_key: str = "",
    max_rounds: int = 8,
    temperature: float = 0.0,
    vacant_home: str | None = None,
    system_prompt: str = DEFAULT_SYSTEM,
    uvx: str = "uvx",
    git_ref: str = "git+https://github.com/cosmopig/Vacant.git",
) -> RouteResult:
    """Run a ReAct loop that wraps a vacant MCP server with any
    OpenAI-compatible LLM endpoint. Returns the transcript so callers
    can render it however they like (stdout, file, telemetry)."""
    env = {**os.environ, "VACANT_NAME": name}
    if vacant_home:
        env["VACANT_HOME"] = vacant_home

    params = StdioServerParameters(
        command=uvx,
        args=["--from", git_ref, "vacant", "mcp"],
        env=env,
    )

    history: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    transcript: list[tuple[str, str]] = []

    async with httpx.AsyncClient(timeout=300.0) as http, stdio_client(params) as (r, w):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            tools = await sess.list_tools()
            tool_names = sorted(t.name for t in tools.tools)

            for round_no in range(1, max_rounds + 1):
                llm_text = await _llm_complete(
                    http,
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    messages=history,
                    temperature=temperature,
                )
                transcript.append(("assistant", llm_text))
                history.append({"role": "assistant", "content": llm_text})

                parsed = parse_action(llm_text)
                if parsed is None:
                    transcript.append(
                        (
                            "system",
                            f"(no <vacant_action> in round {round_no}; nudging LLM)",
                        )
                    )
                    history.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous turn did not contain a "
                                "<vacant_action> block. Emit exactly one. If "
                                "you have an answer, use "
                                '<vacant_action name="final">...</vacant_action>.'
                            ),
                        }
                    )
                    continue

                action_name, body = parsed
                if action_name == "final":
                    transcript.append(("final", body))
                    return RouteResult(exit_code=0, transcript=transcript)

                if action_name not in tool_names:
                    note = f"Unknown action {action_name!r}. Available: {[*tool_names, 'final']}"
                    transcript.append(("system", note))
                    history.append({"role": "user", "content": note})
                    continue

                # Zero-arg tools (e.g. vacant_describe) tolerate a non-empty
                # body — small models like padding it with prose. Discard
                # rather than failing.
                tool_spec = next((t for t in tools.tools if t.name == action_name), None)
                required = (
                    list((tool_spec.inputSchema or {}).get("required", [])) if tool_spec else []
                )
                args: dict[str, Any]
                if not required and not body.strip().startswith("{"):
                    args = {}
                else:
                    try:
                        args = json.loads(body) if body.strip() else {}
                    except json.JSONDecodeError as exc:
                        note = (
                            f"Action {action_name} body is not valid JSON "
                            f"({exc}). Reformat and try again."
                        )
                        transcript.append(("system", note))
                        history.append({"role": "user", "content": note})
                        continue

                try:
                    result = await sess.call_tool(action_name, arguments=args)
                except Exception as exc:
                    note = f"Action {action_name} failed: {exc}"
                    transcript.append(("system", note))
                    history.append({"role": "user", "content": note})
                    continue

                payload_text = ""
                for chunk in result.content:
                    payload_text += getattr(chunk, "text", "")
                transcript.append((f"tool:{action_name}", payload_text))
                history.append(
                    {
                        "role": "user",
                        "content": (
                            f"Tool {action_name} returned:\n{payload_text}\nDecide the next action."
                        ),
                    }
                )

    transcript.append(("system", f"hit max_rounds={max_rounds} without final"))
    return RouteResult(exit_code=2, transcript=transcript)


def render_transcript(transcript: list[tuple[str, str]]) -> str:
    """Format a transcript as a human-readable string."""
    parts: list[str] = []
    for role, text in transcript:
        parts.append(f"--- {role} ---")
        parts.append(text)
    return "\n".join(parts)


def main(  # pragma: no cover -- thin sync wrapper around run_route
    *,
    prompt: str,
    name: str,
    model: str,
    base_url: str,
    api_key: str,
    max_rounds: int,
    temperature: float,
    vacant_home: str | None,
    uvx: str,
) -> int:
    """Synchronous entry point — used by the Typer ``vacant route``
    command and by ``examples/agent/route.py``."""
    result = asyncio.run(
        run_route(
            prompt=prompt,
            name=name,
            model=model,
            base_url=base_url,
            api_key=api_key,
            max_rounds=max_rounds,
            temperature=temperature,
            vacant_home=vacant_home,
            uvx=uvx,
        )
    )
    print(render_transcript(result.transcript))
    return result.exit_code
