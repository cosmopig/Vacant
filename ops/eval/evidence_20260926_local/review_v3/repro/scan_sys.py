import json, re, sys, collections
RE = re.compile(r"\b(?:budget|limit|maximum|max|at most|no more than|up to)\b[^.\n]{0,40}?\b(\d{1,4})\s+(?:model\s+|agent\s+|llm\s+)?(?:turns|steps|iterations)\b", re.I)
seen = collections.Counter(); n = 0; firsts = collections.Counter(); ctx = collections.Counter()
for line in open(sys.argv[1]):
    try: d = json.loads(line)
    except Exception: continue
    tag = d.get("tag") or ""
    if "v3local" not in tag: continue
    req = d.get("request_from_agent") or {}
    msgs = req.get("messages") or []
    sysm = [m for m in msgs if isinstance(m, dict) and m.get("role") in ("system", "developer")]
    if not sysm: continue
    c = sysm[0].get("content")
    t = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    n += 1
    m = RE.search(t)
    firsts[(tag.split("-")[2] if tag.count("-")>=2 else tag, m.group(0) if m else None)] += 1
    ctx["project_context" in t] += 1
print("requests with system prompt:", n)
for k, v in firsts.most_common(20): print(v, k)
print("has <project_context>:", dict(ctx))
