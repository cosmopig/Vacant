import json, re, pathlib, collections, sys
sys.path.insert(0, "/tmp/claude-0/review_effect/headroom")
from parse import expected_of, guideline_of, WRITE_BASH
P = pathlib.Path("/tmp/claude-0/review_effect/headroom/paid/jobs")
runs = json.load(open("/home/user/Vacant/ops/eval/evidence_20260925/formal/runs.json"))
def parse(p):
    turn = 0; ev = dict(chunks=[], calls=[], writes=[], nudges=[], stops=[], turns=0)
    for line in open(p):
        try: e = json.loads(line)
        except Exception: continue
        t = e.get("type")
        if t == "turn_start": turn += 1
        elif t == "message_end":
            m = e.get("message") or {}; role = m.get("role")
            for c in m.get("content") or []:
                if not isinstance(c, dict): continue
                if c.get("type") == "text" and role in ("assistant", "toolResult"):
                    ev["chunks"].append(dict(turn=turn, role=role, err=bool(m.get("isError")) if role == "toolResult" else False, tool=m.get("toolName"), call_id=m.get("toolCallId"), text=c.get("text", "")))
                elif c.get("type") == "thinking":
                    ev["chunks"].append(dict(turn=turn, role="thinking", err=False, tool=None, call_id=None, text=c.get("thinking", "")))
                elif c.get("type") == "toolCall":
                    name = c.get("name"); args = c.get("arguments") or {}
                    ev["calls"].append(dict(turn=turn, name=name, id=c.get("id"), args=args))
                    wrote = None
                    if name in ("write", "edit") and str(args.get("path") or "").endswith("answer.txt"): wrote = str(args.get("content"))
                    elif name == "bash" and "answer.txt" in str(args.get("command")) and WRITE_BASH.search(str(args.get("command"))): wrote = str(args.get("command"))
                    if wrote is not None: ev["writes"].append(dict(turn=turn, content=wrote[:500]))
        elif t == "turn_end":
            ev["stops"].append((turn, (e.get("message") or {}).get("stopReason")))
    ev["turns"] = turn
    return ev
out = []
for r in runs:
    if r["infra_void"]: continue
    tr = P / r["job"] / r["trial"]
    vout = (tr / "verifier" / "test-stdout.txt").read_text() if (tr / "verifier" / "test-stdout.txt").exists() else ""
    got = re.search(r"Got: (.*)", vout)
    vc = None
    if (tr / "agent" / "vacant_check.json").exists():
        try: vc = json.loads((tr / "agent" / "vacant_check.json").read_text().strip().splitlines()[-1])
        except Exception: pass
    g, q = guideline_of(r["task"])
    out.append(dict(task=r["task"], arm=r["arm"], model=r["model"], sample=1, reward=r["reward"], file=("answer.txt not found" not in vout) if vout else None,
                    got=got.group(1) if got else None, expected=expected_of(r["task"]), guideline=g, nreq=r["requests"], cost=r["cost_usd"], exc=r["exception"], vc=vc,
                    pi=parse(tr / "agent" / "pi.txt")))
json.dump(out, open("/tmp/claude-0/review_effect/headroom/paid_runs.json", "w"))
print(len(out), collections.Counter((x["model"], x["arm"], x["reward"], x["file"]) for x in out))
