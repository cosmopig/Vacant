import json, collections, sys
sys.path.insert(0, "/tmp/claude-0/review_effect/headroom")
from vis import visibility, match_text, kind
R = [r for r in json.load(open("paid_runs.json")) if r["task"] not in ("5", "70")]
def st(r): return "OK" if r["reward"] == 1.0 else ("NF" if r["file"] is False else "WR")
for m in ("g4", "q38"):
    for a in ("A", "C"):
        rs = [r for r in R if r["model"] == m and r["arm"] == a]
        c = collections.Counter(st(r) for r in rs)
        nf = [r for r in rs if st(r) == "NF"]
        v1 = v_think = v_last = 0; turns = collections.Counter()
        for r in nf:
            if kind(r["expected"]) == "yesno_na": continue
            thinking = [ch for ch in r["pi"]["chunks"] if ch["role"] == "thinking"]
            r2 = dict(r); r2["pi"] = dict(r["pi"]); r2["pi"]["chunks"] = [ch for ch in r["pi"]["chunks"] if ch["role"] != "thinking"]
            v = visibility(r2)
            if v["t1_first"]: v1 += 1; turns["<=8" if v["t1_first"] <= 8 else "9-12" if v["t1_first"] <= 12 else "13-15"] += 1
            if v["last_short_match"] and v["last_short_match"][1]: v_last += 1
            # thinking: value stated in the model's own reasoning in the last 3 turns
            if any(match_text(r["expected"], ch["text"]) for ch in thinking if ch["turn"] >= r["pi"]["turns"] - 3): v_think += 1
        print(f"paid {m} {a}: {dict(c)}; NF with value in short computed output (T1) {v1} {dict(turns)}; last-short-output correct {v_last}; value in thinking of last 3 turns {v_think}")
# relaunch cross-arm (A and C treated as two samples; C had no effect on outcome p=0.21/0.29)
for m in ("g4", "q38"):
    by = collections.defaultdict(dict)
    for r in R:
        if r["model"] == m: by[r["task"]][r["arm"]] = r
    base = sum(st(v["A"]) == "OK" for v in by.values()) + sum(st(v["C"]) == "OK" for v in by.values())
    rel = 0; extra = 0; extra_req = 0
    for t, v in by.items():
        for first, second in (("A", "C"), ("C", "A")):
            f = v[first]
            if st(f) == "NF": rel += st(v[second]) == "OK"; extra += 1; extra_req += v[second]["nreq"]
            else: rel += st(f) == "OK"
    n = len(by)
    print(f"paid {m}: mean single {base/(2*n):.3f}; relaunch-on-NF (other arm as 2nd attempt, both orders) {rel/(2*n):.3f} (+{(rel-base)/(2*n)*100:.1f} pp); extra attempts/task {extra/(2*n):.2f}; extra requests/task {extra_req/(2*n):.1f}")
