import json, collections, datetime as dt
L="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/ledger/ledger.jsonl"
rows = json.load(open("/tmp/claude-0/verify_formal/rows.json"))
cfg_up = {r["tag"]: r["up"] for r in rows}
per = collections.defaultdict(list)
other_prefixes = collections.Counter()
for ln in open(L):
    d = json.loads(ln)
    if d["tag"].startswith("v3local-"): per[d["tag"]].append(d)
    else: other_prefixes[d["tag"].split("-g12")[0]] += 1
print("other tag prefixes:", other_prefixes.most_common(20))
print("v3local tags in ledger:", len(per), "expected", len(cfg_up), "missing:", sorted(set(cfg_up)-set(per))[:10], "extra:", sorted(set(per)-set(cfg_up))[:10])
C=collections.Counter
ups_multi = {t: C(d["upstream"] for d in v) for t,v in per.items() if len({d["upstream"] for d in v})>1}
print("tags with >1 upstream:", ups_multi)
mism = [(t, {d['upstream'] for d in v}, cfg_up.get(t)) for t,v in per.items() if {d["upstream"] for d in v} != {cfg_up.get(t)}]
print("ledger upstream != config upstream:", mism)
print("think field:", C(d["think"] for v in per.values() for d in v))
print("model field:", C(d["model"] for v in per.values() for d in v))
print("status:", C(d["status"] for v in per.values() for d in v))
print("stream_error:", C(bool(d.get("stream_error")) for v in per.values() for d in v))
print("reasoning_tokens>0:", sum(1 for v in per.values() for d in v if (d.get("usage") or {}).get("reasoning_tokens")))
print("attempts>1:", sum(1 for v in per.values() for d in v if (d.get("attempts") or 1)>1))
# requests per tag by arm
byarm = collections.defaultdict(list)
for t,v in per.items():
    arm = t.split("-g12-off-")[1].split("-")[0]
    byarm[arm].append(len(v))
for a,l in sorted(byarm.items()):
    print(a, "tags", len(l), "total req", sum(l), "mean", round(sum(l)/len(l),2), ">15:", sum(1 for x in l if x>15), "max", max(l))
# errors per tag
errs = {t: sum(1 for d in v if d["status"]!=200 or d.get("stream_error")) for t,v in per.items()}
print("tags with errors:", {t:(e,len(per[t])) for t,e in errs.items() if e})
json.dump({t:[(d["ts"], d["status"], d["upstream"], (d.get("usage") or {}).get("completion_tokens")) for d in v] for t,v in per.items()}, open("/tmp/claude-0/verify_formal/ledger_v3local.json","w"))
