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
    assert R.search("Use at most 20 turns.").group(1) == "20"
    assert R.search("Read up to 5 files.") is None
    assert R.search("Summarize in 3 bullet points.") is None
    # v3.1：專案說明裡的計畫步數、重試次數不是回合上限（pi 也把 AGENTS.md 放進系統提示）
    assert R.search("Break large changes into at most 6 steps.") is None
    assert R.search("Retry flaky tests up to 5 iterations.") is None


@pytest.mark.skipif(not pathlib.Path("/opt/node22/bin/node").exists() and not __import__("shutil").which("node"),
                    reason="node not installed")
def test_the_extension_reads_the_last_stated_budget(tmp_path):
    """harness 把上限接在專案說明後面：取最後一句（v3.1）。在真的 node 裡跑擴充的 readBudget。"""
    import shutil
    import subprocess
    node = shutil.which("node") or "/opt/node22/bin/node"
    js = AG.pi_extension_text()
    src = re.search(r"const BUDGET_RE = (/.*/i);", js).group(1)
    fn = re.search(r"function readBudget[\s\S]*?\n\}", js).group(0)
    prog = (f"const BUDGET_RE = {src};\n{fn}\nconsole.log(JSON.stringify(["
            "readBudget('Project rule: at most 8 turns per sub-task.\\n\\nYou have a hard budget of 15 model turns.'),"
            "readBudget('no budget here'), readBudget('max 3 turns')]));")
    out = subprocess.run([node, "-e", prog], capture_output=True, text=True, timeout=30)
    assert json.loads(out.stdout) == [15, None, None]


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


def test_a_file_written_under_the_agents_subfolder_counts_as_there(tmp_path, monkeypatch, proj):
    """專案根＝git 根、agent 在子資料夾裡工作：相對路徑的要求檔寫在子資料夾裡也算在（v3.1）。"""
    import subprocess
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    sub = proj / "analysis"
    sub.mkdir()
    a = Pi(sub)
    a.ask("Read ../data/sales.csv and write the total to out.txt as a single number.")
    a.bash("echo 2045 > out.txt", "", write={"out.txt": "2045\n"})
    (proj / "out.txt").unlink(missing_ok=True)
    (sub / "out.txt").write_text("2045\n")
    assert a.turn(13)["action"] == "allow"
    d = a.ev("stop", final_text="The total is in out.txt.")
    assert "does not exist" not in (d.get("reason") or "")


def test_beyond_the_stated_budget_the_budget_is_ignored(proj):
    """用超過寫明的上限（沒有人在執行它）：不再當成最後一回合（v3.1）。"""
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    d = a.ev("stop", final_text="Done.", turn=20, budget=15)
    assert d["action"] == "continue" and "turns left" not in d["reason"]
    assert a.turn(20, budget=15)["action"] == "allow"


def test_no_budget_means_the_stop_check_is_unchanged(proj):
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    d = a.ev("stop", final_text="The total is 2045.")
    assert d["action"] == "continue" and d["reason"].startswith(REVIEW_HEADER)
    assert "turns left" not in d["reason"]


# ── last turn: only the missing file is sent back ────────────────────

def _two_findings(a):
    """一個真的「失敗的步驟」（自己寫的腳本跑失敗、之後才寫出交付物）＋要求的檔不存在。"""
    a.ask()
    a.n += 1
    w = {"path": "analyze.py", "content": "import pandas\n"}
    a.ev("pre_tool", tool="write", call_id=f"c{a.n}", input=w)
    (a.p / "analyze.py").write_text("import pandas\n")
    a.ev("post_tool", tool="write", call_id=f"c{a.n}", input=w, output="ok")
    a.n += 1
    run = {"command": "python3 analyze.py"}
    a.ev("pre_tool", tool="bash", call_id=f"c{a.n}", input=run)
    a.ev("post_tool", tool="bash", call_id=f"c{a.n}", input=run,
         output="Traceback (most recent call last):\nValueError: bad", is_error=True)
    a.bash("echo draft > notes.md", "", write={"notes.md": "draft\n"})


def test_with_one_turn_left_only_the_missing_file_is_sent_back(proj, tmp_path):
    a = Pi(proj)
    _two_findings(a)
    full = [ln for ln in a.ev("stop", final_text="Done.")["reason"].splitlines() if ln.startswith("- ")]
    assert len(full) == 2                                         # 沒有上限：兩條都退回
    b = Pi(proj, sid="T")
    _two_findings(b)
    d = b.ev("stop", final_text="Done.", turn=14, budget=15)
    body = [ln for ln in d["reason"].splitlines() if ln.startswith("- ")]
    assert len(body) == 1 and "/app/answer.txt" in body[0] and "1 of 15" in body[0]


# ── ended before the agent said it was done ─────────────────────────

def test_a_run_cut_off_before_the_stop_check_still_gets_a_note_for_the_person(proj):
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    a.turn(13)
    a.turn(14)
    d = a.ev("session_end", reason="quit", turn=16, budget=15, aborted=True)
    assert d == {"action": "allow", "reason": ""}                # 什麼都不送給模型
    note = (Recorder(proj).dir / "delivery.md").read_text()
    assert "Ended before the agent said it was done, after the stated 15 model turns; no delivery check ran." in note
    assert "/app/answer.txt: does not exist. Budget reminders were sent after turns 13, 14." in note
    assert [e["type"] for e in Recorder(proj).events()].count("ended") == 1


def test_no_cut_off_note_unless_the_run_was_aborted(proj):
    """`opencode run`（不跑交件前檢查）、檢查出錯、延後：都不是「還沒說做完」（v3.1）。"""
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    a.ev("session_end", reason="quit", turn=5, budget=15)
    assert [e["type"] for e in Recorder(proj).events()].count("ended") == 0


def test_a_run_sent_back_on_its_last_turn_and_then_cut_off_gets_a_note(proj):
    a = Pi(proj)
    a.ask()
    a.bash("ls data", "sales.csv")
    assert a.ev("stop", final_text="Done.", turn=14, budget=15)["action"] == "continue"
    a.ev("session_end", reason="quit", turn=15, budget=15, aborted=True)
    note = (Recorder(proj).dir / "delivery.md").read_text()
    assert "the last delivery check had sent it back" in note


def test_no_cut_off_note_when_the_stop_check_ran(proj):
    a = Pi(proj)
    a.ask()
    a.bash("echo 2045 > /app/answer.txt", "", write={"answer.txt": "2045\n"})
    a.ev("stop", final_text="The answer is in /app/answer.txt.")
    a.ev("session_end", reason="quit", aborted=True)
    assert [e["type"] for e in Recorder(proj).events()].count("ended") == 0
