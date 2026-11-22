"""清理預設不動磁碟，舊資料才可刪除。"""
import os

import pytest


@pytest.fixture(autouse=True)
def own_processes(monkeypatch):
    from vacant_network import maintenance as M
    def active():
        paths = [M.pathlib.Path.cwd()]
        for p in M.pathlib.Path('/proc/self/fd').iterdir():
            try:
                paths.append(M.pathlib.Path(os.readlink(p)))
            except FileNotFoundError:
                pass
        return paths
    monkeypatch.setattr(M, '_active', active)


def old(path):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in dirs + files:
            os.utime(os.path.join(root, name), (1, 1), follow_symlinks=False)
    os.utime(path, (1, 1))


def test_cleanup_dry_run_then_apply(tmp_path):
    from vacant_network.maintenance import clean
    work, project = tmp_path / "work", tmp_path / "project"
    work.mkdir()
    project.mkdir()
    stale = work / "stale"
    stale.mkdir()
    old(stale)
    recent = work / "recent"
    recent.mkdir()
    cache = project / ".pytest_cache"
    cache.mkdir()
    old(cache)
    log = project / "nohup.log"
    log.write_text("12345")
    os.utime(log, (1, 1))
    args = dict(work=work, project=project, age=60, max_bytes=4, keep=2)
    assert clean(**args)
    assert stale.exists() and cache.exists() and log.exists()
    clean(**args, apply=True)
    assert not stale.exists() and not cache.exists()
    assert recent.exists() and (project / "nohup.log.1").read_text() == "12345"
    assert log.read_text() == ""


def test_cleanup_skips_links_recent_children_and_in_use(tmp_path):
    from vacant_network.maintenance import clean
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (work / "link").symlink_to(outside)
    busy = work / "busy"
    busy.mkdir()
    f = busy / "held"
    f.write_text("x")
    old(busy)
    with f.open():
        clean(work=work, project=None, age=1, apply=True)
    assert busy.exists() and outside.exists()
    (busy / "new").write_text("new")
    os.utime(busy, (1, 1))
    clean(work=work, project=None, age=1, apply=True)
    assert busy.exists()


def test_cleanup_empty_invalid_and_linked_roots(tmp_path):
    from vacant_network.maintenance import clean
    assert clean(work=tmp_path / "missing", project=None) == []
    with pytest.raises(ValueError):
        clean(work=tmp_path, project=None, age=-1)
    link = tmp_path / "link"
    link.symlink_to(tmp_path)
    with pytest.raises(OSError):
        clean(work=link, project=None)


def test_rotation_keeps_n_and_refuses_planted_backup(tmp_path):
    from vacant_network.maintenance import clean
    project = tmp_path / "project"
    project.mkdir()
    for n in range(4):
        log = project / "nohup.log"
        log.write_text(str(n) * 5)
        os.utime(log, (1, 1))
        clean(work=tmp_path / "missing", project=project, max_bytes=4, keep=2, apply=True)
    assert (project / "nohup.log.1").read_text() == "33333"
    assert (project / "nohup.log.2").read_text() == "22222"
    assert not (project / "nohup.log.3").exists()
    (project / "nohup.log.2").unlink()
    outside = tmp_path / "outside"
    outside.write_text("safe")
    (project / "nohup.log.2").symlink_to(outside)
    log.write_text("large")
    os.utime(log, (1, 1))
    with pytest.raises(ValueError):
        clean(work=tmp_path / "missing", project=project, max_bytes=4, keep=2, apply=True)
    assert outside.read_text() == "safe"


def test_cli_refuses_uninspectable_processes(tmp_path, monkeypatch, capsys):
    from vacant_network import maintenance as M
    def denied():
        raise PermissionError("cannot inspect active processes")
    monkeypatch.setattr(M, '_active', denied)
    monkeypatch.setenv("VACANT_WORK", str(tmp_path))
    with pytest.raises(SystemExit) as exc:
        M.main(["--apply"])
    assert exc.value.code == 1
    assert "cleanup refused" in capsys.readouterr().err
