"""R11: attempt budget is not enforced from the ledger: gate (max 1) can be judged repeatedly with --attempt 1."""
import importlib.util, pathlib, tempfile, os
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["VACANT_HOME"] = str(tmp / "agent-home")
ws = tmp / "app"; ws.mkdir()
rs = tmp / "suite"; rs.mkdir()
(rs / "test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
rh = tmp / "rh"
out = b.prepare(workspace=ws, task_id="T", suite=rs, deliverable="solution.py", mode="gate",
                attempts=None, feedback_rounds=3, suite_timeout_s=20,
                destination="dir:.vacant/native-release", receiver_home=rh)
print("gate max attempts:", out["attempts"])
for sol in ("return 0", "return 1", "return a + b"):
    (ws / "solution.py").write_text(f"def add(a, b): {sol}\n")
    print(" judge --attempt 1 ->", b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rh)["outcome"])
st = b.status(workspace=ws, receiver_home=rh)
print("release:", b.release(workspace=ws, receiver_home=rh)["released"], "| status.attempts =", st["attempts"], "decisions =", st["decisions"])
