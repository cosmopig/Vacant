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
                     totals=["sales:amount=Sales", "data/costs.tsv:amount=Costs"])
    cl = _claims(raw)
    s = cl["total_sales_amount"]["params"]
    assert (s["csv"], s["column"], s["report"]) == ("input:sales", "amount", "report.md")
    assert cl["total_costs_amount"]["params"]["delimiter"] == "\t"
    assert cl["total_costs_amount"]["authority"] == "fact"
    # 同一份報告兩個總數：兩個欄都叫 amount，預設標籤會撞在一起（見下面的碰撞測試），
    # 這裡各自給了明確的 =LABEL，不再互相看成「兩個不同的 Total」
    assert "Sales" in s["pattern"] and "the number after 'Sales'" in cl["total_sales_amount"][
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
    assert "the number after '合計'" in summ["checks"][-1]["what"]
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


# ── 2026-09-25 對抗審查（`quick`）的回歸：#12／#14／#16／#17／C2／C3 ────────────────

def test_1_derived_task_id_always_carries_the_project_hash_no_collision(tmp_path):
    """#12：兩個不同專案，同樣的目錄名（`hw`）、同樣的 `--deliverable answer.md`，衍生出的
    task_id 過去只在名字裡有換不過來的字元時才加雜湊——同目錄名就會撞成同一個 task_id，
    共用同一本帳，course2 的 `vacant release` 就會發出 course1 已核可的成果。"""
    course1 = tmp_path / "course1" / "hw"
    course2 = tmp_path / "course2" / "hw"
    for c in (course1, course2):
        c.mkdir(parents=True)
        (c / "answer.md").write_text("# Answer\n")
    raw1, _ = C.quick(course1, deliverable=["answer.md"])
    raw2, _ = C.quick(course2, deliverable=["answer.md"])
    assert raw1["task_id"] != raw2["task_id"]
    assert C._ID_RE.match(raw1["task_id"]) and C._ID_RE.match(raw2["task_id"])
    # 雜湊確實是專案路徑，不是隨機的：同一個專案再跑一次，id 不變（可重現、不是每次亂數）
    raw1b, _ = C.quick(course1, deliverable=["answer.md"])
    assert raw1b["task_id"] == raw1["task_id"]


def test_1_intake_serve_refuses_two_contracts_with_the_same_task_id(proj, tmp_path, monkeypatch):
    """#12 defense-in-depth：`vacant intake serve` 給兩份 task_id 一樣的契約，過去
    `contract_paths[c.task_id] = p` 會安靜地只留下最後一個，讓提交者互相看到彼此的任務。"""
    from vacant_network.intake import cli as intake_cli

    called: list[dict] = []
    monkeypatch.setattr("vacant_network.intake.server.serve",
                        lambda **kw: called.append(kw) or 0)
    raw1, _ = C.quick(proj, deliverable=["report.md"], must=["x"], task_id="dup")
    c1 = proj / "c1.json"
    c1.write_text(json.dumps(raw1))
    proj2 = tmp_path / "proj2"
    proj2.mkdir()
    raw2, _ = C.quick(proj2, deliverable=["report.md"], must=["x"], task_id="dup")
    c2 = proj2 / "c2.json"
    c2.write_text(json.dumps(raw2))
    args = intake_cli.build_parser().parse_args(
        ["intake", "serve", "--contract", str(c1), "--contract", str(c2),
         "--insecure-no-token"])
    rc = intake_cli.cmd_intake(args)
    assert rc == 2 and not called


@pytest.mark.parametrize("data_csv, totals, spec_that_collides", [
    ("id,amount,amount_usd\n1,10,11\n2,20,22\n3,40,44\n", ["amount", "amount_usd"], "amount_usd"),
    ('id,amount,"net amount"\n1,10,8\n2,20,16\n3,40,32\n', ["amount", "net amount"], "net amount"),
    ("id,q1,q12\n1,5,50\n2,6,60\n", ["q1", "q12"], "q12"),
])
def test_2_colliding_total_labels_are_refused_at_write_time(proj, data_csv, totals,
                                                             spec_that_collides):
    """#14：兩個 `--total` 的預設標籤一個包含另一個（`amount`/`amount_usd`、`amount`/
    `net amount`、`q1`/`q12`），寬鬆的文字比對分不清是哪一個——正確的報告被 HOLD、
    錯的總數從來不會 FAIL。應該在寫契約的當下就炸，而不是留到 `vacant check`。"""
    (proj / "data" / "d2.csv").write_text(data_csv)
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["report.md"], inputs=["data/d2.csv"], totals=totals)
    assert spec_that_collides in str(e.value) and "collide" in str(e.value)
    assert "--total COLUMN=LABEL" in str(e.value)


