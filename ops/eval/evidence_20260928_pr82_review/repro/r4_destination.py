"""R4: default release destination lives in the agent workspace (dir:.vacant/native-release)."""
import importlib.util, pathlib, tempfile, os, json
from vacant_network.intake import contract as C
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

def setup(mode="conform"):
    tmp = pathlib.Path(tempfile.mkdtemp())
    os.environ["VACANT_HOME"] = str(tmp / "agent-home")
    ws = tmp / "app"; ws.mkdir()
    rs = tmp / "srv/eval/receiver/T/tests_visible"; rs.mkdir(parents=True)
    (rs / "test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
    rh = tmp / "srv/eval/receiver/T/vacant"
    b.prepare(workspace=ws, task_id="T", suite=rs, deliverable="solution.py", mode=mode,
              attempts=None, feedback_rounds=3, suite_timeout_s=20,
              destination="dir:.vacant/native-release", receiver_home=rh)
    return tmp, ws, rs, rh

# (a) post-release tamper: status keeps reporting the accepted sha as live
tmp, ws, rs, rh = setup()
(ws / "solution.py").write_text("def add(a, b): return a + b\n")
j = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rh)
r = b.release(workspace=ws, receiver_home=rh)
pub = ws / ".vacant/native-release/T/solution.py"
pub.write_text("def add(a, b): return 0\n")          # agent's leftover background process
st = b.status(workspace=ws, receiver_home=rh)
print("(a) judge", j["outcome"], "released", r["released"], "| status", st["state"],
      "destination_live.sha==accepted:", st["destination_live"]["artifact_sha256"] == j["artifact_sha256"],
      "| file hidden grader would read:", pub.read_text().strip())

# (b) symlink redirect: receiver writes where the agent points it (here: into the pinned receiver suite)
tmp, ws, rs, rh = setup()
(ws / "solution.py").write_text("def add(a, b): return a + b\n")
(ws / ".vacant/native-release").symlink_to(rs)            # agent, before it stops
pin_before = C.path_sha256(rs)
j = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rh)
r = b.release(workspace=ws, receiver_home=rh)
print("(b) released", r["released"], "canonical", r["canonical_destination"])
print("    receiver suite dir now contains:", sorted(p.relative_to(rs).as_posix() for p in rs.rglob("*") if p.is_file()))
print("    suite pin still valid:", C.path_sha256(rs) == pin_before)
j2 = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rh)
print("    re-judge of the SAME good candidate:", j2["outcome"], j2["results"][0]["detail"][:80])
