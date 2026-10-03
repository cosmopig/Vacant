import json, collections, re
IO="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/ledger/io.jsonl"
per = collections.defaultdict(lambda: {"n":0,"nudge_first":None,"check_first":None,"other_vacant":0,"params":set(),"ts":[]})
MARK_N="Before the turn budget runs out"; MARK_C="Before delivery: a review"
pat=re.compile(r"vacant", re.I)
with open(IO) as f:
    for line in f:
        if '"tag": "v3local-g12-off-' not in line[:300]: continue
        e=json.loads(line); tag=e["tag"]; d=per[tag]; d["n"]+=1; d["ts"].append(e.get("ts"))
        req=e.get("request_from_agent") or {}
        d["params"].add(json.dumps({k:v for k,v in req.items() if k not in ("messages","tools")}, sort_keys=True))
        msgs=json.dumps(req.get("messages"))
        if MARK_N in msgs and d["nudge_first"] is None: d["nudge_first"]=d["n"]
        if MARK_C in msgs and d["check_first"] is None: d["check_first"]=d["n"]
        # other vacant mentions not from those two markers
        s=msgs.replace(MARK_N,"").replace(MARK_C,"")
        if pat.search(s): d["other_vacant"]+=1
out={k:{**v,"params":sorted(v["params"])} for k,v in per.items()}
json.dump(out, open("/tmp/claude-0/verify_formal/attr/io_scan.json","w"))
print(len(out))
