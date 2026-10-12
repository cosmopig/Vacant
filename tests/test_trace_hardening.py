"""可究責追緝的對抗審查回歸（2026-09-24：五個鏡頭 46 條逐條重現＋完備性批判；
`ops/accountability/review_m8/`）。每一條一個會紅的測試；名字裡帶審查編號。"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import subprocess
import sys

import pytest

from vacant_network.adapters import hook
from vacant_network.intake import contract as C
from vacant_network.intake import keys
from vacant_network.trace import actors as A
from vacant_network.trace import blame as B
from vacant_network.trace import capture
from vacant_network.trace import feedback as F
from vacant_network.trace import recorder as R
from vacant_network.trace import rerun
from vacant_network.trace import workspace as W

MAIN = R.Actor("claude", "s1")
SUB = R.Actor("claude", "s1", agent="ae25", agent_type="general-purpose")
SALES = "id,amount\n1,10\n2,20\n3,30\n"


def _proj(tmp_path, monkeypatch, claims, inputs=None, files=None, include=None):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    keys.init_local()
    p = tmp_path / "proj"
    (p / "data").mkdir(parents=True, exist_ok=True)
    (p / ".vacant").mkdir(exist_ok=True)
    (p / "data" / "sales.csv").write_text(SALES)
    for rel, text in (files or {}).items():
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text(text)
    raw = C.scaffold("h", deliverable=include or ["report.md", "out.json"])
    raw["inputs"] = inputs if inputs is not None else {"sales": {"path": "data/sales.csv"}}
    raw["claims"] = claims
    raw["hooks"] = {"stop_check": True, "max_feedback_rounds": 2, "submit_on_end": False}
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    return p, C.load(cp), R.Recorder(p)


TOTAL = [{"id": "total", "verifier": "csv_total", "authority": "fact",
          "params": {"csv": "input:sales", "column": "amount", "report": "report.md"}}]


def _step(rec, sid, actor, tool, inp, out="", write=None):
    rec.pre(sid, actor, tool, inp)
    if write:
        write[0].parent.mkdir(parents=True, exist_ok=True)
        write[0].write_text(write[1])
    return rec.post(sid, actor, tool, inp, out)


def _blames(p, c, rec):
    return B.blame_results(rec, c, rerun.run(c, p, sandbox="none"), p, sandbox="none")


# ── blame ───────────────────────────────────────────────────────────

def test_blame0_the_located_line_is_traced_not_any_occurrence(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, [{"id": "todo", "verifier": "text",
                      "params": {"path": "report.md", "must_not_contain": ["TODO"]}}])
    _step(rec, "t1", SUB, "Write", {"c": 1}, write=(p / "report.md", "# R\nIntro TODO\n"))
    _step(rec, "t2", MAIN, "Edit", {"c": 2},
          write=(p / "report.md", "# R\nIntro TODO\nConclusion TODO\n"))
    _step(rec, "t3", SUB, "Edit", {"c": 3},
          write=(p / "report.md", "# R\nIntro done.\nConclusion TODO\n"))
    [b] = _blames(p, c, rec)
    assert b["step"]["step"] == "t2" and b["confidence"] == "provable"


@pytest.mark.parametrize("cmd,cwd", [("python3 -u calc.py > report.md", ""),
                                     ("uv run calc.py > report.md", ""),
                                     ("cd tools && python calc.py > ../report.md", "tools")])
def test_blame1_scripts_behind_flags_runners_and_cd_are_found(tmp_path, monkeypatch, cmd, cwd):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    script = "print('Total:', sum(r for r in [1, 2, 3]))\n"
    _step(rec, "t1", SUB, "Write", {"file_path": f"{cwd}/calc.py".lstrip("/")},
          write=(p / cwd / "calc.py", script))
    _step(rec, "t2", MAIN, "Bash", {"command": cmd}, write=(p / "report.md", "Total: 6\n"))
    [b] = _blames(p, c, rec)
    assert (b["step"]["step"], b["confidence"]) == ("t1", "lineage_internal")


def test_blame1_a_script_nobody_wrote_is_the_given_tooling(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL,
                      files={"scripts/calc.py": "print('Total:', 6)\n".replace("6", "len('abcdef')")})
    _step(rec, "t1", MAIN, "Bash", {"command": "python scripts/calc.py > report.md"},
          write=(p / "report.md", "Total: 6\n"))
    [b] = _blames(p, c, rec)
    assert b["fault_class"] == "input" and b["source"]["path"] == "scripts/calc.py"
    assert b["confidence"] != "provable"


def test_blame2_json_shaped_outputs_are_read_as_text(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL, files={"notes/q2.txt": "Q2 summary\n999 in"})
    _step(rec, "t1", MAIN, "Bash", {"command": "cat notes/q2.txt"},
          {"stdout": "Q2 summary\n999 in", "stderr": ""})
    _step(rec, "t2", MAIN, "Write", {"content": "Total: 999"}, write=(p / "report.md",
                                                                        "Total: 999\n"))
    [b] = _blames(p, c, rec)
    assert b["fault_class"] == "input" and b["source"]["path"] == "notes/q2.txt"


def test_blame3_json_schema_blames_whoever_wrote_the_bad_value(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, [{"id": "shape", "verifier": "json_schema", "params": {
        "path": "out.json", "schema": {"type": "object", "properties": {
            "total": {"type": "integer", "minimum": 0}}}}}])
    _step(rec, "t1", MAIN, "Write", {"c": "ok"}, write=(p / "out.json", '{\n "total": 60\n}\n'))
    _step(rec, "t2", SUB, "Edit", {"c": -5}, write=(p / "out.json", '{\n "total": -5\n}\n'))
    [b] = _blames(p, c, rec)
    assert b["value"] == "-5" and b["step"]["step"] == "t2"


def test_blame4_own_earlier_write_is_not_an_external_source(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    _step(rec, "t1", MAIN, "Write", {"file_path": "notes.md", "content": "Total: 999"},
          {"type": "create", "content": "Total: 999"}, write=(p / "notes.md", "Total: 999\n"))
    _step(rec, "t2", MAIN, "Write", {"content": "Total: 999"}, write=(p / "report.md",
                                                                        "Total: 999\n"))
    [b] = _blames(p, c, rec)
    assert b["fault_class"] == "agent"


def test_blame5_a_task_notification_is_not_the_users_message():
    assert capture.prompt_source("claude", {}, "<task-notification>\n<tool-use-id>toolu_1"
                                 "</tool-use-id>\n<result>999</result>") == \
        ("subagent_result", "toolu_1")
    assert capture.prompt_source("codex", {"agent_id": "x"}, "do the sums")[0] == "parent_agent"
    assert capture.prompt_source("claude", {}, "write the report")[0] == "user"


def test_blame6_an_input_the_agent_edited_is_not_the_inputs_fault(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL,
                      inputs={"sales": {"path": "data/sales.csv"},
                              "cities": {"path": "data/cities.csv"}},
                      files={"data/cities.csv": "city,pop\nX,3072\n"})
    _step(rec, "t1", MAIN, "Edit", {"file_path": "data/cities.csv", "new_string": "9999"},
          write=(p / "data/cities.csv", "city,pop\nX,9999\n"))
    _step(rec, "t2", MAIN, "Read", {"file_path": str(p / "data/cities.csv")}, "X,9999")
    _step(rec, "t3", MAIN, "Write", {"content": "Total: 9999"}, write=(p / "report.md",
                                                                         "Total: 9999\n"))
    [b] = _blames(p, c, rec)
    assert b["fault_class"] == "agent" and b["step"]["step"] == "t1"


def test_blame7_writes_during_a_read_only_tool_are_not_its_writes(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    rec.pre("t1", MAIN, "Read", {"file_path": "x"})
    (p / "report.md").write_text("Total: 999\n")
    rec.post("t1", MAIN, "Read", {"file_path": "x"}, "")
    [b] = _blames(p, c, rec)
    assert b["state"] == "candidate_set" and b["confidence"] != "provable"


def test_blame8_the_parents_agent_call_is_not_concurrent_with_its_subagent(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    rec.pre("a1", MAIN, "Agent", {"prompt": "sum it"})
    _step(rec, "s1", SUB, "Write", {"content": "Total: 999"}, write=(p / "report.md",
                                                                       "Total: 999\n"))
    e = rec.post("a1", MAIN, "Agent", {"prompt": "sum it"}, "done")
    assert e["writes"] == [] and e["delegated"] == ["report.md"]
    [b] = _blames(p, c, rec)
    assert (b["step"]["step"], b["confidence"]) == ("s1", "provable")


def test_blame9_the_check_suite_is_never_the_blamed_location(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL,
                      inputs={"sales": {"path": "data/sales.csv"},
                              "suite": {"path": "checks"}},
                      files={"checks/test_visible.py": "def check_add():\n    assert 1\n"},
                      include=["**"])
    r = {"detail": "test_visible.py::check_add — assert [test_visible.py:2: assert 1]"}
    locs = B._fallback_locations(C.Claim("pc", "python_checks", {}, True, "fact", ""), r, p, c)
    assert all(not loc.path.startswith("checks/") for loc in locs)


def test_blame10_an_unrelated_big_file_does_not_disable_provable(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    monkeypatch.setattr(W, "MAX_BLOB", 100)
    (p / "assets").mkdir()
    (p / "assets" / "big.pdf").write_bytes(b"x" * 500)
    _step(rec, "t1", MAIN, "Write", {"content": "Total: 999"}, write=(p / "report.md",
                                                                        "Total: 999\n"))
    [b] = _blames(p, c, rec)
    assert b["confidence"] == "provable"


def test_critique_instruction_files_are_sources(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL,
                      files={"CLAUDE.md": "House rule: the quarterly total is 777.\n"})
    _step(rec, "t1", MAIN, "Write", {"content": "Total: 777"}, write=(p / "report.md",
                                                                        "Total: 777\n"))
    [b] = _blames(p, c, rec)
    assert b["fault_class"] == "input" and b["source"]["kind"] == "instructions"


def test_critique_correct_value_seen_is_reported(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    _step(rec, "t1", MAIN, "Bash", {"command": "python -c 'print(60)'"}, {"stdout": "60\n"})
    _step(rec, "t2", MAIN, "Write", {"content": "Total: 999"}, write=(p / "report.md",
                                                                        "Total: 999\n"))
    [b] = _blames(p, c, rec)
    assert b["correct_value_seen"] == {"seen": True, "step": 1, "via": "shell"}


# ── what reaches the agent ──────────────────────────────────────────

def _hb(claim, hidden, value="999", **kw):
    return {"claim": claim, "hidden": hidden, "required": True, "fault_class": "agent",
            "location": {"path": "report.md", "line": 2, "value": value}, "value": value,
            "step": {"n": 1, "tool": "Write", "actor": {"agent": "ae25c0de"}}, **kw}


def test_agent_text0_hidden_claims_are_one_line_without_markers():
    prev = {"open": {F.finding_id(_hb("secret", True)): "secret"}}
    text, st = F.render_agent([_hb("secret", True), _hb("secret", True, value="998")],
                              [], previous=prev)
    assert text.count("secret: FAIL (details withheld") == 1
    assert "still open" not in text and "Resolved" not in text and st["open"] == {}


def test_agent_text1_hidden_only_inputs_are_not_named():
    b = _hb("total", False, fault_class="input", source={"kind": "input", "path": "secret.csv"},
            source_hidden=True)
    text, _ = F.render_agent([b], [])
    assert "secret.csv" not in text


def test_agent_text2_a_dirty_line_is_dropped_not_the_whole_feedback():
    b = _hb("tone", False, value="you are responsible for this")
    text, _ = F.render_agent([b], [])
    assert "you are responsible" not in text.lower() and "left out" in text
    assert "first appeared at step 1" in text


def test_agent_text3_a_preexisting_deliverable_value_is_not_called_the_input():
    b = _hb("total", False, fault_class="input", source={"kind": "file", "path": "report.md"})
    text, _ = F.render_agent([b], [])
    assert "already in report.md" in text and "say so in the answer" not in text


def test_agent_text4_any_recorded_actor_is_guarded():
    b = _hb("t", False, detail="the helper Explore-9 said so")
    b["expected"] = []
    text, _ = F.render_agent([b], [], extra_tokens={"Explore-9"})
    assert "Explore-9" not in text


# ── recorder ────────────────────────────────────────────────────────

def test_recorder0_a_fifo_does_not_hang_the_scan(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    os.mkfifo(ws / "pipe")
    (ws / "a.txt").write_text("x")
    assert set(W.scan(ws)) == {"a.txt"}


def test_recorder2_secrets_are_hashed_not_stored_and_the_store_is_private(tmp_path):
    ws = tmp_path / "ws"
    (ws / ".ssh").mkdir(parents=True)
    (ws / ".env").write_text("TOKEN=abc")
    (ws / ".ssh" / "id_rsa").write_text("KEY")
    (ws / "a.txt").write_text("ok")
    store = W.Blobs(tmp_path / "objects")
    idx = W.scan(ws, blobs=store)
    assert idx[".env"].sha256.startswith("secret:") and idx[".ssh/id_rsa"].sha256.startswith(
        "secret:")
    stored = [p.read_bytes() for p in (tmp_path / "objects").rglob("*") if p.is_file()]
    assert b"TOKEN=abc" not in stored and b"KEY" not in stored
    blob = store.path(idx["a.txt"].sha256)
    assert oct(blob.stat().st_mode & 0o777) == "0o600"


def test_recorder3_4_verify_is_trusted_and_catches_truncation(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))          # 沒有 keys init
    ws = tmp_path / "ws"
    ws.mkdir()
    rec = R.Recorder(ws)
    _step(rec, "t1", MAIN, "Write", {}, write=(ws / "a", "1"))
    _step(rec, "t2", MAIN, "Write", {}, write=(ws / "b", "2"))
    assert rec.verify()[0]
    lines = rec.chain_path.read_text().splitlines()
    rec.chain_path.write_text("\n".join(lines[:-2]) + "\n")
    ok, why = rec.verify()
    assert not ok and "truncated" in why


def test_recorder5_an_edited_chain_records_no_consequence(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    _step(rec, "t1", SUB, "Write", {}, write=(p / "report.md", "Total: 999\n"))
    lines = rec.chain_path.read_text().splitlines()
    d = json.loads(lines[-1])
    d["payload"]["actor"]["agent"] = "someone-else"
    lines[-1] = json.dumps(d)
    rec.chain_path.write_text("\n".join(lines) + "\n")
    hook.handle("claude", "Stop", {"session_id": "s1", "cwd": str(p)})
    assert A.ActorBook().state()["cells"] == []


def test_recorder6_a_torn_last_line_is_set_aside_and_recording_continues(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    ws = tmp_path / "ws"
    ws.mkdir()
    rec = R.Recorder(ws)
    _step(rec, "t1", MAIN, "Write", {}, write=(ws / "a", "1"))
    with rec.chain_path.open("ab") as f:
        f.write(b'{"half": ')
    _step(rec, "t2", MAIN, "Write", {}, write=(ws / "b", "2"))
    assert [e["step"] for e in rec.events() if e["type"] == "step"] == ["t1", "t2"]
    assert any(e["type"] == "coverage" and e.get("torn_tail_bytes") for e in rec.events())
    assert rec.verify()[0]


def test_recorder7_one_sessions_stop_does_not_close_anothers_step(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    ws = tmp_path / "ws"
    ws.mkdir()
    rec = R.Recorder(ws)
    other = R.Actor("codex", "sB")
    rec.pre("u1", other, "shell", {"command": "long"})
    assert rec.settle(MAIN) == []
    assert "u1" in rec._state()["pending"]


def test_recorder8_chmod_is_a_change(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "run.sh").write_text("echo")
    s0 = W.scan(ws)
    os.chmod(ws / "run.sh", 0o755)
    assert [c.path for c in W.diff(s0, W.scan(ws, s0))] == ["run.sh"]


def test_recorder9_too_many_files_is_a_gap_not_a_blame(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    monkeypatch.setattr(W, "MAX_FILES", 3)
    for i in range(5):
        (p / f"f{i}").write_text(str(i))
    _step(rec, "t1", MAIN, "Write", {}, write=(p / "report.md", "Total: 999\n"))
    [b] = _blames(p, c, rec)
    assert b["state"] == "UNOBSERVED" and "not observed" in b["note"]


def test_recorder10_a_replayed_step_is_counted_once(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    ws = tmp_path / "ws"
    ws.mkdir()
    rec = R.Recorder(ws)
    e = _step(rec, "t1", MAIN, "Write", {}, write=(ws / "a", "1"))
    rec.append("step", {k: v for k, v in e.items() if k not in ("seq", "hash")})
    assert [s.id for s in B.Trace(rec).steps] == ["t1"]


def test_recorder11_home_and_state_dirs_are_never_traced(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "home" / ".vacant"))
    monkeypatch.setenv("VACANT_TRACE", "1")
    (tmp_path / "home" / ".vacant" / "x").mkdir(parents=True)
    assert capture.workspace_for(str(tmp_path / "home")) is None
    assert capture.workspace_for(str(tmp_path)) is None                       # 家目錄的上層
    assert capture.workspace_for(str(tmp_path / "home" / ".vacant" / "x")) is None
    (tmp_path / "home" / "proj").mkdir()
    assert capture.workspace_for(str(tmp_path / "home" / "proj")) is not None


def test_recorder12_directory_symlinks_are_recorded(tmp_path):
    ws = tmp_path / "ws"
    (ws / "v1").mkdir(parents=True)
    (ws / "v1" / "r.txt").write_text("1")
    os.symlink("v1", ws / "current")
    assert W.scan(ws)["current"].sha256 == "link:v1"


# ── consequences ────────────────────────────────────────────────────

def test_consequences0_finding_ids_are_scoped_per_project():
    b = {"claim": "total", "location": {"path": "report.md", "line": 1, "value": "999"}}
    assert F.finding_id(b, scope="p1") != F.finding_id(b, scope="p2")


def test_consequences1_2_hooks_under_vacant_do_record_no_outcome(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    monkeypatch.setenv("VACANT_HOOK_NO_SUBMIT", "1")
    (rec.dir).mkdir(parents=True, exist_ok=True)
    (rec.dir / "feedback_state.json").write_text(json.dumps({"outcomes": {"claude:s1":
                                                                           "reject"}}))
    capture._outcome(rec, MAIN, c)
    assert A.ActorBook().events() == []


def test_consequences2_a_session_without_its_own_check_records_no_outcome(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    rec.dir.mkdir(parents=True, exist_ok=True)
    (rec.dir / "feedback_state.json").write_text(json.dumps(
        {"outcome": "reject", "outcomes": {"codex:other": "reject"}}))
    capture._outcome(rec, MAIN, c)
    assert A.ActorBook().events() == []


def test_consequences3_routing_adds_up_a_platforms_cells(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    book = A.ActorBook()
    for i in range(3):
        A.record_outcome(book, session_key=f"a{i}", actor={"platform": "codex", "model": "m1"},
                         accepted=True, contract=None, workspace=tmp_path)
        A.record_outcome(book, session_key=f"b{i}", actor={"platform": "codex", "model": "m2"},
                         accepted=True, contract=None, workspace=tmp_path)
    assert A.pick_agent(book, "", ["codex"])["runs"] == {"codex": 6}


def test_consequences4_5_dismissal_needs_a_known_id(tmp_path, monkeypatch, capsys):
    from vacant_network.trace import cli as TC
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    _step(rec, "t1", MAIN, "Write", {}, write=(p / "report.md", "Total: 60\n"))
    monkeypatch.chdir(p)
    assert TC.main(["flag", "--dismiss", "f_doesnotexist", "because"]) == 2


def test_critique_one_platform_does_not_age_anothers_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    book = A.ActorBook()
    for i in range(2):
        A.record_outcome(book, session_key=f"c{i}", actor={"platform": "claude"}, accepted=True,
                         contract=None, workspace=tmp_path)
    before = [x["mean"] for x in book.state()["cells"] if x["key"][1] == "claude"]
    for i in range(400):
        book._append({"id": f"x{i}", "kind": "outcome", "accepted": False,
                      "key": list(A.key_of({"platform": "codex"}))})
    after = [x["mean"] for x in book.state()["cells"] if x["key"][1] == "claude"]
    assert before == after


# ── integration ─────────────────────────────────────────────────────

def test_integration4_the_agent_cannot_run_vacant_flag(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    out, _e, _c = hook.handle("claude", "PreToolUse", {
        "session_id": "s", "cwd": str(p), "tool_name": "Bash", "tool_use_id": "x",
        "tool_input": {"command": "vacant flag --dismiss f_1 'not mine'"}})
    assert "deny" in out


def test_integration3_a_non_terminal_session_end_records_no_outcome(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    (p / "report.md").write_text("Total: 999\n")
    hook.handle("pi", "stop", {"cwd": str(p), "session_id": "S1"})
    hook.handle("pi", "session_end", {"cwd": str(p), "session_id": "S1", "reason": "reload"})
    assert [e for e in A.ActorBook().events() if e["kind"] == "outcome"] == []


def test_integration7_legacy_trace_wire_renderer_still_routes(tmp_path):
    f = tmp_path / "wire.jsonl"
    f.write_text("")
    r = subprocess.run([sys.executable, "-m", "vacant_network", "trace", str(f)],
                       capture_output=True, text=True, timeout=120,
                       env={**os.environ, "VACANT_HOME": str(tmp_path / "vh")})
    assert "MCP trace" in r.stdout


def test_encoded_shell_write_regression_still_holds(tmp_path, monkeypatch):
    p, c, rec = _proj(tmp_path, monkeypatch, TOTAL)
    b64 = base64.b64encode(b"Total: 999\n").decode()
    _step(rec, "t1", MAIN, "Bash", {"command": f"printf '%s' {b64} | base64 -d > report.md"},
          write=(p / "report.md", "Total: 999\n"))
    [b] = _blames(p, c, rec)
    assert b["confidence"] == "provable" and pathlib.Path(p / "report.md").is_file()


def test_recorder11b_vacant_do_workspaces_under_the_work_root_are_traced(tmp_path, monkeypatch):
    """`vacant do` 的每一個工作區都在工作區根（`$VACANT_HOME-work`）底下：根本身不追，根底下的照追。
    整個根曾經被當成狀態目錄 ⇒ `vacant do` 一步都沒記（R536 的追緝回饋少了「第幾步」；2026-09-25 冒煙抓到）。"""
    from vacant_network.intake import statepaths
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_TRACE", "1")
    wd = statepaths.work_dir()
    ws = wd / "task-1" / "20260925T000000-1-abc" / "ws"
    ws.mkdir(parents=True)
    assert capture.workspace_for(str(ws)) == ws.resolve()
    assert capture.workspace_for(str(wd)) is None
    assert capture.workspace_for(str(tmp_path / "vh" / "trace")) is None
