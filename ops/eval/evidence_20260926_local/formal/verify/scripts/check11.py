import json, pathlib, re
F = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3")
rows = json.load(open("/tmp/claude-0/verify_formal/rows.json"))
rk = {(r["task"], r["arm"], r["sample"]): r for r in rows}
for t in ("23","62","30","1"):
    for s in (1,2,3):
        for a in ("A","C2"):
            r = rk[(t,a,s)]
            vc = r["vc"] if isinstance(r["vc"], dict) else {}
            trial = F / f"g12-off-{a}-s{s}" / r["job"] / r["trial"]
            pi = (trial/"agent"/"pi.txt").read_text(errors="replace")
            # find writes to answer.txt
            w = [m.start() for m in re.finditer(r"answer\.txt", pi)]
            print(t, s, a, "reward", r["reward"], "nudges", vc.get("nudge_turns"), "reviews", vc.get("review_actions"), "answer.txt mentions", len(w))
