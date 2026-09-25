"""xpath/locate 對抗審查回歸（2026-09-25，`locate.py`／`feedback.py`／`intake/server.py`）：
定位要照實說「驗證器看到的是什麼」，回饋要用穩定的身分認同一個沒解決的問題。

情境（見各測試前的編號，對應審查清單）：
  1  `forbid_paths`／`text`／`exists` 定位不可以掃到繳付物以外的檔（Stop／`vacant do`／
     `finalize` 這三條路餵的是活的工作區，不是收件口那份已經套過 include／exclude 的隔離區）
  2  `exists` 的 `min_count`：每一個數量不夠的樣式都要報，不是只報完全零命中的
  3  字數規則的 finding id 不可以隨每一輪量到的數字變——同一條沒解決的主張不能被誤報「已解決」
  4  整檔位置（沒有值、沒有行）一律說「最後寫這個檔的是哪一步」，不是「這個值第一次出現」
  5  缺的 `must_contain`：內部用的跳脫正規式不可以被當成「檔案裡的值」印給人看
  6  HTTP 回饋：開著的必要主張全部卡在 UNKNOWN／CONFLICT 時，footer 與 `submitter_fixable`
     要照實說「這不是你能改的」，不要叫提交者重試
  7  RL 的來源說明不可以夾帶指令（「如果輸入錯了，在答案裡指出來」）
  8  （獨立審查對 item 2/3 的回歸）`exists` 半滿足（數量不夠但不是 0）的 finding id
     也不可以隨每一輪數到的數字變——item 3 只堵住了長度規則那條路，這是同一個洞
  9  （獨立審查對 item 5 的回歸）缺的 `required_headings` 拿掉 `value` 之後，
     `note` 也要說出是哪一個標題，不然三個讀者都看不出缺的是哪一個
"""
from __future__ import annotations

import base64
import json

import pytest

from vacant_network.intake import contract as C
from vacant_network.intake import flow
from vacant_network.intake import keys
from vacant_network.intake.server import IntakeApp
from vacant_network.trace import blame as B
from vacant_network.trace import feedback as F
from vacant_network.trace import locate as L
from vacant_network.trace import recorder as R
from vacant_network.trace import rerun

MAIN = R.Actor("claude", "s1")


@pytest.fixture
def vhome(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    keys.init_local()
    return tmp_path


def _proj(base, claims, *, deliverable=("src/**",), inputs=None, files=None):
    p = base / "proj"
    (p / ".vacant").mkdir(parents=True, exist_ok=True)
    for rel, text in (files or {}).items():
        full = p / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(text)
    raw = C.scaffold("t", deliverable=list(deliverable))
    raw["inputs"] = inputs or {}
    if claims:
        raw["claims"] = claims                # 空清單 ⇒ 保留 scaffold 內建的 no_secrets_shipped 等
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    return p, C.load(cp), R.Recorder(p)


def _step(rec, sid, actor, tool, inp, out="", write=None):
    rec.pre(sid, actor, tool, inp)
    if write:
        write[0].parent.mkdir(parents=True, exist_ok=True)
        write[0].write_text(write[1])
    return rec.post(sid, actor, tool, inp, out)


def _http_app(base, claims, *, inputs=None, files=None, deliverable=("report.md",)):
    proj = base / "p"
    (proj / ".vacant").mkdir(parents=True, exist_ok=True)
    for rel, text in (files or {}).items():
        (proj / rel).parent.mkdir(parents=True, exist_ok=True)
        (proj / rel).write_text(text)
    raw = C.scaffold("h1", deliverable=list(deliverable), destination="dir:published")
    raw["inputs"] = inputs or {}
    raw["claims"] = claims
    cp = proj / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    flow.lock(cp)
    return IntakeApp([cp], token="t", sandbox="none")


def _submit(app, task_id, files):
    return app.submit(task_id, {"files": {k: base64.b64encode(v.encode()).decode()
                                          for k, v in files.items()}})


# ── item 1: 定位不可以跑出繳付物外面（#3/#15/#20/#21） ──────────────────────

def test_1_forbid_paths_ignores_a_file_outside_the_deliverable(vhome):
    """`.env.example` 在 `src/**` 外面（deliverable 的範圍是 `src/**`），`no_secrets_shipped`
    的驗證器本身（跑在 manifest 上）不會提到它；重掃活的工作區的舊定位器會。"""
    p, c, rec = _proj(vhome, [], deliverable=("src/**",),
                      files={"src/main.py": "x = 1\n", "src/.env": "SECRET=1\n",
                             ".env.example": "TEMPLATE=1\n"})
    _step(rec, "t1", MAIN, "Write", {"file_path": "src/.env"})
    results = rerun.run(c, p, sandbox="none")
    blames = B.blame_results(rec, c, results, p, sandbox="none")
    paths = {b["location"]["path"] for b in blames if b["claim"] == "no_secrets_shipped"}
    assert paths == {"src/.env"}


def test_1_loc_forbid_prefers_the_verifiers_own_matched_evidence(tmp_path):
    """`_loc_forbid` 直接呼叫：給了 `evidence.matched`（驗證器自己判定過的）就只認那份，
    不重掃 `adir`——就算 `adir` 裡還有別的、契約範圍外的違規檔。"""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / ".env").write_text("A=1\n")
    (tmp_path / ".env.example").write_text("B=1\n")     # 不在 evidence.matched 裡
    ev = {"matched": ["src/.env"]}
    locs = L._loc_forbid({"paths": ["**/.env", "**/.env.*"]}, ev, {}, tmp_path)
    assert [x.path for x in locs] == ["src/.env"]


