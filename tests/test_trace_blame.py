"""追到造成錯誤的那一步（`trace/blame.py`）：一個症狀、不同的起因、一個盲點。

情境（DECISION_20260924_ACCOUNTABLE_TRACE §五）：
  B  agent 憑空寫錯        ⇒ provable（事實層），重跑翻轉在寫下它的那一步
  A  輸入本來就錯          ⇒ input／lineage_exact，指到輸入檔的那一行，agent 不背
  A′ 輸入經 `cat` 讀進來    ⇒ 同上（不是只認 Read 工具）
  C  中間的腳本算錯        ⇒ lineage_internal，指到**寫腳本**的那一步，不是寫報告的那一步
  D  改動沒被記錄（負控制）⇒ UNOBSERVED／gap，不怪任何人
  子 agent 寫錯、主 agent 照抄 ⇒ 指到子 agent 的那一步
  平行的兩步               ⇒ candidate_set
"""
from __future__ import annotations

import json

import pytest

from vacant_network.intake import contract as C
from vacant_network.intake import keys
from vacant_network.trace import blame as B
from vacant_network.trace import recorder as R
from vacant_network.trace import rerun
from vacant_network.trace.locate import Location

MAIN = R.Actor("claude", "s1")
SUB = R.Actor("claude", "s1", agent="ae25", agent_type="general-purpose")
SALES = "id,amount\n1,10\n2,20\n3,30\n"


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    keys.init_local()
    p = tmp_path / "proj"
    (p / "data").mkdir(parents=True)
    (p / ".vacant").mkdir()
    (p / "data" / "sales.csv").write_text(SALES)
    (p / "data" / "cities.csv").write_text("city,population\nSpringfield,3072\n")
    raw = C.scaffold("t", deliverable=["report.md"])
    raw["inputs"] = {"sales": {"path": "data/sales.csv"}, "cities": {"path": "data/cities.csv"}}
    raw["claims"] = [{"id": "total", "verifier": "csv_total", "authority": "fact",
                      "params": {"csv": "input:sales", "column": "amount",
                                 "report": "report.md"}}]
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    return p, C.load(cp), R.Recorder(p)


def _step(rec, sid, actor, tool, inp, out="", write=None):
    rec.pre(sid, actor, tool, inp)
    if write:
        path, text = write
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return rec.post(sid, actor, tool, inp, out)


def _final_blame(proj):
    p, c, rec = proj
    res = rerun.run(c, p)
    return B.blame_results(rec, c, res, p, sandbox="none")


def test_B_agent_writes_a_wrong_total_from_nowhere_is_provable(proj):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Read", {"file_path": str(p / "data/sales.csv")}, SALES)
    _step(rec, "t2", MAIN, "Write", {"file_path": str(p / "report.md"),
                                     "content": "# Q3\nTotal: 999\n"},
          write=(p / "report.md", "# Q3\nTotal: 999\n"))
    [b] = _final_blame(proj)
    assert (b["state"], b["fault_class"], b["confidence"], b["layer"]) == \
        ("located", "agent", "provable", "fact")
    assert b["step"]["step"] == "t2" and b["location"]["line"] == 2
    assert b["rerun"]["before"]["value_here"] is False
    assert b["rerun"]["after"] == {**b["rerun"]["after"], "status": "FAIL", "value_here": True}
    assert b["expected"][0]["value"] == "60"          # 重算出來應該是多少


def test_A_the_input_itself_is_wrong_blames_the_input_not_the_agent(proj):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Read", {"file_path": str(p / "data/cities.csv")},
          "city,population\nSpringfield,3072\n")
    _step(rec, "t2", MAIN, "Write", {"file_path": str(p / "report.md"),
                                     "content": "Population: 3072\n"},
          write=(p / "report.md", "Population: 3072\n"))
    tr = B.Trace(rec)
    b = B.blame_location(tr, Location("report.md", 1, value="3072"), contract=c)
    assert (b["fault_class"], b["confidence"]) == ("input", "lineage_exact")
    assert b["source"] == {"kind": "input", "name": "cities", "path": "data/cities.csv", "line": 2}
    assert [x.get("step") for x in b["chain"]] == ["t2", "t1"]


