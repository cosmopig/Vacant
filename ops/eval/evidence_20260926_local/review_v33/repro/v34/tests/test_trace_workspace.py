"""追緝的工作區量具（`vacant_network/trace/workspace.py`）。"""
from __future__ import annotations

import os
import pathlib

from vacant_network.trace import workspace as W


def _w(root: pathlib.Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def test_scan_diff_and_rebuild_any_state(tmp_path):
    ws, store = tmp_path / "ws", W.Blobs(tmp_path / "objects")
    _w(ws, {"report.md": "Total: 60\n", "data/a.csv": "x\n", ".git/HEAD": "ref"})
    s0 = W.scan(ws, blobs=store)
    assert ".git/HEAD" not in s0 and set(s0) == {"report.md", "data/a.csv"}
    (ws / "report.md").write_text("Total: 999\n")
    os.remove(ws / "data/a.csv")
    _w(ws, {"notes/new.txt": "hi"})
    s1 = W.scan(ws, s0, blobs=store)
    ch = {c.path: c.kind for c in W.diff(s0, s1)}
    assert ch == {"report.md": "modified", "data/a.csv": "deleted", "notes/new.txt": "added"}
    back = tmp_path / "back"
    assert W.materialize(s0, store, back) == []
    assert (back / "report.md").read_text() == "Total: 60\n"      # 之前的狀態可以重建
    assert W.index_root(W.load(W.dump(s1))) == W.index_root(s1)


def test_incremental_scan_reuses_unchanged_hashes(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    _w(ws, {f"f{i}.txt": str(i) for i in range(20)})
    s0 = W.scan(ws)
    calls = []
    real = W.hashlib.sha256

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(W.hashlib, "sha256", counting)
    W.scan(ws, s0)
    assert calls == []                                                # 沒變的一個都不重算


def test_exec_bit_and_symlinks_are_seen(tmp_path):
    ws = tmp_path / "ws"
    _w(ws, {"run.sh": "echo"})
    s0 = W.scan(ws)
    os.chmod(ws / "run.sh", 0o755)
    os.symlink("/etc/hostname", ws / "link")
    s1 = W.scan(ws, s0, full=True)
    kinds = {c.path: c.kind for c in W.diff(s0, s1)}
    assert kinds == {"run.sh": "modified", "link": "added"}
    assert s1["link"].sha256 == "link:/etc/hostname"
