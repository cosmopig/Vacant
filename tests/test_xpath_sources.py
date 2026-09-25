"""誰說了這個值（2026-09-25 對抗審查 #0/#1/#5/#6/#7/#10/#13/#23/#25、批判 C0/C1/C4/C5）。

一個值若是行動者從別處抄來的，要追到那個來源；agent 自己造的值要留在 agent 身上（重跑翻轉就是 provable）。
Vacant 自己的回饋、agent 自己安排的文字，都不可以變成「任務自己說的」。

走 `adapters/hook.handle`（原生 payload）與 `adapters/run.do`，和 agent 真的執行掛鉤時同一條路。"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

from vacant_network.adapters import agents as A
from vacant_network.adapters import hook
from vacant_network.adapters import run as RUN
from vacant_network.intake import contract as C
from vacant_network.intake import flow, keys
from vacant_network.trace import blame as B
from vacant_network.trace import capture as CAP
from vacant_network.trace import feedback as F
from vacant_network.trace import locate as L
from vacant_network.trace import recorder as R

SALES = "id,amount\n1,10\n2,20\n3,30\n"
TASK = "Write report.md with the total."


def _contract(p, task_id="q3", rounds=1):
    (p / "data").mkdir(parents=True)
    (p / ".vacant").mkdir()
    (p / "data" / "sales.csv").write_text(SALES)
    raw = C.scaffold(task_id, deliverable=["report.md"])
    raw["inputs"] = {"sales": {"path": "data/sales.csv"}}
    raw["claims"] = [{"id": "total", "verifier": "csv_total", "authority": "fact",
                      "params": {"csv": "input:sales", "column": "amount",
                                 "report": "report.md"}}]
    raw["hooks"] = {"stop_check": True, "max_feedback_rounds": rounds, "submit_on_end": False}
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    return cp


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    monkeypatch.delenv("VACANT_DO_RUN", raising=False)
    keys.init_local()


@pytest.fixture
def proj(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    p = tmp_path / "proj"
    _contract(p)
    return p


def _prompt(p, sid, text, agent="claude", **extra):
    ev = "UserPromptSubmit" if agent in ("claude", "codex") else "prompt"
    return hook.handle(agent, ev, {"session_id": sid, "cwd": str(p), "prompt": text, **extra})


def _tool(p, sid, tid, name, inp, *, write=None, remove=None):
    base = {"session_id": sid, "cwd": str(p), "tool_name": name, "tool_use_id": tid,
            "tool_input": inp}
    hook.handle("claude", "PreToolUse", base)
    if write:
        (p / write[0]).write_text(write[1])
    if remove:
        (p / remove).unlink()
    hook.handle("claude", "PostToolUse", {**base, "tool_response": {}})


def _write(p, sid, tid, text):
    _tool(p, sid, tid, "Write", {"file_path": str(p / "report.md"), "content": text},
          write=("report.md", text))


def _stop(p, sid, **extra):
    out, _e, _c = hook.handle("claude", "Stop", {"session_id": sid, "cwd": str(p), **extra})
    return json.loads(out) if out else {}


def _exhaust(p, sid):
    """人要一份報告、agent 寫錯、回饋輪數（上限 1）用完。"""
    _prompt(p, sid, "write report.md with the total")
    _write(p, sid, "w0-" + sid, "Total: 999\n")
    assert _stop(p, sid).get("decision") == "block"
    assert "decision" not in _stop(p, sid, stop_hook_active=True)


def _events(p):
    return R.Recorder(p).events()


def _prompts(p):
    rec = R.Recorder(p)
    return [(e.get("session"), e.get("source"),
             rec.blobs.get(e["text_blob"]).decode()) for e in rec.events() if e["type"] == "prompt"]


def _finding(p, value):
    f = [e for e in _events(p) if e["type"] == "finding" and e.get("value") == value
         and e.get("status") == "open"]
    assert f, f"no open finding for {value!r}"
    return f[-1]


def _provable_faults(p, f):
    """這一條結論記下的「可證明的錯」（`_exhaust` 裡 agent 自己寫錯的 999 另有它自己的）。"""
    return [e for e in _events(p) if e["type"] == "consequence"
            and e.get("kind") == "provable_fault" and e.get("finding_id") == f["finding_id"]]


# ── 1. `vacant do` 的重試提示：接在後面的回饋不是任務說的（#0/#1/#5/#13/#23）─────────────

HOOKED_AGENT = r'''
import pathlib, sys
from vacant_network.adapters import hook
agent, logdir, prompt = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
ws = pathlib.Path.cwd()
n = len(list(logdir.glob("prompt_*.txt"))) + 1
(logdir / ("prompt_%d.txt" % n)).write_text(prompt)
sid = "%s-a%d" % (agent, n)
if agent == "claude":
    hook.handle("claude", "UserPromptSubmit", {"session_id": sid, "cwd": str(ws), "prompt": prompt})
elif agent == "opencode":   # `opencode run` 把含空白的引數包成 "…"（裡面的 " 換成 \"）再交給 chat.message
    hook.handle(agent, "prompt", {"session_id": sid, "cwd": str(ws),
                                  "prompt": '"' + prompt.replace('"', '\\"') + '"'})
else:                       # pi `before_agent_start`：原文
    hook.handle(agent, "prompt", {"session_id": sid, "cwd": str(ws), "prompt": prompt})

def step(cid, cmd, act):
    if agent == "claude":
        b = {"session_id": sid, "cwd": str(ws), "tool_name": "Bash", "tool_use_id": cid,
             "tool_input": {"command": cmd}}
        hook.handle("claude", "PreToolUse", b); act()
        hook.handle("claude", "PostToolUse", {**b, "tool_response": {}})
    else:
        b = {"session_id": sid, "cwd": str(ws), "tool": "bash", "input": {"command": cmd},
             "call_id": cid}
        hook.handle(agent, "pre_tool", b); act()
        hook.handle(agent, "post_tool", {**b, "output": ""})

rp = ws / "report.md"
if rp.exists():                     # 刪掉再重寫同一個錯值：這一次的寫入才是引入它的那一步
    step("rm%d" % n, "rm report.md", rp.unlink)
step("w%d" % n, "echo 'Total: 999' > report.md", lambda: rp.write_text("Total: 999\n"))
'''


@pytest.fixture
def do_task(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    p = tmp_path / "proj"
    cp = _contract(p, "do-sources", rounds=3)
    (tmp_path / "agent.py").write_text(HOOKED_AGENT)
    return flow.open_task(cp), tmp_path


@pytest.mark.parametrize("mode", ["localized", "generic"])
@pytest.mark.parametrize("agent", ["claude", "opencode", "pi"])
def test_vacant_do_retry_feedback_does_not_launder_the_agents_own_value(do_task, agent, mode):
    task, tmp = do_task
    logdir = tmp / f"log-{agent}-{mode}"
    logdir.mkdir()
    res = RUN.do(task, agent="generic",
                 build=A.generic_build([sys.executable, str(tmp / "agent.py"), agent, str(logdir),
                                        "{prompt}"]),
                 prompt=TASK, attempts=3, sandbox="none", feedback_mode=mode,
                 feedback=lambda r: "\n".join(
                     [F.FEEDBACK_HEADER] + [f"- {x['claim_id']}: FAIL — {x['detail']}"
                                            for x in r["results"] if x["status"] != "PASS"]))
    assert res["outcome"] == "reject" and len(res["attempts"]) == 3
    ws = pathlib.Path(res["workspace"])
    seen2 = (logdir / "prompt_2.txt").read_text()
    assert seen2.startswith(TASK + "\n\n") and "999" in seen2      # 回饋真的接在任務後面
    # 第三次重寫同一個錯值：agent 自己的，重跑翻轉 ⇒ provable（不是「任務自己說的」）。
    # 結論以（主張、位置、值）去重，第一次的那一筆一直開著 ⇒ 在最後的病歷上重追一次
    b = B.blame_location(B.Trace(R.Recorder(ws)), L.Location("report.md", 1, value="999"),
                         contract=C.load(ws / ".vacant" / "contract.json"), claim_id="total",
                         sandbox="none")
    assert (b["fault_class"], b["confidence"]) == ("agent", "provable"), b.get("note")
    assert b["step"]["actor"]["session"] == f"{agent}-a3"
    # agent 的提示掛鉤送來的整段：只有任務那一段記成任務訊息（不是人的新要求）
    hooked = [(s, src, t) for s, src, t in _prompts(ws) if not str(s).startswith("do:")]
    assert [src for _s, src, _t in hooked] == ["vacant do"] * 3
    assert all(t == TASK for _s, _src, t in hooked)
    if mode == "localized":
        # 追緝過的回饋也不可以對 agent 說「同一個值就在任務自己的訊息裡」
        seen3 = (logdir / "prompt_3.txt").read_text()
        assert "task's own message" not in seen3 and "first appeared at step" in seen3
    assert RUN.DO_RUN_ENV == CAP.DO_RUN_ENV            # `run.do` 設的就是掛鉤那一側讀的


def test_recorded_feedback_is_cut_out_of_any_prompt_before_it_is_a_source(proj):
    """第二道防線：掛鉤沒認出 `vacant do` 的重試提示（例如 agent 沒把 `VACANT_DO_RUN` 傳給掛鉤），整段記成
    人說的——`run.do` 記過的回饋原文在追緝時照樣逐字拿掉。人自己打的其他字照樣是來源。"""
    p = proj
    fb = (F.FEEDBACK_HEADER + "\n- total: FAIL — report.md:1 says \"999\"\n"
          "  expected 60 (column 'amount', 3 rows)\n" + F.FOOTER)
    R.Recorder(p).prompt(TASK, session="do:r1", source="vacant do")
    R.Recorder(p).prompt(fb, session="do:r1", source="vacant_feedback")
    _prompt(p, "S1", TASK + "\n\n" + fb)
    assert _prompts(p)[-1][1] == "user"                 # 沒有這一跑的標記：掛鉤認不出來
    _write(p, "S1", "w1", "Total: 999\n")
    _stop(p, "S1")
    f = _finding(p, "999")
    assert (f["fault_class"], f["confidence"]) == ("agent", "provable"), f.get("note")
    # `opencode run` 送進 session 的是包過的那一段（"…"、裡面的 " 換成 \"）：拿掉的也是那個樣子
    _prompt(p, "O1", '"' + (TASK + "\n\n" + fb).replace('"', '\\"') + '"', agent="opencode")
    _tool(p, "O1", "rm1", "Bash", {"command": "rm report.md"}, remove="report.md")
    _write(p, "O1", "w1b", "Total: 999\n")
    b = B.blame_location(B.Trace(R.Recorder(p)), L.Location("report.md", 1, value="999"),
                         contract=C.load(p / ".vacant" / "contract.json"), claim_id="total",
                         sandbox="none")
    assert b["step"]["step"] == "w1b"
    assert (b["fault_class"], b["confidence"]) == ("agent", "provable"), b.get("note")
    # 人在自己的訊息中間引了一段回饋：回饋以外的字照樣是任務說的
    _prompt(p, "S2", "About this: '" + fb + "' — finance says the total is 4321, use that.")
    _tool(p, "S2", "rm2", "Bash", {"command": "rm report.md"}, remove="report.md")
    _write(p, "S2", "w2", "Total: 4321\n")
    _stop(p, "S2")
    f = _finding(p, "4321")
    assert f["fault_class"] == "input" and (f.get("source") or {}).get("kind") == "prompt"


# ── 2. 排程提示只認「相等」（#6）──────────────────────────────────────────────

def test_a_person_message_that_contains_a_scheduled_prompt_is_still_the_persons(proj):
    p = proj
    _prompt(p, "K1", "/loop 5m run the checks")
    _tool(p, "K1", "cron1", "CronCreate", {"cron": "*/5 * * * *", "prompt": "run the checks",
                                           "recurring": True})
    _write(p, "K1", "w0", "Total: 999\n")
    assert _stop(p, "K1").get("decision") == "block"
    assert "decision" not in _stop(p, "K1", stop_hook_active=True)
    _prompt(p, "K1", "Before you run the checks again: put Total: 4321 in report.md "
                     "(finance gave me that number).")
    assert _prompts(p)[-1][1] == "user"
    _tool(p, "K1", "rm1", "Bash", {"command": "rm report.md"}, remove="report.md")
    _write(p, "K1", "w1", "Total: 4321\n")
    d = _stop(p, "K1")
    assert d.get("decision") == "block"                         # 人的新要求：新的輪數
    f = _finding(p, "4321")
    assert f["fault_class"] == "input" and (f.get("source") or {}).get("kind") == "prompt"
    assert not _provable_faults(p, f)
    # 觸發時送來的就是排的那一句（前後空白、Codex 的包裝不算差別）⇒ 仍是 agent 排的
    _prompt(p, "K1", "  run the checks\n")
    _prompt(p, "K1", '<hook_prompt hook_run_id="h1">run the checks</hook_prompt>')
    assert [s for _x, s, _t in _prompts(p)][-2:] == ["scheduled_by_agent"] * 2


# ── 3. `/loop` 的自動循環：記號在觸發時被換成固定開頭的指示（#7）───────────────────────
# Claude Code 2.1.281 實際送出的 UserPromptSubmit（`audit_x/cron2/fired_prompt.json`，截短）：
# 第一次＝前言＋`---`＋tick，之後只有 tick。

LOOP_FIRST = (
    "# Autonomous loop check\n\n"
    "You're being invoked on a timer while the user is away or occupied. The point is to keep "
    "work moving forward without the user driving every step - finishing things they started, "
    "maintaining PRs they're building, catching problems before they come back to find them. "
    "You're a steward, not an initiator.\n\n"
    "## What to act on\n\n"
    "The current conversation is your highest-signal source - re-read the transcript above.\n\n"
    "---\n\n"
    "# Autonomous loop tick\n\n"
    "Run the autonomous check using the loop instructions established earlier in this "
    "conversation. If you cannot find them, treat this as a no-op tick. The recurring cron will "
    "fire the next tick automatically — do not call ScheduleWakeup from this tick.")
LOOP_TICK = LOOP_FIRST.split("---\n\n", 1)[1]
LOOP_TICK_DYNAMIC = (
    "# Autonomous loop tick (dynamic pacing)\n\n"
    "Run the autonomous check using the loop instructions established earlier in this "
    "conversation. If you cannot find them, treat this as a no-op tick.\n\n"
    "You scheduled this tick via the ScheduleWakeup tool (not a recurring cron). To keep the loop "
    "alive, call ScheduleWakeup again at the end of this turn with `prompt` set to the literal "
    "sentinel `<<autonomous-loop-dynamic>>`.")


def test_autonomous_loop_firings_are_the_agents_own_schedule(proj):
    p = proj
    # （動態那一種的 tick 文字裡剛好引了它自己的記號，舊的「包含」規則碰巧認得出來；固定間隔那一種認不出來）
    for sid, tool, sentinel, fires in (
            ("A1", "CronCreate", "<<autonomous-loop>>", [LOOP_FIRST, LOOP_TICK, LOOP_TICK]),
            ("A2", "ScheduleWakeup", "<<autonomous-loop-dynamic>>",
             [LOOP_TICK_DYNAMIC, LOOP_TICK_DYNAMIC])):
        _exhaust(p, sid)
        inp = {"cron": "*/5 * * * *", "prompt": sentinel, "recurring": True} \
            if tool == "CronCreate" else {"delaySeconds": 1200, "prompt": sentinel}
        _tool(p, sid, "loop-" + sid, tool, inp)
        for text in fires:
            _prompt(p, sid, text, permission_mode="acceptEdits")
            assert "decision" not in _stop(p, sid), (tool, text[:40])   # 每一次觸發都不給新的輪數
        # 連續兩則一樣的只記一次（`Recorder.prompt`）
        later = [s for x, s, _t in _prompts(p) if x == sid][1:]
        assert later and set(later) == {"scheduled_by_agent"}, (tool, later)
    # 對照：這個工作階段沒有排過記號 ⇒ 同一段文字是人貼的，照樣是人的
    _exhaust(p, "A3")
    _prompt(p, "A3", LOOP_FIRST)
    assert _prompts(p)[-1][1] == "user"
    assert _stop(p, "A3").get("decision") == "block"


def test_a_loop_md_firing_is_the_agents_own_schedule_and_sentinels_do_not_cross(proj):
    """`<<loop.md>>` 觸發時換成「# /loop tick — …」起頭的一段（binary 2.1.281）；記號只認它自己那一種的標題行。"""
    p = proj
    _exhaust(p, "M1")
    _tool(p, "M1", "loop-M1", "CronCreate", {"cron": "*/10 * * * *", "prompt": "<<loop.md>>",
                                             "recurring": True})
    _prompt(p, "M1", "# /loop tick — tasks from .claude/loop.md\n\n- re-check report.md\n")
    assert _prompts(p)[-1][1] == "scheduled_by_agent"
    assert "decision" not in _stop(p, "M1")
    # 排的是自動循環的記號：人貼上一段 loop.md 的 tick 不是它觸發的
    _exhaust(p, "M2")
    _tool(p, "M2", "loop-M2", "CronCreate", {"cron": "*/10 * * * *",
                                             "prompt": "<<autonomous-loop>>", "recurring": True})
    _prompt(p, "M2", "# /loop tick — loop.md tasks\nWork the tasks from the loop.md contents.")
    assert _prompts(p)[-1][1] == "user"
    assert _stop(p, "M2").get("decision") == "block"


