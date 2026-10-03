import json,sys,collections
rows=[json.loads(l) for l in open(sys.argv[1])]
rows=[r for r in rows if r["has_outcome"]]
blocked=[r for r in rows if r["stop_decision"]=="block"]
fc=[r for r in rows if r["fully_correct"]]
kinds=collections.Counter(k for r in blocked for k in set(r["sent_kinds"]))
unread_paths=collections.Counter(f["path"] for r in blocked for f in r["findings"] if f["kind"]=="unread")
only_unread=[r for r in blocked if set(r["sent_kinds"])=={"unread"}]
print(json.dumps({"cells":len(rows),"fully_correct":len(fc),"blocked":len(blocked),
 "blocked_fully_correct":sum(1 for r in blocked if r["fully_correct"]),
 "blocked_not_fully_correct":sum(1 for r in blocked if not r["fully_correct"]),
 "cells_by_kind":dict(kinds),"unread_paths":dict(unread_paths),"blocked_only_unread":len(only_unread)},indent=1))
