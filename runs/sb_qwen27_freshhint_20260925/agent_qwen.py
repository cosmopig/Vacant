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
"""
import json
import os
import re
import sys
import urllib.request

MODEL = os.environ.get("VACANT_SB_MODEL", "qwen/qwen3.8-27b")
MAX_TOKENS = int(os.environ.get("VACANT_SB_MAX_TOKENS", "8192"))
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
            "## Acceptance feedback from the previous attempt\n\n"
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
        content = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        print(f"agent: unexpected reply shape: {e!r}", file=sys.stderr)
        return 3

    blocks = re.findall(r"```python\s*\n(.*?)```", content, re.S)
    if not blocks:
        blocks = re.findall(r"```\s*\n(.*?)```", content, re.S)
    code = blocks[-1] if blocks else content
    if not code.strip():
        print("agent: no code in the reply", file=sys.stderr)
        return 3

    with open(os.path.join(cwd, "solution.py"), "w", encoding="utf-8") as f:
        f.write(code.rstrip("\n") + "\n")
    print(f"agent: wrote solution.py ({len(code)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
