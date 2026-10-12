import json, sys, pathlib
R = pathlib.Path(sys.argv[1])
print("==", R.name, (R/"exit.txt").read_text().strip() if (R/"exit.txt").exists() else "")
for ln in (R/"probe.jsonl").read_text().splitlines():
    e = json.loads(ln); pid = e.pop("pid"); ch = e.pop("child")
    print(("  CHILD " if ch else "  ") + json.dumps(e, ensure_ascii=False))
print(" -- model requests (mock.jsonl) --")
for ln in (R/"mock.jsonl").read_text().splitlines():
    r = json.loads(ln)
    if r.get("method") != "POST": continue
    msgs = r["body"].get("messages", [])
    tail = []
    for m in msgs[-4:]:
        c = m.get("content")
        s = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
        tags = [t for t in ("VACANT-INJECT-AT-TURN1","VACANT-INJECT-AT-TURN2","VACANT-INJECT-AT-TURN3","VACANT-FOLLOWUP","CHILD-TASK") if t in (s or "")]
        tail.append(f"{m['role']}{tags if tags else ''}")
    sysm = [m for m in msgs if m["role"] in ("system","developer")]
    budget = any("hard budget of" in json.dumps(m) for m in sysm)
    allinj = [t for t in ("VACANT-INJECT-AT-TURN3",) if t in json.dumps(msgs)]
    print(f"  req#{r['i']} step={r['step']} nmsgs={len(msgs)} tail={tail} budget_in_sys={budget} has_turn3_inject={bool(allinj)}")
if (R/"proj"/"answer.txt").exists(): print("  answer.txt =", (R/"proj"/"answer.txt").read_text().strip())
err = (R/"stderr.txt").read_text().strip() if (R/"stderr.txt").exists() else ""
if err: print("  stderr:", err[:500])
