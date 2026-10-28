"""Scratch probe for round 145 (deleted after use)."""
from __future__ import annotations
import json, pathlib
from vacant_network import retention
from vacant_network.adapters import hook, install as INS
from vacant_network.trace import capture
from vacant_network.trace.recorder import Recorder
from vacant_network.trace.blame import Trace
import pytest


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE"):
        monkeypatch.delenv(k, raising=False)
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    return tmp_path


def _step(proj, n, tool, inp, write=None):
    pre = {"session_id": "S1", "cwd": str(proj), "tool_name": tool,
           "tool_use_id": f"t{n}", "tool_input": inp}
    hook.handle("claude", "PreToolUse", pre)
    for rel, content in (write or {}).items():
        f = proj / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
    post = {**pre, "tool_response": {"stdout": "ok", "stderr": ""}}
    hook.handle("claude", "PostToolUse", post)


def test_probe(env):
    proj = env / "work" / "big_proj"
    proj.mkdir(parents=True)
    for i in range(30):
        (proj / f"bg_{i:02d}.txt").write_text(f"background content {i}\n" * 200)
    (proj / "app.py").write_text("def calc():\n    return 1\n")
    hook.handle("claude", "UserPromptSubmit", {
        "session_id": "S1", "cwd": str(proj), "prompt": "Update app.py to return 2."})
    _step(proj, 1, "Read", {"file_path": str(proj / "app.py")})
    _step(proj, 2, "Write", {"file_path": str(proj / "app.py"),
                             "content": "def calc():\n    return 2\n"},
          write={"app.py": "def calc():\n    return 2\n"})
    ws = capture.workspace_for(str(proj))
    rec = Recorder(ws)
    tr = Trace(rec)
    s1_idx, s2_idx = tr.steps[0].post_index, tr.steps[1].post_index
    blobs = sorted(f.name for f in rec.blobs.root.rglob("*") if f.is_file())
    print("\nBLOBS:", len(blobs), blobs[:12])
    print("app@ s1:", repr(tr.file_text(s1_idx, "app.py")))
    print("app@ s2:", repr(tr.file_text(s2_idx, "app.py")))
    print("bg0@ s2:", repr((tr.file_text(s2_idx, "bg_00.txt") or None) and "OK" or None))
    dry = retention.compact_trace(active_window_s=0.0, dry_run=True)
    print("dry inactive:", dry["files_removed"], dry["bytes_freed"])
    res = retention.compact_trace(active_window_s=0.0, dry_run=False)
    print("real inactive:", res["files_removed"], res["bytes_freed"])
    print("app@ s1 post-gc:", repr(tr.file_text(s1_idx, "app.py")))
    print("bg0@ s2 post-gc:", repr((tr.file_text(s2_idx, "bg_00.txt") or None) and "OK" or None))
    dest = env / "materialized"
    tr.materialize(s1_idx, dest)
    print("materialize app:", repr((dest / "app.py").read_text()))
    print("materialize bg15:", "OK" if (dest / "bg_15.txt").is_file() else "MISSING")
    ok, msg = rec.verify()
    print("verify:", ok, msg)
    ok2, msg2 = rec.verify_since(0)
    print("verify_since:", ok2, msg2)
    # now modify a bg file after gc: does the before version come back?
    _step(proj, 3, "Edit", {"file_path": str(proj / "bg_00.txt")},
          write={"bg_00.txt": "changed after gc\n"})
    tr2 = Trace(Recorder(capture.workspace_for(str(proj))))
    s3_idx = tr2.steps[-1].post_index
    s0_idx = tr2.steps[0].post_index
    print("bg0 pre-edit (s0):", repr((tr2.file_text(s0_idx, "bg_00.txt") or None) and "OK" or None))
    print("bg0 post-edit (s3):", repr((tr2.file_text(s3_idx, "bg_00.txt") or None) and "OK" or None))
    ok3, msg3 = rec.verify()
    print("verify after step3:", ok3, msg3)