def test_2_explicit_labels_avoid_the_collision_and_a_wrong_total_fails_not_unknown(proj):
    """給了不會互相包含的 `=LABEL`，兩個總數各自能被找到；錯的總數要 FAIL，不是 UNKNOWN。"""
    (proj / "data" / "d2.csv").write_text(
        "id,amount,amount_usd\n1,10,11\n2,20,22\n3,40,44\n")
    raw, _ = C.quick(proj, deliverable=["report.md"], inputs=["data/d2.csv"],
                     totals=["amount=Amount", "amount_usd=USD"])
    out, res = _outcome(proj, raw, {"report.md": "Total Amount: 70\nTotal USD: 77\n"})
    assert out == "accept", res
    out, res = _outcome(proj, raw, {"report.md": "Total Amount: 999\nTotal USD: 77\n"})
    ids = _claims(raw)
    amount_id = next(i for i in ids if i.startswith("total_") and "amount_usd" not in i)
    assert res[amount_id][0] == "FAIL", res


def test_2_label_word_boundary_does_not_match_inside_a_longer_word(proj):
    """`_label_pattern` 的邊界現在擋整個詞（字母／數字／底線），不是只擋字母。"""
    pat = C._label_pattern("amount")
    import re
    assert not re.search(pat, "amount_usd: 77")
    assert re.search(pat, "amount: 70")
    pat_q1 = C._label_pattern("q1")
    assert not re.search(pat_q1, "q12: 60")
    assert re.search(pat_q1, "q1: 60")


def test_3_replace_path_never_leaves_the_new_contract_shadowed(proj):
    """#16：`--replace --path vacant.contract.json` 過去只是把新檔寫在旁邊——
    `.vacant/contract.json` 還在，`C.find` 照樣先挑到舊的那份，check/do/hooks 全部繼續用
    舊契約。新版本要嘛把舊的搬開讓新檔案生效，要嘛整個還原並回報，不留下這種「寫了但沒用」
    的狀態。"""
    (proj / "report.md").write_text("all fine here\n")
    r1 = _cli(proj, "--deliverable", "report.md", "--must", "fine", "--lock")
    assert r1.returncode == 0, r1.stderr
    r2 = _cli(proj, "--replace", "--path", "vacant.contract.json", "--deliverable", "report.md",
              "--must", "Conclusion", "--lock")
    assert r2.returncode == 0, r2.stderr
    found = C.find(proj)
    assert found is not None
    # 不管新版本選的策略是搬開舊檔還是拒絕整個寫入，find() 找到的一定不能是「寫了看不到效果」
    # 的舊契約——用它真的驗一次 report.md，若它還要求 'fine' 而不是 'Conclusion' 就是舊契約
    c = C.load(found)
    wants_conclusion = any("Conclusion" in cl.description for cl in c.claims)
    assert wants_conclusion, f"{found} still enforces the old claim, not the one just written"


def test_4_sum_only_last_row_is_warned_not_refused(proj):
    """#17：最後一列的值剛好等於前面幾列的和（例如 10/20/30），但**沒有**任何一格寫著
    'Total'／'合計' 之類的標籤——這是很普通的資料（案例正好是這個 repo 自己另一些測試的
    fixture），不該被拒絕；量具給的是警告，契約照樣寫得出來。"""
    (proj / "data" / "u.csv").write_text("id,amount\n1,10\n2,20\n3,30\n")
    raw, summ = C.quick(proj, deliverable=["report.md"], inputs=["data/u.csv"],
                        totals=["amount"])
    assert any("line 4" in w and "sum of the rows above" in w for w in summ["warnings"])
    assert any(c["verifier"] == "csv_total" for c in raw["claims"])
    # 真的有標籤的總計列還是要擋
    (proj / "data" / "labelled.csv").write_text("id,amount\n1,10\n2,20\nTotal,30\n")
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["report.md"], inputs=["data/labelled.csv"], totals=["amount"])
    assert "totals row" in str(e.value)


def test_4_cli_prints_the_sum_only_warning(proj):
    (proj / "data" / "u.csv").write_text("id,amount\n1,10\n2,20\n3,30\n")
    r = _cli(proj, "--deliverable", "report.md", "--input", "data/u.csv", "--total", "amount")
    assert r.returncode == 0, r.stderr
    assert "warning" in r.stdout and "line 4" in r.stdout


def test_5_input_equal_to_deliverable_is_refused_at_write_time(proj):
    """critic C2：`--input notes.md --deliverable notes.md` 寫得出一份 agent 永遠滿足不了的
    契約——hook 把每個契約 input 都設成寫保護，check 卻要求同一個檔案改變。"""
    (proj / "notes.md").write_text("draft\n")
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["notes.md"], inputs=["notes.md"], must=["Summary"])
    assert "notes.md" in str(e.value) and "also inside the deliverable" in str(e.value)


