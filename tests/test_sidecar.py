"""旁路 sidecar（`vacant_network/vrun/sidecar.py`）：不碰模型端點的可究責層。

每一條對應 DECISION_20260924_MEDIATION_WITHOUT_MODEL_WRAP 的一個主張或誠實邊界。
"""
import json
import pathlib
import socket
import threading
import time

import pytest

from vacant_network.vrun import sidecar as sc


def _tl(path: pathlib.Path, *objs):
    with open(path, "a") as f:
        for o in objs:
            f.write(json.dumps(o) + "\n")


def _t_start(path):
    path.write_text("")
    _tl(path, {"type": "user", "message": {"role": "user", "content": "do it"}})


def _t_tool(path, tid, i=0, *, sidechain=False):
    _tl(path, {"type": "assistant", "requestId": f"req_{tid}", "isSidechain": sidechain,
               "message": {"content": [{"type": "tool_use", "id": tid, "name": "Write",
                                        "input": {}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid}]}})


def _t_end(path):
    _tl(path, {"type": "assistant", "requestId": "req_last",
               "message": {"content": [{"type": "text", "text": "done"}]}})


def _env(coll, **kw):
    e = {"VACANT_SC_ADDR": coll.addr, "VACANT_SC_TOKEN": coll.token}
    e.update(kw)
    return e


def _fire(coll, event, **payload):
    rc, _ = sc.hook_main(event, json.dumps(payload), _env(coll))
    assert rc == 0


@pytest.fixture
def coll(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps(sc.claude_settings("hook")))
    c = sc.Collector(hook_cfg_path=str(cfg))
    c.start()
    yield c
    c.stop()


def _honest_run(coll, tmp_path, ws, tids=("t1", "t2")):
    tp = tmp_path / "t.jsonl"
    _t_start(tp)
    _fire(coll, "SessionStart", transcript_path=str(tp))
    for tid in tids:
        _t_tool(tp, tid)
        _fire(coll, "PreToolUse", tool_name="Write", tool_use_id=tid, cwd=str(ws),
              tool_input={"file_path": str(ws / f"{tid}.txt"), "content": "x"},
              transcript_path=str(tp))
        (ws / f"{tid}.txt").write_text("x")
        _fire(coll, "PostToolUse", tool_name="Write", tool_use_id=tid, cwd=str(ws),
              tool_input={"file_path": str(ws / f"{tid}.txt")}, transcript_path=str(tp))
    _t_end(tp)
    _fire(coll, "SessionEnd", transcript_path=str(tp))
    return tp


def _reconcile(coll, tp, ws, before, *, failclosed=True, cfg_start="same"):
    from vacant_network.vrun import wshash
    after = wshash.tree_leaves(ws)
    ev = list(coll.events)
    chk = sc.verify_transcript_checkpoints(str(tp) if tp else None,
                                           [e["transcript"] for e in ev])
    return sc.reconcile(ev, sc.transcript_skeleton(tp), transcript_check=chk,
                        ws_diff=wshash.diff_leaves(before, after), workspace=str(ws),
                        hook_cfg_start=coll.hook_cfg_sha256() if cfg_start == "same" else cfg_start,
                        hook_cfg_end=coll.hook_cfg_sha256(), failclosed=failclosed)


def test_honest_run_is_r_full_and_third_party_verifies(coll, tmp_path):
    from vacant_network.vrun import wshash
    ws = tmp_path / "ws"
    ws.mkdir()
    before = wshash.tree_leaves(ws)
    tp = _honest_run(coll, tmp_path, ws)
    r = _reconcile(coll, tp, ws, before)
    assert r["level"] == "R-full", r["gaps"]
    assert r["channel_tier"] == "unobserved"
    assert r["model_requests_reported"] == 3
    sealed = sc.seal(coll, tmp_path / "run", reconciled=r, skeleton=sc.transcript_skeleton(tp),
                     transcript_path=str(tp), ws_start="a", ws_end="b", accepted=True,
                     verdict_sha256=None, task_id="t")
    assert sealed["issued"]
    v = sc.verify_run(tmp_path / "run", str(tp))
    assert v["verdict"] == "OK" and v["record_tier"] == "R-full"


def test_payload_text_never_reaches_the_chain(coll, tmp_path):
    secret = "sk-ant-THIS-MUST-NOT-LEAK"
    _fire(coll, "UserPromptSubmit", prompt=f"my key is {secret}")
    blob = json.dumps([e.to_json() for e in coll.book.entries])
    assert secret not in blob


