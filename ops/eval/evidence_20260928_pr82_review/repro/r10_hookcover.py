"""R10: the agent's pre-tool hook protects only ITS VACANT_HOME; a same-uid --receiver-home is outside that rule."""
import importlib.util, pathlib, tempfile, os
from vacant_network.intake import contract as C
from vacant_network.adapters.hookpolicy import HookEvent, decide_pre_tool
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
for label, use_rh in (("no --receiver-home (shared VACANT_HOME)", False), ("--receiver-home, same uid", True)):
    tmp = pathlib.Path(tempfile.mkdtemp())
    os.environ["VACANT_HOME"] = str(tmp / "agent-home")
    ws = tmp / "app"; (ws / "tests_visible").mkdir(parents=True)
    (ws / "tests_visible/test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
    rh = tmp / "srv/eval/receiver/T/vacant" if use_rh else None
    b.prepare(workspace=ws, task_id="T", suite=None, deliverable="solution.py", mode="repair",
              attempts=None, feedback_rounds=3, suite_timeout_s=20,
              destination="dir:.vacant/native-release", receiver_home=rh)
    root = (rh / "intake") if rh else (tmp / "agent-home/intake")
    c = C.load(ws / ".vacant/contract.json")
    key = root / "keys/owner/identity.key"; trust = root / "trust.json"
    rd = decide_pre_tool(HookEvent(agent="pi", kind="pre_tool", tool="read", paths=[str(key)], cwd=str(ws)), c)
    wr = decide_pre_tool(HookEvent(agent="pi", kind="pre_tool", tool="write", paths=[str(trust)], cwd=str(ws)), c)
    sh = decide_pre_tool(HookEvent(agent="pi", kind="pre_tool", tool="bash", command=f"cat {key}", cwd=str(ws)), c)
    print(f"{label:42s} read owner key: {rd.action:5s} write trust.json: {wr.action:5s} `cat key`: {sh.action}")
