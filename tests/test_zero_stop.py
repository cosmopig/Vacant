"""零設定的回合結束（`trace/zerostop.py` 經過真的 `hook.handle`）：退回、改好之後放行、交件說明、
回合上限、新要求重新算、失敗一律放行、病歷壞掉就擱到旁邊（DECISION_20260925_ZERO_CONFIG_DESIGN §二、§四、§五）。"""
import json
import pathlib
import subprocess

import pytest

from vacant_network.adapters import hook
from vacant_network.adapters import install as INS
from vacant_network.adapters.hookpolicy import vacant_state_dir
from vacant_network.trace import zerostop
from vacant_network.trace.feedback import REVIEW_HEADER
from vacant_network.trace.recorder import Recorder

SALES = "date,region,amount\n2026-07-01,north,1200\n2026-07-02,south,845\n" \
        "2026-07-03,north,310\n2026-07-04,east,1990\n2026-07-05,south,467\n"
ASK = "Using data/sales.csv, write the total amount to report.md."


def _install(mode="evidence"):
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": mode}))


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


@pytest.fixture
def inproc(monkeypatch):
    """子行程換成同一個行程裡跑（快）；真的子行程另有一條測試。"""
    monkeypatch.setattr(zerostop, "_run_child", zerostop.check)


class Agent:
    def __init__(self, proj: pathlib.Path, session: str = "S"):
        self.p, self.s, self.n = proj, session, 0

    def ask(self, text: str) -> None:
        hook.handle("claude", "UserPromptSubmit", {"session_id": self.s, "cwd": str(self.p),
                                                   "prompt": text})

    def step(self, tool, inp, output=None, *, write=None):
        self.n += 1
        pre = {"session_id": self.s, "cwd": str(self.p), "tool_name": tool,
               "tool_use_id": f"t{self.n}", "tool_input": inp}
        hook.handle("claude", "PreToolUse", pre)
        for rel, content in (write or {}).items():
            (self.p / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.p / rel).write_text(content)
        hook.handle("claude", "PostToolUse", {**pre, "tool_response": output or {}})

    def read(self, rel):
        self.step("Read", {"file_path": str(self.p / rel)},
                  {"file": {"content": (self.p / rel).read_text()}})

    def write(self, rel, content):
        self.step("Write", {"file_path": str(self.p / rel), "content": content}, {},
                  write={rel: content})

    def bash(self, cmd, stdout=""):
        self.step("Bash", {"command": cmd}, {"stdout": stdout, "stderr": ""})

    def stop(self, final="Done."):
        out, err, code = hook.handle("claude", "Stop", {
            "session_id": self.s, "cwd": str(self.p), "hook_event_name": "Stop",
            "stop_hook_active": False, "last_assistant_message": final})
        assert code == 0 and err == ""
        return json.loads(out) if out else {}


def _proj(env, name="proj"):
    p = env / "work" / name
    (p / "data").mkdir(parents=True)
    (p / "data" / "sales.csv").write_text(SALES)
    (p / ".git").mkdir()
    return p


def _note(p) -> str:
    return (Recorder(p).dir / "delivery.md").read_text()


def test_a_made_up_total_is_sent_back_then_the_fixed_one_is_delivered_with_a_note(env):
    """真的子行程：沒讀資料就寫的總數被退回；讀了、改對之後放行，交件說明寫出改了什麼。"""
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "# Sales\n\nTotal amount: 5,200\n")
    d = a.stop()
    assert d.get("decision") == "block"
    r = d["reason"]
    assert r.startswith(REVIEW_HEADER)
    assert 'report.md line 3: "5,200"' in r and "data/sales.csv" in r
    a.read("data/sales.csv")
    a.write("report.md", "# Sales\n\nTotal amount: 4,812\n")
    d2 = a.stop("The total is 4,812.")
    assert "decision" not in d2
    msg = d2["systemMessage"]
    assert "Redone before delivery: 2 point(s)." in msg and "delivery.md" in msg
    assert len(msg.splitlines()) <= zerostop.NOTE_MAX_LINES
    note = _note(p)
    assert "round 1:" in note and "the value was changed" in note
    assert "it was opened afterwards" in note
    kinds = [e.get("action") for e in Recorder(p).events() if e["type"] == "review"]
    assert kinds == ["continue", "allow"]


def test_observe_mode_never_sends_anything_back_but_writes_the_note(env, inproc):
    _install("observe")
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "Total amount: 5,200\n")
    d = a.stop()
    assert "decision" not in d
    assert "Observed (not sent back, observe mode)" in _note(p)


def test_without_install_nothing_is_recorded_or_checked(env, inproc):
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "Total amount: 5,200\n")
    assert a.stop() == {}
    assert not list((env / "vh").rglob("delivery.md"))


def test_rounds_stop_at_two_and_what_is_left_is_told_to_the_person(env, inproc):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "Total amount: 5,200\n")
    assert a.stop()["decision"] == "block"
    a.write("report.md", "Total amount: 5,300\n")
    d = a.stop()
    assert d["decision"] == "block"
    assert "(still open)" not in d["reason"].split("5,300")[0][-5:]      # 新的值，不是同一條
    a.write("report.md", "Total amount: 5,400\n")
    d3 = a.stop()
    assert "decision" not in d3
    assert "Still open after 2 round(s)" in d3["systemMessage"]
    assert "Still open after 2 round(s)" in _note(p)


def test_the_same_open_point_is_marked_still_open(env, inproc):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "Total amount: 5,200\n")
    a.stop()
    d = a.stop()                               # 什麼都沒改就又說做完
    assert "(still open)" in d["reason"]


