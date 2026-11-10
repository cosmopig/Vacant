"""Normalize a pi `--mode json` event stream into the common trajectory schema.

Schema (one JSON object per line in `trajectory.jsonl`; schema_version 0.1):
  {"run_id", "task_id", "condition", "step", "t" (unix s),
   "kind": "plan" | "tool" | "final",
   "action": one of ACTIONS (tool/final steps) or null (plan text),
   "tool": pi tool name or null, "args": dict | null,
   "text": assistant text (plan/final) or null,
   "files_read": [..], "files_written": [..], "command": str | null,
   "is_error": bool, "retry_of": step | null,
   "usage": {"input","output"} | null}

The action alphabet is deliberately small so process sequences from different
agents/users are comparable:
  R read a file      S search/explore (ls, find, grep, git status/diff/log)
  E edit/write file  X run code/other command
  T run tests        A ask the user a question
  F final answer without asking
"""
from __future__ import annotations

import json
import re
import shlex
from typing import Any, Iterable

ACTIONS = "RSEXTAF"
TEST_RE = re.compile(r"\b(pytest|unittest|tox|nox|npm (run )?test|go test|cargo test)\b")
READ_CMDS = {"cat", "head", "tail", "less", "more", "nl", "wc", "bat"}
SEARCH_CMDS = {"ls", "find", "grep", "rg", "tree", "fd", "ag", "pwd"}
EDIT_RE = re.compile(r"(sed\s+-i|\btee\b|>\s*[\w./-]+|\bmv\b|\brm\b|\bcp\b|\bpatch\b|\bgit apply\b)")
QUESTION_RE = re.compile(r"\?\s*$|？\s*$|\b(could you|can you|do you want|would you like|should i|which (one|option)|please (confirm|clarify))\b", re.I | re.M)


def classify_bash(cmd: str) -> str:
    c = cmd.strip()
    if TEST_RE.search(c):
        return "T"
    first = ""
    try:
        first = shlex.split(c)[0] if c else ""
    except ValueError:
        first = c.split()[0] if c.split() else ""
    first = first.rsplit("/", 1)[-1]
    if first == "git":
        sub = c.split()[1] if len(c.split()) > 1 else ""
        return "S" if sub in {"status", "diff", "log", "show", "grep", "ls-files"} else "X"
    if EDIT_RE.search(c) and first not in SEARCH_CMDS:
        return "E"
    if first in READ_CMDS or (first == "sed" and "-n" in c):
        return "R"
    if first in SEARCH_CMDS:
        return "S"
    return "X"


def classify_tool(name: str, args: dict[str, Any]) -> str:
    if name == "read":
        return "R"
    if name in {"grep", "find", "ls"}:
        return "S"
    if name in {"edit", "write"}:
        return "E"
    if name == "bash":
        return classify_bash(str(args.get("command", "")))
    return "X"


def looks_like_question(text: str) -> bool:
    return bool(text and QUESTION_RE.search(text.strip()))


def normalize(events: Iterable[dict], run_id: str, task_id: str, condition: str) -> list[dict]:
    steps: list[dict] = []
    seen_calls: dict[str, int] = {}
    last_error_sig: str | None = None

    def add(**kw):
        base = {"run_id": run_id, "task_id": task_id, "condition": condition, "step": len(steps),
                "t": None, "kind": None, "action": None, "tool": None, "args": None, "text": None,
                "files_read": [], "files_written": [], "command": None, "is_error": False,
                "retry_of": None, "usage": None}
        base.update(kw)
        steps.append(base)
        return base

    pending: dict[str, dict] = {}
    for ev in events:
        if ev.get("type") == "message_end" and ev["message"].get("role") == "assistant":
            msg = ev["message"]
            t = (msg.get("timestamp") or 0) / 1000 or None
            usage = msg.get("usage")
            u = {"input": usage.get("input"), "output": usage.get("output")} if usage else None
            texts = [c.get("text", "") for c in msg.get("content", []) if c.get("type") == "text"]
            text = "\n".join(x for x in texts if x).strip()
            calls = [c for c in msg.get("content", []) if c.get("type") == "toolCall"]
            if calls:
                if text:
                    add(t=t, kind="plan", text=text, usage=u)
                    u = None
                for c in calls:
                    args = c.get("arguments") or {}
                    act = classify_tool(c["name"], args)
                    s = add(t=t, kind="tool", action=act, tool=c["name"], args=args, usage=u)
                    u = None
                    p = args.get("path") or args.get("file_path")
                    if act == "R" and p:
                        s["files_read"] = [p]
                    if c["name"] in {"edit", "write"} and p:
                        s["files_written"] = [p]
                    if c["name"] == "bash":
                        s["command"] = args.get("command")
                    sig = json.dumps([c["name"], args], sort_keys=True)
                    if sig == last_error_sig and sig in seen_calls:
                        s["retry_of"] = seen_calls[sig]
                    seen_calls[sig] = s["step"]
                    pending[c.get("id")] = s
            else:
                add(t=t, kind="final", action="A" if looks_like_question(text) else "F", text=text, usage=u)
        elif ev.get("type") == "tool_execution_end":
            s = pending.get(ev.get("toolCallId"))
            if s is not None:
                s["is_error"] = bool(ev.get("isError"))
                if s["is_error"]:
                    last_error_sig = json.dumps([s["tool"], s["args"]], sort_keys=True)
                elif last_error_sig == json.dumps([s["tool"], s["args"]], sort_keys=True):
                    last_error_sig = None
    return steps


def load_events(path: str) -> list[dict]:
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out
