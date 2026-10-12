import json, collections, re
rows = json.load(open("/tmp/claude-0/verify_formal/attr/runs.json"))
EXC={"5","70"}
def texts(trial, upto=99):
    out=[]; turn=0
    for line in open(trial+"/agent/pi.txt"):
        try: e=json.loads(line)
        except: continue
        if e.get("type")=="turn_start": turn+=1
        if turn>upto: break
        if e.get("type")=="message_end":
            m=e.get("message") or {}
            if m.get("role") in ("toolResult","assistant"):
                for c in m.get("content") or []:
                    if c.get("type")=="text": out.append(c.get("text",""))
    return "\n".join(out)
def seen(exp, txt):
    exp=exp.strip()
    if not exp: return False
    try:
        x=float(exp)
        for tok in re.findall(r"-?\d+(?:\.\d+)?", txt):
            try:
                if abs(float(tok)-x) <= max(0.01, abs(x)*1e-4) : return True
            except: pass
        return False
    except ValueError:
        parts=[p.strip().lower() for p in exp.split(",") if p.strip()]
        return all(p in txt.lower() for p in parts)
c=collections.Counter()
for r in rows:
    if r["task"] in EXC or not r["expected"]: continue
    p=r["pi"]; w=p["writes"]; fw=min(w) if w else 99
    elig = p["turns"]>=14 and fw>13
    if not elig: continue
    s = seen(r["expected"], texts(r["trial"], 13))
    st = "OK" if r["reward"]==1.0 else ("NF" if r["answer_file"] is False else "WR")
    c[(r["arm"], "expected_value_seen_by_t13" if s else "not_seen", st)]+=1
for k in sorted(c): print(k, c[k])
