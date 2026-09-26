import json, collections, re
rows = json.load(open("/tmp/claude-0/verify_formal/attr/runs.json"))
EXC={"5","70"}
def st(r):
    if r["reward"] == 1.0: return "OK"
    return "NF" if r["answer_file"] is False else "WR"
def tool_texts_before(trial, turn_lim):
    txt=[]; turn=0
    for line in open(trial+"/agent/pi.txt"):
        try: e=json.loads(line)
        except: continue
        t=e.get("type")
        if t=="turn_start": turn+=1
        if turn>turn_lim: break
        if t=="message_end":
            m=e.get("message") or {}
            if m.get("role") in ("toolResult","assistant"):
                for c in m.get("content") or []:
                    if c.get("type")=="text": txt.append(c.get("text",""))
                    if c.get("type")=="thinking": txt.append(c.get("thinking",""))
    return "\n".join(txt)
res=collections.Counter()
for r in rows:
    if r["arm"]!="C2" or r["task"] in EXC or not r["pi"]["nudges"]: continue
    w=r["pi"]["writes"]
    if not w or min(w)<=r["pi"]["nudges"][0]: continue
    got=(r["got"] or "").strip(); exp=(r["expected"] or "").strip()
    before=tool_texts_before(r["trial"], r["pi"]["nudges"][0])
    # sourced: the written answer string (or each comma part) appears in tool results/assistant text up to nudge turn
    parts=[p.strip() for p in re.split(r"[,;]", got) if p.strip()]
    src = bool(parts) and all(p in before for p in parts)
    res[(st(r), src)]+=1
    if st(r)=="OK": print(f"{r['task']:>5} s{r['sample']} OK exp={exp[:40]!r:44} got={got[:40]!r:44} value_seen_before_nudge={src}")
print(res)
