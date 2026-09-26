import json, collections, datetime as dt
L="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/ledger/ledger.jsonl"
f = lambda ts: dt.datetime.utcfromtimestamp(ts).strftime("%m-%d %H:%M:%S")
start = dt.datetime(2026,9,26,3,55,28,tzinfo=dt.timezone.utc).timestamp()
end = dt.datetime(2026,9,26,17,25,15,tzinfo=dt.timezone.utc).timestamp()
other = collections.defaultdict(list)
for ln in open(L):
    d = json.loads(ln)
    if not d["tag"].startswith("v3local-") and start <= d["ts"] <= end:
        other[(d["tag"].split("-g12")[0] if "-g12" in d["tag"] else d["tag"], d["upstream"])].append(d["ts"])
for k,v in sorted(other.items()):
    print(k, len(v), f(min(v)), f(max(v)))