def test_5_input_covered_by_a_deliverable_glob_is_also_refused(proj):
    (proj / "out").mkdir()
    (proj / "out" / "raw.csv").write_text("id,amount\n1,1\n")
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["out/**"], inputs=["out/raw.csv"], must=["x"],
                report="out/raw.csv")
    assert "also inside the deliverable" in str(e.value)


def test_6_directory_deliverable_with_an_existing_env_file_is_refused(proj):
    """critic C3：`--deliverable .` 在一個已經有 `.env.example`／`.env` 的專案裡，會寫出一份
    `no_secrets_shipped` 主張立刻就過不了的契約——第一次 `vacant check` 就 REJECT，而 hook
    路徑會要 agent 刪掉別人的憑證檔。應該在寫契約的當下就講清楚，且不要自動排除。"""
    (proj / "app.py").write_text("print(1)\n")
    (proj / ".env.example").write_text("API_URL=\n")
    with pytest.raises(C.ContractError) as e:
        C.quick(proj, deliverable=["."], must=["print"], report="app.py")
    assert ".env.example" in str(e.value) and "--exclude" in str(e.value)


def test_6_exclude_lets_the_deliverable_pass_and_is_not_automatic(proj):
    (proj / "app.py").write_text("print(1)\n")
    (proj / ".env.example").write_text("API_URL=\n")
    # 不給 --exclude：還是拒絕（不自動排除）
    with pytest.raises(C.ContractError):
        C.quick(proj, deliverable=["."], must=["print"], report="app.py")
    raw, _ = C.quick(proj, deliverable=["."], must=["print"], report="app.py",
                     exclude=["**/.env.example"])
    assert "**/.env.example" in raw["deliverable"]["exclude"]
    out, res = _outcome(proj, raw, {"app.py": "print(1)\n", ".env.example": "API_URL=\n"})
    assert out == "accept", res


def test_6_cli_exclude_flag_is_repeatable(proj):
    (proj / "app.py").write_text("print(1)\n")
    (proj / ".env.example").write_text("API_URL=\n")
    r = _cli(proj, "--deliverable", ".", "--must", "print", "--report", "app.py",
             "--exclude", "**/.env.example")
    assert r.returncode == 0, r.stderr
    raw = json.loads((proj / ".vacant" / "contract.json").read_text())
    assert "**/.env.example" in raw["deliverable"]["exclude"]


def test_replace_with_a_custom_path_is_refused_when_a_standard_contract_is_in_use(tmp_path, monkeypatch, capsys):
    """審查 quick major：`--replace --path my.contract.json` 旁邊有 .vacant/contract.json 時，新檔不會生效。"""
    from vacant_network.intake import cli as icli
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    p = tmp_path / "proj"
    p.mkdir()
    (p / "a.md").write_text("hello\n")
    monkeypatch.chdir(p)
    assert icli.main(["contract", "quick", "--deliverable", "a.md", "--must", "hello"]) == 0
    before = (p / ".vacant" / "contract.json").read_bytes()
    rc = icli.main(["contract", "quick", "--replace", "--path", "my.contract.json",
                    "--deliverable", "a.md", "--must", "NEWTHING"])
    err = capsys.readouterr().err
    assert rc == 2 and "nothing picks up" in err
    assert not (p / "my.contract.json").exists()
    assert (p / ".vacant" / "contract.json").read_bytes() == before


def test_quick_refuses_a_toml_target(tmp_path, monkeypatch, capsys):
    from vacant_network.intake import cli as icli
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    p = tmp_path / "proj"
    p.mkdir()
    (p / "a.md").write_text("hello\n")
    monkeypatch.chdir(p)
    assert icli.main(["contract", "quick", "--path", ".vacant/contract.toml",
                      "--deliverable", "a.md", "--must", "hello"]) == 2
    assert "writes JSON" in capsys.readouterr().err
    assert not (p / ".vacant" / "contract.toml").exists()


def test_input_inside_a_directory_deliverable_suggests_exclude_without_a_second_error(tmp_path):
    from vacant_network.intake import contract as C
    p = tmp_path / "proj"
    p.mkdir()
    (p / "data.csv").write_text("id,amount\n1,10\n2,20\n")
    (p / "r.md").write_text("Total 30\n")
    try:
        C.quick(p, deliverable=["."], inputs=["data.csv"], totals=["amount"], report="r.md", cwd=p)
    except C.ContractError as e:
        msg = "; ".join(e.problems)
    else:
        raise AssertionError("expected a refusal")
    assert "--exclude data.csv" in msg and "could never change" not in msg
    assert "add --input" not in msg
