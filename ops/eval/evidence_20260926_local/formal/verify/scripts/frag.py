import sys, itertools
sys.path.insert(0, "/tmp/claude-0/verify_formal")
from load import load
from stats import *
rows,_ = load()
tasks77=[t for t in sorted({k[0] for k in rows},key=int) if t not in ("5","70")]
S=[1,2,3]
d=per_task_diffs(rows,"A","C2",tasks77,S)
big=[t for t,v in d.items() if abs(v)>=F(2,3)]
small_pos=[t for t,v in d.items() if v==F(1,3)]
cnt=0
for c in itertools.combinations(big,2):
    p=wilcoxon_exact([x for tt,x in d.items() if tt not in c])["p"]; cnt+=p>=0.05
print("remove 2 of 6 big-gain tasks: %d/15 pairs give p>=0.05"%cnt)
ps=[wilcoxon_exact([x for tt,x in d.items() if tt not in (b,s)])["p"] for b in big for s in small_pos]
print("remove 1 big + 1 (+1/3) task: %d/%d give p>=0.05, max %.4f"%(sum(p>=0.05 for p in ps),len(ps),max(ps)))
ps=[wilcoxon_exact([x for tt,x in d.items() if tt not in c])["p"] for c in itertools.combinations(small_pos,2)]
print("remove 2 (+1/3) tasks: %d/%d give p>=0.05, max %.4f"%(sum(p>=0.05 for p in ps),len(ps),max(ps)))
print("remove all 6 big tasks:", wilcoxon_exact([x for tt,x in d.items() if tt not in big]), "mean", float(sum(x for tt,x in d.items() if tt not in big))/71)
# C2-only fragility
def pval(rw): return wilcoxon_exact(list(per_task_diffs(rw,"A","C2",tasks77,S).values()))["p"]
for arm,fr,to in (("C2",1.0,0.0),("A",0.0,1.0)):
    rw={k:dict(v) for k,v in rows.items()}; fl=[]
    while pval(rw)<0.05:
        best=None
        for k,r in rw.items():
            if k[0] in tasks77 and k[1]==arm and r["reward"]==fr:
                r["reward"]=to; p=pval(rw); r["reward"]=fr
                if best is None or p>best[0]: best=(p,k)
        rw[best[1]]["reward"]=to; fl.append((best[1],round(best[0],4)))
    print(f"fragility flipping only {arm} {fr}->{to}:", fl)
# per-machine per-run rate difference and interaction bootstrap
import random
pairs={m:[] for m in ("w401","1003")}
for t in tasks77:
    for s in S:
        m=rows[(t,"A",s)]["upstream"]; pairs[m].append(int(rows[(t,"C2",s)]["reward"]==1)-int(rows[(t,"A",s)]["reward"]==1))
for m,v in pairs.items(): print(m, "task-samples",len(v),"C2-A per-run",round(sum(v)/len(v),4), "only_C2",v.count(1),"only_A",v.count(-1))
