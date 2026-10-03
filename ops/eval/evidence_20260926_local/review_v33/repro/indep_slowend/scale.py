"""How long the real session_end hook takes on the cut-off path as the record grows (no slowdown)."""
import json, os, pathlib, subprocess, sys, time
root = pathlib.Path(sys.argv[1]); N = int(sys.argv[2])
os.environ["HOME"] = str(root / "home"); os.environ["VACANT_HOME"] = str(root / "vh")
(root / "home").mkdir(parents=True, exist_ok=True)
from vacant_network.adapters import hook, install as INS
p = INS.state_root() / "install.json"; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
app = root / "app"; (app / "data").mkdir(parents=True, exist_ok=True)
(app / "data" / "sales.csv").write_text("date,amount\n2026-07-01,1200\n2026-07-02,845\n")
def ev(event, **kw):
    out, err, code = hook.handle("pi", event, {"cwd": str(app), "session_id": "S1", **kw}); assert code == 0
ev("prompt", prompt="Answer the question using the files in data/. Question: what is the total amount? "
                    "Write the answer to /app/answer.txt as a single number.")
t = time.time()
for n in range(N):
    inp = {"command": f"cat data/sales.csv # {n}"}
    ev("pre_tool", tool="bash", call_id=f"c{n}", input=inp)
    ev("post_tool", tool="bash", call_id=f"c{n}", input=inp, output="date,amount")
build = time.time() - t
t = time.time()
r = subprocess.run([sys.executable, "-m", "vacant_network", "hook", "pi", "session_end"],
                   input=json.dumps({"cwd": str(app), "session_id": "S1", "reason": "quit", "turn": N,
                                     "budget": N, "aborted": True}), capture_output=True, text=True)
print(json.dumps({"steps": N, "build_s": round(build, 1), "session_end_hook_s": round(time.time() - t, 2),
                  "rc": r.returncode}))
