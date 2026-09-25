"""`vacant contract quick`：一般人真的會寫的那種契約（`intake/contract.quick`）。

只有人寫出來的才是必要的主張；不替人猜；欄名寫錯在寫契約時就炸；摘要說清楚沒驗什麼。"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from vacant_network.adapters import hook
from vacant_network.intake import contract as C
from vacant_network.intake import keys

SALES = "id,region,amount,qty\n1,North,10,2\n2,South,20,3\n3,North,39,1\n"


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_HOOK_NO_SUBMIT", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
        monkeypatch.delenv(k, raising=False)
    keys.init_local()
    p = tmp_path / "proj"
    (p / "data").mkdir(parents=True)
    (p / "data" / "sales.csv").write_text(SALES)
    return p


def _claims(raw):
    return {c["id"]: c for c in raw["claims"]}


def test_only_what_the_person_wrote_is_required_and_nothing_is_guessed(proj):
    raw, summary = C.quick(proj, deliverable=["report.md"], inputs=["data/sales.csv"],
                           must=["Recommendation"])
    cl = _claims(raw)
    assert set(cl) == {"deliverable_present", "no_secrets_shipped", C.QUICK_TEXT_ID}
    assert all(c["required"] for c in cl.values())
    # 數字欄只當提示，不自己變成主張
    assert not any(c["verifier"] == "csv_total" for c in cl.values())
    assert any("amount" in h and "--total sales:" in h for h in summary["hints"])
    assert "vacant flag" in summary["not_checked"]                  # 沒驗的事說出來，也說怎麼補
    assert raw["inputs"] == {"sales": {"path": "data/sales.csv"}}
    C.parse(raw, path=proj / ".vacant" / "contract.json")          # 本身是合法契約


def test_must_is_plain_text_not_a_regex(proj):
    raw, _ = C.quick(proj, deliverable=["report.md"], must=["Total (USD): $1.5k"])
    pat = _claims(raw)[C.QUICK_TEXT_ID]["params"]["must_contain"][0]
    import re
    assert re.search(pat, "x Total (USD): $1.5k y") and not re.search(pat, "Total USD 1x5k")


def test_a_wrong_column_fails_when_the_contract_is_written(proj):
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["report.md"], inputs=["data/sales.csv"], totals=["amont"])
    assert "no column 'amont'" in str(e.value) and "amount" in str(e.value)


@pytest.mark.parametrize("totals, why", [
    (["amount"], "say which input"),                         # 兩個 CSV：要說哪一個
    (["nosuch:amount"], "no input named"),
])
def test_totals_must_name_an_input_when_it_is_ambiguous(proj, totals, why):
    (proj / "data" / "costs.csv").write_text("id,amount\n1,5\n")
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["report.md"], inputs=["data/sales.csv", "data/costs.csv"],
                totals=totals)
    assert why in str(e.value)


def test_total_by_input_name_or_path_and_tsv(proj):
    (proj / "data" / "costs.tsv").write_text("id\tamount\n1\t5\n2\t6\n")
    raw, _ = C.quick(proj, deliverable=["report.md"],
                     inputs=["data/sales.csv", "data/costs.tsv"],
                     totals=["sales:amount", "data/costs.tsv:amount"])
    cl = _claims(raw)
    assert cl["total_sales_amount"]["params"] == {"csv": "input:sales", "column": "amount",
                                                  "report": "report.md"}
    assert cl["total_costs_amount"]["params"]["delimiter"] == "\t"
    assert cl["total_costs_amount"]["authority"] == "fact"


def test_a_glob_deliverable_needs_report_for_content_checks(proj):
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["out/**"], must=["x"])
    assert "--report" in str(e.value)
    raw, _ = C.quick(proj, deliverable=["out/**"], must=["x"], report="out/summary.md")
    assert _claims(raw)[C.QUICK_TEXT_ID]["params"]["path"] == "out/summary.md"


def test_inputs_must_be_files_inside_the_project(proj, tmp_path):
    outside = tmp_path / "elsewhere.csv"
    outside.write_text("a\n1\n")
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["report.md"], inputs=[str(outside), "data/missing.csv"])
    assert "inside the project" in str(e.value) and "no such file" in str(e.value)


def _cli(proj, *args):
    return subprocess.run([sys.executable, "-m", "vacant_network", "contract", "quick", *args],
                          cwd=proj, capture_output=True, text=True, timeout=120)


def test_cli_writes_locks_and_refuses_to_overwrite(proj):
    r = _cli(proj, "--deliverable", "report.md", "--input", "data/sales.csv",
             "--must", "Recommendation", "--total", "amount", "--lock", "--json")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["locked"]["pins"]["sales"] and len(out["checks"]) == 4
    raw = json.loads((proj / ".vacant" / "contract.json").read_text())
    assert raw["inputs"]["sales"]["sha256"] and C.load(proj / ".vacant" / "contract.json")
    again = _cli(proj, "--deliverable", "report.md")
    assert again.returncode != 0 and "refusing to overwrite" in again.stderr


def test_the_trace_feedback_works_on_a_quick_contract(proj):
    """一行寫出來的契約，回合結束時照樣給 agent 位置與應有的值。"""
    assert _cli(proj, "--deliverable", "report.md", "--input", "data/sales.csv",
                "--total", "amount", "--lock").returncode == 0
    base = {"session_id": "Q1", "cwd": str(proj)}
    hook.handle("claude", "UserPromptSubmit", {**base, "prompt": "write report.md"})
    inp = {"file_path": str(proj / "report.md"), "content": "# Q3\n\nTotal: 70\n"}
    hook.handle("claude", "PreToolUse", {**base, "tool_name": "Write", "tool_use_id": "w1",
                                         "tool_input": inp})
    (proj / "report.md").write_text("# Q3\n\nTotal: 70\n")
    hook.handle("claude", "PostToolUse", {**base, "tool_name": "Write", "tool_use_id": "w1",
                                          "tool_input": inp, "tool_response": {}})
    out, _e, _c = hook.handle("claude", "Stop", base)
    d = json.loads(out)
    assert d["decision"] == "block"
    assert 'report.md:3 says "70"' in d["reason"] and "expected 69" in d["reason"]