def test_A_prime_input_read_through_cat_still_traces_to_the_input(proj):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Bash", {"command": "cat data/cities.csv"},
          {"stdout": "city,population\nSpringfield,3072\n"})
    _step(rec, "t2", MAIN, "Edit", {"file_path": "report.md", "new_string": "Population: 3072"},
          write=(p / "report.md", "Population: 3072\n"))
    b = B.blame_location(B.Trace(rec), Location("report.md", 1, value="3072"), contract=c)
    assert (b["fault_class"], b["confidence"]) == ("input", "lineage_exact")
    assert b["source"]["name"] == "cities"


def test_C_a_buggy_script_is_blamed_on_the_step_that_wrote_the_script(proj):
    p, c, rec = proj
    script = "import csv\nprint('Total:', sum(int(r['id']) for r in csv.DictReader(open('data/sales.csv'))))\n"
    _step(rec, "t1", MAIN, "Write", {"file_path": "calc.py", "content": script},
          write=(p / "calc.py", script))
    _step(rec, "t2", MAIN, "Bash", {"command": "python calc.py > report.md"},
          write=(p / "report.md", "Total: 6\n"))
    [b] = _final_blame(proj)
    assert (b["fault_class"], b["confidence"]) == ("agent", "lineage_internal")
    assert b["step"]["step"] == "t1"                         # 寫腳本的那一步
    assert [x.get("step") for x in b["chain"] if "step" in x] == ["t2", "t1"]


def test_D_unrecorded_change_is_a_gap_not_a_blame(proj):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Read", {"file_path": "data/sales.csv"}, SALES)
    (p / "report.md").write_text("Total: 999\n")            # 掛鉤不在的時候寫的
    _step(rec, "t2", MAIN, "Read", {"file_path": "report.md"}, "Total: 999")
    [b] = _final_blame(proj)
    assert (b["state"], b["fault_class"], b["confidence"]) == ("UNOBSERVED", "unattributable", "gap")
    assert b["step"] is None


def test_subagent_wrote_it_and_main_copied_it(proj):
    p, c, rec = proj
    _step(rec, "a1", MAIN, "Agent", {"prompt": "count the sales"}, "")
    _step(rec, "s1", SUB, "Write", {"file_path": "notes.txt", "content": "total=999"},
          write=(p / "notes.txt", "total=999\n"))
    _step(rec, "a2", MAIN, "Read", {"file_path": "notes.txt"}, "total=999")
    _step(rec, "a3", MAIN, "Write", {"file_path": "report.md", "content": "Total: 999"},
          write=(p / "report.md", "Total: 999\n"))
    [b] = _final_blame(proj)
    assert b["step"]["step"] == "s1" and b["step"]["actor"]["agent"] == "ae25"
    assert (b["fault_class"], b["confidence"]) == ("agent", "lineage_internal")


def test_parallel_steps_give_a_candidate_set(proj):
    p, c, rec = proj
    rec.pre("x", MAIN, "Bash", {"command": "gen"})
    rec.pre("y", SUB, "Bash", {"command": "other"})
    (p / "report.md").write_text("Total: 999\n")
    rec.post("x", MAIN, "Bash", {"command": "gen"}, "")
    rec.post("y", SUB, "Bash", {"command": "other"}, "")
    [b] = _final_blame(proj)
    assert b["state"] == "candidate_set" and {x["step"] for x in b["candidates"]} == {"x", "y"}


def test_correct_report_has_nothing_to_blame(proj):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Write", {"file_path": "report.md", "content": "Total: 60"},
          write=(p / "report.md", "Total: 60\n"))
    assert _final_blame(proj) == []


def test_value_fixed_later_moves_the_blame_to_whoever_reintroduced_it(proj):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Write", {"content": "Total: 999"}, write=(p / "report.md", "Total: 999\n"))
    _step(rec, "t2", MAIN, "Edit", {"new_string": "Total: 60"}, write=(p / "report.md", "Total: 60\n"))
    _step(rec, "t3", SUB, "Edit", {"new_string": "Total: 999"}, write=(p / "report.md", "Total: 999\n"))
    [b] = _final_blame(proj)
    assert b["step"]["step"] == "t3" and b["confidence"] == "provable"
