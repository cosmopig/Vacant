import importlib.util, json, pathlib, sys, tempfile, os
WT = pathlib.Path(sys.argv[1])
tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["VACANT_HOME"] = str(tmp/"agent_home"); os.environ["HOME"] = str(tmp/"home"); (tmp/"home").mkdir()
for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"): os.environ.pop(k, None)
spec = importlib.util.spec_from_file_location("b", WT/"ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
from vacant_network.adapters import hook, install as INS
from vacant_network.trace import zerostop
zerostop._run_child = zerostop.check
p = INS.state_root()/"install.json"; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))

def run(ws, sid):
    base = {"cwd": str(ws), "session_id": sid}
    hook.handle("pi", "prompt", {**base, "prompt": "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file."})
    pre = {**base, "tool": "write", "call_id": "c1", "input": {"path": str(ws/"solution.py"), "content": "def add(a,b): return a+b\n"}}
    hook.handle("pi", "pre_tool", pre); (ws/"solution.py").write_text("def add(a,b): return a+b\n"); hook.handle("pi", "post_tool", {**pre, "output": "ok"})
    out,_,_ = hook.handle("pi", "stop", {**base, "final_text": "Wrote solution.py. All tests pass."})
    return json.loads(out)

def mk(name):
    ws = tmp/name; (ws/"tests_visible").mkdir(parents=True); (ws/".git").mkdir()
    (ws/"tests_visible"/"test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2,3)==5\n")
    (ws/"goal.md").write_text("Implement add(a, b) in solution.py.\n"); (ws/"contract.md").write_text("Write solution.py.\n")
    return ws
ws = mk("no_bridge"); print("evidence install, no bridge contract ->", run(ws, "S1")["action"])
ws = mk("with_bridge")
b.prepare(workspace=ws, task_id="r6", suite=None, deliverable="solution.py", mode="gate", attempts=None,
          feedback_rounds=3, suite_timeout_s=20, destination="dir:.vacant/native-release", receiver_home=tmp/"recv")
print("evidence install + bridge gate contract ->", run(ws, "S2")["action"])