def test_1_end_to_end_a_non_utf8_file_outside_the_deliverable_is_never_cited(vhome):
    """`must_not_contain` 的樣式（`**/*.md`）比繳付物（`docs/**`）寬：工作區裡另一個不是
    UTF-8 的 `.md` 在繳付物外面，不可以被舊定位器（重掃活的工作區）當成「not UTF-8 text」
    報出來——它根本不在驗證器看過、也不在追緝看得到的範圍裡（2026-09-25 對抗審查 #3）。"""
    p, c, rec = _proj(vhome, [{"id": "no_todo", "verifier": "text", "required": True,
                               "authority": "requirement",
                               "params": {"path": "**/*.md", "must_not_contain": ["TODO"]}}],
                      deliverable=("docs/**",))
    (p / "docs").mkdir(parents=True, exist_ok=True)
    (p / "docs" / "a.md").write_text("intro TODO here\n")
    (p / "outside.md").write_bytes(b"\xff\xfe not part of the deliverable\n")
    _step(rec, "t1", MAIN, "Write", {"file_path": "docs/a.md"})
    results = rerun.run(c, p, sandbox="none")
    blames = B.blame_results(rec, c, results, p, sandbox="none")
    paths = {b["location"]["path"] for b in blames if b["claim"] == "no_todo"}
    assert paths == {"docs/a.md"}
    assert not any("UTF-8" in (b["location"].get("note") or "") for b in blames)


