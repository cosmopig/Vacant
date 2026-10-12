import json, collections, hashlib, re
IO="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/ledger/io.jsonl"
C=collections.Counter
re_sent = C(); re_agent = C(); think_resp = C(); first = {}; nreq = C(); extra_keys = C()
sys_hash = collections.defaultdict(set); tools_hash = collections.defaultdict(set)
reasoning_nonempty = []; lastmsg = collections.defaultdict(list); sent_other = C()
with open(IO, "rb") as f:
    for ln in f:
        if b'"v3local-' not in ln[:300]:
            continue
        d = json.loads(ln)
        t = d["tag"]
        if not t.startswith("v3local-"): continue
        arm = t.split("-g12-off-")[1].split("-")[0]
        rs = d.get("request_sent") or {}
        ra = d.get("request_from_agent") or {}
        re_sent[(arm, rs.get("reasoning_effort"))] += 1
        re_agent[(arm, ra.get("reasoning_effort"), json.dumps(ra.get("reasoning")) if "reasoning" in ra else None)] += 1
        sent_other[(arm, tuple(sorted(k for k in rs if k != "messages")))] += 1
        extra_keys[(arm, tuple(sorted(k for k in ra if k not in ("messages","tools"))))] += 1
        resp = d.get("response") or ""
        if isinstance(resp, (dict, list)): resp = json.dumps(resp)
        # reasoning content check
        m = re.findall(r'"reasoning_content"\s*:\s*"((?:[^"\\]|\\.)*)"', resp)
        m2 = re.findall(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', resp)
        nonempty = [x for x in m + m2 if x.strip()]
        think_resp[(arm, bool(nonempty))] += 1
        if nonempty and len(reasoning_nonempty) < 5: reasoning_nonempty.append((t, nonempty[0][:200]))
        if "<think>" in resp or "<|channel|>" in resp or "thought" in resp[:0]:
            think_resp[(arm, "think_tag")] += 1
        msgs = ra.get("messages") or []
        if msgs and msgs[0].get("role") == "system":
            sys_hash[arm].add(hashlib.sha256(json.dumps(msgs[0], sort_keys=True).encode()).hexdigest()[:12])
        tools_hash[arm].add(hashlib.sha256(json.dumps(ra.get("tools"), sort_keys=True).encode()).hexdigest()[:12])
        if d.get("status") == 200:
            nreq[t] += 1
            h = hashlib.sha256(json.dumps(ra, sort_keys=True).encode()).hexdigest()
            if t not in first or d["ts"] < first[t][0]: first[t] = (d["ts"], h)
print("reasoning_effort sent:", re_sent)
print("reasoning in agent req:", re_agent)
print("sent keys:", sent_other)
print("agent keys:", extra_keys)
print("response reasoning nonempty:", think_resp); print(reasoning_nonempty)
print("system prompt hashes per arm:", {a: len(s) for a,s in sys_hash.items()})
print("tools hashes per arm:", {a: sorted(s) for a,s in tools_hash.items()})
g = collections.defaultdict(dict)
for t,(ts,h) in first.items():
    rest = t.split("-g12-off-")[1]; arm, task, s = rest.split("-")
    g[(task, s)][arm] = h
print("first-request groups", len(g), "differ:", [k for k,v in g.items() if len(set(v.values()))>1], "incomplete:", [k for k,v in g.items() if len(v)!=3])
json.dump(dict(nreq), open("/tmp/claude-0/verify_formal/io_nreq.json","w"))
