"""R3: default layout (suite = /app/tests_visible), receiver home protected & untouched.
An agent-left background process flips the suite file; pin check and run_suite read the suite twice."""
import importlib.util, pathlib, tempfile, os, sys, subprocess, time
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
SANDBOX = sys.argv[1] if len(sys.argv) > 1 else "none"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20

tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["VACANT_HOME"] = str(tmp / "agent-home")
ws = tmp / "app"; suite = ws / "tests_visible"; suite.mkdir(parents=True)
GOOD = "def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n"
FAKE = "def check_add():\n    pass\n" + "#" * (len(GOOD) - 27) + "\n"
(suite / "test_visible.py").write_text(GOOD)
rh = tmp / "receiver"
out = b.prepare(workspace=ws, task_id="T", suite=None, deliverable="solution.py", mode="gate",
                attempts=None, feedback_rounds=3, suite_timeout_s=20,
                destination="dir:.vacant/native-release", receiver_home=rh)
os.chmod(rh, 0o500)   # pretend receiver home is not agent-writable (agent never touches it anyway)
(ws / "solution.py").write_text("def add(a, b): return 0\n")   # wrong
# ---- agent leaves this running (same uid, only touches its own /app) ----
flipper = subprocess.Popen([sys.executable, "-c", f"""
import os, pathlib, time
d = pathlib.Path({str(suite)!r}); g = d.parent/'.g'; f = d.parent/'.f'
G, F = {GOOD!r}, {FAKE!r}
while True:
    g.write_text(G); os.replace(g, d/'test_visible.py'); time.sleep(0.0007)
    f.write_text(F); os.replace(f, d/'test_visible.py'); time.sleep(0.0007)
"""])
time.sleep(0.3)
res = {}
try:
    for i in range(N):
        j = b.judge(workspace=ws, sandbox=SANDBOX, attempt=1, receiver_home=rh)
        res[j["outcome"]] = res.get(j["outcome"], 0) + 1
        if j["outcome"] == "accept" and "rel" not in res and os.environ.get("STOP_AT_ACCEPT", "1") == "1":
            flipper.kill(); flipper.wait()
            (suite / "test_visible.py").write_text(GOOD)
            for x in (".g", ".f"):
                (ws / x).unlink(missing_ok=True)
            r = b.release(workspace=ws, receiver_home=rh)
            res["rel"] = r.get("released")
            print("accepted wrong solution; release:", r.get("released"),
                  (ws / ".vacant/native-release/T/solution.py").read_text().strip() if r.get("released") else r.get("reasons"))
            break
finally:
    if flipper.poll() is None:
        flipper.kill()
print(SANDBOX, res)
