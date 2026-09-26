"""Independent repro against the 11f91f87 snapshot (sys.path points at the extracted tree)."""
import json, pathlib, subprocess, sys
SRC = "/tmp/claude-0/review_v3/verify_ended/src"
sys.path.insert(0, SRC)
sys.path.insert(0, SRC + "/tests")
import vacant_network
assert vacant_network.__file__.startswith(SRC), vacant_network.__file__
import pytest
from test_zero_budget import Pi, proj, _install, ASK, SALES  # noqa: F401
from vacant_network.adapters import hook
from vacant_network.trace.recorder import Recorder
from vacant_network.trace import zerostop


def _types(p):
    return [e["type"] for e in Recorder(p).events()]


def _note(p):
    return (Recorder(p).dir / "delivery.md").read_text()


# control: stop check runs normally -> no ended note
def test_control_normal_stop(proj):
    a = Pi(proj)
    a.ask()
    a.bash("cat data/sales.csv", SALES)
    a.bash("echo 2045 > /app/answer.txt", "", write={"answer.txt": "2045\n"})
    d = a.ev("stop", final_text="The total is 2045.", turn=3, budget=15)
    out = a.ev("session_end", reason="quit", turn=3, budget=15)
    t = _types(proj)
    print("CONTROL types tail:", t[-6:], "stop:", d)
    assert t.count("review") == 1 and t.count("ended") == 0


# (a1) the check child times out
def test_a_timeout(proj, monkeypatch):
    a = Pi(proj)
    a.ask()
    a.bash("cat data/sales.csv", SALES)
    a.bash("echo 2045 > /app/answer.txt", "", write={"answer.txt": "2045\n"})
    def slow(req):
        raise subprocess.TimeoutExpired(cmd="check", timeout=zerostop.CHECK_TIMEOUT_S)
    monkeypatch.setattr(zerostop, "_run_child", slow)
    d = a.ev("stop", final_text="The total is 2045. Done.", turn=3, budget=15)
    print("stop decision:", d)
    a.ev("session_end", reason="quit", turn=3, budget=15)
    t = _types(proj)
    md = _note(proj)
    print("A1 types:", t.count("review"), t.count("ended"))
    print(md)
    assert t.count("review") == 0 and t.count("ended") == 1
    assert "Ended before the agent said it was done" in md


# (a2) the check child raises (non-zero exit)
def test_a_error(proj, monkeypatch):
    a = Pi(proj)
    a.ask()
    a.bash("cat data/sales.csv", SALES)
    def boom(req):
        raise RuntimeError("check exited 1: MemoryError")
    monkeypatch.setattr(zerostop, "_run_child", boom)
    a.ev("stop", final_text="The total is 2045.", turn=4, budget=15)
    a.ev("session_end", reason="quit", turn=4, budget=15)
    md = _note(proj)
    print(md)
    assert "Ended before the agent said it was done" in md


# (b) opencode run: plugin never sends stop, dispose sends session_end without a reason
def test_b_opencode_run(proj):
    def oc(event, **kw):
        out, err, code = hook.handle("opencode", event, {"cwd": str(proj), "session_id": "O", **kw})
        return json.loads(out) if out else {}
    oc("prompt", prompt=ASK)
    oc("pre_tool", tool="bash", call_id="c1", input={"command": "cat data/sales.csv"})
    oc("post_tool", tool="bash", call_id="c1", input={"command": "cat data/sales.csv"}, output=SALES)
    oc("pre_tool", tool="bash", call_id="c2", input={"command": "echo 2045 > /app/answer.txt"})
    (proj / "answer.txt").write_text("2045\n")
    oc("post_tool", tool="bash", call_id="c2", input={"command": "echo 2045 > /app/answer.txt"}, output="")
    oc("session_end")   # dispose() in `opencode run`
    t = _types(proj)
    md = _note(proj)
    print("B types:", t.count("review"), t.count("ended"))
    print(md)
    assert "Ended before the agent said it was done" in md


# (c) claude: last Stop deferred for a running sub-agent, then SessionEnd
def test_c_claude_deferred(proj, monkeypatch):
    def cc(event, **kw):
        out, err, code = hook.handle("claude", event, {"cwd": str(proj), "session_id": "C",
                                                       "hook_event_name": event, **kw})
        return out
    cc("UserPromptSubmit", prompt=ASK)
    cc("PreToolUse", tool_name="Bash", tool_use_id="t1", tool_input={"command": "cat data/sales.csv"})
    cc("PostToolUse", tool_name="Bash", tool_use_id="t1", tool_input={"command": "cat data/sales.csv"},
       tool_response={"stdout": SALES})
    monkeypatch.setattr(hook, "_defer_for_subagents", lambda contract, ev: True)
    o = cc("Stop", last_assistant_message="Total is 2045; a sub-agent is double-checking.")
    print("claude stop out:", repr(o))
    cc("SessionEnd", reason="prompt_input_exit")
    t = _types(proj)
    md = _note(proj)
    print("C types:", t.count("review"), t.count("ended"))
    print(md)
    assert "Ended before the agent said it was done" in md
