import json, collections, math
from fractions import Fraction as F
exec(open("decomp.py").read().split("# baseline")[0])
def elig(r):
    p=r["pi"]; w=p["writes"]; fw=min(w) if w else 99
    return p["turns"]>=14 and fw>13
de=[]; dn=[]
for t in tasks:
    ce=sum(ok(R[(t,"C2",s)]) for s in (1,2,3) if elig(R[(t,"C2",s)])); ae=sum(ok(R[(t,"A",s)]) for s in (1,2,3) if elig(R[(t,"A",s)]))
    cn=sum(ok(R[(t,"C2",s)]) for s in (1,2,3) if not elig(R[(t,"C2",s)])); an=sum(ok(R[(t,"A",s)]) for s in (1,2,3) if not elig(R[(t,"A",s)]))
    de.append(F(ce-ae,3)); dn.append(F(cn-an,3))
print("eligible-stratum per-task diffs:", wilcoxon(de), "sum runs", sum(3*x for x in de))
print("non-eligible-stratum per-task diffs:", wilcoxon(dn), "sum runs", sum(3*x for x in dn))
# Fisher exact 4/79 vs 26/82
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    def p(x): return math.comb(r1,x)*math.comb(n-r1,c1-x)/math.comb(n,c1)
    p0=p(a); return sum(p(x) for x in range(max(0,c1-(n-r1)), min(r1,c1)+1) if p(x)<=p0*(1+1e-9))
print("Fisher eligible A 4/79 vs C2 26/82:", fisher(4,75,26,56))
print("Fisher non-eligible A 116/152 vs C2 111/149:", fisher(116,36,111,38))
# leave-one-task-out on primary
d0 = {t: F(sum(ok(R[(t,"C2",s)]) for s in (1,2,3)) - sum(ok(R[(t,"A",s)]) for s in (1,2,3)), 3) for t in tasks}
ps=[]
for t in tasks:
    if d0[t]==0: continue
    ps.append((wilcoxon([d0[u] for u in tasks if u!=t])["p"], t))
ps.sort(reverse=True); print("leave-one-out max p:", ps[:4])
# drop tasks better only via no-action runs (33,51,65) -- and symmetric: drop worse tasks with no v3 action in the losing runs
for drop in (["33","51","65"], ["33","51","65","12","47"], ["23","35","62"], ["23"], ["62"]):
    w=wilcoxon([d0[u] for u in tasks if u not in drop]); print("drop", drop, round(w["p"],4), w["pos"], w["neg"])
