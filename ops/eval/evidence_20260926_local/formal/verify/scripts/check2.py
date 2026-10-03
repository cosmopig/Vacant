import json, collections, datetime as dt, statistics
rows = json.load(open("/tmp/claude-0/verify_formal/rows.json"))
g = collections.defaultdict(dict)
for r in rows: g[(r["task"], r["sample"])][r["arm"]] = r
def t(x): return dt.datetime.fromisoformat(x.replace("Z","+00:00"))
diffup = [k for k,v in g.items() if len({x["up"] for x in v.values()})>1]
print("groups", len(g), "upstream differs:", diffup)
spreads = []
for k,v in g.items():
    st = [t(x["started"]) for x in v.values()]
    spreads.append(((max(st)-min(st)).total_seconds(), k))
spreads.sort(reverse=True)
print("start spread top 10 (s):", [(round(a), b) for a,b in spreads[:10]])
print("median spread", statistics.median(a for a,_ in spreads))
print("spread>600s:", sum(1 for a,_ in spreads if a>600))
# sample ordering: min start of sample k+1 vs max finish/start of sample k per machine
for up in ("w401","1003"):
    for s in (1,2,3):
        rs=[r for r in rows if r["up"]==up and r["sample"]==s]
        print(up, s, "n", len(rs), "first start", min(r["started"] for r in rs), "last start", max(r["started"] for r in rs), "last finish", max(r["finished"] for r in rs))
