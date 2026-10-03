import json, sys, os
from vacant_network.trace.recorder import Recorder
r = Recorder(sys.argv[1])
print("trace dir:", r.dir)
print("delivery.md exists:", (r.dir / "delivery.md").exists())
evs = list(r.events())
print("event types:", [e.get("type") for e in evs])
for e in evs:
    if e.get("type") == "ended":
        print("ended:", json.dumps({k: e.get(k) for k in ("checked", "final_answer", "missing")}))
if (r.dir / "delivery.md").exists():
    print((r.dir / "delivery.md").read_text())
