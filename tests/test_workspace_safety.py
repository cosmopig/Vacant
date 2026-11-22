"""工作區複製及回寫的連結邊界。"""
import pathlib

import pytest

from vacant_network.adapters import restart as R


def test_acceptance_never_restores_through_external_link(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"unchanged")
    (ws / "test_x.py").symlink_to(outside)
    try:
        R.acceptance({"test_x.py": b"import unittest\n"}, ws)
    except (OSError, ValueError):
        pass
    assert outside.read_bytes() == b"unchanged"


@pytest.mark.parametrize("parent", [False, True])
def test_write_back_rejects_destination_links(tmp_path, parent):
    project, ws, outside = (tmp_path / n for n in ("project", "ws", "outside"))
    for p in (project, ws, outside):
        p.mkdir()
    rel = pathlib.Path("d/x") if parent else pathlib.Path("x")
    (ws / rel).parent.mkdir(exist_ok=True)
    (ws / rel).write_text("attack")
    (outside / "x").write_text("safe")
    (project / ("d" if parent else "x")).symlink_to(outside if parent else outside / "x")
    with pytest.raises((OSError, ValueError)):
        R._write_back(project, ws, set())
    assert (outside / "x").read_text() == "safe"


def test_fresh_copy_rejects_escape_and_preserves_relative_link(tmp_path):
    from vacant_network.adapters.workspace import copy_workspace
    src = tmp_path / "src"
    src.mkdir()
    (src / "x").write_text("ok")
    (src / "link").symlink_to("x")
    copy_workspace(src, tmp_path / "dest", set())
    assert (tmp_path / "dest/link").is_symlink()
    (src / "escape").symlink_to("../../outside")
    with pytest.raises(ValueError):
        copy_workspace(src, tmp_path / "bad", set())


def test_copy_rejects_symlinked_destination_parent(tmp_path):
    from vacant_network.adapters.workspace import copy_workspace
    src = tmp_path / "src"
    src.mkdir()
    (src / "x").write_text("ok")
    (tmp_path / "link").symlink_to(src)
    with pytest.raises(OSError):
        copy_workspace(src, tmp_path / "link/dest", set())


def test_copy_rejects_planted_destination_and_source_parent(tmp_path):
    from vacant_network.adapters.workspace import copy_workspace
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()
    (src / "x").write_text("ok")
    dest.symlink_to(src)
    with pytest.raises(FileExistsError):
        copy_workspace(src, dest, set())
    with pytest.raises(OSError):
        copy_workspace(dest, tmp_path / "other", set())
    assert (src / "x").read_text() == "ok"