def test_tool_use_without_prehook_is_broken(coll, tmp_path):
    """掛鉤中途被拆：transcript 有 t3，鏈上沒有 ⇒ R-broken（A1／A4 的形狀）。"""
    from vacant_network.vrun import wshash
    ws = tmp_path / "ws"
    ws.mkdir()
    before = wshash.tree_leaves(ws)
    tp = _honest_run(coll, tmp_path, ws)
    _t_tool(tp, "t3")  # 掛鉤拆掉之後的動作：transcript 有、鏈上沒有
    r = _reconcile(coll, tp, ws, before)
    assert r["tool_uses_without_prehook"] == ["t3"]
    assert r["transcript_grew_after_session_end"] is True
    assert r["level"] == "R-broken"


def test_transcript_edit_breaks_append_only_and_verify(coll, tmp_path):
    from vacant_network.vrun import wshash
    ws = tmp_path / "ws"
    ws.mkdir()
    before = wshash.tree_leaves(ws)
    tp = _honest_run(coll, tmp_path, ws)
    r = _reconcile(coll, tp, ws, before)
    sc.seal(coll, tmp_path / "run", reconciled=r, skeleton=sc.transcript_skeleton(tp),
            transcript_path=str(tp), ws_start="a", ws_end="b", accepted=None,
            verdict_sha256=None, task_id="t")
    tp.write_text(tp.read_text().replace("do it", "do  it"))
    v = sc.verify_run(tmp_path / "run", str(tp))
    assert v["verdict"] == "BROKEN"


def test_tampered_reconciled_json_is_broken(coll, tmp_path):
    from vacant_network.vrun import wshash
    ws = tmp_path / "ws"
    ws.mkdir()
    before = wshash.tree_leaves(ws)
    tp = _honest_run(coll, tmp_path, ws)
    r = _reconcile(coll, tp, ws, before)
    sc.seal(coll, tmp_path / "run", reconciled=r, skeleton=sc.transcript_skeleton(tp),
            transcript_path=str(tp), ws_start="a", ws_end="b", accepted=None,
            verdict_sha256=None, task_id="t")
    p = tmp_path / "run" / "reconciled.json"
    d = json.loads(p.read_text())
    d["tool_uses_without_prehook"] = []
    d["level"] = "R-full"
    d["hook_events_n"] += 1
    p.write_text(json.dumps(d))
    assert sc.verify_run(tmp_path / "run")["verdict"] == "BROKEN"


def test_no_canary_refuses_receipt(coll, tmp_path):
    r = sc.reconcile([], None, transcript_check={"append_only": None}, ws_diff=None,
                     workspace=str(tmp_path), hook_cfg_start=None, hook_cfg_end=None,
                     failclosed=True)
    assert r["level"] == "R-none"
    sealed = sc.seal(coll, tmp_path / "run", reconciled=r, skeleton=None, transcript_path=None,
                     ws_start=None, ws_end=None, accepted=None, verdict_sha256=None, task_id="t")
    assert not sealed["issued"]
    assert sc.verify_run(tmp_path / "run")["verdict"] == "NO_RECEIPT"


def test_transcript_missing_is_r_none_not_zero(coll, tmp_path):
    """`--no-session-persistence`：沒有 transcript ＝沒量到，不是「零通模型呼叫」。"""
    _fire(coll, "SessionStart")
    r = sc.reconcile(list(coll.events), None, transcript_check={"append_only": None},
                     ws_diff={"added": [], "removed": [], "changed": []},
                     workspace=str(tmp_path), hook_cfg_start="x", hook_cfg_end="x",
                     failclosed=True)
    assert r["model_requests_reported"] is None
    assert r["level"] == "R-none" and r["gaps"] == ["transcript_missing"]


def test_unmeasured_is_never_satisfied(coll, tmp_path):
    """hook 設定雜湊沒量到 ⇒ R-partial，不是 R-full（鐵律 3）。"""
    from vacant_network.vrun import wshash
    ws = tmp_path / "ws"
    ws.mkdir()
    before = wshash.tree_leaves(ws)
    tp = _honest_run(coll, tmp_path, ws)
    r = _reconcile(coll, tp, ws, before, cfg_start=None)
    assert r["hook_cfg_changed"] is None
    assert r["level"] == "R-partial" and "hook_cfg_unmeasured" in r["gaps"]


