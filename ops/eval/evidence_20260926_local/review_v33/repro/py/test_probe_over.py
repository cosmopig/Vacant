import sys
sys.path.insert(0, "/home/user/Vacant/tests")
from test_zero_budget import Pi, proj, _install  # noqa: F401
from vacant_network.trace import zerostop
from vacant_network.trace.recorder import Recorder


def test_over_budget_after_failed_stop_check(proj, monkeypatch):
    real = zerostop._run_child
    def boom(req):
        raise RuntimeError("check crashed")
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    a.bash("echo 2045 > /app/answer.txt", "", write={"answer.txt": "2045\n"})
    monkeypatch.setattr(zerostop, "_run_child", boom)
    d = a.ev("stop", final_text="Done.", turn=25, budget=10)     # stop check fails -> allow
    print("STOP", d)
    monkeypatch.setattr(zerostop, "_run_child", real)
    a.ev("session_end", reason="quit", turn=25, budget=10, aborted=False, final_answer=True, final_text="Done.")
    print((Recorder(proj).dir / "delivery.md").read_text())