def test_1_allowed_restricts_files_glob_without_touching_disk_outside_it(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.env").write_text("x\n")
    (tmp_path / "other.env").write_text("y\n")
    allowed = frozenset({"src/a.env"})
    assert L._files(tmp_path, "*.env", allowed) == []          # 不比對到 allowed 集合外的東西
    assert L._files(tmp_path, "**/*.env", allowed) == ["src/a.env"]


# ── item 2: `_loc_exists` 的 min_count（#24） ────────────────────────────

def test_2_loc_exists_reports_every_pattern_under_min_count(tmp_path):
    (tmp_path / "tables").mkdir()
    (tmp_path / "tables" / "a.csv").write_text("x\n")
    ev = {"counts": {"figures/*.png": 0, "tables/*.csv": 1}}
    locs = L._loc_exists({"paths": ["figures/*.png", "tables/*.csv"], "min_count": 3}, ev,
                         {}, tmp_path)
    by_path = {x.path: x.note for x in locs}
    assert by_path == {"figures/*.png": "found 0, need 3", "tables/*.csv": "found 1, need 3"}


def test_2_loc_exists_end_to_end_through_the_stop_check(vhome):
    p, c, rec = _proj(vhome, [{"id": "outputs", "verifier": "exists", "required": True,
                               "authority": "requirement",
                               "params": {"paths": ["figures/*.png", "tables/*.csv"],
                                         "min_count": 3}}],
                      deliverable=("figures/**", "tables/**"))
    _step(rec, "t1", MAIN, "Write", {"file_path": "tables/a.csv"},
          write=(p / "tables" / "a.csv", "x\n1\n"))
    results = rerun.run(c, p, sandbox="none")
    blames = B.blame_results(rec, c, results, p, sandbox="none")
    text, _ = F.render_agent(blames, results)
    assert "figures/*.png" in text and "tables/*.csv" in text
    assert "found 1, need 3" in text


# ── item 3: 字數規則的 finding id 要穩（#8/#22） ─────────────────────────────

def test_3_length_rule_finding_id_is_stable_while_the_note_changes(tmp_path):
    params = {"path": "report.md", "min_words": 50}
    (tmp_path / "report.md").write_text("word " * 10)
    [loc1] = L._loc_text(params, {}, {"detail": "report.md: 10 words < min 50"}, tmp_path)
    (tmp_path / "report.md").write_text("word " * 20)
    [loc2] = L._loc_text(params, {}, {"detail": "report.md: 20 words < min 50"}, tmp_path)
    assert loc1.note != loc2.note                       # 顯示的字照實反映當下量到的數字
    b1 = {"claim": "long_enough", "location": loc1.to_json()}
    b2 = {"claim": "long_enough", "location": loc2.to_json()}
    assert F.finding_id(b1) == F.finding_id(b2)          # 身分不隨數字變


def test_3_end_to_end_stop_hook_does_not_report_a_false_resolved(vhome):
    p, c, rec = _proj(vhome, [{"id": "long_enough", "verifier": "text", "required": True,
                               "authority": "requirement",
                               "params": {"path": "report.md", "min_words": 50}}],
                      deliverable=("report.md",))
    prev = None
    seen = []
    for n in (10, 20, 30):
        _step(rec, f"t{n}", MAIN, "Write", {"file_path": "report.md"},
              write=(p / "report.md", ("word " * n)))
        results = rerun.run(c, p, sandbox="none")
        blames = B.blame_results(rec, c, results, p, sandbox="none")
        text, prev = F.render_agent(blames, results, previous=prev)
        seen.append(text)
    assert "Resolved since the last check" not in seen[1]
    assert "Resolved since the last check" not in seen[2]


# ── item 4: 整檔位置的措辭（#25） ────────────────────────────────────────────

def test_4_wholefile_offending_location_says_last_writer_not_first_appeared():
    b = {"claim": "no_secrets_shipped",
         "location": {"path": ".env", "kind": "offending",
                      "note": "a file the contract forbids (**/.env)"},
         "step": {"n": 4, "tool": "Edit"}, "fault_class": "agent",
         "chain": [{"step": "t4"}]}
    text = "\n".join(F.agent_lines(b))
    assert "the last recorded step that wrote .env: step 4 (Edit)" in text
    assert "first appeared" not in text


def test_4_end_to_end_forbidden_file_wording(vhome):
    p, c, rec = _proj(vhome, [], deliverable=("**",))
    _step(rec, "t1", MAIN, "Write", {"file_path": "app.js"}, write=(p / "app.js", "x\n"))
    _step(rec, "t2", MAIN, "Write", {"file_path": ".env"}, write=(p / ".env", "K=1\n"))
    _step(rec, "t3", MAIN, "Edit", {"file_path": ".env"}, write=(p / ".env", "K=1\nD=1\n"))
    results = rerun.run(c, p, sandbox="none")
    blames = B.blame_results(rec, c, results, p, sandbox="none")
    text, _ = F.render_agent(blames, results)
    assert "the last recorded step that wrote .env: step 3 (Edit)" in text
    assert "this value first appeared" not in text


# ── item 5: 缺的 must_contain 不可以把跳脫正規式當值印出來（#18） ──────────────

def test_5_missing_must_contain_value_is_hidden_from_readers(tmp_path):
    (tmp_path / "report.md").write_text("Revenue fell.\n")
    [loc] = L._loc_text({"path": "report.md", "must_contain": ["Q3 revenue grew"]}, {}, {}, tmp_path)
    assert loc.kind == "missing" and loc.value            # 內部字串還在（比對／重跑要用）
    b = {"claim": "says_what_you_asked", "location": loc.to_json(), "value": loc.value}
    assert F._shown_value(b) is None
    report = F.render_report([b], [], outcome="reject", coverage={})
    assert "- value:" not in report
    summary = F.human_summary(
        [b], [{"claim_id": "says_what_you_asked", "status": "FAIL", "required": True}],
        None, why_open=None)
    assert " = " not in summary


def test_5_http_issue_value_is_null_for_a_missing_must_contain(vhome):
    app = _http_app(vhome, [{"id": "says", "verifier": "text", "required": True,
                             "authority": "requirement",
                             "params": {"path": "report.md", "must_contain": ["Q3 revenue grew"]}}])
    code, res = _submit(app, "h1", {"report.md": "Revenue fell.\n"})
    assert code == 200
    [issue] = res["issues"]
    assert issue["value"] is None
    assert "Q3 revenue grew" in issue["note"]              # 人看得懂的話還在 note 裡


def test_5_a_real_offending_value_is_still_shown(tmp_path):
    """不要矯枉過正：`kind != missing` 的位置（真的錯的值）照樣要看得到值。"""
    (tmp_path / "report.md").write_text("Total: 999\n")
    b = {"claim": "total", "location": {"path": "report.md", "line": 1, "value": "999",
                                        "kind": "offending"}, "value": "999"}
    assert F._shown_value(b) == "999"


# ── item 6: HTTP footer／submitter_fixable（#19） ───────────────────────────

def test_6_footer_says_not_agent_fixable_when_only_review_is_open(vhome):
    app = _http_app(vhome, [
        {"id": "has_summary", "verifier": "text", "required": True, "authority": "requirement",
         "params": {"path": "report.md", "must_contain": ["Summary"]}},
        {"id": "editor_ok", "verifier": "review", "required": True, "authority": "requirement",
         "params": {"min_reviews": 1}}])
    code, res = _submit(app, "h1", {"report.md": "# Summary\nall good\n"})
    assert code == 200 and res["outcome"] == "hold"
    assert res["submitter_fixable"] is False
    assert "Fix these and submit again" not in res["feedback"]
    assert "task owner" in res["feedback"]


def test_6_footer_still_invites_a_resubmit_for_an_ordinary_fail(vhome):
    app = _http_app(vhome, [{"id": "says", "verifier": "text", "required": True,
                             "authority": "requirement",
                             "params": {"path": "report.md", "must_contain": ["Summary"]}}])
    code, res = _submit(app, "h1", {"report.md": "nope\n"})
    assert code == 200 and res["outcome"] == "reject"
    assert res["submitter_fixable"] is True
    assert "Fix these and submit again" in res["feedback"]


# ── item 7: RL 來源說明不夾帶指令（R536 相關；#2） ───────────────────────────

def test_7_input_source_line_carries_no_instruction():
    b = {"claim": "total", "location": {"path": "report.md", "line": 1, "value": "4321"},
         "value": "4321", "fault_class": "input",
         "source": {"kind": "input", "path": "inputs/notes.txt", "line": 2, "observed": True}}
    text = "\n".join(F.agent_lines(b))
    assert "the same value is in inputs/notes.txt line 2 (the given input)" in text
    assert "if the input is wrong" not in text
    assert "say so in the answer" not in text


# ── item 8: `exists` 半滿足時 finding id 也要穩（獨立審查對 item 2/3 的回歸） ─────
# item 3 只把「身分」從「note」搬到「key」用在長度規則上；`_loc_exists` 的
# min_count 位置一樣是 note 帶著會變的數字（`found N, need M`）、沒有 key，
# 同一個洞在 exists 這條路上還在：agent 加了一個檔案、樣式還是不夠，note 的
# N 變了、finding_id 就變了，回饋錯報一條「已解決」。

def test_8_loc_exists_key_is_stable_across_a_growing_count(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "n1.md").write_text("x\n")
    params = {"paths": ["notes/*.md"], "min_count": 3}
    [loc1] = L._loc_exists(params, {"counts": {"notes/*.md": 1}}, {}, tmp_path)
    (tmp_path / "notes" / "n2.md").write_text("x\n")
    [loc2] = L._loc_exists(params, {"counts": {"notes/*.md": 2}}, {}, tmp_path)
    assert loc1.note != loc2.note                       # 顯示的字照實反映當下數到的數量
    assert loc1.key and loc1.key == loc2.key             # 身分不隨數字變
    b1 = {"claim": "outputs", "location": loc1.to_json()}
    b2 = {"claim": "outputs", "location": loc2.to_json()}
    assert F.finding_id(b1) == F.finding_id(b2)


def test_8_end_to_end_stop_hook_does_not_report_a_false_resolved_for_exists(vhome):
    p, c, rec = _proj(vhome, [{"id": "outputs", "verifier": "exists", "required": True,
                               "authority": "requirement",
                               "params": {"paths": ["notes/*.md", "figs/*.png"],
                                         "min_count": 3}}],
                      deliverable=("notes/**", "figs/**"))
    prev = None
    seen = []
    for n in (1, 2):
        _step(rec, f"t{n}", MAIN, "Write", {"file_path": f"notes/n{n}.md"},
              write=(p / "notes" / f"n{n}.md", "x\n"))
        results = rerun.run(c, p, sandbox="none")
        blames = B.blame_results(rec, c, results, p, sandbox="none")
        text, prev = F.render_agent(blames, results, previous=prev)
        seen.append(text)
    # round 2 仍然只交了 2 個 notes、0 個 figs——兩個樣式都還沒過，不該有任何 resolved
    assert "Resolved since the last check" not in seen[1]


# ── item 9: 缺的 heading 要說出是哪一個（獨立審查對 item 5 的回歸） ────────────
# item 5 把 `kind == missing` 的 `value`（比對用的內部字串）從讀者看得到的地方
# 拿掉是對的，但 `required_headings` 那個 `note` 本來就是常數字串
# "missing heading"，沒有帶標題名字——拿掉 value 之後，issues[]／report／
# summary 三處都看不出缺的是哪一個標題。

def test_9_missing_heading_name_is_in_the_note(tmp_path):
    (tmp_path / "report.md").write_text("# Summary\nok\n")
    locs = L._loc_text({"path": "report.md",
                        "required_headings": ["Summary", "Risks", "Budget"]}, {}, {}, tmp_path)
    by_note = {loc.note for loc in locs}
    assert by_note == {"missing heading 'Risks'", "missing heading 'Budget'"}


def test_9_http_issue_note_names_the_missing_heading(vhome):
    app = _http_app(vhome, [{"id": "has_headings", "verifier": "text", "required": True,
                             "authority": "requirement",
                             "params": {"path": "report.md",
                                       "required_headings": ["Summary", "Risks", "Budget"]}}])
    code, res = _submit(app, "h1", {"report.md": "# Summary\nok\n"})
    assert code == 200
    notes = {i["note"] for i in res["issues"]}
    assert notes == {"missing heading 'Risks'", "missing heading 'Budget'"}
    assert all(i["value"] is None for i in res["issues"])       # item 5 仍然成立：不印內部字串


def test_9_render_report_shows_no_bare_value_line_but_names_the_heading(vhome):
    p, c, rec = _proj(vhome, [{"id": "has_headings", "verifier": "text", "required": True,
                               "authority": "requirement",
                               "params": {"path": "report.md",
                                         "required_headings": ["Summary", "Risks"]}}],
                      deliverable=("report.md",))
    _step(rec, "t1", MAIN, "Write", {"file_path": "report.md"},
          write=(p / "report.md", "# Summary\nok\n"))
    results = rerun.run(c, p, sandbox="none")
    blames = B.blame_results(rec, c, results, p, sandbox="none")
    [b] = [x for x in blames if x["claim"] == "has_headings"]
    assert F._shown_value(b) is None                    # item 5: 不印跳脫過的內部值
    report = F.render_report(blames, results, outcome="reject", coverage={})
    assert "- value:" not in report
    assert "Risks" in report                             # 但標題名字要看得到（在 note 裡）
