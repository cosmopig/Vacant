import json, os, pathlib, sys, tempfile
tmp = pathlib.Path(tempfile.mkdtemp(dir="/tmp/claude-0/review_v3"))
os.environ["HOME"] = str(tmp/"home"); (tmp/"home").mkdir()
os.environ["VACANT_HOME"] = str(tmp/"vh")
for k in ("VACANT_TRACE","VACANT_MODE","VACANT_HOOK_NO_STOP","VACANT_FEEDBACK_MODE"): os.environ.pop(k, None)
from vacant_network.adapters import hook, install as INS
from vacant_network.trace import zerostop
from vacant_network.trace.recorder import Recorder
print("using", zerostop.__file__)
p = INS.state_root()/"install.json"; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
app = tmp/"app"; (app/"data").mkdir(parents=True); (app/"data"/"sales.csv").write_text("date,amount\n2026-07-01,1200\n2026-07-02,845\n")
def boom(req): raise RuntimeError("simulated check failure")
zerostop._run_child = boom
def ev(event, **kw):
    out, err, code = hook.handle("pi", event, {"cwd": str(app), "session_id": "S", **kw})
    return json.loads(out) if out else {}
ev("prompt", prompt="Answer using data/. What is the total amount? Write the answer to /app/answer.txt as a single number.")
inp = {"command": "python3 -c 'print(2045)' > answer.txt"}
ev("pre_tool", tool="bash", call_id="c1", input=inp)
(app/"answer.txt").write_text("2045\n")
ev("post_tool", tool="bash", call_id="c1", input=inp, output="")
print("stop ->", ev("stop", final_text="The total is 2045; written to /app/answer.txt.", turn=3, budget=15))
print("session_end ->", ev("session_end", reason="quit", turn=3, budget=15))
for md in (pathlib.Path(os.environ["VACANT_HOME"])/"trace"/"projects").glob("*/delivery.md"):
    print(md.read_text())
print([e["type"] for e in Recorder(app).events()])