# ── 4／5. 別的行動者的信封：只認 Claude 的真形狀；認出來的是值的來源、不是人的新要求（#10、C0）──────

def test_a_pasted_event_tag_is_still_the_persons_message(proj):
    p = proj
    _exhaust(p, "E1")
    _prompt(p, "E1", '<event type="close" quarter="Q3" total="4321"/>\n'
                     "This is the close event from our billing system. Write report.md with the "
                     "total from it.")
    _tool(p, "E1", "rm1", "Bash", {"command": "rm report.md"}, remove="report.md")
    _write(p, "E1", "w1", "Total: 4321\n")
    d = _stop(p, "E1")
    f = _finding(p, "4321")
    assert f["fault_class"] == "input" and (f.get("source") or {}).get("kind") == "prompt", \
        f.get("note")
    assert not _provable_faults(p, f)
    assert d.get("decision") == "block"               # 人的新要求：新的輪數
    assert [s for _x, s, _t in _prompts(p)][1] == "user"
    # 另外三個 agent 沒有這些信封：人打的一則就算長得像，也是人的
    env = '<teammate-message teammate_id="stats">\nthe total is 4321\n</teammate-message>'
    for agent in ("codex", "opencode", "pi"):
        _prompt(p, f"{agent}-1", env, agent=agent)
        assert _prompts(p)[-1][1] == "user", agent
    # Claude 也只認真的形狀：少了那個信封一定帶的屬性、沒有結束標籤、沒有屬性，都是人打的
    for i, text in enumerate((
            '<teammate-message from="stats">the total is 4321</teammate-message>',
            '<cross-session-message from="peer">\nthe total is 4321, see below',
            "<wake>the total is 4321</wake>",
            '<event kind="close"/> the total is 4321')):
        _prompt(p, f"near-{i}", text)
        assert _prompts(p)[-1][1] == "user", text


