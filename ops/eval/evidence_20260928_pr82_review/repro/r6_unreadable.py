"""R6 (simulated EACCES): repair arm with a receiver suite the agent uid cannot read -> Stop check is UNKNOWN -> no feedback."""
import importlib.util, pathlib, tempfile, os, errno
from vacant_network.intake import contract as C, flow
from vacant_network.adapters.hookpolicy import HookEvent, decide_stop
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["VACANT_HOME"] = str(tmp / "agent-home")
ws = tmp / "app"; ws.mkdir()
recv = tmp / "srv/eval/receiver/T"; rs = recv / "tests_visible"; rs.mkdir(parents=True)
(rs / "test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
b.prepare(workspace=ws, task_id="T", suite=rs, deliverable="solution.py", mode="repair",
          attempts=None, feedback_rounds=3, suite_timeout_s=20,
          destination="dir:.vacant/native-release", receiver_home=recv / "vacant")
(ws / "solution.py").write_text("def add(a, b): return 0\n")
c = C.load(ws / ".vacant/contract.json")
chk = lambda cc, bd: flow.check(cc, bd, sandbox="none")
d = decide_stop(HookEvent(agent="pi", kind="stop", session_id="s-readable", cwd=str(ws)), c, check_fn=chk)
print("receiver suite readable   -> stop:", d.action)
# emulate `chmod 700 /srv/eval/receiver/T` owned by the receiver account (agent gets EACCES)
real_stat = pathlib.Path.stat
def stat(self, *a, **k):
    if str(self).startswith(str(recv)):
        raise PermissionError(errno.EACCES, "Permission denied", str(self))
    return real_stat(self, *a, **k)
pathlib.Path.stat = stat
d = decide_stop(HookEvent(agent="pi", kind="stop", session_id="s-unreadable", cwd=str(ws)), c, check_fn=chk)
print("receiver suite unreadable -> stop:", d.action, d.record)
