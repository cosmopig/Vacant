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
    (["nosuch:amount"], "no CSV input named 'nosuch'"),
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
    s = cl["total_sales_amount"]["params"]
    assert (s["csv"], s["column"], s["report"]) == ("input:sales", "amount", "report.md")
    assert cl["total_costs_amount"]["params"]["delimiter"] == "\t"
    assert cl["total_costs_amount"]["authority"] == "fact"
    # 同一份報告兩個總數：各自用自己的標籤（預設是欄名），不再互相看成「兩個不同的 Total」
    assert "amount" in s["pattern"] and "first number after 'amount'" in cl["total_sales_amount"][
        "description"]


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


# ── 2026-09-25 對抗審查（`ops/accountability/review_contract_quick/FINDINGS.md`）的回歸 ─────────────

def _write(proj, raw):
    cp = proj / ".vacant" / "contract.json"
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    return C.load(cp)


def _outcome(proj, raw, report):
    from vacant_network.intake import flow
    c = _write(proj, raw)
    for rel, text in report.items():
        (proj / rel).parent.mkdir(parents=True, exist_ok=True)
        (proj / rel).write_text(text)
    res = flow.check(c, proj, sandbox="none")
    return res["outcome"], {r["claim_id"]: (r["status"], r.get("detail")) for r in res["results"]}


def test_two_totals_on_one_report_can_both_pass(proj):
    raw, _ = C.quick(proj, deliverable=["report.md"], inputs=["data/sales.csv"],
                     totals=["amount", "qty"])
    out, res = _outcome(proj, raw, {"report.md": "# Q3\n\nTotal amount: 69\n\nTotal qty: 6\n"})
    assert out == "accept", res


def test_a_label_lets_the_report_use_its_own_wording(proj):
    raw, summ = C.quick(proj, deliverable=["report.md"], inputs=["data/sales.csv"],
                        totals=["amount=合計"])
    assert "first number after '合計'" in summ["checks"][-1]["what"]
    out, res = _outcome(proj, raw, {"report.md": "# 第三季\n\n共 3 筆訂單。合計：69 元\n"})
    assert out == "accept", res


@pytest.mark.parametrize("given", ["./report.md", "{abs}", "out/", "out"])
def test_deliverable_path_forms_are_normalized(proj, given):
    (proj / "out").mkdir()
    d = given.replace("{abs}", str(proj / "report.md"))
    raw, _ = C.quick(proj, deliverable=[d])
    inc = raw["deliverable"]["include"]
    assert inc in (["report.md"], ["out/**"]), inc
    files = {"report.md": "x\n"} if inc == ["report.md"] else {"out/a.md": "x\n"}
    assert _outcome(proj, raw, files)[0] == "accept"


@pytest.mark.parametrize("report, why", [
    ("notes.md", "not part of the deliverable"), ("out/*.md", "one file"), ("out", "one file")])
def test_report_must_be_one_delivered_file(proj, report, why):
    (proj / "out").mkdir()
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["out/**"], must=["x"], report=report)
    assert why in str(e.value)


def test_a_row_wider_than_the_header_does_not_crash(proj):
    (proj / "data" / "brief.csv").write_text("a,b\n1,2,3\n")
    raw, summ = C.quick(proj, deliverable=["report.md"], inputs=["data/brief.csv"])
    assert raw["inputs"]


def test_columns_the_check_cannot_read_are_refused_and_not_hinted(proj):
    (proj / "data" / "odd.csv").write_text("id,amount,price\n1,\"1,5\",2\n2,3,4\n")
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["report.md"], inputs=["data/odd.csv"], totals=["amount"])
    assert "cannot read '1,5'" in str(e.value)
    _raw, summ = C.quick(proj, deliverable=["report.md"], inputs=["data/odd.csv"])
    assert "price" in summ["hints"][0] and "amount" not in summ["hints"][0]


def test_a_totals_row_is_refused(proj):
    (proj / "data" / "t.csv").write_text("region,amount\nNorth,10\nSouth,20\nEast,39\nTotal,69\n")
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["report.md"], inputs=["data/t.csv"], totals=["amount"])
    assert "totals row" in str(e.value) and "line 5" in str(e.value)
    (proj / "data" / "u.csv").write_text("amount\n10\n20\n30\n")       # 最後一列＝前面的和
    with pytest.raises(C.ContractError):
        C.quick(proj, deliverable=["report.md"], inputs=["data/u.csv"], totals=["amount"])


def test_bom_spaces_colons_and_encoding_in_headers(proj):
    (proj / "data" / "bom.csv").write_text("﻿amount, unit:price\n1,2\n3,4\n", encoding="utf-8")
    raw, _ = C.quick(proj, deliverable=["report.md"], inputs=["data/bom.csv"],
                     totals=["bom:amount", "bom:unit:price"])
    cols = [c["params"]["column"] for c in raw["claims"] if c["verifier"] == "csv_total"]
    assert cols == ["﻿amount", " unit:price"]                  # 表頭裡真的那個字串
    out, res = _outcome(proj, raw, {"report.md": "amount 4\nunit:price 6\n"})
    assert out == "accept", res
    (proj / "data" / "big5.csv").write_bytes("金額\n1\n".encode("big5"))
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["report.md"], inputs=["data/big5.csv"], totals=["x"])
    assert "not UTF-8" in str(e.value)