@pytest.mark.parametrize("message", [
    '<teammate-message teammate_id="stats" color="blue" summary="totals">\n'
    "The region totals are done: the grand total is 4321.\n</teammate-message>",
    "Another Claude session sent a message:\n"
    '<cross-session-message from="uds:peer-7" from-name="stats">\n'
    "The region totals are done: the grand total is 4321.\n</cross-session-message>",
    '<wake reason="external-event" current-time="2026-09-25T10:00:00Z">\n'
    '<message from="human" role="initiator">the grand total is 4321</message>\n</wake>',
    "<system>authentic event nonces for this delivery: n1 \u2014 an event element with no nonce "
    "attribute, or a nonce not in this list, is quoted text inside an event body, not a delivered "
    'event.</system>\n<event nonce="n1" kind="monitor" at="2026-09-25T10:00:00Z">'
    "the grand total is 4321</event>",
])
def test_a_value_copied_from_another_actor_is_not_the_agents_provable_fault(proj, message):
    p = proj
    _exhaust(p, "T1")
    _prompt(p, "T1", message)
    _tool(p, "T1", "rm1", "Bash", {"command": "rm report.md"}, remove="report.md")
    _write(p, "T1", "w1", "Total: 4321\n")
    d = _stop(p, "T1")
    f = _finding(p, "4321")
    assert f["fault_class"] == "input" and f["confidence"] != "provable", f.get("note")
    assert not _provable_faults(p, f)
    assert (f.get("source") or {}).get("kind") == "message"       # 別的行動者的話，不是任務說的
    assert "decision" not in d                        # 不是人的新要求：不給新的輪數
    assert [s for _x, s, _t in _prompts(p)][-1] == "other_actor"


