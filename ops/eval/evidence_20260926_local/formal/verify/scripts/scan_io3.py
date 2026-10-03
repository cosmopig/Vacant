import json, collections, re
IO="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/ledger/io.jsonl"
C=collections.Counter
chan = C(); nonempty = C(); samples = []
with open(IO, "rb") as f:
    for ln in f:
        if b'"v3local-' not in ln[:300]: continue
        d = json.loads(ln); t = d["tag"]
        if not t.startswith("v3local-"): continue
        arm = t.split("-g12-off-")[1].split("-")[0]
        resp = d.get("response") or ""
        # reassemble streamed content
        content = []
        for m in re.finditer(r'^data: (\{.*\})\s*$', resp, re.M):
            try: j = json.loads(m.group(1))
            except ValueError: continue
            for ch in j.get("choices") or []:
                dl = ch.get("delta") or ch.get("message") or {}
                if dl.get("content"): content.append(dl["content"])
                for k in ("reasoning_content","reasoning"):
                    if dl.get(k): nonempty[(arm, "field_"+k)] += 1
        if not content and resp.startswith("{"):
            try:
                j = json.loads(resp); content = [(j["choices"][0]["message"].get("content") or "")]
            except Exception: pass
        s = "".join(content)
        if "<|channel>" in s or "thought" in s[:40]:
            chan[arm] += 1
            m = re.search(r"<\|channel>thought(.*?)<channel\|>", s, re.S)
            if m and m.group(1).strip():
                nonempty[(arm, "thought_text")] += 1
                if len(samples) < 3: samples.append((t, m.group(1)[:200]))
print("responses with channel markers:", chan)
print("non-empty thinking:", nonempty)
print(samples)
