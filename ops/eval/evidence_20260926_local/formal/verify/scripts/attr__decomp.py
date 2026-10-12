import json, collections
from fractions import Fraction as F
rows = json.load(open("/tmp/claude-0/verify_formal/attr/runs.json"))
EXC = {"5", "70"}
R = {(r["task"], r["arm"], r["sample"]): r for r in rows}
tasks = sorted({r["task"] for r in rows if r["task"] not in EXC}, key=int)
def ok(r): return 1 if r["reward"] == 1.0 else 0
def cat(r):
    p = r["pi"]; w = p["writes"]; fw = min(w) if w else None
    if p["nudges"] and fw is not None and fw > p["nudges"][0]: return "N"
    if p["checks"] and fw is not None and fw > p["checks"][0]: return "K"
    return "0"
def wilcoxon(diffs):
    pairs = [abs(d) for d in diffs if d != 0]; signs = [1 if d > 0 else -1 for d in diffs if d != 0]
    n = len(pairs)
    if n == 0: return None
    order = sorted(range(n), key=lambda i: pairs[i]); ranks = [F(0)] * n; i = 0
    while i < n:
        j = i
        while j + 1 < n and pairs[order[j + 1]] == pairs[order[i]]: j += 1
        for t in range(i, j + 1): ranks[order[t]] = F(i + j, 2) + 1
        i = j + 1
    wp = sum(r for r, s in zip(ranks, signs) if s > 0); mean = sum(ranks) / 2
    counts = collections.Counter({F(0): 1})
    for r in ranks:
        nc = collections.Counter()
        for k, v in counts.items(): nc[k + r] += v; nc[k] += v
        counts = nc
    dev = abs(wp - mean)
    p = F(sum(v for k, v in counts.items() if abs(k - mean) >= dev), 2 ** n)
    return dict(n=n, w_plus=float(wp), p=float(p), pos=sum(1 for s in signs if s > 0), neg=sum(1 for s in signs if s < 0))
# baseline
d0 = [F(sum(ok(R[(t,"C2",s)]) for s in (1,2,3)) - sum(ok(R[(t,"A",s)]) for s in (1,2,3)), 3) for t in tasks]
print("reported primary (recomputed exact, rational ranks):", wilcoxon(d0), "mean", float(sum(d0)/len(d0)))
# categories of C2 correct runs
tot = collections.Counter()
for t in tasks:
    for s in (1,2,3):
        r = R[(t,"C2",s)]
        tot[(cat(r), "OK" if ok(r) else "no")] += 1
print("C2 runs by (category, correct):", dict(tot))
print("A correct", sum(ok(R[(t,'A',s)]) for t in tasks for s in (1,2,3)), "C2 correct", sum(ok(R[(t,'C2',s)]) for t in tasks for s in (1,2,3)))
# counterfactual 1: strip correct runs that came from nudge (N) -> 0
def cf(strip):
    d=[]
    for t in tasks:
        c = sum(ok(R[(t,"C2",s)]) and cat(R[(t,"C2",s)]) not in strip for s in (1,2,3))
        a = sum(ok(R[(t,"A",s)]) for s in (1,2,3))
        d.append(F(c - a, 3))
    return wilcoxon(d), float(sum(d)/len(d))
print("strip nudge-driven corrects:", cf({"N"}))
print("strip nudge+check-driven corrects:", cf({"N","K"}))
# counterfactual 2: keep only the nudge channel: C2' = A outcome except eligible-stratum A runs replaced... (not per-run identifiable) -> skip
# per-task table for better/worse
print()
for t in tasks:
    a = [ok(R[(t,"A",s)]) for s in (1,2,3)]; c = [ok(R[(t,"C2",s)]) for s in (1,2,3)]
    if sum(c) == sum(a): continue
    cats = [cat(R[(t,"C2",s)]) for s in (1,2,3)]
    cN = sum(1 for s in range(3) if c[s] and cats[s]=="N"); cK = sum(1 for s in range(3) if c[s] and cats[s]=="K"); c0 = sum(1 for s in range(3) if c[s] and cats[s]=="0")
    print(f"task {t:>5} A={sum(a)} C2={sum(c)} diff={sum(c)-sum(a):+d}  C2 correct via nudge={cN} check={cK} none={c0}  C2 cats={cats}")
