"""Read-only reconstruction of per-turn state for the 2026-09-25 formal DABstep batch.

For every (model, arm, task) latest run: per assistant turn (1-based model request),
  - tool calls actually executed (have a toolResult),
  - whether /app/answer.txt exists at the end of the turn (transcript heuristic; for the C arm
    also Vacant's own workspace trace, used as ground truth where present),
  - thinking text and visible text (for candidate-answer extraction in nudge_sim.py).

Nothing under /home/user/Vacant is written.
"""
import glob
import json
import os
import re
import shlex

SCR = "/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad"
JOBS = SCR + "/formal/jobs"
PIN = SCR + "/dabstep_pinned/formal"
RUNS = "/home/user/Vacant/ops/eval/evidence_20260925/formal/runs.json"


def latest_runs():
    runs = json.load(open(RUNS))
    latest = {}
    for r in runs:
        k = (r["model"], r["arm"], r["task"])
        if k not in latest or r["job"] > latest[k]["job"]:
            latest[k] = r
    return latest


def expected(task):
    s = open(f"{PIN}/dabstep-{task}/tests/test.sh").read()
    return s.split("<<'ANSWER_EOF'\n")[1].split("\nANSWER_EOF")[0]


def trial_dir(r):
    return os.path.join(JOBS, r["job"], r["trial"])


def verifier(r):
    so = open(os.path.join(trial_dir(r), "verifier/test-stdout.txt")).read()
    if "answer.txt not found" in so:
        return {"exists": False, "got": None}
    m = re.search(r"^Got: (.*)$", so, re.M)
    return {"exists": True, "got": m.group(1) if m else None}


# ---------------------------------------------------------------- answer.txt write detection
ANS = r"""["']?((?:/app/)?answer\.txt)["']?"""
RE_REDIR = re.compile(r"(?<![0-9&])>{1,2}\s*" + ANS + r"(?![\w.])")
RE_TEE = re.compile(r"\btee\s+(?:-a\s+)?" + ANS + r"(?![\w.])")
RE_PYOPEN = re.compile(r"""open\(\s*["']((?:/app/)?answer\.txt)["']\s*,\s*["'][wa]""")
RE_CPMV = re.compile(r"\b(?:cp|mv)\s+\S+\s+" + ANS + r"(?![\w.])")
RE_TOUCH = re.compile(r"\btouch\s+" + ANS + r"(?![\w.])")
RE_RM = re.compile(r"\brm\s+(?:-\w+\s+)*" + ANS + r"(?![\w.])")


def _abs(path, cmd, pos):
    """Resolve a (possibly relative) answer.txt path; cwd = last `cd X` before pos, else /app."""
    if path.startswith("/"):
        return path
    cwd = "/app"
    for m in re.finditer(r"\bcd\s+(\S+)", cmd[:pos]):
        d = m.group(1).strip("'\";&")
        cwd = d if d.startswith("/") else os.path.normpath(os.path.join(cwd, d))
    return os.path.join(cwd, path)


def _literal_content(cmd, pos):
    """Best effort: echo "X" > answer.txt / printf 'X' > answer.txt -> X."""
    seg = cmd[:pos]
    seg = re.split(r"[;&|\n]", seg)[-1]
    m = re.match(r"\s*(echo|printf)\s+(?:-[ne]+\s+)?(.*?)\s*>{1,2}\s*$", seg + ">")
    if not m:
        return None
    try:
        parts = shlex.split(m.group(2))
    except ValueError:
        return None
    if m.group(1) == "printf" and parts:
        if len(parts) >= 2 and "%s" in parts[0]:
            return parts[1]
        return parts[0].replace("\\n", "\n")
    return " ".join(parts)


def bash_answer_ops(cmd):
    """Return list of (op, abs_path, literal_content_or_None) for answer.txt in a bash command."""
    ops = []
    for rx in (RE_REDIR, RE_TEE, RE_PYOPEN, RE_CPMV, RE_TOUCH):
        for m in rx.finditer(cmd):
            p = _abs(m.group(1), cmd, m.start())
            lit = _literal_content(cmd, m.start()) if rx is RE_REDIR else None
            ops.append((m.start(), "write", p, lit))
    for m in RE_RM.finditer(cmd):
        ops.append((m.start(), "delete", _abs(m.group(1), cmd, m.start()), None))
    ops.sort()
    return [(o, p, c) for _, o, p, c in ops]


