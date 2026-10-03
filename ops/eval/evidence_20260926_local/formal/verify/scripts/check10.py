import json, pathlib, re, collections
F = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3")
rows = json.load(open("/tmp/claude-0/verify_formal/rows.json"))
rk = {(r["task"], r["arm"], r["sample"]): r for r in rows}
def vout(r):
    p = F / f"g12-off-{r['arm']}-s{r['sample']}" / r["job"] / r["trial"] / "verifier" / "test-stdout.txt"
    return p.read_text(errors="replace")
EX={"5","70"}
gain = []; loss=[]
for (t,a,s), r in rk.items():
    if a != "C2" or t in EX: continue
    ra = rk[(t,"A",s)]
    if r["reward"] and not ra["reward"]:
        v = vout(r); va = vout(ra)
        exp = re.search(r"Expected: (.*)", v); got = re.search(r"Got: (.*)", v)
        gain.append((t, s, exp and exp.group(1)[:60], got and got.group(1)[:60], "A:" + ("noans" if "not found" in va else "wrong")))
    if ra["reward"] and not r["reward"]:
        v = vout(r)
        loss.append((t, s, "C2:" + ("noans" if "not found" in v else "wrong")))
print("C2 correct & A not:", len(gain))
for g in sorted(gain, key=lambda x:(int(x[0]),x[1])): print("  ", g)
print("A correct & C2 not:", len(loss), collections.Counter(x[2] for x in loss))
# overall expected answer types in the gains
