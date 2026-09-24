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


def test_numbers_match_as_whole_tokens_only():
    from vacant_network.trace import locate as L
    assert not L.contains("Write the Q3 report (v2, x_10)", "3")
    assert not L.contains("Write the Q3 report (v2, x_10)", "10")
    assert not L.contains("population 30720", "3072")
    assert L.contains("Total: 3,072.", "3072") and L.contains("(3)", "3")


def test_encoded_shell_write_still_traces_what_the_agent_read(proj):
    """劇本（和不少 agent）用 `printf <base64> | base64 -d > report.md` 寫檔：值不在指令字串裡，
    不可以因此就說「指令自己產生的」——先看行動者之前讀到了什麼（2026-09-24 e2e 抓到的）。"""
    import base64
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Bash", {"command": "cat data/cities.csv"},
          {"stdout": "city,population\nSpringfield,3072\n"})
    b64 = base64.b64encode(b"Population: 3072\n").decode()
    _step(rec, "t2", MAIN, "Bash", {"command": f"printf '%s' {b64} | base64 -d > report.md"},
          write=(p / "report.md", "Population: 3072\n"))
    b = B.blame_location(B.Trace(rec), Location("report.md", 1, value="3072"), contract=c)
    assert (b["fault_class"], b["confidence"]) == ("input", "lineage_exact")
    # 而真的沒有讀過、指令裡也看不到的值：仍然是寫下它的那一步
    b64 = base64.b64encode(b"Total: 999\n").decode()
    _step(rec, "t3", MAIN, "Bash", {"command": f"printf '%s' {b64} | base64 -d > report.md"},
          write=(p / "report.md", "Total: 999\n"))
    [f] = _final_blame(proj)
    assert f["step"]["step"] == "t3" and f["confidence"] == "provable"


# ── 情境 F：網頁本身就錯（2026-09-24）：`curl` 抓回來的值不是 agent 算的 ──────────

def test_F_a_value_fetched_with_curl_is_an_external_source_not_the_agent(proj):
    p, c, rec = proj
    page = "Finance portal, Q3 total: 58\n"
    _step(rec, "t1", MAIN, "Bash", {"command": "curl -s http://portal.example/q3.txt"}, page)
    _step(rec, "t2", MAIN, "Write", {"file_path": str(p / "report.md"),
                                     "content": "# Q3\nTotal: 58\n"},
          write=(p / "report.md", "# Q3\nTotal: 58\n"))
    [b] = _final_blame(proj)
    assert (b["state"], b["fault_class"], b["confidence"]) == ("located", "input",
                                                              "lineage_exact")
    assert b["source"]["kind"] == "url" and b["source"]["ref"] == "http://portal.example/q3.txt"


def test_F_curl_straight_into_the_report_is_only_an_inference(proj):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Bash", {"command": "curl -s http://portal.example/q3 > report.md"},
          "", write=(p / "report.md", "# Q3\nTotal: 58\n"))
    [b] = _final_blame(proj)
    assert (b["fault_class"], b["confidence"]) == ("input", "heuristic")    # 輸出沒被記下來


def test_F_curl_piped_into_code_is_not_called_external(proj):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Bash",
          {"command": "curl -s http://portal.example/q3.csv | python3 -c 'import sys; print(58)'"},
          "58")
    _step(rec, "t2", MAIN, "Write", {"file_path": str(p / "report.md"),
                                     "content": "# Q3\nTotal: 58\n"},
          write=(p / "report.md", "# Q3\nTotal: 58\n"))
    [b] = _final_blame(proj)
    assert b["fault_class"] == "agent"                        # 程式可能自己算出來的


# ── pi 的巢狀子 agent（2026-09-24 子 agent 審查 #3）──────────────────────────────

