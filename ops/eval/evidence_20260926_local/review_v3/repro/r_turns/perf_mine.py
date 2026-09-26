import os, sys, time, json, pathlib, tempfile
base = pathlib.Path("/tmp/claude-0/review_v3/r_turns/perf")
import shutil; shutil.rmtree(base, ignore_errors=True)
(base/"home").mkdir(parents=True); (base/"app").mkdir()
os.environ["HOME"]=str(base/"home"); os.environ["VACANT_HOME"]=str(base/"vh")
sys.path.insert(0, "/home/user/Vacant")
from vacant_network.adapters import install as INS
p = INS.state_root()/"install.json"; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
from vacant_network.trace.recorder import Recorder
from vacant_network.trace import zerostop
from vacant_network.trace.evidence import Evidence
rec = Recorder(base/"app")
N=int(sys.argv[1])
t=time.time()
for i in range(N):
    rec.append("prompt", {"session": "S", "source":"user", "text_blob": None, "n": i})
print("append", N, time.time()-t)
t=time.time(); rec.events(); print("events", time.time()-t)
t=time.time(); Evidence(rec, platform="pi", session="S").window(); print("window", time.time()-t)
t=time.time(); r=zerostop.ended("pi","S",str(base/"app"),mode="evidence"); print("ended", time.time()-t, r)
