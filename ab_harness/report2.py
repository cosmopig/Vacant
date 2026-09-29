import collections
import json
import pathlib
import sys

RUNS2 = pathlib.Path("/home/user1/ab-20260928/runs2")


def load():
    out = {}
    for d in sorted(RUNS2.iterdir()):
        f = d / "rec.json"
        if d.is_dir() and f.exists():
            r = json.loads(f.read_text())
            out.setdefault(r["task"], {})[r["arm"]] = r
    return out


def mcnemar_exact(b, c):
    from math import comb
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(comb(n, i) for i in range(k + 1)) * 0.5 ** n)


def block(tasks, label):
    if not tasks:
        print(f"\n### {label}: no complete triads")
        return
    n = len(tasks)
    rows = [v for v in tasks.values()]
    pc = sum(1 for v in rows if v["PC"]["correct"])
    rp0 = sum(1 for v in rows if v["RP0"]["correct"])
    rpl = sum(1 for v in rows if v["RPL"]["correct"])
    pc_first = sum(1 for v in rows if v["PC"]["correct"])
    rpl_att = [v["RPL"].get("attempts", 0) for v in rows]
    rpl_wall = [v["RPL"].get("wall_s") or 0 for v in rows]
    pc_wall = [v["PC"].get("wall_s") or 0 for v in rows]
    rp0_wall = [v["RP0"].get("wall_s") or 0 for v in rows]
    b_only = sum(1 for v in rows if v["RPL"]["correct"] and not v["RP0"]["correct"])
    a_only = sum(1 for v in rows if v["RP0"]["correct"] and not v["RPL"]["correct"])
    d = b_only + a_only
    p = mcnemar_exact(a_only, b_only)
    print(f"\n### {label}  (n = {n} complete triads)")
    rpn = sum(1 for v in rows if v.get("RPN", {}).get("correct"))
    have_n = sum(1 for v in rows if "RPN" in v)
    print(f"  PC   ceiling, interface given, 1 shot : {pc}/{n} ({100*pc/n:.1f}%)")
    print(f"  RP0  floor,    interface NOT given, 1 : {rp0}/{n} ({100*rp0/n:.1f}%)")
    if have_n:
        print(f"  RPN  retry, NO suite, <=3 sessions    : {rpn}/{have_n} ({100*rpn/have_n:.1f}%)")
        print(f"  RPL  gate + suite feedback, <=3       : {rpl}/{n} ({100*rpl/n:.1f}%)")
        print()
        print(f"  RPL - RP0 = {100*(rpl-rp0)/n:+.1f} pp   <- CONFOUNDED: nested design,")
        print( "        RPL's first attempt IS the RP0 run, so this also buys extra tries")
        print(f"  RPN - RP0 = {100*(rpn-rp0)/have_n:+.1f} pp   <- what extra tries alone buy")
        print(f"  RPL - RPN = {100*(rpl-rpn)/have_n:+.1f} pp   <- the feedback's marginal value")
    else:
        print(f"  RPL  gate + retry loop, <=3 sessions  : {rpl}/{n} ({100*rpl/n:.1f}%)")
        print(f"  RPL - RP0 = {100*(rpl-rp0)/n:+.1f} pp   <- CONFOUNDED (no RPN control yet)")
    print(f"  cost: mean attempts RPL {sum(rpl_att)/n:.2f}"
          f" | mean wall PC {sum(pc_wall)/n:.0f}s"
          f" RP0 {sum(rp0_wall)/n:.0f}s RPL {sum(rpl_wall)/n:.0f}s")
    print(f"  paired: RPL-only-correct {b_only}, RP0-only-correct {a_only}, "
          f"discordant {d}")
    if d == 0:
        print("  p = not computable (zero discordant pairs) -- cannot separate")
    elif d < 6:
        print(f"  p = {p:.4f}  [only {d} discordant pairs: UNRESOLVED, not a result]")
    else:
        print(f"  p = {p:.4f}")
    if pc / n < 0.5:
        print("  PC < 0.5  =>  CEILING_TOO_LOW: the task is too hard for this model,")
        print("               the pipeline question was never posed on this stratum.")


data = load()
paired = {t: v for t, v in data.items() if {"PC", "RP0", "RPL"} <= set(v)}
print("=" * 74)
print("WAVE 2 (R535 bank) — three arms, reported separately by stratum")
print("=" * 74)
print(f"complete triads: {len(paired)} / {len(data)} tasks touched")
print(f"incomplete: {sorted(set(data) - set(paired))[:12]}")
block({t: v for t, v in paired.items() if t.startswith("s1_")}, "S1  (interface NOT given, design intent >=0.8 first-shot fail)")
block({t: v for t, v in paired.items() if t.startswith("s2_")}, "S2  (design intent 0.4-0.8 first-shot fail)")
block(paired, "BOTH strata pooled -- shown only to be explicit that it is forbidden by the R535 report_rule")