def parse_session(r):
    path = glob.glob(trial_dir(r) + "/agent/pi/sessions/*.jsonl")
    assert len(path) == 1, path
    msgs = [json.loads(l) for l in open(path[0])]
    results = {}
    for o in msgs:
        m = o.get("message") or {}
        if m.get("role") == "toolResult":
            results[m["toolCallId"]] = m
    turns = []
    custom = []
    for o in msgs:
        if o["type"] == "custom_message":
            custom.append({"after_turn": len(turns), "customType": o.get("customType")})
        m = o.get("message") or {}
        if m.get("role") != "assistant":
            continue
        # pi appends a zero-usage, empty assistant message when Harbor's max_turns extension aborts;
        # it is not a model request.
        if m.get("stopReason") == "error" and not m.get("content") and \
                m.get("errorMessage") == "This operation was aborted":
            continue
        t = {"turn": len(turns) + 1, "stop": m.get("stopReason"), "thinking": "", "text": "",
             "calls": []}
        for c in m.get("content") or []:
            if c["type"] == "thinking":
                t["thinking"] += c.get("thinking", "") + "\n"
            elif c["type"] == "text":
                t["text"] += c.get("text", "") + "\n"
            elif c["type"] == "toolCall":
                res = results.get(c["id"])
                t["calls"].append({"id": c["id"], "name": c["name"], "args": c.get("arguments") or {},
                                   "executed": res is not None,
                                   "is_error": bool(res and res.get("isError")),
                                   "result": "".join(x.get("text", "") for x in (res or {}).get("content", [])
                                                     if isinstance(x, dict))})
        turns.append(t)
    return turns, custom


def heuristic_exists(turns):
    """Per-turn: does /app/answer.txt exist at end of turn, per transcript heuristics.

    write/edit tool on (/app/)answer.txt; bash `>`/`>>`/tee/python open(...,'w'|'a')/cp/mv/touch;
    rm deletes. Only executed tool calls count. A bash call whose result isError is still counted
    as writing (flag `uncertain`) because a chained command may have written before failing.
    """
    exists = False
    out = []
    for t in turns:
        writes = []
        uncertain = False
        for c in t["calls"]:
            if not c["executed"]:
                continue
            if c["name"] in ("write", "edit"):
                p = str(c["args"].get("path", ""))
                ap = p if p.startswith("/") else os.path.join("/app", p)
                if ap == "/app/answer.txt":
                    if c["is_error"]:
                        uncertain = True
                        continue
                    exists = True
                    writes.append({"via": c["name"], "content": c["args"].get("content") if c["name"] == "write" else None})
            elif c["name"] == "bash":
                for op, p, lit in bash_answer_ops(c["args"].get("command", "")):
                    if p != "/app/answer.txt":
                        continue
                    if op == "delete":
                        exists = False
                        writes.append({"via": "bash-rm", "content": None})
                    else:
                        exists = True
                        if c["is_error"]:
                            uncertain = True
                        writes.append({"via": "bash", "content": lit})
        out.append({"exists": exists, "writes": writes, "uncertain": uncertain})
    return out


def trace_exists(r, turns):
    """C arm only: Vacant's workspace trace (post_index of each recorded step) -> per-turn existence
    and answer.txt content hash. Returns None if no trace."""
    projs = glob.glob(trial_dir(r) + "/agent/vacant_home/trace/projects/*/chain.ndjson")
    if not projs:
        return None
    objdir = os.path.join(trial_dir(r), "agent/vacant_home/trace/objects")
    step_state = {}
    for pth in projs:
        for l in open(pth):
            o = json.loads(l)
            if o.get("type") != "step":
                continue
            p = o["payload"]
            idx = p.get("post_index")
            if not idx:
                continue
            f = os.path.join(objdir, idx[:2], idx)
            if not os.path.exists(f):
                continue
            ix = json.load(open(f))
            ent = ix.get("answer.txt")
            content = None
            if ent:
                cf = os.path.join(objdir, ent[0][:2], ent[0])
                if os.path.exists(cf):
                    content = open(cf, "rb").read().decode("utf-8", "replace")
            step_state[p["step"]] = {"exists": ent is not None, "content": content}
    out = []
    cur = None
    for t in turns:
        for c in t["calls"]:
            if c["id"] in step_state:
                cur = step_state[c["id"]]
        out.append(None if cur is None else dict(cur))
    return out
