import json, collections
rows = json.load(open("/tmp/claude-0/verify_formal/attr/runs.json"))
EXC = {"5", "70"}
R = {(r["task"], r["arm"], r["sample"]): r for r in rows}
tasks = sorted({r["task"] for r in rows if r["task"] not in EXC}, key=int)
def st(r):
    if r["reward"] == 1.0: return "OK"
    return "NF" if r["answer_file"] is False else "WR"
def c2mech(r):
    p = r["pi"]; n = p["nudges"]; w = p["writes"]; ch = p["checks"]
    tags = []
    if n:
        # write after first nudge?
        post = [t for t in w if t > n[0]]
        pre = [t for t in w if t <= n[0]]
        tags.append("N%s" % n)
        if pre: tags.append("preW%s" % pre)
        if post: tags.append("postW%s" % post)
    else:
        tags.append("noN")
    if ch:
        tags.append("CHK%s" % ch)
        postc = [t for t in w if t > ch[0]]
        if postc: tags.append("WafterCHK%s" % postc)
    return " ".join(tags)
def mechclass(r):
    """classify the reason C2 run could be influenced"""
    p = r["pi"]; n = p["nudges"]; w = p["writes"]; ch = p["checks"]
    first_w = min(w) if w else None
    if n and first_w is not None and first_w > n[0]:
        k = "write_after_nudge"
    elif n:
        k = "nudged_no_write_after"  # includes pre-write? (nudge only fires when file missing)
    else:
        k = "no_nudge"
    if ch:
        k += "+check"
    return k
better, worse, same = [], [], []
for t in tasks:
    a = [R[(t, "A", s)]["reward"] or 0 for s in (1, 2, 3)]
    c = [R[(t, "C2", s)]["reward"] or 0 for s in (1, 2, 3)]
    d = sum(c) / 3 - sum(a) / 3
    (better if d > 0 else worse if d < 0 else same).append((t, d))
print("better", len(better), "worse", len(worse), "tie", len(same))
for name, grp in (("BETTER", better), ("WORSE", worse)):
    print("=====", name)
    for t, d in grp:
        print(f"task {t} d={d:+.2f}  A:", " ".join(st(R[(t,'A',s)]) for s in (1,2,3)),
              " C2:", " ".join(st(R[(t,'C2',s)]) for s in (1,2,3)))
        for s in (1, 2, 3):
            r = R[(t, "C2", s)]
            print(f"    C2 s{s} {st(r)} turns={r['pi']['turns']} writes={r['pi']['writes']} {c2mech(r)} exc={r['exception']}")
