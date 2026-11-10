"""Score llm_forced.py predictions against model-free baselines on the same cells.

Baselines come from hier.py (cache: ~/.cache/vacant/twin2k500/hier_results.pkl, key S10/S20):
  ITEM_MAJ     item-level majority of the other people (ignores price)
  PRICE_PRIOR  price-aware population logistic, no personal data (K=0)
  PRICE_K5     PRICE_PRIOR + personal residual from 5 other own decisions
Missing / unparsable LLM answers count as misses. Paired McNemar (exact) + person
bootstrap; Wilson 95% CI; ask curve = abstain on the lowest |p_A-0.5| fraction.

  python score_forced.py --pred ~/.cache/vacant/llm_forced_10/predictions.jsonl --sample-key S10
"""
import argparse, json, math, pickle, random
from collections import defaultdict
from pathlib import Path
from scipy.stats import binomtest

SEED = 20261109

def wilson(h, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = h / n; d = 1 + z * z / n; c = p + z * z / (2 * n); s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - s) / d, (c + s) / d

def mcnemar(base, new):
    b = sum(1 for x, y in zip(base, new) if y and not x); c = sum(1 for x, y in zip(base, new) if x and not y)
    return b, c, (binomtest(b, b + c, .5).pvalue if b + c else 1.0)

def boot(base, new, people, n=2000):
    rng = random.Random(0); byp = defaultdict(list)
    for x, y, p in zip(base, new, people):
        byp[p].append(int(y) - int(x))
    ks = list(byp); res = []
    for _ in range(n):
        s = [v for k in (rng.choice(ks) for _ in ks) for v in byp[k]]; res.append(sum(s) / len(s))
    res.sort(); return res[int(.025 * n)], res[int(.975 * n)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--sample-key", default="S10")
    ap.add_argument("--hier", default=str(Path.home() / ".cache/vacant/twin2k500/hier_results.pkl"))
    ap.add_argument("--out")
    a = ap.parse_args()
    H = pickle.load(open(a.hier, "rb"))[a.sample_key]
    truth, base = {}, {"ITEM_MAJ": {}, "PRICE_PRIOR": {}, "PRICE_K5": {}}
    for p, q, pred, y, itemmaj in H[0]:
        truth[(p, q)] = y; base["PRICE_PRIOR"][(p, q)] = pred == y; base["ITEM_MAJ"][(p, q)] = itemmaj == y
    for p, q, pred, y, _ in H[5]:
        base["PRICE_K5"][(p, q)] = pred == y
    arms = defaultdict(dict)
    for line in open(Path(a.pred).expanduser()):
        r = json.loads(line)
        k = (r["pid"], r["qid"])
        order = random.Random(f"{SEED}:{r['pid']}:{r['qid']}").randrange(2)
        if r["prediction"] in ("A", "B"):
            canon = 0 if (r["prediction"] == "A") == (order == 0) else 1
            assert (r["truth"] == "A") == ((truth[k] == 0) == (order == 0)), "label/order mismatch"
            ok = canon == truth[k]
        else:
            ok = False
        pa = r["p_A"] if isinstance(r["p_A"], (int, float)) else 0.5
        arms[r["arm"]][k] = (ok, abs(pa - 0.5), r["prediction"] is None)
    keys = sorted(truth)
    out = []
    w = out.append
    w(f"# llm_forced scoring ({a.sample_key}, {len(keys)} cells)\n")
    w("| Arm | Answered | Strict acc. | Wilson 95% | vs ITEM_MAJ | vs PRICE_PRIOR | vs PRICE_K5 |")
    w("|---|---:|---:|---|---|---|---|")
    rows = {n: {k: base[n][k] for k in keys} for n in base}
    for arm, d in sorted(arms.items()):
        rows[arm] = {k: (d[k][0] if k in d else False) for k in keys}
    for name, d in rows.items():
        c = [d[k] for k in keys]; h = sum(c); lo, hi = wilson(h, len(c))
        ans = sum(1 for k in keys if k in arms.get(name, {}) and not arms[name][k][2]) if name in arms else len(keys)
        cells = []
        for bn in ("ITEM_MAJ", "PRICE_PRIOR", "PRICE_K5"):
            if bn == name:
                cells.append("—"); continue
            bl = [rows[bn][k] for k in keys]; b, cc, p = mcnemar(bl, c); bt = boot(bl, c, [k[0] for k in keys])
            cells.append(f"{(h - sum(bl)) / len(c):+.3f} (b={b}, c={cc}, p={p:.2g}, boot [{bt[0]:+.3f},{bt[1]:+.3f}])")
        w(f"| {name} | {ans}/{len(keys)} | {h / len(c):.3f} ({h}/{len(c)}) | {lo:.3f}–{hi:.3f} | " + " | ".join(cells) + " |")
    if "FORCED_NONE" in arms and "FORCED_PRECEDENT5" in arms:
        bl = [rows["FORCED_NONE"][k] for k in keys]; nw = [rows["FORCED_PRECEDENT5"][k] for k in keys]
        b, cc, p = mcnemar(bl, nw); bt = boot(bl, nw, [k[0] for k in keys])
        w(f"\nFORCED_PRECEDENT5 − FORCED_NONE: {(sum(nw) - sum(bl)) / len(keys):+.3f} (b={b}, c={cc}, McNemar p={p:.2g}, boot [{bt[0]:+.3f},{bt[1]:+.3f}])")
    w("\n## Ask curve (abstain on lowest-confidence fraction; accuracy on the rest)\n")
    w("| Arm | ask 0% | 10% | 20% | 30% | 50% |"); w("|---|---|---|---|---|---|")
    for arm, d in sorted(arms.items()):
        rr = sorted(((d[k][1] if k in d else 0.0, rows[arm][k]) for k in keys), key=lambda t: -t[0])
        cells = []
        for f in (0, .1, .2, .3, .5):
            kept = rr[:int(round(len(rr) * (1 - f)))]; h = sum(x[1] for x in kept); lo, hi = wilson(h, len(kept))
            cells.append(f"{h / len(kept):.3f} ({h}/{len(kept)}; {lo:.3f}–{hi:.3f})")
        w(f"| {arm} | " + " | ".join(cells) + " |")
    text = "\n".join(out) + "\n"
    print(text)
    if a.out:
        Path(a.out).expanduser().write_text(text)

if __name__ == "__main__":
    main()
