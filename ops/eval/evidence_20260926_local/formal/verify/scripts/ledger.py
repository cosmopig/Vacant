import json, collections, sys
sys.path.insert(0, "/tmp/claude-0/verify_formal")
from load import load
rows,_ = load()
L = "/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/ledger/ledger.jsonl"
per = collections.defaultdict(lambda: dict(ok=0, err=0, se=0, ups=set(), ts=[]))
for ln in open(L):
    d = json.loads(ln)
    t = d.get("tag","")
    if not t.startswith("v3local-"): continue
    p = per[t]
    if d.get("status")==200 and not d.get("stream_error"): p["ok"]+=1
    else: p["err"]+=1
    if d.get("stream_error"): p["se"]+=1
    p["ups"].add(d.get("upstream")); p["ts"].append(d["ts"])
print("tags in ledger:", len(per))
tags = {f"v3local-g12-off-{a}-{t}-s{s}":(t,a,s) for (t,a,s) in rows}
print("result tags missing from ledger:", [t for t in tags if t not in per])
print("ledger tags without result:", [t for t in per if t not in tags])
print("zero-ok runs:", [t for t,p in per.items() if p["ok"]==0])
print("upstream mismatch:", [t for t,p in per.items() if t in tags and p["ups"]!={rows[tags[t]]["upstream"]}])
print("runs >15 ok requests:", [(t,p["ok"]) for t,p in per.items() if p["ok"]>15])
# errors by arm
E = collections.Counter(); R = collections.Counter(); runs_err = collections.Counter()
for t,p in per.items():
    if t not in tags: continue
    task,a,s = tags[t]
    if task in ("5","70"): continue
    E[a]+=p["err"]; R[a]+=p["ok"]; runs_err[a]+= p["err"]>0
print("errors by arm (77 tasks):", dict(E), "ok requests:", dict(R), "runs with any error:", dict(runs_err))
# requests per run by arm
import statistics
for a in ("A","C1","C2"):
    v=[per[f"v3local-g12-off-{a}-{t}-s{s}"]["ok"] for (t,aa,s) in rows if aa==a and t not in ("5","70")]
    print(a, "requests per run: mean %.2f median %s max %d; n=15: %d" % (statistics.mean(v), statistics.median(v), max(v), sum(x==15 for x in v)))
# the 3 rerun tags: split by gap
for t in ("v3local-g12-off-A-1273-s3","v3local-g12-off-C2-1273-s3","v3local-g12-off-C2-69-s3"):
    ts=sorted(per[t]["ts"]); gaps=[(b-a) for a,b in zip(ts,ts[1:])]; i=max(range(len(gaps)),key=lambda k:gaps[k])
    print(t, "total", len(ts), "split", i+1, len(ts)-i-1, "gap_s", round(gaps[i]))
