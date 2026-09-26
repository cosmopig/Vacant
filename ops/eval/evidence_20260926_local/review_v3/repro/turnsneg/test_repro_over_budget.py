"""Repro: once TURNS > stated budget, the zero-config Stop check is narrowed to missing_output only."""
import json
import pathlib

import pytest

from vacant_network.adapters import hook
from vacant_network.adapters import install as INS
from vacant_network.trace import zerostop
from vacant_network.trace.recorder import Recorder

ASK = ("Answer the question using the files in data/. Question: what is the total amount? "
       "Write the answer to /app/answer.txt as a single number.")
SALES = "date,amount\n2026-07-01,1200\n2026-07-02,845\n"


def _install(mode="evidence"):
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": mode}))


@pytest.fixture
def proj(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(zerostop, "_run_child", zerostop.check)
    p = tmp_path / "app"
    (p / "data").mkdir(parents=True)
    (p / "data" / "sales.csv").write_text(SALES)
    _install()
    return p


class Pi:
    def __init__(self, p, sid="S"):
        self.p, self.sid, self.n = p, sid, 0

    def ev(self, event, **kw):
        out, err, code = hook.handle("pi", event, {"cwd": str(self.p), "session_id": self.sid, **kw})
        assert code == 0 and err == ""
        return json.loads(out) if out else {}

    def ask(self, text=ASK):
        return self.ev("prompt", prompt=text)

    def bash(self, cmd, output="", write=None):
        self.n += 1
        inp = {"command": cmd}
        self.ev("pre_tool", tool="bash", call_id=f"c{self.n}", input=inp)
        for rel, content in (write or {}).items():
            (self.p / rel).write_text(content)
        self.ev("post_tool", tool="bash", call_id=f"c{self.n}", input=inp, output=output)


def _scenario(a):
    a.ask()
    # a failed step that the agent then ignores, and an answer file written anyway
    a.bash("awk -F, 'NR>1{s+=$2}END{print s}' data/sales.csv", "awk: Error: bad field")
    a.bash("echo 9999 > /app/answer.txt", "", write={"answer.txt": "9999\n"})


def test_baseline_no_budget_failed_step_is_sent_back(proj):
    a = Pi(proj, sid="A")
    _scenario(a)
    d = a.ev("stop", final_text="Done. The total is 2045.")
    print("NO BUDGET:", json.dumps(d)[:600])
    assert d["action"] == "continue"


def test_under_budget_failed_step_is_sent_back(proj):
    a = Pi(proj, sid="B")
    _scenario(a)
    d = a.ev("stop", final_text="Done. The total is 2045.", turn=5, budget=20)
    print("TURN 5/20:", json.dumps(d)[:600])
    assert d["action"] == "continue"


def test_over_budget_failed_step_silently_dropped(proj):
    a = Pi(proj, sid="C")
    _scenario(a)
    d = a.ev("stop", final_text="Done. The total is 2045.", turn=32, budget=20)
    print("TURN 32/20:", json.dumps(d)[:600])
    assert d["action"] == "allow"        # the failed step is no longer sent back


def test_over_budget_missing_file_says_negative_turns(proj):
    a = Pi(proj, sid="D")
    a.ask()
    a.bash("python3 bad.py", "Traceback (most recent call last):\nValueError: bad")
    d = a.ev("stop", final_text="Done. The total is 2045.", turn=32, budget=20)
    print("TURN 32/20 missing:", d["reason"])
    assert d["action"] == "continue"
    assert "-12 of 20" in d["reason"]
    body = [ln for ln in d["reason"].splitlines() if ln.startswith("- ")]
    assert len(body) == 1


def test_at_budget_exactly_also_narrowed(proj):
    a = Pi(proj, sid="E")
    _scenario(a)
    d = a.ev("stop", final_text="Done. The total is 2045.", turn=20, budget=20)
    print("TURN 20/20:", json.dumps(d)[:600])
    assert d["action"] == "allow"
