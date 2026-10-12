"""Reproduce: headless `opencode run` (NONINTERACTIVE => no 'stop' event), agent finishes normally,
dispose() sends session_end {cwd, session_id} with no reason. Does v3 write an 'ended before done' note?"""
import json, os, pathlib, sys, tempfile
tree = sys.argv[1]
sys.path.insert(0, tree)
tmp = pathlib.Path(tempfile.mkdtemp(prefix="oc_ended_", dir="/tmp/claude-0/review_v3/oc_ended"))
home = tmp / "home"; home.mkdir()
os.environ["HOME"] = str(home)
os.environ["VACANT_HOME"] = str(tmp / "vh")
for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE", "VACANT_HOOK_NO_SUBMIT"):
    os.environ.pop(k, None)
from vacant_network.adapters import hook
from vacant_network.adapters import install as INS
from vacant_network.trace.recorder import Recorder
print("module:", hook.__file__)
p = INS.state_root() / "install.json"; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
app = tmp / "app"; (app / "data").mkdir(parents=True)
(app / "data" / "sales.csv").write_text("date,amount\n2026-07-01,1200\n2026-07-02,845\n")
ASK = ("Answer the question using the files in data/. Question: what is the total amount? "
       "Write the answer to /app/answer.txt as a single number.")
# requested file path: make it resolvable -- use the project-relative answer path
ASK = ASK.replace("/app/answer.txt", str(app / "answer.txt"))
SID = "ses_main"
def ev(event, **kw):
    out, err, code = hook.handle("opencode", event, {"cwd": str(app), **kw})
    return code, err, out
# exactly what the plugin sends: chat.message -> prompt ; tool.execute.before/after -> pre/post_tool
print(ev("prompt", prompt=ASK, session_id=SID))
inp = {"command": "cat data/sales.csv"}
ev("pre_tool", tool="bash", input=inp, call_id="c1", session_id=SID)
ev("post_tool", tool="bash", input=inp, call_id="c1", output="date,amount\n2026-07-01,1200\n2026-07-02,845\n", session_id=SID)
inp2 = {"filePath": str(app / "answer.txt"), "content": "2045\n"}
ev("pre_tool", tool="write", input=inp2, call_id="c2", session_id=SID)
(app / "answer.txt").write_text("2045\n")
ev("post_tool", tool="write", input=inp2, call_id="c2", output="Wrote file successfully.", session_id=SID)
# NONINTERACTIVE: no stop. dispose(): session_end {cwd, session_id}
r = ev("session_end", session_id=SID)
print("session_end ->", r)
evs = Recorder(app).events()
print("event types:", [e["type"] for e in evs])
print("ended events:", [e for e in evs if e["type"] == "ended"])
rec = Recorder(app)
md = rec.dir / "delivery.md"
print("delivery.md exists:", md.is_file())
if md.is_file(): print(md.read_text())
