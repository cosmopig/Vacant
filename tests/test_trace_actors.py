"""後果（`trace/actors.py`）：只有事實層進信譽、人撤銷逐位元反轉、輸入錯記來源、缺口不怪人、路由。"""
from __future__ import annotations

import pytest

from vacant_network.trace import actors as A
from vacant_network.trace import feedback as F


@pytest.fixture
def book(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return A.ActorBook()


class _C:
    claims = ()


def _blame(conf, fault="agent", actor=None, claim="total", source=None, value="999"):
    return {"claim": claim, "confidence": conf, "fault_class": fault,
            "location": {"path": "report.md", "line": 2, "value": value}, "value": value,
            "step": {"n": 2, "step": "t2", "tool": "Write",
                     "actor": actor or {"platform": "claude", "session": "s",
                                        "agent": "a1", "agent_type": "helper"}},
            "source": source, "chain": [{"actor": {"platform": "claude"}}]}


def test_only_provable_touches_reputation(book, tmp_path):
    bs = [_blame("provable"), _blame("lineage_internal", value="1"), _blame("heuristic", value="2")]
    got = A.consequences(book, bs, contract=_C(), workspace=tmp_path, finding_id=F.finding_id)
    assert [e["kind"] for e in got] == ["provable_fault"]
    st = book.state()
    [cell] = st["cells"]
    assert cell["provable_faults"] == 1 and cell["key"][0] == "builtin:helper"
    assert cell["mean"] < 0.5


def test_dismiss_reverses_exactly(book, tmp_path):
    before = book.state()["cells"]
    [ev] = A.consequences(book, [_blame("provable")], contract=_C(), workspace=tmp_path,
                          finding_id=F.finding_id)
    assert book.state()["cells"] != before
    assert A.dismiss(book, ev["finding_id"], "the verifier was wrong")
    after = book.state()
    assert after["cells"] == before and ev["finding_id"] in after["dismissed"]
    assert len(book.events()) == 2                                    # 兩筆都留


def test_input_fault_tallies_the_source_and_gap_counts_coverage(book, tmp_path):
    bs = [_blame("lineage_exact", fault="input",
                 source={"kind": "input", "name": "cities", "path": "data/cities.csv"}),
          _blame("gap", fault="unattributable", value="7")]
    A.consequences(book, bs, contract=_C(), workspace=tmp_path, finding_id=F.finding_id)
    st = book.state()
    assert st["cells"] == []                                          # 沒有任何行動者被記
    assert st["sources"]["input:data/cities.csv"]["count"] == 1
    assert st["coverage_gaps"] == {"claude": 1}


def test_consequences_are_idempotent(book, tmp_path):
    for _ in range(3):
        A.consequences(book, [_blame("provable")], contract=_C(), workspace=tmp_path,
                       finding_id=F.finding_id)
    assert book.state()["cells"][0]["provable_faults"] == 1


def test_routing_explores_until_n_then_uses_ucb(book, tmp_path):
    fam = ""
    for i in range(A.MIN_N):
        A.record_outcome(book, session_key=f"c{i}", actor={"platform": "claude"},
                         accepted=True, contract=None, workspace=tmp_path)
    p = A.pick_agent(book, fam, ["claude", "codex"])
    assert p["agent"] == "codex" and "exploring" in p["why"]         # 小樣本不拿來做決定
    for i in range(A.MIN_N):
        A.record_outcome(book, session_key=f"x{i}", actor={"platform": "codex"},
                         accepted=i == 0, contract=None, workspace=tmp_path)
    p = A.pick_agent(book, fam, ["claude", "codex"])
    assert p["agent"] == "claude" and "5/5" in p["why"] and "1/5" in p["why"]
    line = A.recommendation_line(book, fam)
    assert "claude main [unknown] 5/5 accepted" in line


def test_changed_subagent_definition_is_a_new_cell(book, tmp_path):
    d = tmp_path / ".claude" / "agents"
    d.mkdir(parents=True)
    (d / "helper.md").write_text("v1")
    a = {"platform": "claude", "agent": "x", "agent_type": "helper"}
    k1 = A.key_of(a, None, tmp_path)
    (d / "helper.md").write_text("v2 — different instructions")
    assert A.key_of(a, None, tmp_path)[0] != k1[0] and k1[0].startswith("def:helper:")