def test_shell_attributed_change_is_opaque_not_full(coll, tmp_path):
    from vacant_network.vrun import wshash
    ws = tmp_path / "ws"
    ws.mkdir()
    before = wshash.tree_leaves(ws)
    tp = tmp_path / "t.jsonl"
    _t_start(tp)
    _fire(coll, "SessionStart", transcript_path=str(tp))
    _t_tool(tp, "b1")
    _fire(coll, "PreToolUse", tool_name="Bash", tool_use_id="b1", transcript_path=str(tp),
          tool_input={"command": "echo x > y.txt"})
    (ws / "y.txt").write_text("x")
    _fire(coll, "PostToolUse", tool_name="Bash", tool_use_id="b1", transcript_path=str(tp))
    _t_end(tp)
    _fire(coll, "SessionEnd", transcript_path=str(tp))
    r = _reconcile(coll, tp, ws, before)
    assert r["ws_shell_attributed"] == ["y.txt"] and r["ws_unexplained"] == []
    assert r["level"] == "R-opaque"


def test_change_with_no_tool_at_all_is_unexplained(coll, tmp_path):
    from vacant_network.vrun import wshash
    ws = tmp_path / "ws"
    ws.mkdir()
    before = wshash.tree_leaves(ws)
    tp = _honest_run(coll, tmp_path, ws)
    (ws / "sneaky.txt").write_text("outside")
    r = _reconcile(coll, tp, ws, before)
    assert r["ws_unexplained"] == ["sneaky.txt"] and r["level"] == "R-broken"


def test_event_inside_shell_window_is_flagged():
    ev = [{"event": "PreToolUse", "tool_name": "Bash", "tool_use_id": "b"},
          {"event": "PreToolUse", "tool_name": "Write", "tool_use_id": "forged"},
          {"event": "PostToolUse", "tool_name": "Bash", "tool_use_id": "b"},
          {"event": "PreToolUse", "tool_name": "Write", "tool_use_id": "w"}]
    assert sc.shell_window_intrusions(ev) == ["forged"]


def test_bad_token_is_recorded_not_silently_dropped(coll):
    rc, _ = sc.hook_main("PreToolUse", "{}", {"VACANT_SC_ADDR": coll.addr,
                                              "VACANT_SC_TOKEN": "wrong"})
    assert rc == 0  # 不是 fail-closed 模式
    assert coll.rejects == 1
    assert any(e.type == "sc_reject" for e in coll.book.entries)


def test_failclosed_denies_tool_when_collector_is_gone(tmp_path):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # 沒人在聽
    fb = tmp_path / "fb.jsonl"
    env = {"VACANT_SC_ADDR": f"127.0.0.1:{port}", "VACANT_SC_TOKEN": "x",
           "VACANT_SC_FAILCLOSED": "1", "VACANT_SC_FALLBACK": str(fb)}
    assert sc.hook_main("PreToolUse", "{}", env)[0] == 2
    assert sc.hook_main("PostToolUse", "{}", env)[0] == 0  # 只擋 PreToolUse
    assert sc.hook_main("PreToolUse", "{}", dict(env, VACANT_SC_FAILCLOSED="0"))[0] == 0
    assert fb.read_text().count("\n") == 3


def test_hung_collector_denies_within_own_timeout(tmp_path):
    """collector 吊死（接受連線但不回）：逾時要當拒絕，不是安靜放行（Fable #1 Q3-2）。"""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    conns = []
    threading.Thread(target=lambda: conns.append(srv.accept()), daemon=True).start()
    env = {"VACANT_SC_ADDR": f"127.0.0.1:{srv.getsockname()[1]}", "VACANT_SC_TOKEN": "x",
           "VACANT_SC_FAILCLOSED": "1", "VACANT_SC_TIMEOUT": "0.5"}
    t = time.time()
    rc, _ = sc.hook_main("PreToolUse", "{}", env)
    assert rc == 2 and time.time() - t < 3
    srv.close()


def test_no_addr_is_a_noop():
    assert sc.hook_main("PreToolUse", "{}", {}) == (0, "")


def test_claude_settings_shape():
    s = sc.claude_settings("H")
    assert s["hooks"]["PreToolUse"][0]["matcher"] == "*"
    assert "matcher" not in s["hooks"]["SessionStart"][0]
    assert s["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "H PreToolUse"
