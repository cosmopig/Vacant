import json, collections
rows = json.load(open("/tmp/claude-0/verify_formal/attr/runs.json"))
EXC = {"5", "70"}
def st(r):
    if r["reward"] == 1.0: return "OK"
    return "NF" if r["answer_file"] is False else "WR"
# need per-turn tool info: re-derive "turn 13 had tool call" -> use turns>=14 as proxy (turn 13 ended toolUse => another turn started)
def eligible(r):
    p = r["pi"]; w = p["writes"]
    first_w = min(w) if w else 99
    # reached turn 14 (i.e. turn 13 ended with tool use) and no write by turn 13
    return p["turns"] >= 14 and first_w > 13
out = collections.defaultdict(collections.Counter)
for r in rows:
    if r["task"] in EXC: continue
    arm = r["arm"]; p = r["pi"]
    e = eligible(r)
    nud = bool(p["nudges"]); chk = bool(p["checks"])
    key = ("elig" if e else "notelig") + ("+N" if nud else "") + ("+CHK" if chk else "")
    out[arm][(key, st(r))] += 1
for arm in ("A", "C1", "C2"):
    print("==", arm)
    keys = sorted({k for k, _ in out[arm]})
    for k in keys:
        ok = out[arm][(k, "OK")]; nf = out[arm][(k, "NF")]; wr = out[arm][(k, "WR")]
        print(f"  {k:22s} n={ok+nf+wr:3d} OK={ok:3d} NF={nf:3d} WR={wr:3d}")
