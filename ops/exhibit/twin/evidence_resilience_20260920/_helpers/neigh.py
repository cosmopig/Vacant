import json
import sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception as e:  # noqa: BLE001
    print("neighbour_has_twin=0"); print("err=%s" % type(e).__name__); sys.exit(0)
p = [x for x in d.get("people", []) if x.get("id") == "neighbour"]
print("neighbour=%d" % len(p))
print("neighbour_has_twin=%d" % (1 if (p and p[0].get("engine")) else 0))
