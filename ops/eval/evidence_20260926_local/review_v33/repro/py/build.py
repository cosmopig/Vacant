import json, os, pathlib, sys, time
root = pathlib.Path(sys.argv[1]); N = int(sys.argv[2])
os.environ["HOME"] = str(root / "home"); os.environ["VACANT_HOME"] = str(root / "vh")
for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
    os.environ.pop(k, None)
(root / "home").mkdir(parents=True, exist_ok=True)
sys.path.insert(0, "/home/user/Vacant")
from vacant_network.adapters import hook, install as INS
p = INS.state_root() / "install.json"; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
app = root / "app"; (app / "data").mkdir(parents=True, exist_ok=True)
(app / "data" / "sales.csv").write_text("date,amount\n2026-07-01,1200\n2026-07-02,845\n")
def ev(event, sid, **kw):
    out, err, code = hook.handle("pi", event, {"cwd": str(app), "session_id": sid, **kw})
    return json.loads(out) if out else {}
t0 = time.time()
ev("prompt", "OLD", prompt="Answer using data/. Write the answer to /app/answer.txt.")
for i in range(N):
    inp = {"command": f"cat data/sales.csv # {i}"}
    ev("pre_tool", "OLD", tool="bash", call_id=f"c{i}", input=inp)
    ev("post_tool", "OLD", tool="bash", call_id=f"c{i}", input=inp, output="date,amount\n2026-07-01,1200\n")
print("built", N, "steps in", round(time.time() - t0, 1), "s")
