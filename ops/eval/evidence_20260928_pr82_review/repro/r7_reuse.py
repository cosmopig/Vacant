"""R7: same --task-id + same --receiver-home across two runs (seeds/arms) => release of seed 2 publishes seed 1's artifact."""
import importlib.util, pathlib, tempfile, os
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["VACANT_HOME"] = str(tmp / "agent-home")
rs = tmp / "srv/eval/receiver/HumanEval_141/tests_visible"; rs.mkdir(parents=True)
(rs / "test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
rh = tmp / "srv/eval/receiver/HumanEval_141/vacant"
def run(seed, sol):
    ws = tmp / f"app_s{seed}"; ws.mkdir()
    b.prepare(workspace=ws, task_id="HumanEval_141", suite=rs, deliverable="solution.py", mode="gate",
              attempts=None, feedback_rounds=3, suite_timeout_s=20,
              destination="dir:.vacant/native-release", receiver_home=rh)
    (ws / "solution.py").write_text(sol)
    j = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rh)
    r = b.release(workspace=ws, receiver_home=rh)     # as in the module docstring: judge, then release
    pub = ws / ".vacant/native-release/HumanEval_141/solution.py"
    print(f"seed {seed}: judge={j['outcome']} judged_sha={str(j.get('artifact_sha256'))[:12]} "
          f"released={r.get('released')} released_sha={str(r.get('artifact_sha256'))[:12]} "
          f"published={pub.read_text().strip() if pub.exists() else None!r}")
run(1, "def add(a, b): return a + b\n")
run(2, "def add(a, b): return 0\n")
