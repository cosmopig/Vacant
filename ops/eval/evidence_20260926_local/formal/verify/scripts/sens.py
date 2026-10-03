import sys, json, collections, itertools
sys.path.insert(0, "/tmp/claude-0/verify_formal"); sys.path.insert(0, "/home/user/Vacant")
from load import load
from stats import *
from fractions import Fraction as F
from vacant_network.research import wilcoxon_signed_rank_exact, mcnemar_exact
rows, _ = load()
alltasks = sorted({k[0] for k in rows}, key=int)
tasks77 = [t for t in alltasks if t not in ("5", "70")]
S = [1, 2, 3]
def frozen(v):
    fl = [float(x) for x in v]
    return wilcoxon_signed_rank_exact([x for x in fl if x != 0])["p"]
def frozen_as_pipeline(rows, x, y, tasks, samples):
    fl=[]
    for t in tasks:
        a=[int(rows[(t,x,s)]["reward"]==1) for s in samples]; c=[int(rows[(t,y,s)]["reward"]==1) for s in samples]
        fl.append(sum(c)/len(c)-sum(a)/len(a))
    return wilcoxon_signed_rank_exact([z for z in fl if z!=0])
print("frozen pipeline C1 vs A:", frozen_as_pipeline(rows,"A","C1",tasks77,S))
print("frozen pipeline C2 vs C1:", frozen_as_pipeline(rows,"C1","C2",tasks77,S))
# per-sample McNemar
for s in S:
    for x, y in (("A","C2"),("A","C1"),("C1","C2")):
        b = sum(1 for t in tasks77 if rows[(t,y,s)]["reward"]==1 and rows[(t,x,s)]["reward"]!=1)
        c = sum(1 for t in tasks77 if rows[(t,x,s)]["reward"]==1 and rows[(t,y,s)]["reward"]!=1)
        print(f"s{s} {y} vs {x}: only_{y}={b} only_{x}={c} mcnemar p={mcnemar_exact(b,c):.4f}")
# per arm/sample counts from raw
for a in ("A","C1","C2"):
    for s in S:
        rs=[rows[(t,a,s)] for t in tasks77]
        print(a,s,"correct",sum(r["reward"]==1 for r in rs),"no_answer",sum(r["answer_missing"] for r in rs),"wrong",sum(r["reward"]!=1 and not r["answer_missing"] for r in rs))
# pooled cell-level McNemar (ignores task clustering)
b=sum(1 for t in tasks77 for s in S if rows[(t,"C2",s)]["reward"]==1 and rows[(t,"A",s)]["reward"]!=1)
c=sum(1 for t in tasks77 for s in S if rows[(t,"A",s)]["reward"]==1 and rows[(t,"C2",s)]["reward"]!=1)
print("pooled cells C2 vs A:", b, c, "mcnemar p (ignores clustering)", mcnemar_exact(b,c))
def R(name, diffs):
    r = report(name, diffs); r["frozen_float_p"] = round(frozen(diffs.values()),5); print(json.dumps(r))
print("\n== sensitivity C2 vs A ==")
R("primary 77 tasks, s1-3", per_task_diffs(rows,"A","C2",tasks77,S))
R("79 tasks incl 5,70", per_task_diffs(rows,"A","C2",alltasks,S))
R("samples 1-2 only", per_task_diffs(rows,"A","C2",tasks77,[1,2]))
R("samples 1-3 only", per_task_diffs(rows,"A","C2",tasks77,[1,3]))
R("samples 2-3 only", per_task_diffs(rows,"A","C2",tasks77,[2,3]))
for s in S:
    R(f"sample {s} only", per_task_diffs(rows,"A","C2",tasks77,[s]))
rerun = {("1273",3),("69",3)}
R("drop rerun task-samples (1273-s3, 69-s3) for all arms", per_task_diffs(rows,"A","C2",tasks77,S, cell_filter=lambda r:(r["task"],r["sample"]) not in rerun))
R("drop tasks 1273 and 69 entirely", per_task_diffs(rows,"A","C2",[t for t in tasks77 if t not in ("1273","69")],S))
for m in ("w401","1003"):
    R(f"machine {m} only", per_task_diffs(rows,"A","C2",tasks77,S, cell_filter=lambda r,m=m: r["upstream"]==m))
# timeouts
print("AgentTimeoutError cells:", [(k, r["upstream"]) for k,r in rows.items() if r["exc"]])
R("drop task-samples with any AgentTimeoutError", per_task_diffs(rows,"A","C2",tasks77,S, cell_filter=lambda r: not any(rows[(r["task"],a,r["sample"])]["exc"] for a in ("A","C1","C2"))))
