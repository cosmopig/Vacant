import sys, json, collections
sys.path.insert(0, "/home/user/Vacant/ops/eval/local")
import run_batch
tasks = json.load(open("/home/user/Vacant/ops/eval/pilot/tasks.json"))["formal_79"]
cells = run_batch.plan(tasks, ["A","C1","C2"], [1,2,3], 20260926, {"w401":3, "1003":1})
print("planned", len(cells))
rows = json.load(open("/tmp/claude-0/verify_formal/rows.json"))
rk = {(r["task"], r["arm"], r["sample"]): r for r in rows}
# upstream matches plan
print("plan upstream mismatch:", [(c, rk[(c[0],c[1],c[2])]["up"]) for c in cells if rk[(c[0],c[1],c[2])]["up"] != c[3]])
# per machine, compare planned order vs actual start order (excluding the 3 reruns)
void = {("1273","A",3), ("1273","C2",3), ("69","C2",3)}
for up in ("w401","1003"):
    planned = [(c[0],c[1],c[2]) for c in cells if c[3]==up and (c[0],c[1],c[2]) not in void]
    actual = [k for k,_ in sorted(((k, r["started"]) for k,r in rk.items() if r["up"]==up and k not in void), key=lambda x: x[1])]
    # measure max displacement
    pos = {k:i for i,k in enumerate(actual)}
    disp = [abs(pos[k]-i) for i,k in enumerate(planned)]
    print(up, "n", len(planned), "max displacement", max(disp), "n displaced>5", sum(d>5 for d in disp))
# progress.jsonl order
prog = [json.loads(l) for l in open("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3/progress.jsonl")]
print("progress records", len(prog), "dups:", [k for k,v in collections.Counter((p["task"],p["arm"],p["sample"]) for p in prog).items() if v>1])
print("progress missing:", [k for k in rk if k not in {(p["task"],p["arm"],p["sample"]) for p in prog}])
print("rc!=0:", [p for p in prog if p["rc"]!=0]); print("has_result False:", [p for p in prog if not p["has_result"]])
print("progress upstream mismatch:", [p for p in prog if rk[(p["task"],p["arm"],p["sample"])]["up"] != p["upstream"]])
print("first/last at:", prog[0]["at"], prog[-1]["at"])
