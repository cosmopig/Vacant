"""Process-based relaunch policies (no answer judged): relaunch when the delivery has a process red flag;
deliver the first attempt without a red flag, else the earliest attempt that delivered a file."""
import json, collections, itertools
R = json.load(open("/tmp/claude-0/review_effect/headroom/runs.json"))
R = [r for r in R if r["task"] not in ("5", "70")]
by = collections.defaultdict(dict)
for r in R: by[(r["arm"], r["task"])][r["sample"]] = r
tasks = sorted({r["task"] for r in R}, key=int)
def ok(r): return r["reward"] == 1.0
def nf(r): return r["file"] is False
def late(r):
    n = r["pi"]["nudges"]; w = [x["turn"] for x in r["pi"]["writes"]]
    return bool(n and w and min(w) >= min(n))
def prose(r):
    g = (r["got"] or "").strip(); return len(g.split()) >= 6
def sentback_unresolved(r):
    a = (r.get("vc") or {}).get("review_actions") or []; return bool(a) and a[-1] != "allow"
def run(arm, red, max_att):
    acc = ex = exreq = 0; n = 0
    for t in tasks:
        runs = [by[(arm, t)][s] for s in (1, 2, 3)]
        for perm in itertools.permutations(runs):
            used = 0; chosen = None
            for k in range(max_att):
                used += 1
                if not red(perm[k]): chosen = perm[k]; break
            if chosen is None:
                files = [p for p in perm[:used] if not nf(p)]
                chosen = files[0] if files else perm[0]
            acc += ok(chosen); ex += used - 1; exreq += sum(p["nreq"] for p in perm[1:used]); n += 1
    return acc / n, ex / n * 1.0, exreq / n
base = {a: sum(ok(r) for r in R if r["arm"] == a) / 231 for a in ("A", "C1", "C2")}
pol = {"NF": nf, "NF|late": lambda r: nf(r) or late(r), "NF|late|prose": lambda r: nf(r) or late(r) or prose(r),
       "NF|unresolved-sendback": lambda r: nf(r) or sentback_unresolved(r),
       "NF|late|unresolved": lambda r: nf(r) or late(r) or sentback_unresolved(r)}
for a in ("A", "C1", "C2"):
    for name, f in pol.items():
        for m in (2, 3):
            acc, ex, exr = run(a, f, m)
            print(f"{a:3s} base {base[a]:.3f} relaunch-on[{name:22s}] max {m}: {acc:.3f} ({(acc-base[a])*100:+.1f} pp) extra attempts/task {ex:.2f}, extra requests/task {exr:.1f}")
# per-task where gains come from for A NF relaunch (max 2)
print("\nA relaunch-on-NF(max2) gain by task (expected acc - base):")
g = []
for t in tasks:
    runs = [by[("A", t)][s] for s in (1, 2, 3)]
    b = sum(ok(r) for r in runs) / 3
    acc = 0
    for perm in itertools.permutations(runs):
        acc += ok(perm[0]) if not nf(perm[0]) else ok(perm[1])
    acc /= 6
    if acc - b > 1e-9: g.append((t, round(acc - b, 3), [("OK" if ok(r) else "NF" if nf(r) else "WR") for r in runs]))
for x in sorted(g, key=lambda x: -x[1]): print("  ", x)
print("sum gain (tasks):", round(sum(x[1] for x in g), 2), "=", round(sum(x[1] for x in g) / 77 * 100, 1), "pp")
