import json, collections
rows = json.load(open("/tmp/claude-0/verify_formal/attr/runs.json"))
EXC={"5","70"}
R = {(r["task"], r["arm"], r["sample"]): r for r in rows}
cache={}
def calls(trial):
    if trial in cache: return cache[trial]
    out=[]; turn=0
    for line in open(trial+"/agent/pi.txt"):
        try: e=json.loads(line)
        except: continue
        if e.get("type")=="turn_start": turn+=1
        if e.get("type")=="tool_execution_start":
            out.append((turn, json.dumps([e.get("toolName"), e.get("args")], sort_keys=True)))
    cache[trial]=out; return out
def prefix_turn(x,y):
    """number of leading turns whose tool calls match exactly"""
    k=0
    while k<min(len(x),len(y)) and x[k]==y[k]: k+=1
    if k==min(len(x),len(y)) and len(x)==len(y): return 99
    return x[k][0]-1 if k<len(x) else (y[k][0]-1 if k<len(y) else 99)
def cmp(a1,s1,a2,s2):
    c=collections.Counter()
    for t in {r["task"] for r in rows}:
        if t in EXC: continue
        p=prefix_turn(calls(R[(t,a1,s1)]["trial"]), calls(R[(t,a2,s2)]["trial"]))
        c["identical" if p==99 else ("<=3" if p<=3 else "4-8" if p<=8 else "9-12" if p<=12 else ">=13")]+=1
    return dict(c)
for s in (1,2,3): print("A vs C2 same sample", s, cmp("A",s,"C2",s)); print("A vs C1 same sample", s, cmp("A",s,"C1",s))
print("A s1 vs A s2", cmp("A",1,"A",2)); print("A s1 vs A s3", cmp("A",1,"A",3)); print("A s2 vs A s3", cmp("A",2,"A",3))
# nudged C2 runs: did A (same sample) match up to the nudge turn?
c=collections.Counter(); ex=[]
for r in rows:
    if r["arm"]!="C2" or r["task"] in EXC or not r["pi"]["nudges"]: continue
    a=R[(r["task"],"A",r["sample"])]
    p=prefix_turn(calls(a["trial"]), calls(r["trial"]))
    n=r["pi"]["nudges"][0]
    c[("A matched through nudge turn" if p>=n else "diverged before nudge")]+=1
print(c)
print("--- matched-through-nudge natural experiments")
def st(r):
    if r["reward"] == 1.0: return "OK"
    return "NF" if r["answer_file"] is False else "WR"
for r in rows:
    if r["arm"]!="C2" or r["task"] in EXC or not r["pi"]["nudges"]: continue
    a=R[(r["task"],"A",r["sample"])]
    p=prefix_turn(calls(a["trial"]), calls(r["trial"]))
    if p>=r["pi"]["nudges"][0]:
        print(r["task"], r["sample"], "A:", st(a), a["pi"]["turns"], a["pi"]["writes"], " C2:", st(r), r["pi"]["turns"], r["pi"]["writes"], r["pi"]["nudges"], "prefix", p)
