"""R2: receiver home the agent can write (omitted -> ambient VACANT_HOME, or inside /app): full bypass."""
import importlib.util, json, pathlib, tempfile, os, sys
from vacant_network.intake import flow
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

def run(label, rh_fn):
    tmp = pathlib.Path(tempfile.mkdtemp())
    os.environ["VACANT_HOME"] = str(tmp / "shared-vacant-home")
    ws = tmp / "app"; (ws / "tests_visible").mkdir(parents=True)
    (ws / "tests_visible/test_visible.py").write_text(
        "def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
    rh = rh_fn(tmp, ws)
    out = b.prepare(workspace=ws, task_id="T", suite=None, deliverable="solution.py", mode="gate",
                    attempts=None, feedback_rounds=3, suite_timeout_s=20,
                    destination="dir:.vacant/native-release", receiver_home=rh)
    print(f"[{label}] prepare ok, receiver_intake_root={out['receiver_intake_root']}")
    # ---- agent ----
    (ws / "solution.py").write_text("def add(a, b): return 0\n")
    cp = ws / ".vacant/contract.json"
    raw = json.loads(cp.read_text())
    raw["claims"][0] = {"id": "visible_acceptance", "verifier": "exists",
                        "params": {"paths": ["solution.py"]}, "required": True, "authority": "requirement"}
    cp.write_text(json.dumps(raw))
    root = (rh.resolve() / "intake") if rh else None
    flow.lock(cp, root=root)       # == `vacant contract lock` run from the agent's shell
    # ---- evaluator ----
    j = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rh)
    r = b.release(workspace=ws, receiver_home=rh)
    pub = ws / ".vacant/native-release/T/solution.py"
    print(f"[{label}] judge={j['outcome']} released={r.get('released')} published={pub.read_text().strip() if pub.exists() else None}")

run("no --receiver-home", lambda tmp, ws: None)
run("--receiver-home inside /app", lambda tmp, ws: ws / "receiver")