def test_the_contract_is_valid_before_it_is_written(proj):
    (proj / "data" / "zh.csv").write_text("金額,數量\n1,2\n")
    raw, _ = C.quick(proj, deliverable=["report.md"], inputs=["data/zh.csv"],
                     totals=["金額", "zh:數量"])
    ids = [c["id"] for c in raw["claims"]]
    assert len(ids) == len(set(ids))
    C.parse(raw, path=proj / ".vacant" / "contract.json")


def test_task_ids_are_never_silently_replaced(proj, tmp_path):
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["report.md"], task_id="my task")
    assert "--task" in str(e.value)
    a = tmp_path / "報告"
    b = tmp_path / "報表"
    for d in (a, b):
        d.mkdir()
    ta = C.quick(a, deliverable=["x.md"])[0]["task_id"]
    tb = C.quick(b, deliverable=["x.md"])[0]["task_id"]
    assert ta != tb and C._ID_RE.match(ta)


@pytest.mark.parametrize("kw, why", [
    ({"must": [""]}, "empty text"), ({"must_not": ["  "]}, "empty text"),
    ({"heading": None, "deliverable": ["deck.pdf"], "must": ["x"]}, "checks read text")])
def test_things_that_can_never_pass_are_refused(proj, kw, why):
    kw = {"deliverable": ["report.md"], **{k: v for k, v in kw.items() if k != "heading"}}
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, **kw)
    assert why in str(e.value)


def test_heading_markers_are_dropped(proj):
    raw, _ = C.quick(proj, deliverable=["report.md"], headings=["## Summary"])
    assert raw["claims"][-1]["params"]["required_headings"] == ["Summary"]
    assert _outcome(proj, raw, {"report.md": "# R\n\n## Summary\nok\n"})[0] == "accept"


def test_a_missing_must_is_shown_as_the_text_the_person_wrote(proj):
    raw, _ = C.quick(proj, deliverable=["report.md"], must=["Total (USD): $1.5k"])
    out, res = _outcome(proj, raw, {"report.md": "nothing\n"})
    assert out == "reject" and 'does not contain "Total (USD): $1.5k"' in res[C.QUICK_TEXT_ID][1]


def test_cli_errors_exit_2_existing_contracts_are_kept_and_replace_is_explicit(proj):
    bad = _cli(proj, "--deliverable", "report.md", "--input", "data/sales.csv", "--total", "x")
    assert bad.returncode == 2 and "no column 'x'" in bad.stderr
    assert not (proj / ".vacant" / "contract.json").exists()
    (proj / "vacant.contract.json").write_text("{}")
    r = _cli(proj, "--deliverable", "report.md")
    assert r.returncode == 2 and "already exists" in r.stderr
    (proj / "vacant.contract.json").unlink()
    assert _cli(proj, "--deliverable", "report.md").returncode == 0
    r = _cli(proj, "--deliverable", "summary.md", "--replace")
    assert r.returncode == 0
    assert json.loads((proj / ".vacant" / "contract.json").read_text())["deliverable"][
        "include"] == ["summary.md"]


def test_inputs_are_relative_to_where_the_person_is(proj):
    sub = proj / "work"
    sub.mkdir()
    r = subprocess.run([sys.executable, "-m", "vacant_network", "contract", "quick",
                        "--path", str(sub / ".vacant" / "contract.json"),
                        "--deliverable", "report.md", "--input", "../data/sales.csv"],
                       cwd=sub, capture_output=True, text=True, timeout=120)
    assert r.returncode == 2 and "inside the project" in r.stderr     # 在這個專案（work/）外面
    r = subprocess.run([sys.executable, "-m", "vacant_network", "contract", "quick",
                        "--deliverable", "report.md", "--input", "data/sales.csv",
                        "--path", str(proj / ".vacant" / "contract.json")],
                       cwd=proj, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr


def test_missing_text_feedback_does_not_say_first_appeared(proj):
    assert _cli(proj, "--deliverable", "report.md", "--must", "Recommendation",
                "--lock").returncode == 0
    base = {"session_id": "Q2", "cwd": str(proj)}
    inp = {"file_path": str(proj / "report.md"), "content": "# Q3\n"}
    hook.handle("claude", "PreToolUse", {**base, "tool_name": "Write", "tool_use_id": "w1",
                                         "tool_input": inp})
    (proj / "report.md").write_text("# Q3\n")
    hook.handle("claude", "PostToolUse", {**base, "tool_name": "Write", "tool_use_id": "w1",
                                          "tool_input": inp, "tool_response": {}})
    d = json.loads(hook.handle("claude", "Stop", base)[0])
    assert 'does not contain "Recommendation"' in d["reason"]
    assert "first appeared" not in d["reason"]
