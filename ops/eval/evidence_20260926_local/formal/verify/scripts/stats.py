import sys, math, random, collections, json
from fractions import Fraction as F
sys.path.insert(0, "/tmp/claude-0/verify_formal")
from load import load

def wilcoxon_exact(diffs, zero="wilcox"):
    """Exact two-sided Wilcoxon signed-rank with exact (Fraction) midranks.
    zero='wilcox' drops zeros; 'pratt' ranks zeros then drops them from the statistic."""
    d = [F(x) for x in diffs]
    if zero == "wilcox":
        d = [x for x in d if x != 0]
    absd = sorted(set(abs(x) for x in d))
    # midranks
    order = sorted(d, key=abs)
    rank_of = {}
    i = 0
    n = len(order)
    while i < n:
        j = i
        while j + 1 < n and abs(order[j+1]) == abs(order[i]):
            j += 1
        rank_of[abs(order[i])] = F(i + j + 2, 2)
        i = j + 1
    ranks = [rank_of[abs(x)] for x in d if x != 0]
    signs = [1 if x > 0 else -1 for x in d if x != 0]
    wplus = sum(r for r, s in zip(ranks, signs) if s > 0)
    # exact null distribution via DP on doubled ranks (integers)
    ir = [int(r * 2) for r in ranks]
    dist = collections.Counter({0: 1})
    for r in ir:
        nd = collections.Counter()
        for k, c in dist.items():
            nd[k] += c; nd[k + r] += c
        dist = nd
    total2 = sum(ir)
    mean2 = F(total2, 2)
    w2 = int(wplus * 2)
    dev = abs(w2 - mean2)
    ext = sum(c for k, c in dist.items() if abs(k - mean2) >= dev)
    return dict(n=len(ranks), wplus=float(wplus), p=ext / 2 ** len(ranks))

def sign_test(pos, neg):
    n = pos + neg
    if n == 0: return 1.0
    k = min(pos, neg)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)

def perm_mean(diffs):
    """exact sign-flip permutation test on the sum of diffs (two-sided)."""
    d = [F(x) for x in diffs if x != 0]
    den = 1
    for x in d: den = den * x.denominator // math.gcd(den, x.denominator)
    iv = [int(abs(x) * den) for x in d]
    obs = int(sum(x for x in d) * den)
    dist = collections.Counter({0: 1})
    for v in iv:
        nd = collections.Counter()
        for k, c in dist.items():
            nd[k + v] += c; nd[k - v] += c
        dist = nd
    ext = sum(c for k, c in dist.items() if abs(k) >= abs(obs))
    return ext / 2 ** len(iv)

def boot_ci(diffs, B=20000, seed=1):
    rng = random.Random(seed)
    n = len(diffs); x = [float(v) for v in diffs]
    ms = sorted(sum(x[rng.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return ms[int(0.025 * B)], ms[int(0.975 * B) - 1]

def paired_t(diffs):
    x = [float(v) for v in diffs]; n = len(x); m = sum(x) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1))
    t = m / (sd / math.sqrt(n))
    # two-sided p from t with n-1 df via scipy-free approximation: use incomplete beta
    return t, n - 1

def per_task_diffs(rows, x, y, tasks, samples, cell_filter=lambda r: True):
    diffs = {}
    for t in tasks:
        keep = [s for s in samples if all((t, a, s) in rows and cell_filter(rows[(t, a, s)]) for a in (x, y))]
        if not keep: continue
        px = F(sum(int(rows[(t, x, s)]["reward"] == 1) for s in keep), len(keep))
        py = F(sum(int(rows[(t, y, s)]["reward"] == 1) for s in keep), len(keep))
        diffs[t] = py - px
    return diffs

def report(name, diffs):
    v = list(diffs.values())
    pos = sum(1 for d in v if d > 0); neg = sum(1 for d in v if d < 0)
    w = wilcoxon_exact(v)
    wp = wilcoxon_exact(v, zero="pratt")
    out = dict(name=name, tasks=len(v), mean=round(float(sum(v)) / len(v), 4), better=pos, worse=neg,
               wilcoxon_p=round(w["p"], 5), wplus=w["wplus"], n=w["n"], pratt_p=round(wp["p"], 5),
               sign_p=round(sign_test(pos, neg), 5), perm_p=round(perm_mean(v), 5),
               boot95=tuple(round(c, 4) for c in boot_ci(v)))
    return out
