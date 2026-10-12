import json, re, glob, pathlib, sys
L = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3")
WRITE_BASH = re.compile(r"(>>?\s*['\"]?(/app/)?answer\.txt)|(tee\s+(-a\s+)?['\"]?(/app/)?answer\.txt)|((cp|mv)\s+\S+\s+['\"]?(/app/)?answer\.txt)|(open\([^)]*answer\.txt[^)]*['\"][wa]['\"])|(write_text)")
def parse_pi(p):
    turn = 0
    ev = {"turns": 0, "writes": [], "bash_mentions": [], "nudges": [], "checks": [], "check_texts": [],
          "stop_turns": [], "last_stop": None, "final_text": None, "texts": [], "write_contents": []}
    try:
        f = open(p)
    except OSError:
        return None
    for line in f:
        try:
            e = json.loads(line)
        except Exception:
            continue
        t = e.get("type")
        if t == "turn_start":
            turn += 1
        elif t == "tool_execution_start":
            name = e.get("toolName"); args = e.get("args") or {}
            if name in ("write", "edit"):
                path = str(args.get("path") or args.get("file_path") or "")
                if path.endswith("answer.txt"):
                    ev["writes"].append(turn); ev["write_contents"].append((turn, str(args.get("content"))[:200]))
            elif name == "bash":
                cmd = str(args.get("command") or "")
                if "answer.txt" in cmd:
                    ev["bash_mentions"].append(turn)
                    if WRITE_BASH.search(cmd) and "answer.txt" in cmd:
                        ev["writes"].append(turn); ev["write_contents"].append((turn, cmd[:200]))
        elif t == "entry_appended":
            en = e.get("entry") or {}
            ct = en.get("customType")
            if ct == "vacant-budget":
                ev["nudges"].append(turn)
            elif ct == "vacant-check":
                ev["checks"].append(turn); ev["check_texts"].append(str(en.get("content"))[:600])
        elif t == "turn_end":
            m = e.get("message") or {}
            sr = m.get("stopReason"); ev["last_stop"] = sr
            if sr == "stop":
                ev["stop_turns"].append(turn)
                txt = " ".join(c.get("text", "") for c in (m.get("content") or []) if c.get("type") == "text")
                ev["texts"].append((turn, txt[:400]))
    ev["turns"] = turn
    return ev

rows = []
for res in sorted(L.glob("g12-off-*-s*/*/dabstep-*__*/result.json")):
    trial = res.parent
    arm, s = trial.parents[1].name.removeprefix("g12-off-").rsplit("-s", 1)
    task = trial.name.split("__")[0].removeprefix("dabstep-")
    r = json.loads(res.read_text())
    vr = r.get("verifier_result") or {}
    reward = (vr.get("rewards") or {}).get("reward", vr.get("reward"))
    try:
        vout = (trial / "verifier" / "test-stdout.txt").read_text()
    except OSError:
        vout = ""
    exp = re.search(r"Expected: (.*)", vout); got = re.search(r"Got: (.*)", vout)
    vc = None
    if (trial / "agent" / "vacant_check.json").exists():
        try: vc = json.loads((trial / "agent" / "vacant_check.json").read_text().strip().splitlines()[-1])
        except Exception: vc = None
    ev = parse_pi(trial / "agent" / "pi.txt")
    rows.append({"task": task, "arm": arm, "sample": int(s), "trial": str(trial), "reward": reward,
                 "started": r.get("started_at"), "exception": (r.get("exception_info") or {}).get("exception_type"),
                 "answer_file": (False if "answer.txt not found" in vout else True if "Got:" in vout else None),
                 "expected": exp.group(1) if exp else None, "got": got.group(1) if got else None,
                 "vc": vc, "pi": ev})
json.dump(rows, open("/tmp/claude-0/verify_formal/attr/runs.json", "w"))
print(len(rows))
