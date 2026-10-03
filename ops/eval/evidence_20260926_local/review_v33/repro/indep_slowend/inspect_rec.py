import json, os, pathlib, sys, time
R = pathlib.Path(sys.argv[1])
os.environ["HOME"] = str(R / "home"); os.environ["VACANT_HOME"] = str(R / "vh")
from vacant_network.trace.recorder import Recorder
rec = Recorder(R / "app")
evs = rec.events()
print("record dir:", rec.dir)
print("event types (last 6):", [e.get("type") for e in evs][-6:])
print("has 'ended':", any(e.get("type") == "ended" for e in evs),
      "| has session_closed:", any(e.get("type") == "session_closed" for e in evs))
md = rec.dir / "delivery.md"
print("delivery.md exists:", md.is_file())
if md.is_file():
    print("  ", md.read_text().splitlines()[6:12])
zs = rec.dir / "zero_state.json"
print("zero_state.json:", (time.ctime(zs.stat().st_mtime) if zs.is_file() else None))
if (R / "slow.log").is_file():
    print("slow.log:", (R / "slow.log").read_text().strip().splitlines())
