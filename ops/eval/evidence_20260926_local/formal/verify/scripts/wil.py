import json, itertools, collections
from fractions import Fraction
A="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/analysis_formal"
cells = json.load(open(A+"/cells.json"))
EX={"5","70"}
ck = {(c["task"], c["arm"], c["sample"]): c for c in cells}
tasks = sorted({c["task"] for c in cells if c["task"] not in EX}, key=int)
def mean(t,a): return Fraction(sum(1 for s in (1,2,3) if ck[(t,a,s)]["reward"]), 3)
def exact_wilcoxon(d):
    d=[x for x in d if x!=0]
    n=len(d); ab=sorted(abs(x) for x in d)
    # midranks
    ranks={}
    i=0
    while i<n:
        j=i
        while j+1<n and ab[j+1]==ab[i]: j+=1
        ranks[ab[i]]=Fraction(i+1+j+1,2); i=j+1
    r=[ranks[abs(x)] for x in d]
    wplus=sum(rr for rr,x in zip(r,d) if x>0)
    # exact distribution over sign flips using doubled ranks (integers)
    r2=[int(2*rr) for rr in r]
    dist=collections.Counter({0:1})
    for v in r2:
        nd=collections.Counter()
        for k,c in dist.items():
            nd[k]+=c; nd[k+v]+=c
        dist=nd
    total=2**n; W2=int(2*wplus); mu2=sum(r2)/2
    # two-sided: P(|W - mu| >= |w - mu|)
    dev=abs(W2-mu2)
    p=sum(c for k,c in dist.items() if abs(k-mu2)>=dev-1e-9)/total
    return float(wplus), n, p
for y,x in (("C2","A"),("C1","A"),("C2","C1")):
    d=[mean(t,y)-mean(t,x) for t in tasks]
    w,n,p=exact_wilcoxon(d)
    print(f"{y} vs {x}: tasks {len(d)} mean_diff {float(sum(d)/len(d)):.4f} better {sum(v>0 for v in d)} worse {sum(v<0 for v in d)} W+ {w} n {n} p {p:.4f}")
    print("   diffs:", collections.Counter(str(v) for v in d if v!=0))

print("--- sensitivity: drop (69,s3) and (1273,s3) for all arms")
drop = {("69",3), ("1273",3)}
def mean2(t,a):
    ss=[s for s in (1,2,3) if (t,s) not in drop]
    return Fraction(sum(1 for s in ss if ck[(t,a,s)]["reward"]), len(ss))
d=[mean2(t,"C2")-mean2(t,"A") for t in tasks]
print("C2 vs A", exact_wilcoxon(d), float(sum(d)/len(d)))
print("--- original values of those cells:", [(t,a,3,ck[(t,a,3)]["reward"]) for t in ("69","1273") for a in ("A","C1","C2")])
print("--- also frozen-function on same data")
import sys; sys.path.insert(0,"/home/user/Vacant")
from vacant_network.research import wilcoxon_signed_rank_exact
dd=[float(x) for x in d if x!=0]
print(wilcoxon_signed_rank_exact(dd))

print("--- fragility: drop tasks with guessable expected answers (23 '0', 62 'Not Applicable', 30 'yes')")
for drop_t in (["23","62"], ["23","62","30"]):
    tt=[t for t in tasks if t not in drop_t]
    d=[mean(t,"C2")-mean(t,"A") for t in tt]
    print(drop_t, exact_wilcoxon(d))
