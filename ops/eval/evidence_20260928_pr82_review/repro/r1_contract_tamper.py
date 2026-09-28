"""R1: agent edits /app/.vacant/contract.json after prepare; judge does not check the lock."""
import importlib.util, json, pathlib, sys, tempfile, os
from vacant_network.intake import contract as C
from vacant_network.intake import flow
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["VACANT_HOME"] = str(tmp / "agent-vacant-home")   # agent's home, NOT the receiver's
ws = tmp / "app"; (ws / "tests_visible").mkdir(parents=True)
recv_suite = tmp / "srv/eval/receiver/T/tests_visible"; recv_suite.mkdir(parents=True)
for d in (ws / "tests_visible", recv_suite):
    (d / "test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
rh = tmp / "srv/eval/receiver/T/vacant"
out = b.prepare(workspace=ws, task_id="T", suite=recv_suite, deliverable="solution.py", mode="conform",
                attempts=None, feedback_rounds=3, suite_timeout_s=20,
                destination="dir:.vacant/native-release", receiver_home=rh)
locked_sha = out["contract_sha256"]
# ---- agent (same uid, but never touches receiver suite / receiver home) ----
(ws / "solution.py").write_text("def add(a, b): return 0\n")          # wrong
cp = ws / ".vacant/contract.json"
raw = json.loads(cp.read_text())
raw["claims"][0] = {"id": "visible_acceptance", "verifier": "exists",
                    "params": {"paths": ["solution.py"]}, "required": True, "authority": "requirement"}
cp.write_text(json.dumps(raw))
# ---- evaluator ----
j = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rh)
print("judge outcome:", j["outcome"], "| contract judged == locked?", C.load(cp).sha256 == locked_sha)
print("bridge exit code would be:", b.EXIT.get(j["outcome"]))
r = b.release(workspace=ws, receiver_home=rh)
print("release:", r.get("released"), r.get("reasons"))
