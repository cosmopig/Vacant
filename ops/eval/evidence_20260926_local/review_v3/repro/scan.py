import json, glob, os, sys
base = "/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3"
for arm in ("C1","C2"):
  for d in sorted(glob.glob(f"{base}/g12-off-{arm}-s1/*/*/agent")):
    vc = os.path.join(d, "vacant_check.json")
    try: v = json.load(open(vc))
    except Exception as e: v = {}
    # pi.txt: json mode events
    turns = 0; last = None; stop_reasons = []
    try:
        for ln in open(os.path.join(d, "pi.txt")):
            try: e = json.loads(ln)
            except: continue
            if e.get("type") == "turn_end":
                turns += 1
                m = e.get("message") or {}
                tc = [c for c in (m.get("content") or []) if c.get("type") == "toolCall"]
                txt = "".join(c.get("text","") for c in (m.get("content") or []) if c.get("type")=="text")
                last = (len(tc), m.get("stopReason"), txt[:100].replace("\n"," "))
    except FileNotFoundError: pass
    rew = open(os.path.join(os.path.dirname(d), "verifier/reward.txt")).read().strip() if os.path.exists(os.path.join(os.path.dirname(d), "verifier/reward.txt")) else None
    print(arm, d.split("/")[-2][:40], "turns", turns, "reviews", v.get("reviews"), v.get("review_actions"), "nudges", v.get("nudges"), v.get("nudge_turns"), "ended", v.get("ended_notes"), "reward", rew, "last", last)
