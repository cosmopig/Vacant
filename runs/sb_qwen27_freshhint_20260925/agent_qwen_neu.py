#!/usr/bin/env python3
"""One-shot coding agent for the sb_qwen27_freshhint small batch.

Reads TASK.md from the current directory (and VACANT_FEEDBACK.md if present),
calls the OpenAI-compatible endpoint at $OPENAI_BASE_URL (under `vacant run`
that is the tee proxy, so every request is wire-captured), extracts the
python code block from the reply, and writes solution.py.

The agent is deliberately minimal and identical across all arms: the only
arm-specific input is VACANT_FEEDBACK.md, which `vacant run` writes into the
workspace (fresh_hint arm only) and which the base instructions tell the
agent to read if present.

Exit codes: 0 = solution.py written (right or wrong — the gate decides);
3 = infrastructure failure (endpoint unreachable, no code in the reply).

LABEL-NEUTRAL VARIANT (round 21): byte-identical to agent_qwen.py except the
one header line under which the feedback file's CONTENT is embedded (the
file name never reaches the model — the agent passes content only). The
label cell tests whether the label "## Acceptance feedback from the previous
attempt" is what carries the effect, versus any extra prompt content.
See name_cell.py.
"""
import json
import os
import re
import sys
import urllib.request

MODEL = os.environ.get("VACANT_SB_MODEL", "qwen/qwen3.8-27b")
# 2026-10-24 (round 10): default raised 8192 -> 32768.
# v1 (8192) incident: on lcb_3485/lcb_3487 every attempt used the whole budget
# on reasoning_content (finish_reason=length) and returned empty content, so the
# agent produced no deliverable and all 6 cells of those two tasks were void.
# The LM Studio build cannot turn thinking off (enable_thinking:false and
# /no_think both still produce reasoning_content), so the budget must cover
# thinking + answer. See cells_v1_8192/ for the wire evidence.
MAX_TOKENS = int(os.environ.get("VACANT_SB_MAX_TOKENS", "32768"))
TIMEOUT_S = 600


def main() -> int:
    cwd = os.getcwd()
    task_path = os.path.join(cwd, "TASK.md")
    if not os.path.exists(task_path):
        print("agent: TASK.md not found in", cwd, file=sys.stderr)
        return 3
    with open(task_path, encoding="utf-8") as f:
        task = f.read()

    fb_path = os.path.join(cwd, "VACANT_FEEDBACK.md")
    feedback = ""
    if os.path.exists(fb_path):
        with open(fb_path, encoding="utf-8") as f:
            feedback = f.read()

    base = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
    if not base:
        print("agent: OPENAI_BASE_URL not set; cannot call the model",
              file=sys.stderr)
        return 3
    url = base + "/chat/completions"

    prompt = (
        "You are a Python coding agent. Work in the current directory.\n\n"
        + task
        + "\n\n"
    )
    if feedback:
        prompt += (
            "## Note\n\n"
            + feedback
            + "\n\n"
        )
    prompt += (
        "Write the complete file solution.py in the current directory, "
        "defining the required entry-point function.\n"
        "Reply with the full content of solution.py inside exactly one "
        "```python code block. No prose outside the code block."
    )

    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — infra failure must be visible
        print(f"agent: model call failed: {e!r}", file=sys.stderr)
        return 3

    try:
        choice = data["choices"][0]
        msg = choice["message"]
        content = msg["content"] or ""
        reasoning = msg.get("reasoning_content") or ""
        finish = choice.get("finish_reason")
    except (KeyError, IndexError, TypeError) as e:
        print(f"agent: unexpected reply shape: {e!r}", file=sys.stderr)
        return 3

    blocks = re.findall(r"```python\s*\n(.*?)```", content, re.S)
    if not blocks:
        blocks = re.findall(r"```\s*\n(.*?)```", content, re.S)
    code = blocks[-1] if blocks else content
    if not code.strip():
        # Distinguish the two ways this happens: the model ran out of budget
        # while thinking (content empty, finish_reason=length) versus a reply
        # that simply contains no code. Both are infra failures (rc=3), but
        # the log must say which one it was.
        if finish == "length":
            print(f"agent: BUDGET_TRUNCATED: empty content, "
                  f"finish_reason=length, reasoning_len={len(reasoning)}, "
                  f"max_tokens={MAX_TOKENS}", file=sys.stderr)
        else:
            print(f"agent: no code in the reply "
                  f"(finish_reason={finish!r}, reasoning_len={len(reasoning)})",
                  file=sys.stderr)
        return 3

    with open(os.path.join(cwd, "solution.py"), "w", encoding="utf-8") as f:
        f.write(code.rstrip("\n") + "\n")
    print(f"agent: wrote solution.py ({len(code)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