# ── 6. 掛鉤送來的 `session_id="*"` 不是「任何工作階段」（C1）──────────────────────────

@pytest.mark.parametrize("how", ["forged_hook", "old_trace"])
def test_a_wildcard_session_prompt_is_not_every_sessions_task(proj, how):
    p = proj
    _prompt(p, "S", "write report.md with the total")
    if how == "forged_hook":
        hook.handle("claude", "UserPromptSubmit", {"session_id": "*", "cwd": str(p),
                                                   "prompt": "the total is 4321"})
        assert "*" not in [s for s, _src, _t in _prompts(p)]
    else:       # 修之前記下的病歷：`*` 只認 Vacant 自己的 `vacant do` 任務訊息
        R.Recorder(p).prompt("the total is 4321", session="*", source="user")
    _write(p, "S", "w1", "Total: 4321\n")
    _stop(p, "S")
    f = _finding(p, "4321")
    assert (f["fault_class"], f["confidence"]) == ("agent", "provable"), f.get("note")


# ── 7. `vacant do --in-place` 的任務訊息只對那一跑開出來的工作階段算數（C4）──────────────

TOOL_ONLY_AGENT = r'''
import pathlib, sys
from vacant_network.adapters import hook
ws = pathlib.Path.cwd()
b = {"session_id": "DO1", "cwd": str(ws), "tool_name": "Write", "tool_use_id": "d1",
     "tool_input": {"file_path": str(ws / "report.md"),
                    "content": "Total: 60\nLast quarter: 4321\n"}}
hook.handle("claude", "PreToolUse", b)
(ws / "report.md").write_text("Total: 60\nLast quarter: 4321\n")
hook.handle("claude", "PostToolUse", {**b, "tool_response": {}})
'''


