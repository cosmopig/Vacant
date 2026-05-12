"""Model-agnostic Vacant agent loop (the "skill" for non-tool-capable LLMs).

Hermes / OpenClaw / Claude Desktop / Cursor all expect the LLM to emit
OpenAI function-call JSON to invoke MCP tools. Models smaller than
~7B (Gemma 4 E2B, Qwen 3 4B, etc.) emit free-form text instead and
the framework silently swallows the would-be tool call. This script
is the workaround: a ReAct-style action protocol that any LLM with a
text completion endpoint can drive, dispatching MCP calls on the
client side.

Run::

    OLLAMA_BASE_URL=http://192.168.50.130:11434/v1 \\
    OLLAMA_API_KEY=ollama \\
    python examples/agent/route.py \\
      --name alice --model gemma4:e2b \\
      "Translate this Chinese paragraph and keep cited identifiers verbatim: ..."

What you'll see:

- The LLM produces plain text. The loop scans every assistant turn for
  ``<vacant_action name="X">{json args}</vacant_action>`` blocks.
- Recognised actions: ``vacant_describe`` (no args), ``vacant_spawn``
  (``{policy_mutation, child_name_hint?}``), ``final`` (body = answer).
- Each tool call is routed to a running ``vacant mcp --name <name>``
  subprocess over stdio. The result is appended to the conversation
  history and the LLM gets another turn.
- Loop ends when the LLM emits a ``final`` action (or after
  ``--max-rounds``).

The point: ANY LLM works. Tool-call format support is not required.
Pair this with a system prompt that motivates spawn (a complex /
specialised task) and the LLM will autonomously emit ``vacant_spawn``,
producing real audit chain entries through the same MCP path that
Hermes / OpenClaw use.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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


def _parse_action(text: str) -> tuple[str, str] | None:
    m = ACTION_RE.search(text)
    if not m:
        return None
    name = m.group(1)
    body = (m.group(2) or "").strip()
    return name, body


async def _llm_complete(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
) -> str:
    r = await client.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
        },
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


async def main_async(
    *,
    prompt: str,
    name: str,
    model: str,
    base_url: str,
    api_key: str,
    max_rounds: int,
    temperature: float,
    vacant_home: str | None,
) -> int:
    env = {**os.environ, "VACANT_NAME": name}
    if vacant_home:
        env["VACANT_HOME"] = vacant_home

    params = StdioServerParameters(
        command=os.environ.get("UVX", "uvx"),
        args=[
            "--from",
            "git+https://github.com/cosmopig/Vacant.git",
            "vacant",
            "mcp",
        ],
        env=env,
    )

    history: list[dict[str, str]] = [
        {"role": "system", "content": DEFAULT_SYSTEM},
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

                parsed = _parse_action(llm_text)
                if parsed is None:
                    transcript.append(
                        ("system", f"(no <vacant_action> found in round {round_no}; nudging LLM)")
                    )
                    history.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous turn did not contain a <vacant_action> "
                                "block. Emit exactly one. If you have an answer, use "
                                '<vacant_action name="final">...</vacant_action>.'
                            ),
                        }
                    )
                    continue

                action_name, body = parsed
                if action_name == "final":
                    transcript.append(("final", body))
                    for role, text in transcript:
                        print(f"--- {role} ---")
                        print(text)
                    return 0

                if action_name not in tool_names:
                    note = f"Unknown action {action_name!r}. Available: {[*tool_names, 'final']}"
                    transcript.append(("system", note))
                    history.append({"role": "user", "content": note})
                    continue

                # Resolve the tool's argument schema. Zero-arg tools (e.g.
                # vacant_describe) tolerate a non-empty body — small LLMs love
                # padding it with prose. We discard it rather than failing.
                tool_spec = next((t for t in tools.tools if t.name == action_name), None)
                required = (
                    list((tool_spec.inputSchema or {}).get("required", [])) if tool_spec else []
                )
                if not required and not body.strip().startswith("{"):
                    args: dict[str, Any] = {}
                else:
                    try:
                        args = json.loads(body) if body.strip() else {}
                    except json.JSONDecodeError as exc:
                        note = (
                            f"Action {action_name} body is not valid JSON ({exc}). "
                            "Reformat and try again."
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
            for role, text in transcript:
                print(f"--- {role} ---")
                print(text)
            return 2


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    p.add_argument("prompt", help="User task")
    p.add_argument("--name", default=os.environ.get("VACANT_NAME", "alice"))
    p.add_argument("--model", default=os.environ.get("LLM_MODEL", "gemma4:e2b"))
    p.add_argument(
        "--base-url",
        default=os.environ.get("LLM_BASE_URL") or os.environ.get("OLLAMA_BASE_URL"),
        required=False,
    )
    p.add_argument(
        "--api-key",
        default=os.environ.get("LLM_API_KEY") or os.environ.get("OLLAMA_API_KEY") or "",
    )
    p.add_argument("--max-rounds", type=int, default=8)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--vacant-home", default=os.environ.get("VACANT_HOME"))
    args = p.parse_args()

    if not args.base_url:
        print(
            "error: --base-url (or LLM_BASE_URL / OLLAMA_BASE_URL env) required",
            file=sys.stderr,
        )
        return 2

    return asyncio.run(
        main_async(
            prompt=args.prompt,
            name=args.name,
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            max_rounds=args.max_rounds,
            temperature=args.temperature,
            vacant_home=args.vacant_home,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
