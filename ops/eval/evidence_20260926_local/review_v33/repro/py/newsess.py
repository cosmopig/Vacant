import json, os, pathlib, sys, time
root = pathlib.Path(sys.argv[1]); M = int(sys.argv[2]); sid = sys.argv[3]
os.environ["HOME"] = str(root / "home"); os.environ["VACANT_HOME"] = str(root / "vh")
sys.path.insert(0, "/home/user/Vacant")
from vacant_network.adapters import hook
from vacant_network.trace import zerostop
from vacant_network.trace.recorder import Recorder
app = root / "app"
def ev(event, **kw):
    out, err, code = hook.handle("pi", event, {"cwd": str(app), "session_id": sid, **kw})
    return json.loads(out) if out else {}
ev("prompt", prompt="Answer using data/. Write the answer to /app/answer.txt.")
for i in range(M):
    inp = {"command": f"cat data/sales.csv # n{i}"}
    ev("pre_tool", tool="bash", call_id=f"n{i}", input=inp)
    ev("post_tool", tool="bash", call_id=f"n{i}", input=inp, output="x")
rec = Recorder(app)
st = zerostop._load_state(rec); st.pop("verified", None); zerostop._save_state(rec, st)
for label in ("genesis", "incremental"):
    t = time.time(); out = zerostop._run_child({"ws": str(app), "platform": "pi", "session": sid, "final_text": None})
    print(label, round(time.time() - t, 2), out.get("ran"), len(out.get("result", {}).get("findings") or []))