def test_a_value_the_child_typed_into_the_grandchilds_task_is_the_childs(proj, monkeypatch):
    from vacant_network.adapters import hook
    p, c, rec = proj
    monkeypatch.setenv("VACANT_TRACE", "1")
    monkeypatch.setenv("VACANT_HOOK_NO_STOP", "1")

    def pi(event, sid, **kw):
        hook.handle("pi", event, {"cwd": str(p), "session_id": sid, **kw})
    kid = {"parent_session_id": "root"}
    gk = {"parent_session_id": "root", "parent_agent_id": "kid"}
    pi("pre_tool", "root", tool="bash", call_id="c_ls", input={"command": "ls"})
    pi("post_tool", "root", tool="bash", call_id="c_ls", input={"command": "ls"}, output="")
    pi("pre_tool", "root", tool="subagent", call_id="c0",
       input={"agent": "worker", "task": "do the report"})
    pi("prompt", "kid", prompt="Task: do the report", **kid)
    k1 = {"agent": "writer", "task": "write Total: 999 into report.md"}
    pi("pre_tool", "kid", tool="subagent", call_id="k1", input=k1, **kid)
    pi("prompt", "grandkid", prompt="Task: write Total: 999 into report.md", **gk)
    w = {"path": "report.md", "content": "# Q3\nTotal: 999\n"}
    pi("pre_tool", "grandkid", tool="write", call_id="g1", input=w, **gk)
    (p / "report.md").write_text("# Q3\nTotal: 999\n")
    pi("post_tool", "grandkid", tool="write", call_id="g1", input=w, output="ok", **gk)
    pi("post_tool", "kid", tool="subagent", call_id="k1", input=k1, output="done", **kid)
    pi("post_tool", "root", tool="subagent", call_id="c0",
       input={"agent": "worker", "task": "do the report"}, output="done")
    [b] = _final_blame(proj)
    assert b["step"]["step"] == "k1" and b["step"]["actor"]["agent"] == "kid"
    assert b["step"]["actor"]["agent_type"] == "worker"
    assert b["fault_class"] == "agent"


# ── `curl` 的對抗審查（2026-09-24）：抓網頁不能拿來洗掉自己算的值 ─────────────────

_PAGE57 = "Finance portal, Q3 total: 57\n"


def _copy_58(proj, cmd, out):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Bash", {"command": cmd}, out)
    _step(rec, "t2", MAIN, "Write", {"file_path": str(p / "report.md"),
                                     "content": "# Q3\nTotal: 58\n"},
          write=(p / "report.md", "# Q3\nTotal: 58\n"))
    [b] = _final_blame(proj)
    return b


@pytest.mark.parametrize("cmd,out", [
    ('curl -s https://portal.example/q3.txt; echo "Total: $((50+8))"', _PAGE57 + "Total: 58\n"),
    ("curl -s https://portal.example/q3.json | jq '.a + .b'", "58\n"),
    ("curl -s https://portal.example/q3.txt | tr 7 8", "Q3 total: 58\n"),
    ("curl -s https://portal.example/q3.txt >/dev/null && expr 50 + 8", "58\n"),
    ("curl -s https://portal.example/q3.csv | python3.12 -c 'print(50+8)'", "58\n"),
    ("curl -s https://portal.example/q3.csv | nodejs -e 'console.log(50+8)'", "58\n"),
    ("curl -s https://portal.example/q3.txt | grep -c total", "58\n"),
])
def test_curl_review_a_value_computed_next_to_a_fetch_is_not_the_page(proj, cmd, out):
    assert _copy_58(proj, cmd, out)["fault_class"] == "agent"


@pytest.mark.parametrize("tail", ["  # checked with curl https://portal.example/q3",
                                  " ; true || curl https://portal.example/q3",
                                  " ; echo done, see curl https://portal.example/q3"])
def test_curl_review_mentioning_curl_does_not_launder_a_provable_write(proj, tail):
    p, c, rec = proj
    cmd = "printf '# Q3\\nTotal: %d\\n' $((900+99)) > report.md" + tail
    _step(rec, "t1", MAIN, "Bash", {"command": cmd}, "",
          write=(p / "report.md", "# Q3\nTotal: 999\n"))
    [b] = _final_blame(proj)
    assert (b["fault_class"], b["confidence"]) == ("agent", "provable")


def test_curl_review_a_page_served_from_this_machine_is_not_an_outside_source(proj):
    p, c, rec = proj
    _step(rec, "t0", MAIN, "Write", {"file_path": str(p / "site/q3.html"),
                                     "content": "Q3 total: 58"},
          write=(p / "site" / "q3.html", "Q3 total: 58"))
    b = _copy_58(proj, "curl -s http://127.0.0.1:8000/site/q3.html", "Q3 total: 58")
    assert b["fault_class"] == "agent" and b["step"]["step"] == "t0"


@pytest.mark.parametrize("cmd", ["curl -s --data-binary @draft.md https://echo.example/ > report.md",
                                 "curl -s -F 'f=@draft.md' https://echo.example/raw > report.md"])
