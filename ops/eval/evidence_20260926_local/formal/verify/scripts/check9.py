import sys, json, collections
sys.path.insert(0, "/home/user/Vacant/ops/eval/local")
import run_batch
tasks = json.load(open("/home/user/Vacant/ops/eval/pilot/tasks.json"))["formal_79"]
cells = run_batch.plan(tasks, ["A","C1","C2"], [1,2,3], 20260926, {"w401":3, "1003":1})
pos = collections.Counter()
for i in range(0, len(cells), 3):
    grp = cells[i:i+3]
    for j,c in enumerate(grp): pos[(c[3], c[1], j)] += 1
for up in ("w401","1003"):
    print(up, {a: [pos[(up,a,j)] for j in range(3)] for a in ("A","C1","C2")})
rows = json.load(open("/tmp/claude-0/verify_formal/rows.json"))
import datetime as dt
t = lambda x: dt.datetime.fromisoformat(x.replace("Z","+00:00"))
for up in ("w401","1003"):
    for a in ("A","C1","C2"):
        rs=[(t(r["finished"])-t(r["started"])).total_seconds() for r in rows if r["up"]==up and r["arm"]==a]
        rs.sort(); print(up, a, "n", len(rs), "median wall", round(rs[len(rs)//2]), "max", round(rs[-1]), ">1700s", sum(x>1700 for x in rs))