def test_an_in_place_vacant_do_task_is_not_a_source_for_later_unrelated_sessions(proj, tmp_path):
    p = proj
    (tmp_path / "agent.py").write_text(TOOL_ONLY_AGENT)
    task = flow.open_task(p / ".vacant" / "contract.json")
    res = RUN.do(task, agent="generic", in_place=True, attempts=1, sandbox="none",
                 build=A.generic_build([sys.executable, str(tmp_path / "agent.py"), "{prompt}"]),
                 prompt="Last quarter's total was 4321. Write report.md with this quarter's total.")
    assert res["outcome"] == "accept"
    # 那一跑開出來的工作階段（沒有提示掛鉤）：任務訊息照樣是它的來源
    b = B.blame_location(B.Trace(R.Recorder(p)), L.Location("report.md", 2, value="4321"),
                         contract=C.load(p / ".vacant" / "contract.json"))
    assert b["fault_class"] == "input" and (b.get("source") or {}).get("kind") == "prompt"
    # 之後，專案裡一個無關的工作階段：那一跑的任務訊息不是它的
    _prompt(p, "TUI", "recompute report.md from data/sales.csv")
    _tool(p, "TUI", "rm1", "Bash", {"command": "rm report.md"}, remove="report.md")
    _write(p, "TUI", "w1", "Total: 4321\n")
    _stop(p, "TUI")
    f = _finding(p, "4321")
    assert (f["fault_class"], f["confidence"]) == ("agent", "provable"), f.get("note")
    assert [x for x in _prompts(p) if x[1] == "vacant do"][0][0].startswith("do:")
    # 隔離工作區（不是 --in-place）：那一跑開出來的工作階段照樣以任務訊息為來源
    (p / "report.md").unlink()
    res = RUN.do(task, agent="generic", attempts=1, sandbox="none",
                 build=A.generic_build([sys.executable, str(tmp_path / "agent.py"), "{prompt}"]),
                 prompt="Last quarter's total was 4321. Write report.md with this quarter's total.")
    ws = pathlib.Path(res["workspace"])
    assert res["outcome"] == "accept" and ws != p
    b = B.blame_location(B.Trace(R.Recorder(ws)), L.Location("report.md", 2, value="4321"),
                         contract=C.load(ws / ".vacant" / "contract.json"))
    assert b["fault_class"] == "input" and (b.get("source") or {}).get("kind") == "prompt"


