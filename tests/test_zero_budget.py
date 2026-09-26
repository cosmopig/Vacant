"""零設定 v3（`decisions/DECISION_20260926_ZERO_CONFIG_V3.md`）：回合預算提醒、最後一回合只退回缺檔、
還沒說做完就結束的交件說明、pi 擴充不蓋掉別的擴充的草稿。全部經過真的 `hook.handle("pi", …)`。"""
import json
import pathlib
import re

import pytest

from vacant_network.adapters import agents as AG
from vacant_network.adapters import hook
from vacant_network.adapters import install as INS
from vacant_network.memory import assert_ks1_clean
from vacant_network.trace import zerostop
from vacant_network.trace.feedback import NUDGE_HEADER, REVIEW_HEADER, VACANT_HEADERS
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
    def __init__(self, p: pathlib.Path, sid: str = "S"):
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

    def turn(self, turn, budget=15):
        return self.ev("turn_check", turn=turn, budget=budget)


def _nudges(p):
    return [e for e in Recorder(p).events() if e["type"] == "nudge"]


# ── the budget pattern ───────────────────────────────────────────────

def test_budget_pattern_reads_a_stated_turn_budget_and_nothing_else():
    R = re.compile(AG.BUDGET_RE_SRC, re.I)
    assert R.search("You have a hard budget of 15 model turns. Complete the task").group(1) == "15"
    assert R.search("Use at most 20 steps.").group(1) == "20"
    assert R.search("Read up to 5 files.") is None
    assert R.search("Summarize in 3 bullet points.") is None


def test_the_extension_carries_the_same_pattern_and_appends_to_other_drafts():
    js = AG.pi_extension_text()
    assert "const BUDGET_RE = /" + AG.BUDGET_RE_SRC.replace("/", "\\/") + "/i;" in js
    assert 'pi.on("turn_end"' in js and "turn_check" in js
    # 兩個邊界處理器都接在 event.entries 後面，不蓋掉前面擴充的草稿（pi runner 取最後一個回傳）
    assert js.count("...((event && event.entries) || [])") == 2
    assert "left < 1 || left > 2" in js                      # 只在最後 2 回合
    assert "ctx.signal && ctx.signal.aborted" in js          # 被上限中止的那一回合不送


# ── the reminder ─────────────────────────────────────────────────────

def test_reminder_near_the_end_of_a_stated_budget_when_the_answer_file_is_missing(proj):
    a = Pi(proj)
    a.ask()
    a.bash("python3 -c \"import pandas as pd; print(pd.read_csv('data/sales.csv').amount.sum())\"",
           "2045")
    assert a.turn(10) == {"action": "allow", "reason": ""}       # 還早：什麼都不送
    d = a.turn(13)
    assert d["action"] == "continue"
    lines = d["reason"].splitlines()
    assert lines[0] == NUDGE_HEADER and NUDGE_HEADER in VACANT_HEADERS
    assert "/app/answer.txt" in lines[1] and "2 of 15" in lines[1]
    assert "2045" not in d["reason"]                             # 不引用任何值
    for ln in lines:
        assert_ks1_clean(ln)
    assert a.turn(13)["action"] == "allow"                       # 同一回合不重複
    assert "1 of 15" in a.turn(14)["reason"]
    assert a.turn(15)["action"] == "allow"                       # 上限那一回合（已中止）不送
    assert [e["turn"] for e in _nudges(proj)] == [13, 14]


def test_no_reminder_when_the_file_exists_or_no_budget_or_observe_mode(proj):
    a = Pi(proj)
    a.ask()
    a.bash("echo 2045 > /app/answer.txt", "", write={"answer.txt": "2045\n"})
    assert a.turn(13)["action"] == "allow"
    b = Pi(proj, sid="T")
    (proj / "answer.txt").unlink()
    b.ask()
    b.bash("ls data", "sales.csv")
    assert b.ev("turn_check", turn=13)["action"] == "allow"     # 沒有寫明上限
    _install("observe")
    assert b.turn(13)["action"] == "allow"
    assert _nudges(proj) == []


def test_at_most_two_reminders_per_request_and_a_new_request_starts_over(proj):
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    assert a.turn(13, budget=15)["action"] == "continue"
    assert a.turn(14, budget=15)["action"] == "continue"
    assert a.turn(18, budget=20)["action"] == "allow"            # 同一個要求：已經兩次
    a.ask("Now also write the answer to /app/answer.txt again, from scratch.")
    a.bash("ls data", "sales.csv")
    assert a.turn(18, budget=20)["action"] == "continue"


def test_a_given_input_is_never_reported_as_missing_output(proj):
    a = Pi(proj)
    a.ask("Read data/sales.csv and write the total to data/sales.csv's summary in /app/total.md.")
    a.bash("head data/sales.csv", SALES)
    d = a.turn(13)
    assert d["action"] == "continue" and "sales.csv" not in d["reason"].splitlines()[1].split(",")[0]


def test_no_budget_means_the_stop_check_is_unchanged(proj):
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    d = a.ev("stop", final_text="The total is 2045.")
    assert d["action"] == "continue" and d["reason"].startswith(REVIEW_HEADER)
    assert "turns left" not in d["reason"]


# ── last turn: only the missing file is sent back ────────────────────

def test_with_one_turn_left_only_the_missing_file_is_sent_back(proj):
    a = Pi(proj)
    a.ask()
    a.bash("python3 bad.py", "Traceback (most recent call last):\nValueError: bad")   # 失敗的步驟
    d = a.ev("stop", final_text="Done.", turn=14, budget=15)
    assert d["action"] == "continue"
    body = [ln for ln in d["reason"].splitlines() if ln.startswith("- ")]
    assert len(body) == 1 and "/app/answer.txt" in body[0] and "1 of 15" in body[0]


# ── ended before the agent said it was done ─────────────────────────

def test_a_run_cut_off_before_the_stop_check_still_gets_a_note_for_the_person(proj):
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    a.turn(13)
    a.turn(14)
    d = a.ev("session_end", reason="quit", turn=15, budget=15)
    assert d == {"action": "allow", "reason": ""}                # 什麼都不送給模型
    note = (Recorder(proj).dir / "delivery.md").read_text()
    assert "Ended before the agent said it was done, after 15 of the stated 15 model turns" in note
    assert "/app/answer.txt: does not exist. Budget reminders were sent after turns 13, 14." in note
    assert [e["type"] for e in Recorder(proj).events()].count("ended") == 1


def test_no_cut_off_note_when_the_stop_check_ran(proj):
    a = Pi(proj)
    a.ask()
    a.bash("echo 2045 > /app/answer.txt", "", write={"answer.txt": "2045\n"})
    a.ev("stop", final_text="The answer is in /app/answer.txt.")
    a.ev("session_end", reason="quit")
    assert [e["type"] for e in Recorder(proj).events()].count("ended") == 0
