"""Stage 0（離線、不花錢）：正式批次裡「說做完、答案檔不存在」出現多少次；C 組真的缺檔退回之後發生什麼。"""
import json, glob, re, collections, sys, pathlib
R = pathlib.Path(sys.argv[1])
rows = []
for t in sorted(R.glob("formal_v3/g12-off-*-s*/*/dabstep-*__*")):
    m = re.search(r"g12-off-(\w+)-s(\d)/.*dabstep-(\d+)__", str(t))
    arm, s, task = m.group(1), int(m.group(2)), m.group(3)
    if task in ("5", "70"): continue
    try: reward = float((t/"verifier"/"reward.txt").read_text())
    except Exception: reward = None
    vt = (t/"verifier"/"test-stdout.txt")
    missing = vt.is_file() and "answer.txt not found" in vt.read_text(errors="replace")
    ev = []
    for l in open(t/"agent"/"pi.txt", errors="replace"):
        try: ev.append(json.loads(l))
        except Exception: pass
    turns = sum(1 for e in ev if e.get("type") == "turn_end")
    stops = [ (e.get("message") or {}).get("stopReason") for e in ev if e.get("type") == "turn_end"]
    # 「說做完」：某一回合的助理訊息 stopReason==stop（沒有工具呼叫）
    said_done_turns = [i+1 for i, r in enumerate(stops) if r == "stop"]
    reviews = []
    for ch in glob.glob(str(t/"agent"/"vacant_home"/"trace"/"projects"/"*"/"chain.ndjson")):
        for l in open(ch):
            d = json.loads(l)
            if d.get("type") == "review":
                p = d.get("payload") or {}
                reviews.append((p.get("action"), [f.get("kind") for f in p.get("findings") or []]))
    rows.append(dict(arm=arm, s=s, task=task, reward=reward, missing=missing, turns=turns,
                     said_done_turns=said_done_turns, final_stop=stops[-1] if stops else None, reviews=reviews))
c = collections.Counter()
for r in rows:
    first_done = r["said_done_turns"][0] if r["said_done_turns"] else None
    capped = r["turns"] >= 16 and r["final_stop"] != "stop"
    kind = ("capped" if capped else ("done" if r["final_stop"] == "stop" else f"other:{r['final_stop']}"))
    c[(r["arm"], kind, "no_file" if r["missing"] else ("right" if r["reward"] == 1 else "wrong"))] += 1
for k in sorted(c): print(k, c[k])
print("--- C arms: runs with a missing_output send-back, and the end state")
cc = collections.Counter()
for r in rows:
    mo = [x for x in r["reviews"] if x[0] == "continue" and "missing_output" in x[1]]
    if mo:
        cc[(r["arm"], "no_file" if r["missing"] else ("right" if r["reward"] == 1 else "wrong"))] += 1
for k in sorted(cc): print(k, cc[k])
print("--- all send-back kinds (continue) per arm")
kk = collections.Counter()
for r in rows:
    for a, ks in r["reviews"]:
        if a == "continue":
            for k in set(ks): kk[(r["arm"], k)] += 1
for k in sorted(kk): print(k, kk[k])
json.dump(rows, open(sys.argv[2], "w"), indent=0)
