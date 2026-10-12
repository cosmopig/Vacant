import json, pathlib, sys
sys.path.insert(0, "/home/user/Vacant")
sys.path.insert(0, "/home/user/Vacant/tests")
import pytest
from test_zero_budget import Pi, proj, _install, ASK, SALES  # noqa
from vacant_network.trace.recorder import Recorder
from vacant_network.trace import zerostop


def test_cutoff_after_last_turn_pushback_gets_no_final_note(proj):
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    # turn 14: agent says done without writing -> last-turn pushback
    d = a.ev("stop", final_text="The total is 2045.", turn=14, budget=15)
    assert d["action"] == "continue"
    # turn 15: agent writes the file, Harbor aborts at turn_end 15 (no settle)
    a.bash("echo 2045 > /app/answer.txt", "", write={"answer.txt": "2045\n"})
    a.ev("session_end", reason="quit", turn=15, budget=15)
    evs = [e["type"] for e in Recorder(proj).events()]
    print(evs.count("ended"), evs.count("review"))
    js = json.loads((Recorder(proj).dir / "delivery.json").read_text())
    md = (Recorder(proj).dir / "delivery.md").read_text()
    print(md)
    print("in_progress", js.get("in_progress"))
    assert evs.count("ended") == 0 and js.get("in_progress") is True


def test_turns_left_negative_downgrades_stop(proj):
    a = Pi(proj)
    a.ask()
    a.bash("python3 bad.py", "Traceback (most recent call last):\nValueError: bad")
    d = a.ev("stop", final_text="Done.", turn=30, budget=5)
    print(d["reason"])
    body = [ln for ln in d["reason"].splitlines() if ln.startswith("- ")]
    assert len(body) == 1 and "-25 of 5" in body[0]


def test_stop_check_error_then_ended_note_claims_not_done(proj, monkeypatch):
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    def boom(req):
        raise RuntimeError("x")
    monkeypatch.setattr(zerostop, "_run_child", boom)
    d = a.ev("stop", final_text="The total is 2045.")
    a.ev("session_end", reason="quit")
    md = (Recorder(proj).dir / "delivery.md").read_text()
    print(md)
    assert "Ended before the agent said it was done" in md