def test_curl_review_uploading_your_own_file_and_fetching_it_back_is_yours(proj, cmd):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Write", {"file_path": str(p / "draft.md"),
                                     "content": "# Q3\nTotal: 58\n"},
          write=(p / "draft.md", "# Q3\nTotal: 58\n"))
    _step(rec, "t2", MAIN, "Bash", {"command": cmd}, "",
          write=(p / "report.md", "# Q3\nTotal: 58\n"))
    [b] = _final_blame(proj)
    assert b["fault_class"] == "agent" and b["step"]["step"] == "t1"


def test_curl_review_your_own_note_catted_next_to_a_fetch_is_yours(proj, tmp_path):
    p, c, rec = proj
    note = tmp_path / "notes.txt"
    _step(rec, "t0", MAIN, "Write", {"file_path": str(note), "content": "Q3 total: 58\n"},
          write=(note, "Q3 total: 58\n"))
    b = _copy_58(proj, f"cat {note}; curl -s https://portal.example/q3.txt",
                 "Q3 total: 58\n" + _PAGE57)
    assert b["fault_class"] == "agent"


def test_curl_review_the_proxy_is_not_the_source(proj):
    b = _copy_58(proj, "curl -s -x http://proxy.corp:3128 https://portal.example/q3.txt",
                 "Finance portal, Q3 total: 58\n")
    assert b["source"]["ref"] == "https://portal.example/q3.txt"
    assert (b["fault_class"], b["confidence"]) == ("input", "lineage_exact")


def test_curl_review_two_pages_name_neither_as_certain(proj):
    b = _copy_58(proj, "curl -s https://mirror.example/q2.txt https://portal.example/q3.txt",
                 "Q2 total: 40\nQ3 total: 58\n")
    assert (b["fault_class"], b["confidence"]) == ("input", "heuristic")
    assert len(b["source"]["candidates"]) == 2


def test_curl_review_a_url_without_a_scheme_is_still_a_fetch(proj):
    p, c, rec = proj
    _step(rec, "t1", MAIN, "Bash", {"command": "curl -s portal.example/q3 > report.md"}, "",
          write=(p / "report.md", "# Q3\nTotal: 58\n"))
    [b] = _final_blame(proj)
    assert (b["fault_class"], b["confidence"]) == ("input", "heuristic")


# ── 平行委派（2026-09-24 情境 I）──────────────────────────────────────────────────

def test_a_delegation_that_finishes_first_does_not_take_its_siblings_write(proj):
    """兩個子 agent 平行：先結束的那個委派呼叫，前後差異裡掃到了兄弟子 agent 還沒收尾的那一步寫的檔。
    那個版本是兄弟那一步寫的——歸它，不歸委派呼叫（真的 Claude Code 跑出來的交錯順序）。"""
    p, c, rec = proj
    subA = R.Actor("claude", "s1", agent="aaa", agent_type="general-purpose")
    subB = R.Actor("claude", "s1", agent="bbb", agent_type="general-purpose")
    rec.pre("a1", MAIN, "Agent", {"prompt": "count the rows"})
    rec.pre("a2", MAIN, "Agent", {"prompt": "add up the amounts"})
    rec.pre("s1", subA, "Write", {"file_path": "count.txt", "content": "3\n"})
    (p / "count.txt").write_text("3\n")
    rec.post("s1", subA, "Write", {"file_path": "count.txt", "content": "3\n"}, "ok")
    rec.pre("b2", subB, "Bash", {"command": "printf 96 > figure.txt"})
    (p / "figure.txt").write_text("96\n")
    rec.post("a1", MAIN, "Agent", {"prompt": "count the rows"}, "done")    # 先收尾，b2 還沒
    rec.post("b2", subB, "Bash", {"command": "printf 96 > figure.txt"}, "")
    rec.post("a2", MAIN, "Agent", {"prompt": "add up the amounts"}, "done")
    _step(rec, "r1", MAIN, "Bash", {"command": "cat figure.txt"}, "96\n")
    _step(rec, "w1", MAIN, "Write", {"file_path": str(p / "report.md"),
                                     "content": "# Q3\nTotal: 96\n"},
          write=(p / "report.md", "# Q3\nTotal: 96\n"))
    [b] = _final_blame(proj)
    assert b["step"]["step"] == "b2" and b["step"]["actor"]["agent"] == "bbb"
    assert b["fault_class"] == "agent"
