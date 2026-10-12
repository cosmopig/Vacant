"""R9: --receiver-home under the workspace is accepted; with a directory/glob deliverable its private keys are frozen and published."""
import importlib.util, pathlib, tempfile, os
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["VACANT_HOME"] = str(tmp / "agent-home")
ws = tmp / "app"; (ws / "tests_visible").mkdir(parents=True)
(ws / "tests_visible/test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
rh = ws / "eval-receiver"
b.prepare(workspace=ws, task_id="T", suite=None, deliverable="**", mode="gate",
          attempts=None, feedback_rounds=3, suite_timeout_s=20,
          destination="dir:.vacant/native-release", receiver_home=rh)
(ws / "solution.py").write_text("def add(a, b): return a + b\n")
j = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rh)
r = b.release(workspace=ws, receiver_home=rh)
pub = ws / ".vacant/native-release/T"
keys = sorted(p.relative_to(pub).as_posix() for p in pub.rglob("identity.key"))
print("judge", j["outcome"], "released", r.get("released"), "| private keys in the released artifact:", keys)
