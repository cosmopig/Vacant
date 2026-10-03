import json, collections
rows = json.load(open("/tmp/claude-0/verify_formal/attr/runs.json"))
# 1. nudge turns agree?
mis = 0
for r in rows:
    if r["arm"] == "C2":
        vn = (r["vc"] or {}).get("nudge_turns")
        if vn != r["pi"]["nudges"]:
            mis += 1; print("nudge mismatch", r["task"], r["sample"], vn, r["pi"]["nudges"])
print("nudge mismatches", mis)
# 2. answer_file vs writes parsed
c = collections.Counter()
for r in rows:
    w = bool(r["pi"]["writes"])
    c[(r["arm"], r["answer_file"], w)] += 1
for k in sorted(c, key=str): print(k, c[k])
