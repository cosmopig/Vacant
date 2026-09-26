import json, collections
L="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3"
rows = json.load(open("/tmp/claude-0/verify_formal/attr/runs.json"))
R = {(r["task"], r["arm"], r["sample"]): r for r in rows}
def calls(trial):
    out=[]
    for line in open(trial+"/agent/pi.txt"):
        try: e=json.loads(line)
        except: continue
        if e.get("type")=="tool_execution_start":
            out.append(json.dumps([e.get("toolName"), e.get("args")], sort_keys=True))
    return out
pref = collections.Counter(); ident=0; tot=0
for (t,a,s),r in R.items():
    if a!="A": continue
    ca = calls(r["trial"]); cc = calls(R[(t,"C2",s)]["trial"])
    k=0
    while k<min(len(ca),len(cc)) and ca[k]==cc[k]: k+=1
    pref[min(k,5)]+=1; tot+=1
    if ca==cc: ident+=1
print("common prefix length of tool calls A vs C2 same task/sample (capped 5):", sorted(pref.items()), "identical:", ident, "of", tot)
