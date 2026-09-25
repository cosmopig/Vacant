"""後果要是文件說的那個意思，完整性要程式對得出來（2026-09-25 對抗審查 §10 第 7、8、10、16 列）。

1. adoption 只記有說到 agent 工作的裁決：accept→1、有必要主張 FAIL 的 reject→0；
   hold／escalate（等審查、等獨立證據）照記一筆但不進 runs／accepted／信譽——三條路都一樣
   （工作階段結束 `capture._outcome`、`finalize.py`、`vacant do` 的 `run._trace_outcome`）。
2. `vacant trace verify` 讀回任務帳本裡簽過的 `trace_head`：病歷連 `head.json` 一起被截短／換掉 ⇒ BROKEN。
3. `vacant do` 的結果也簽進病歷（`consequence`）；`actors.ndjson` 只是衍生檢視。
4. KS-1 行動者識別收子 agent 定義檔的雜湊；**不收**平台名（會撞到 `CLAUDE.md` 這類檔名）。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

from vacant_network.adapters import hook
from vacant_network.intake import contract as C
from vacant_network.intake import flow, keys
from vacant_network.trace import actors as A
from vacant_network.trace import recorder as R

SALES = "id,amount\n1,10\n2,20\n3,30\n"
CLAIMS_REVIEW = [
    {"id": "total", "verifier": "csv_total", "authority": "fact",
     "params": {"csv": "input:sales", "column": "amount", "report": "report.md"}},
    {"id": "reads_well", "verifier": "review", "authority": "quality"},
]
CLAIMS_TOTAL = CLAIMS_REVIEW[:1]


def _project(tmp_path, claims, name="p"):
    p = tmp_path / name
    (p / "data").mkdir(parents=True)
    (p / ".vacant").mkdir()
    (p / "data" / "sales.csv").write_text(SALES)
    raw = C.scaffold(f"xc-{name}", deliverable=["report.md"])
    raw["inputs"] = {"sales": {"path": "data/sales.csv"}}
    raw["claims"] = claims
    raw["hooks"] = {"stop_check": True, "max_feedback_rounds": 1, "submit_on_end": False}
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    return p


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    monkeypatch.delenv("VACANT_HOOK_NO_SUBMIT", raising=False)
    keys.init_local()
    return tmp_path


def _tool(p, sid, name, inp, resp, *, session="S", sub=False, write=None):
    base = {"session_id": session, "cwd": str(p), "tool_name": name, "tool_use_id": sid,
            "tool_input": inp}
    if sub:
        base.update(agent_id="a7f3c9d2", agent_type="stats-helper")
    hook.handle("claude", "PreToolUse", base)
    if write:
        (p / write[0]).write_text(write[1])
    hook.handle("claude", "PostToolUse", {**base, "tool_response": resp})


def _write_report(p, text, sid="t1", session="S", sub=False):
    _tool(p, sid, "Write", {"file_path": str(p / "report.md"), "content": text},
          {"type": "create"}, session=session, sub=sub, write=("report.md", text))


def _outcome_consequences(rec):
    return [e for e in rec.events() if e["type"] == "consequence" and e.get("kind") == "outcome"]


# ── 1. adoption ─────────────────────────────────────────────────────

def test_adoption_of_maps_only_decisive_outcomes():
    fail = {"claim_id": "total", "status": "FAIL", "required": True}
    unk = {"claim_id": "reads_well", "status": "UNKNOWN", "required": True}
    opt_fail = {"claim_id": "style", "status": "FAIL", "required": False}
    assert A.adoption_of({"outcome": "accept", "results": [unk]}) is True
    assert A.adoption_of({"outcome": "reject", "results": [fail, unk]}) is False
    # 成果收不進隔離區（沒有逐項結果）＝ agent 的繳付物本身的問題
    assert A.adoption_of({"outcome": "reject", "reasons": ["artifact: too big"]}) is False
    assert A.adoption_of({"outcome": "hold", "results": [unk]}) is None
    assert A.adoption_of({"outcome": "escalate", "results": []}) is None
    # unknown_policy=reject：必要主張只有 UNKNOWN（等審查）⇒ 和 hold 一樣不記
    assert A.adoption_of({"outcome": "reject", "results": [unk, opt_fail]}) is None
    assert A.adoption_of({"outcome": None}) is None


def test_undecided_runs_do_not_count_in_runs_or_routing(env):
    book = A.ActorBook()
    ws = env / "w"
    ws.mkdir()
    for i in range(A.MIN_N):
        A.record_outcome(book, session_key=f"c{i}", actor={"platform": "claude"},
                         accepted=True, contract=None, workspace=ws, outcome="accept")
    for i in range(A.MIN_N + 2):
        A.record_outcome(book, session_key=f"x{i}", actor={"platform": "codex"},
                         accepted=None, contract=None, workspace=ws, outcome="hold")
    cells = {c["key"][1]: c for c in book.state()["cells"]}
    assert cells["codex"]["runs"] == 0 and cells["codex"]["accepted"] == 0
    assert cells["codex"]["undecided"] == A.MIN_N + 2
    assert cells["codex"]["observations"] == 0                         # 信譽重播沒碰它
    p = A.pick_agent(book, "", ["claude", "codex"])
    assert p["agent"] == "codex" and "exploring" in p["why"]          # 還是 0 跑，不是 7 跑 0 過
    line = A.recommendation_line(book, "") or ""
    assert "0/0 accepted" in line and "waiting on review" in line


def test_session_end_hold_on_a_review_claim_is_not_recorded_as_not_accepted(env):
    """契約有必要的 review 主張：回合邊界的 `flow.check` 看不到審查 ⇒ hold。以前記成 adoption 0。"""
    p = _project(env, CLAIMS_REVIEW)
    _write_report(p, "Total: 60\n")
    hook.handle("claude", "Stop", {"session_id": "S", "cwd": str(p)})
    hook.handle("claude", "SessionEnd", {"session_id": "S", "cwd": str(p), "reason": "other"})
    [cell] = A.ActorBook().state()["cells"]
    assert cell["runs"] == 0 and cell["accepted"] == 0 and cell["undecided"] == 1
    [ev] = [e for e in A.ActorBook().events() if e["kind"] == "outcome"]
    assert ev["outcome"] == "hold" and ev["accepted"] is None
    [c] = _outcome_consequences(R.Recorder(p))
    assert c["outcome"] == "hold" and c["accepted"] is None


def test_session_end_reject_with_a_failing_claim_still_counts_zero(env):
    p = _project(env, CLAIMS_REVIEW)
    _write_report(p, "Total: 999\n")
    hook.handle("claude", "Stop", {"session_id": "S", "cwd": str(p)})
    hook.handle("claude", "SessionEnd", {"session_id": "S", "cwd": str(p), "reason": "other"})
    cells = [c for c in A.ActorBook().state()["cells"] if c["key"][0] == "claude:main"]
    assert [(c["runs"], c["accepted"], c["undecided"]) for c in cells] == [(1, 0, 0)]
    [c] = _outcome_consequences(R.Recorder(p))
    assert c["outcome"] == "reject" and c["accepted"] is False


def test_finalize_hold_is_not_recorded_as_not_accepted(env):
    from vacant_network.trace import finalize
    p = _project(env, CLAIMS_REVIEW)
    _write_report(p, "Total: 60\n", session="F")
    assert finalize.main([str(p / ".vacant" / "contract.json"), "claude", "F"]) == 0
    [cell] = A.ActorBook().state()["cells"]
    assert cell["runs"] == 0 and cell["undecided"] == 1
    [c] = _outcome_consequences(R.Recorder(p))
    assert c["outcome"] == "hold" and c["accepted"] is None and c["at"] == "session_end"


AGENT = r'''
import pathlib
pathlib.Path("report.md").write_text("Total: 60\n")
'''


def _do(env, claims, name):
    from vacant_network.adapters import agents as AG
    from vacant_network.adapters import run as RUN
    p = _project(env, claims, name=name)
    task = flow.open_task(p / ".vacant" / "contract.json")
    script = env / f"agent_{name}.py"
    script.write_text(AGENT)
    return RUN.do(task, agent="generic",
                  build=AG.generic_build([sys.executable, str(script), "{prompt}"]),
                  prompt="Write report.md with the total.", sandbox="none",
                  feedback=lambda r: "x", feedback_mode="generic")


def test_vacant_do_hold_is_undecided_and_the_outcome_is_on_the_signed_chain(env):
    res = _do(env, CLAIMS_REVIEW, "dohold")
    assert res["outcome"] == "hold"
    [cell] = A.ActorBook().state()["cells"]
    assert cell["runs"] == 0 and cell["undecided"] == 1
    rec = R.Recorder(res["workspace"])
    [c] = _outcome_consequences(rec)                       # §10 第 8 列：簽進病歷，不只 actors.ndjson
    assert c["outcome"] == "hold" and c["accepted"] is None and c["at"] == "vacant_do"
    assert rec.verify()[0]


def test_vacant_do_accept_is_on_the_signed_chain(env):
    res = _do(env, CLAIMS_TOTAL, "doaccept")
    assert res["outcome"] == "accept"
    [cell] = A.ActorBook().state()["cells"]
    assert (cell["runs"], cell["accepted"]) == (1, 1)
    [c] = _outcome_consequences(R.Recorder(res["workspace"]))
    assert c["outcome"] == "accept" and c["accepted"] is True and c["key"] == cell["key"]


def test_actor_book_docstring_says_it_is_an_unsigned_view():
    doc = A.__doc__ or ""
    assert "沒有簽章的衍生檢視" in doc and "簽章的真相來源" in doc


# ── 2. 截短對得出來（任務帳本的錨點）─────────────────────────────────

def _verify(p, capsys):
    from vacant_network.trace import cli
    cwd = os.getcwd()
    os.chdir(p)
    try:
        code = cli.main(["trace", "verify"])
    finally:
        os.chdir(cwd)
    return code, capsys.readouterr().out


def _anchored_project(env):
    p = _project(env, CLAIMS_TOTAL, name="anch")
    _write_report(p, "Total: 999\n")
    hook.handle("claude", "Stop", {"session_id": "S", "cwd": str(p)})     # 錨點寫進任務帳本
    rec = R.Recorder(p)
    from vacant_network.intake.ledger import Ledger
    heads = [e for e in Ledger(C.load(p / ".vacant" / "contract.json").task_id).events()
             if e["type"] == "trace_head"]
    assert heads and heads[-1]["project"] == rec.dir.name
    return p, rec, heads[-1]


def _truncate(rec, keep):
    lines = rec.chain_path.read_bytes().split(b"\n")
    lines = [x for x in lines if x.strip()][:keep]
    rec.chain_path.write_bytes(b"\n".join(lines) + b"\n")
    last = json.loads(lines[-1])
    from vacant_network.logbook import LogEntry
    e = LogEntry.from_json(last)
    # 攻擊者連同沒簽章的 head.json 一起改：只對 head.json 的舊檢查看不出來
    (rec.dir / "head.json").write_text(json.dumps({"seq": e.seq, "hash": e.hash()}))


def test_trace_verify_catches_truncation_below_the_ledger_anchor(env, capsys):
    p, rec, head = _anchored_project(env)
    code, out = _verify(p, capsys)
    assert code == 0 and out.startswith("OK "), out
    _truncate(rec, keep=int(head["seq"]) - 1)              # seq 從 1 起：留下 1..seq-1
    assert rec.verify()[0]                                 # 只看鏈＋head.json 的舊檢查：過
    code, out = _verify(p, capsys)
    assert code == 1 and out.startswith("BROKEN ") and "task ledger" in out, (out, head)


def test_trace_verify_says_it_checked_the_anchor_when_it_holds(env, capsys):
    p, rec, head = _anchored_project(env)
    code, out = _verify(p, capsys)
    assert code == 0 and "matches the task ledger's anchor" in out, out


def test_trace_verify_catches_a_replaced_tail_past_the_anchor(env, capsys):
    p, rec, head = _anchored_project(env)
    _truncate(rec, keep=int(head["seq"]) - 1)
    for i in range(4):                                     # 用本機金鑰重新接到錨點之後
        rec.append("coverage", {"note": f"rewritten {i}"})
    assert rec.verify()[0]
    code, out = _verify(p, capsys)
    assert code == 1 and "does not match" in out


def test_a_truncated_trace_records_no_consequences_at_the_next_turn(env):
    p, rec, head = _anchored_project(env)
    n_before = len(A.ActorBook().events())
    _truncate(rec, keep=int(head["seq"]) - 1)
    hook.handle("claude", "Stop", {"session_id": "S", "cwd": str(p), "stop_hook_active": True})
    assert "does not verify" in (rec.dir / "report.md").read_text()
    assert len(A.ActorBook().events()) == n_before


def test_trace_verify_without_a_ledger_says_it_was_not_checked(env, capsys, monkeypatch):
    monkeypatch.setenv("VACANT_TRACE", "1")
    p = env / "plain"
    p.mkdir()
    rec = R.Recorder(p)
    rec.checkpoint("x")
    rec.append("coverage", {"note": "something"})
    code, out = _verify(p, capsys)
    assert code == 0 and out.startswith("OK ") and "not checked" in out


# ── 4. KS-1 行動者識別 ───────────────────────────────────────────────

def test_actor_tokens_include_the_subagent_definition_hash_but_not_platform_names(env):
    from vacant_network.trace import stopcheck
    p = _project(env, CLAIMS_TOTAL, name="defs")
    d = p / ".claude" / "agents"
    d.mkdir(parents=True)
    (d / "stats-helper.md").write_text("---\nname: stats-helper\n---\nYou add numbers.\n")
    _write_report(p, "Total: 999\n", sub=True)
    rec = R.Recorder(p)
    stream = A.definition_of({"platform": "claude", "agent_type": "stats-helper"}, rec.workspace)
    sha = stream.rsplit(":", 1)[-1]
    assert stream.startswith("claude:def:stats-helper:") and len(sha) == 16
    toks = stopcheck._actor_tokens(rec)
    assert sha in toks and {"a7f3c9d2", "stats-helper"} <= toks
    assert not toks & {"claude", "codex", "opencode", "pi"}
