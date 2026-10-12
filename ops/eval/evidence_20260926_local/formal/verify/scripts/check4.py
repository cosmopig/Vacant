import json, datetime as dt
per = json.load(open("/tmp/claude-0/verify_formal/ledger_v3local.json"))
rows = {r["tag"]: r for r in json.load(open("/tmp/claude-0/verify_formal/rows.json"))}
f = lambda ts: dt.datetime.utcfromtimestamp(ts).strftime("%H:%M:%S")
for t,v in sorted(per.items()):
    if len(v) > 15 or t.endswith(("-1273-s3","-69-s3")):
        r = rows[t]
        before = [x for x in v if x[0] < dt.datetime.fromisoformat(r["started"].replace("Z","+00:00")).timestamp()]
        print(t, len(v), "reward", r["reward"], "exc", r["exc"], "first", f(v[0][0]), "last", f(v[-1][0]), "started", r["started"][11:19], "finished", r["finished"][11:19], "req before trial start:", len(before))
