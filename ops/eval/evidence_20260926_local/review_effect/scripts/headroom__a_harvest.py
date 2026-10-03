"""(a) Harvest ceiling on the local formal batch."""
import json, collections, sys
sys.path.insert(0, "/tmp/claude-0/review_effect/headroom")
from vis import visibility, kind, match_text
from scorer import question_scorer

R = json.load(open("/tmp/claude-0/review_effect/headroom/runs.json"))
EXC = {"5", "70"}
R = [r for r in R if r["task"] not in EXC]


def status(r):
    if r["reward"] == 1.0:
        return "OK"
    return "NF" if r["file"] is False else "WR"


rows = []
for r in R:
    v = visibility(r)
    p = r["pi"]
    w = [x["turn"] for x in p["writes"]]
    nud = p["nudges"]
    rows.append(dict(task=r["task"], arm=r["arm"], s=r["sample"], st=status(r), kind=v["kind"], t1=v["t1_first"], t2=v["t2_first"],
                     t1a=v["t1_assistant_first"], last=v["last_short_match"], turns=p["turns"], writes=w,
                     first_write=min(w) if w else None, nudged=bool(nud), nudge_turns=nud,
                     wrote_after_nudge=bool(nud and w and max(w) >= min(nud) + 0 and any(x > min(nud) - 1 for x in w if x >= min(nud))),
                     got=r["got"], exp=r["expected"], nreq=r["nreq"]))
json.dump(rows, open("/tmp/claude-0/review_effect/headroom/a_rows.json", "w"))

N = collections.Counter(x["arm"] for x in rows)
print("runs per arm (77 tasks x3):", dict(N))
print("\nstatus by arm:", {a: dict(collections.Counter(x["st"] for x in rows if x["arm"] == a)) for a in N})

# sanity: among OK runs, how often is the correct value visible in T1 / T2 (answers are usually computed in tool output)
for a in sorted(N):
    ok = [x for x in rows if x["arm"] == a and x["st"] == "OK" and x["kind"] != "yesno_na"]
    print(f"sanity {a}: OK runs assessable={len(ok)}  t1 visible={sum(1 for x in ok if x['t1'])}  t2 visible={sum(1 for x in ok if x['t2'])}")

print("\n=== (a) harvest: failed runs where correct value visible before the run ended ===")
for a in sorted(N):
    for st in ("NF", "WR"):
        f = [x for x in rows if x["arm"] == a and x["st"] == st]
        ass = [x for x in f if x["kind"] != "yesno_na"]
        t1 = [x for x in ass if x["t1"]]
        t2 = [x for x in ass if x["t2"]]
        last = [x for x in ass if x["last"] and x["last"][1]]
        t1a = [x for x in ass if x["t1a"]]
        print(f"{a} {st}: n={len(f)} assessable={len(ass)}  T1(short computed/assistant)={len(t1)}  T2(anywhere)={len(t2)}  last-short-output-is-correct={len(last)}  assistant-stated={len(t1a)}")

# by turn of first T1 appearance for NF
print("\nNF runs, first turn the correct value appears in a short computed output (T1):")
for a in sorted(N):
    c = collections.Counter()
    for x in rows:
        if x["arm"] == a and x["st"] == "NF" and x["kind"] != "yesno_na":
            c["never" if not x["t1"] else ("<=8" if x["t1"] <= 8 else "9-12" if x["t1"] <= 12 else "13-15")] += 1
    print(a, dict(c))

# C2 capture: runs nudged
print("\n=== C2 (v3) nudged runs: what the reminder captured ===")
nud = [x for x in rows if x["arm"] == "C2" and x["nudged"]]
c = collections.Counter()
for x in nud:
    wrote_after = any(t >= min(x["nudge_turns"]) for t in x["writes"])
    vis_before = x["t1"] is not None and x["t1"] <= min(x["nudge_turns"])
    c[(("wrote" if wrote_after else "nowrite"), x["st"], "T1-visible-before-nudge" if vis_before else "not-visible-before")] += 1
for k in sorted(c):
    print(k, c[k])

# What would a perfect "write what you computed last" harvest give on NF runs of each arm?
print("\n=== ceiling if every NF run delivered its last short computed output (realistic harvest) vs any-visible (optimistic) ===")
for a in sorted(N):
    ar = [x for x in rows if x["arm"] == a]
    ok = sum(1 for x in ar if x["st"] == "OK")
    nf_last = sum(1 for x in ar if x["st"] == "NF" and x["last"] and x["last"][1])
    nf_t1 = sum(1 for x in ar if x["st"] == "NF" and x["t1"])
    n = len(ar)
    print(f"{a}: actual {ok}/{n}={ok/n:.3f}; +NF last-output {nf_last} -> {(ok+nf_last)/n:.3f}; +NF any-T1 {nf_t1} -> {(ok+nf_t1)/n:.3f}")
