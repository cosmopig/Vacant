import json, pathlib, sys
sys.path.insert(0, "/home/user/Vacant/tests")
from test_zero_budget import Pi, proj, _install  # noqa: F401  (fixture)
from vacant_network.trace.recorder import Recorder


def test_sent_back_then_final_on_cap(proj):
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    d = a.ev("stop", final_text="The total is 2045.", turn=14, budget=15)
    print("STOP14", d)
    assert d["action"] == "continue"
    a.ev("session_end", reason="quit", turn=15, budget=15, aborted=True, final_answer=True,
         final_text="The total is 2045.")
    print((Recorder(proj).dir / "delivery.md").read_text())


def test_sent_back_then_cut_off(proj):
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    d = a.ev("stop", final_text="Done.", turn=14, budget=15)
    assert d["action"] == "continue"
    a.bash("cat data/sales.csv", "date,amount")
    a.ev("session_end", reason="quit", turn=16, budget=15, aborted=True)
    print((Recorder(proj).dir / "delivery.md").read_text())