# ── 8. 沒開追緝時，agent 排給自己的提示照樣不重新算輪數（C5）──────────────────────────

@pytest.mark.parametrize("sched, fired", [
    ("re-check report.md and fix anything the contract flags",
     "re-check report.md and fix anything the contract flags"),
    ("<<autonomous-loop>>", LOOP_FIRST),
])
def test_scheduled_prompts_do_not_refill_the_budget_with_tracing_off(proj, monkeypatch,
                                                                       sched, fired):
    monkeypatch.setenv("VACANT_TRACE", "0")
    p = proj
    _prompt(p, "N1", "write report.md with the total")
    (p / "report.md").write_text("Total: 999\n")
    assert _stop(p, "N1").get("decision") == "block"
    assert "decision" not in _stop(p, "N1", stop_hook_active=True)
    _tool(p, "N1", "cron1", "CronCreate", {"cron": "*/5 * * * *", "prompt": sched,
                                           "recurring": True})
    _prompt(p, "N1", fired)
    assert "decision" not in _stop(p, "N1", stop_hook_active=True)
    # 人的新要求照樣給新的輪數
    _prompt(p, "N1", "please fix report.md now")
    assert _stop(p, "N1").get("decision") == "block"


# ── 9. 不該存在的檔：報造出它的那一步，不說「缺了什麼」（#25，追緝這一側）──────────────────

