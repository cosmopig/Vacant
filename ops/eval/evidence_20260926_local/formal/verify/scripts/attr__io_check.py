import json, collections
io=json.load(open("/tmp/claude-0/verify_formal/attr/io_scan.json"))
rows=json.load(open("/tmp/claude-0/verify_formal/attr/runs.json"))
EXC={"5","70"}
c=collections.Counter(); params=collections.Counter(); other=[]
for r in rows:
    tag=f"v3local-g12-off-{r['arm']}-{r['task']}-s{r['sample']}"
    d=io.get(tag)
    if not d: c[("missing",r["arm"])]+=1; continue
    for p in d["params"]: params[(r["arm"],p)]+=1
    if d["other_vacant"]: other.append((tag,d["other_vacant"]))
    hasN=d["nudge_first"] is not None; hasC=d["check_first"] is not None
    c[(r["arm"], "pi_nudge" if r["pi"]["nudges"] else "-", "io_nudge" if hasN else "-", "pi_chk" if r["pi"]["checks"] else "-", "io_chk" if hasC else "-")]+=1
for k in sorted(c, key=str): print(k, c[k])
print("other vacant mentions:", other[:10], len(other))
for k in sorted(params, key=str): print(params[k], k)
