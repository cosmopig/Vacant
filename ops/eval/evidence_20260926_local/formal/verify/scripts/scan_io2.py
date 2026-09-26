import json, collections, re
IO="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/ledger/io.jsonl"
C=collections.Counter
vac = C(); notools = collections.defaultdict(int); per = C(); notool_sample = []
vac_last = C()
with open(IO, "rb") as f:
    for ln in f:
        if b'"v3local-' not in ln[:300]: continue
        d = json.loads(ln); t = d["tag"]
        if not t.startswith("v3local-"): continue
        arm = t.split("-g12-off-")[1].split("-")[0]
        ra = d.get("request_from_agent") or {}
        per[t] += 1
        msgs = ra.get("messages") or []
        txt = json.dumps(msgs)
        if re.search(r"vacant", txt, re.I): vac[arm] += 1
        # user messages that are not the first user message
        users = [m for m in msgs if m.get("role") == "user"]
        if len(users) > 1: vac_last[(arm, "multi_user_msgs")] += 1
        if "tools" not in ra:
            notools[t] += 1
            if len(notool_sample) < 2:
                notool_sample.append((t, [ (m.get("role"), str(m.get("content"))[:300]) for m in msgs[:1] + msgs[-1:]]))
print("requests mentioning 'vacant' by arm:", vac)
print("requests with >1 user message by arm:", vac_last)
print("tool-less requests by tag:", dict(notools))
over = {t: (n, notools.get(t,0)) for t,n in per.items() if n > 15}
print("tags >15 (total, toolless):", over)
print("tags >15 after removing toolless:", {t:v for t,v in over.items() if v[0]-v[1] > 15})
for s in notool_sample: print(s)
