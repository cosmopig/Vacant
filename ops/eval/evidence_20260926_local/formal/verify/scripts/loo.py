import sys, json, collections, itertools, math
sys.path.insert(0, "/tmp/claude-0/verify_formal")
from load import load
from stats import *
from fractions import Fraction as F
rows, _ = load()
alltasks = sorted({k[0] for k in rows}, key=int)
tasks77 = [t for t in alltasks if t not in ("5", "70")]
S=[1,2,3]
d = per_task_diffs(rows,"A","C2",tasks77,S)
nz = {t:v for t,v in d.items() if v!=0}
print("nonzero tasks:", {t:str(v) for t,v in sorted(nz.items(), key=lambda kv:-kv[1])})
for t,v in sorted(nz.items(), key=lambda kv:-kv[1]):
    def s(a): return "".join(("1" if rows[(t,a,k)]["reward"]==1 else ("-" if rows[(t,a,k)]["answer_missing"] else "x")) for k in S)
    ups = "".join(rows[(t,"A",k)]["upstream"][0] for k in S)
    print(f"  task {t:>5} diff {str(v):>5}  A={s('A')} C1={s('C1')} C2={s('C2')} machines={ups}")
# LOO
loo = []
for t in nz:
    v = [x for tt,x in d.items() if tt!=t]
    loo.append((wilcoxon_exact(v)["p"], t, str(d[t])))
loo.sort(reverse=True)
print("LOO max p:", loo[:6])
print("LOO: removing any single task keeps p<0.05?", all(p<0.05 for p,_,_ in loo))
# leave-k-out: max p over all subsets of size k among nonzero tasks
nzt = list(nz)
for k in (2,3):
    best = max((wilcoxon_exact([x for tt,x in d.items() if tt not in c])["p"], c) for c in itertools.combinations(nzt,k))
    cnt = sum(1 for c in itertools.combinations(nzt,k) if wilcoxon_exact([x for tt,x in d.items() if tt not in c])["p"]>=0.05)
    tot = math.comb(len(nzt),k)
    print(f"leave-{k}-out: max p={best[0]:.4f} removing {best[1]}; {cnt}/{tot} subsets give p>=0.05")
# fragility: flip single C2 runs correct->wrong (or A wrong->correct) greedily
import copy
def pval(rw):
    dd = per_task_diffs(rw,"A","C2",tasks77,S); return wilcoxon_exact(list(dd.values()))["p"]
rw = {k:dict(v) for k,v in rows.items()}
flips=[]
while pval(rw) < 0.05:
    best=None
    for (t,a,s),r in rw.items():
        if t not in tasks77: continue
        if a=="C2" and r["reward"]==1: nv=0.0
        elif a=="A" and r["reward"]!=1: nv=1.0
        else: continue
        old=r["reward"]; r["reward"]=nv; p=pval(rw); r["reward"]=old
        if best is None or p>best[0]: best=(p,(t,a,s),nv)
    rw[best[1]]["reward"]=best[2]; flips.append((best[1],round(best[0],4)))
print("greedy fragility (single-run outcome flips to reach p>=0.05):", flips)
# CMH over tasks (stratified by task, 3 A vs 3 C2 runs)
num=0.0; var=0.0; 
for t in tasks77:
    a=sum(rows[(t,"C2",s)]["reward"]==1 for s in S); b=3-a
    c=sum(rows[(t,"A",s)]["reward"]==1 for s in S); dd=3-c
    n=6; m1=a+c
    if m1 in (0,6): continue
    num += a - 3*m1/n
    var += 3*3*m1*(n-m1)/(n*n*(n-1))
chi=(abs(num)-0.5)**2/var; chi_nc=num**2/var
from math import erfc, sqrt
print(f"CMH (task strata): chi2_cc={chi:.3f} p={erfc(sqrt(chi/2)):.4f}; no cc chi2={chi_nc:.3f} p={erfc(sqrt(chi_nc/2)):.4f}")
# paired t
x=[float(v) for v in d.values()]; n=len(x); m=sum(x)/n; sd=(sum((v-m)**2 for v in x)/(n-1))**.5; t=m/(sd/n**.5)
try:
    from scipy import stats as st; print("paired t:", t, 2*st.t.sf(abs(t), n-1))
except Exception as e:
    print("paired t:", t, "(normal approx p)", erfc(abs(t)/sqrt(2)))