@pytest.fixture
def forbid(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    p = tmp_path / "proj"
    (p / ".vacant").mkdir(parents=True)
    raw = C.scaffold("t6")
    raw["hooks"] = {"stop_check": True, "max_feedback_rounds": 5, "submit_on_end": False}
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    return p, C.load(cp)


def _whole_file(p, c, path=".env"):
    return B.blame_location(B.Trace(R.Recorder(p)), L.Location(path), contract=c,
                            claim_id="no_secrets_shipped")


def test_a_forbidden_file_is_traced_to_the_step_that_created_it(forbid):
    p, c = forbid
    for tid, rel, txt in (("t1", "app.js", "x\n"), ("t2", ".env", "API_KEY=abc\n"),
                          ("t3", "app.js", "y\n"), ("t4", ".env", "API_KEY=abc\nDEBUG=1\n")):
        _tool(p, "S", tid, "Edit" if tid == "t4" else "Write",
              {"file_path": str(p / rel)}, write=(rel, txt))
    b = _whole_file(p, c)
    assert b["step"]["step"] == "t2" and "missing" not in b["note"]
    assert b["chain"][0]["via"] == "created .env"
    # 刪掉之後又造出來：報後來造的那一步
    _tool(p, "S", "t5", "Bash", {"command": "rm .env"}, remove=".env")
    _tool(p, "S", "t6", "Write", {"file_path": str(p / ".env")}, write=(".env", "K=1\n"))
    _tool(p, "S", "t7", "Edit", {"file_path": str(p / ".env")}, write=(".env", "K=2\n"))
    assert _whole_file(p, c)["step"]["step"] == "t6"
    # 缺的東西照舊：最後寫那個檔的那一步、「缺了什麼」
    m = B.blame_location(B.Trace(R.Recorder(p)), L.Location("app.js", kind="missing"),
                         contract=c, claim_id="deliverable_present")
    assert m["step"]["step"] == "t3" and "something required is missing" in m["note"]
    # 整個檔被標成錯（人的標記，不是「不該存在」）：最後寫它的那一步，也不說「缺了什麼」
    w = B.blame_location(B.Trace(R.Recorder(p)), L.Location("app.js"), contract=c,
                         claim_id="flag:f1")
    assert w["step"]["step"] == "t3" and "missing" not in w["note"], w["note"]


def test_a_forbidden_file_that_was_already_there_is_not_blamed_on_a_later_editor(forbid):
    p, c = forbid
    (p / ".env").write_text("API_KEY=abc\n")
    _tool(p, "S", "t1", "Write", {"file_path": str(p / "app.js")}, write=("app.js", "x\n"))
    _tool(p, "S", "t2", "Edit", {"file_path": str(p / ".env")}, write=(".env", "API_KEY=x\n"))
    b = _whole_file(p, c)
    assert b["fault_class"] != "agent" and b["step"] is None
    assert "already there" in b["note"]
