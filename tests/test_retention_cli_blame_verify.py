"""GC 回收後的 CLI 整合測試：`vacant trace verify` 照樣 OK、`vacant trace blame` 誠實 UNKNOWN。

對應 ASSIGNMENT「🔴 最優先」第 4 條 (c)「trace verify／blame 在回收後仍成立」：歷史版本被
`retention.compact_trace` 回收後，CLI 端（`cmd_verify`／`cmd_blame`）verify 須退出碼 0、輸出含 OK；
blame 對被刪版本引入的值須誠實回 UNKNOWN / unattributable，不誣賴最後修改者。結構參考
`tests/test_retention.py::test_target_sweep_evicts_historical_versions_and_blame_returns_unknown`；
差別在改走 CLI `main()` 入口、blame 不帶 --value（值由現行第 2 行解析）。
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

from vacant_network import retention
from vacant_network.adapters import install as INS
from vacant_network.trace.cli import main as trace_main
from vacant_network.trace.recorder import Actor, Recorder


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE"):
        monkeypatch.delenv(k, raising=False)
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    return tmp_path


def test_verify_ok_and_blame_unknown_after_gc(env, monkeypatch, capsys):
    vh, ws = pathlib.Path(os.environ["VACANT_HOME"]), env / "work" / "cli_gc"
    ws.mkdir(parents=True)
    (ws / "app.py").write_text("line1 = 100\nline2 = 999\n")
    rec = Recorder(ws)
    rec.baseline()
    s1 = Actor("claude", "s1")
    s2 = Actor("claude", "s2")
    rec.pre("t1", s1, "Edit", {"file_path": str(ws / "app.py"), "new_string": "line1 = 200"})
    (ws / "app.py").write_text("line1 = 200\nline2 = 999\n")
    rec.post("t1", s1, "Edit", {"file_path": str(ws / "app.py"), "new_string": "line1 = 200"}, "ok")
    # 多步修改產生 ~250 KB 歷史版本；line2 的 magic 行由 t2 引入、之後各步保留：
    rec.pre("t2", s1, "Write", {"file_path": str(ws / "app.py"), "content": "magic = 77777\n"})
    (ws / "app.py").write_text("pad = '" + ("A" * 50_000) + "'\nmagic = 77777\n")
    rec.post("t2", s1, "Write", {"file_path": str(ws / "app.py"), "content": "magic = 77777\n"}, "ok")
    for i in range(3, 7):
        content = f"pad = '{chr(65 + i) * 50_000}'\nmagic = 77777\n"
        rec.pre(f"t{i}", s2, "Edit", {"file_path": str(ws / "app.py"), "new_string": f"step_{i}"})
        (ws / "app.py").write_text(content)
        rec.post(f"t{i}", s2, "Edit", {"file_path": str(ws / "app.py"), "new_string": f"step_{i}"}, "ok")
    res = retention.compact_trace(vh, dry_run=False, target_bytes=60_000)
    assert res["target"]["target_reached"] and res["target"]["files_removed"] >= 3
    assert res["target"]["bytes_remaining"] <= 60_000
    ok, msg = rec.verify()
    assert ok, msg
    monkeypatch.chdir(ws)
    rc = trace_main(["trace", "verify"])
    out = capsys.readouterr().out
    assert rc == 0 and "OK" in out, out
    rc = trace_main(["trace", "blame", "app.py:2", "--json"])
    out = capsys.readouterr().out
    assert rc == 0, out
    b = json.loads(out)
    assert b["state"] == "UNKNOWN", b
    assert b["fault_class"] == "unattributable", b


def test_blame_with_explicit_value_unknown_after_gc(env, monkeypatch, capsys):
    vh, ws = pathlib.Path(os.environ["VACANT_HOME"]), env / "work" / "cli_gc_val"
    ws.mkdir(parents=True)
    (ws / "app.py").write_text("line1 = 100\nline2 = 999\n")
    rec = Recorder(ws)
    rec.baseline()
    s1 = Actor("claude", "s1")
    s2 = Actor("claude", "s2")
    rec.pre("t1", s1, "Edit", {"file_path": str(ws / "app.py"), "new_string": "line1 = 200"})
    (ws / "app.py").write_text("line1 = 200\nline2 = 999\n")
    rec.post("t1", s1, "Edit", {"file_path": str(ws / "app.py"), "new_string": "line1 = 200"}, "ok")
    rec.pre("t2", s1, "Write", {"file_path": str(ws / "app.py"), "content": "magic = 77777\n"})
    (ws / "app.py").write_text("pad = '" + ("A" * 50_000) + "'\nmagic = 77777\n")
    rec.post("t2", s1, "Write", {"file_path": str(ws / "app.py"), "content": "magic = 77777\n"}, "ok")
    for i in range(3, 7):
        content = f"pad = '{chr(65 + i) * 50_000}'\nmagic = 77777\n"
        rec.pre(f"t{i}", s2, "Edit", {"file_path": str(ws / "app.py"), "new_string": f"step_{i}"})
        (ws / "app.py").write_text(content)
        rec.post(f"t{i}", s2, "Edit", {"file_path": str(ws / "app.py"), "new_string": f"step_{i}"}, "ok")
    res = retention.compact_trace(vh, dry_run=False, target_bytes=60_000)
    assert res["target"]["target_reached"] and res["target"]["files_removed"] >= 3
    assert res["target"]["bytes_remaining"] <= 60_000
    monkeypatch.chdir(ws)
    rc = trace_main(["trace", "blame", "app.py:2", "--value", "magic = 77777", "--json"])
    out = capsys.readouterr().out
    assert rc == 0, out
    b = json.loads(out)
    assert b["state"] == "UNKNOWN", b
    assert b["fault_class"] == "unattributable", b
