"""Parse local formal_v3 runs into per-turn records (read-only)."""
import json, re, pathlib, sys, lzma
L = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3")
P = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/dabstep_pinned/formal")
OUT = pathlib.Path("/tmp/claude-0/review_effect/mechanism")

def expected_of(task):
    t = (P / f"dabstep-{task}" / "tests" / "test.sh").read_text()
    m = re.search(r"<<'ANSWER_EOF'\n(.*?)\nANSWER_EOF", t, re.S)
    return m.group(1) if m else None

def guideline_of(task):
    t = (P / f"dabstep-{task}" / "instruction.md").read_text()
    m = re.search(r"guidelines you MUST follow when answering the question above: (.*?)\n", t)
    q = re.search(r"Here is the question you need to answer: (.*?)\n", t)
    return (m.group(1) if m else None), (q.group(1) if q else None)

def txt(content):
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in (content or []) if isinstance(c, dict) and c.get("type") == "text")

def parse_pi(p):
    turns = []
    cur = None
    entries = []
    try:
        f = open(p, errors="replace")
    except OSError:
        return None
    for line in f:
        try:
            e = json.loads(line)
        except Exception:
            continue
        t = e.get("type")
        if t == "turn_start":
            cur = {"i": len(turns) + 1, "calls": [], "outs": [], "text": "", "stop": None, "entries": []}
            turns.append(cur)
        elif t == "message_end" and cur is not None:
            m = e.get("message") or {}
            if m.get("role") == "assistant":
                cur["text"] = txt(m.get("content"))[:6000]
                cur["stop"] = m.get("stopReason")
                for c in (m.get("content") or []):
                    if isinstance(c, dict) and c.get("type") == "toolCall":
                        cur["calls"].append({"name": c.get("name"), "args": c.get("arguments")})
                # thinking?
                cur["thinking"] = "\n".join(c.get("thinking", "") for c in (m.get("content") or []) if isinstance(c, dict) and c.get("type") == "thinking")[:3000]
            elif m.get("role") == "toolResult":
                cur["outs"].append({"name": m.get("toolName"), "text": txt(m.get("content"))[:8000], "err": bool(m.get("isError"))})
        elif t == "entry_appended":
            en = e.get("entry") or {}
            ct = en.get("customType")
            if ct in ("vacant-budget", "vacant-check"):
                (cur["entries"] if cur else entries).append({"type": ct, "content": str(en.get("content"))[:1500]})
    return turns

rows = []
for res in sorted(L.glob("g12-off-*-s*/*/dabstep-*__*/result.json")):
    trial = res.parent
    arm, s = trial.parents[1].name.removeprefix("g12-off-").rsplit("-s", 1)
    task = trial.name.split("__")[0].removeprefix("dabstep-")
    r = json.loads(res.read_text())
    vr = r.get("verifier_result") or {}
    reward = (vr.get("rewards") or {}).get("reward")
    try:
        vout = (trial / "verifier" / "test-stdout.txt").read_text()
    except OSError:
        vout = ""
    got = re.search(r"Got: (.*)", vout)
    vc = None
    if (trial / "agent" / "vacant_check.json").exists():
        try:
            vc = json.loads((trial / "agent" / "vacant_check.json").read_text().strip().splitlines()[-1])
        except Exception:
            vc = None
    g, q = guideline_of(task)
    rows.append({"task": task, "arm": arm, "sample": int(s), "trial": str(trial), "reward": reward,
                 "exception": (r.get("exception_info") or {}).get("exception_type"),
                 "answer_file": ("answer.txt not found" not in vout) if vout else None,
                 "expected": expected_of(task), "got": got.group(1) if got else None,
                 "guideline": g, "question": q, "vc": vc, "turns": parse_pi(trial / "agent" / "pi.txt")})
with lzma.open(OUT / "runs_turns.json.xz", "wt") as f:
    json.dump(rows, f)
print(len(rows))