def test_an_unopened_named_file_is_sent_back_only_once(env, inproc):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask("Summarise data/sales.csv in notes.md in one sentence.")
    a.write("notes.md", "The file lists sales by region.\n")
    d = a.stop()
    assert d["decision"] == "block" and "data/sales.csv was named in the task" in d["reason"]
    d2 = a.stop()
    assert "decision" not in d2
    assert "Still open after 1 round(s)" in _note(p)


def test_a_new_request_from_the_person_starts_the_rounds_again(env, inproc):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "Total amount: 5,200\n")
    a.stop()
    a.stop()
    assert "decision" not in a.stop()          # 兩回合用完
    a.ask("Now also write the total to summary.md, reading data/sales.csv again.")
    a.write("summary.md", "Total: 9,999\n")
    d = a.stop()
    assert d["decision"] == "block" and "9,999" in d["reason"] and "5,400" not in d["reason"]


def test_vacant_own_review_text_is_not_a_new_request(env, inproc):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "Total amount: 5,200\n")
    r = a.stop()["reason"]
    a.ask(r)                                    # 有的 agent 把退回的文字當成使用者訊息送回來
    a.stop()
    assert "decision" not in a.stop()           # 沒有因此多出新的回合


def test_a_timeout_or_a_crash_lets_the_work_through_with_one_line(env, monkeypatch):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "Total amount: 5,200\n")

    def slow(req):
        raise subprocess.TimeoutExpired("check", zerostop.CHECK_TIMEOUT_S)
    monkeypatch.setattr(zerostop, "_run_child", slow)
    d = a.stop()
    assert d == {"systemMessage": zerostop.DID_NOT_RUN}

    def boom(req):
        raise RuntimeError("disk")
    monkeypatch.setattr(zerostop, "_run_child", boom)
    assert a.stop() == {"systemMessage": zerostop.DID_NOT_RUN}
    errs = (vacant_state_dir() / "intake" / "hooks" / "errors.jsonl").read_text()
    assert "timed out" in errs and "RuntimeError: disk" in errs


def test_a_record_that_does_not_verify_is_set_aside_and_this_turn_is_not_sent_back(env, inproc):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.read("data/sales.csv")
    a.write("report.md", "Total amount: 4,812\n")
    assert "decision" not in a.stop()           # 驗過一次，記號存起來
    a.write("report.md", "Total amount: 5,200\n")
    rec = Recorder(p)
    lines = rec.chain_path.read_text().splitlines()
    last = json.loads(lines[-1])
    last["ts_ms"] += 1                           # 改掉最後一筆（簽章對不上）
    lines[-1] = json.dumps(last)
    rec.chain_path.write_text("\n".join(lines) + "\n")
    d = a.stop()
    assert "decision" not in d and "did not verify" in d["systemMessage"]
    assert list(rec.dir.glob("chain.set-aside.*.ndjson"))
    a.write("report.md", "Total amount: 5,300\n")   # 之後照常記、照常查
    assert Recorder(p).verify()[0]


def test_pi_final_message_claiming_tests_pass_without_a_run_is_sent_back(env, inproc):
    _install()
    p = _proj(env)
    base = {"cwd": str(p), "session_id": "P1"}
    hook.handle("pi", "prompt", {**base, "prompt": "Add a function add(a, b) to calc.py."})
    pre = {**base, "tool": "write", "call_id": "c1",
           "input": {"path": str(p / "calc.py"), "content": "def add(a, b):\n    return a + b\n"}}
    hook.handle("pi", "pre_tool", pre)
    (p / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    hook.handle("pi", "post_tool", {**pre, "output": "ok"})
    out, _, _ = hook.handle("pi", "stop", {**base, "final_text": "Added add(). All tests pass."})
    d = json.loads(out)
    assert d["action"] == "continue"
    assert "no test or build command ran" in d["reason"]


def test_no_stop_env_and_a_contract_keep_the_old_paths(env, inproc, monkeypatch):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "Total amount: 5,200\n")
    monkeypatch.setenv("VACANT_HOOK_NO_STOP", "1")
    assert a.stop() == {}


def test_while_a_background_sub_agent_runs_the_check_waits(env, inproc):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "Total amount: 5,200\n")
    hook.handle("claude", "SubagentStart", {"session_id": "S", "cwd": str(p),
                                            "hook_event_name": "SubagentStart",
                                            "agent_id": "k1", "agent_type": "general-purpose"})
    assert "decision" not in a.stop()
    hook.handle("claude", "SubagentStop", {"session_id": "S", "cwd": str(p),
                                           "hook_event_name": "SubagentStop", "agent_id": "k1",
                                           "agent_type": "general-purpose",
                                           "stop_hook_active": False})
    assert a.stop()["decision"] == "block"


def test_verify_since_checks_only_the_new_part_and_falls_back_to_the_whole_chain(env, inproc):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.read("data/sales.csv")
    rec = Recorder(p)
    ok, why, mark = rec.verify_since(None)
    assert ok and mark
    a.write("report.md", "Total amount: 4,812\n")
    ok2, why2, mark2 = rec.verify_since(mark)
    assert ok2 and "new entries since entry" in why2 and mark2["seq"] > mark["seq"]
    ok3, why3, _ = rec.verify_since({"seq": mark["seq"], "hash": "0" * 64})
    assert ok3 and "new entries" not in why3            # 記號對不上 ⇒ 整條驗
