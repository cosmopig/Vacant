"""R12: /app/tests_visible (agent copy) and --suite (receiver copy) are never compared or recorded."""
import importlib.util, pathlib, tempfile, os, json
from vacant_network.intake import contract as C
from vacant_network.adapters.hookpolicy import HookEvent, decide_pre_tool
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["VACANT_HOME"] = str(tmp / "agent-home")
ws = tmp / "app"; (ws / "tests_visible").mkdir(parents=True)
(ws / "tests_visible/test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
rs = tmp / "srv/eval/receiver/T/tests_visible"; rs.mkdir(parents=True)
(rs / "test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n    assert add(0.5, 0.25) == 0.75\n")
out = b.prepare(workspace=ws, task_id="T", suite=rs, deliverable="solution.py", mode="conform",
                attempts=None, feedback_rounds=3, suite_timeout_s=20,
                destination="dir:.vacant/native-release", receiver_home=tmp / "rh")
print("prepare:", out["prepared"], "| keys in output:", sorted(out))
print("agent copy sha:", C.path_sha256(ws / "tests_visible")[:12], "receiver copy sha:", out["suite_sha256"][:12])
c = C.load(ws / ".vacant/contract.json")
print("agent write to /app/tests_visible:",
      decide_pre_tool(HookEvent(agent="pi", kind="pre_tool", tool="write", paths=["tests_visible/test_visible.py"], cwd=str(ws)), c).action)
