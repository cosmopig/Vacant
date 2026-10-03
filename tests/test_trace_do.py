"""`vacant do --feedback-mode`：R536 三臂**只差**下一次嘗試的提示（以一個照提示行事的腳本當 agent）。"""
from __future__ import annotations

import json
import sys

import pytest

from vacant_network.adapters import agents as A
from vacant_network.adapters import run as RUN
from vacant_network.intake import contract as C
from vacant_network.intake import flow, keys

AGENT = r'''
import pathlib, sys
prompt = sys.argv[1]
fixed = "expected 60" in prompt              # 只看得懂追緝過的回饋（RL）
pathlib.Path("report.md").write_text("Total: %s\n" % ("60" if fixed else "999"))
pathlib.Path("seen_prompt.txt").write_text(prompt)
'''


@pytest.fixture
def task(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))
    keys.init_local()
    p = tmp_path / "proj"
    (p / "data").mkdir(parents=True)
    (p / ".vacant").mkdir()
    (p / "data" / "sales.csv").write_text("id,amount\n1,10\n2,20\n3,30\n")
    raw = C.scaffold("do-modes", deliverable=["report.md"])
    raw["inputs"] = {"sales": {"path": "data/sales.csv"}}
    raw["claims"] = [{"id": "total", "verifier": "csv_total", "authority": "fact",
                      "params": {"csv": "input:sales", "column": "amount", "report": "report.md"}}]
    raw["attempts"] = {"max": 3}
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    (tmp_path / "agent.py").write_text(AGENT)
    return flow.open_task(cp), tmp_path / "agent.py"


def _do(task, script, mode):
    t, _ = task
    return RUN.do(t, agent="generic", build=A.generic_build([sys.executable, str(script),
                                                            "{prompt}"]),
                  prompt="Write report.md with the total.", sandbox="none",
                  feedback=lambda r: "GENERIC: " + "; ".join(x["detail"] for x in r["results"]),
                  feedback_mode=mode)


def test_localized_arm_carries_location_and_expected_value(task):
    res = _do(task, task[1], "localized")
    assert res["outcome"] == "accept" and len(res["attempts"]) == 2
    assert [a["failing_required"] for a in res["attempts"]] == [1, 0]
    import pathlib
    seen = (pathlib.Path(res["workspace"]) / "seen_prompt.txt").read_text()
    assert 'report.md:1 says "999"' in seen and "expected 60" in seen


def test_generic_arm_gets_the_old_text_only(task):
    res = _do(task, task[1], "generic")
    assert res["outcome"] == "reject" and len(res["attempts"]) == 3
    import pathlib
    seen = (pathlib.Path(res["workspace"]) / "seen_prompt.txt").read_text()
    assert seen.count("GENERIC: report says 999, recomputed 60") == 1


def test_none_arm_redraws_from_a_clean_workspace_with_the_original_prompt(task):
    res = _do(task, task[1], "none")
    assert res["outcome"] == "reject" and len(res["attempts"]) == 3
    import pathlib
    ws = pathlib.Path(res["workspace"])
    assert ws.name == "ws3" and (ws / "seen_prompt.txt").read_text() == \
        "Write report.md with the total."


def test_unknown_mode_is_refused(task):
    with pytest.raises(ValueError):
        _do(task, task[1], "shout")
