"""清理預設不動磁碟，舊資料才可刪除。"""
import os

import pytest


@pytest.fixture(autouse=True)
def own_processes(monkeypatch):
    from vacant_network import maintenance as M
    original = M._active
    def active():
        paths = [M.pathlib.Path.cwd()]
        non_append = set()
        for p in M.pathlib.Path('/proc/self/fd').iterdir():
            try:
                path = M.pathlib.Path(os.readlink(p))
                paths.append(path)
                info = (M.pathlib.Path('/proc/self/fdinfo') / p.name).read_text()
                flags = next(int(line.split()[1], 8) for line in info.splitlines() if line.startswith('flags:'))
                if flags & os.O_ACCMODE in (os.O_WRONLY, os.O_RDWR) and not flags & os.O_APPEND:
                    non_append.add(path)
            except FileNotFoundError:
                pass
        return paths, 0, non_append
    monkeypatch.setattr(M, '_active', active)
    return original


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


@pytest.mark.parametrize("part", ["cwd", "fd"])
def test_cli_reports_uninspectable_processes(tmp_path, monkeypatch, capsys, own_processes, part):
    from vacant_network import maintenance as M
    proc = M.pathlib.Path("/proc")
    process = proc / str(os.getpid())
    iterdir, readlink = M.pathlib.Path.iterdir, os.readlink
    def processes(path):
        if path == process / "fd" and part == "fd":
            raise PermissionError("uninspectable process")
        return iter([process]) if path == proc else iterdir(path)
    def denied(path, *args, **kwargs):
        if path == process / "cwd" and part == "cwd":
            raise PermissionError("uninspectable process")
        return readlink(path, *args, **kwargs)
    monkeypatch.setattr(M.pathlib.Path, "iterdir", processes)
    monkeypatch.setattr(os, "readlink", denied)
    monkeypatch.setattr(M, '_active', own_processes)
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "missing"))
    assert M.main(["--dry-run"]) == 0
    assert '"uninspectable_processes": 1' in capsys.readouterr().out


def test_missing_proc_still_refuses(tmp_path, monkeypatch, own_processes):
    from vacant_network import maintenance as M
    is_dir = M.pathlib.Path.is_dir
    monkeypatch.setattr(M.pathlib.Path, "is_dir",
                        lambda p: False if p == M.pathlib.Path("/proc") else is_dir(p))
    with pytest.raises(OSError, match="cannot inspect"):
        own_processes()


def test_busy_log_copytruncate_preserves_writer_fd(tmp_path):
    from vacant_network.maintenance import clean
    log = tmp_path / "nohup.log"
    log.write_bytes(b"before rotation")
    with log.open("ab", buffering=0) as writer:
        inode = os.fstat(writer.fileno()).st_ino
        args = dict(work=tmp_path / "missing", project=tmp_path, max_bytes=4, keep=2)
        assert clean(**args)[0]["method"] == "copytruncate"
        assert log.read_bytes() == b"before rotation"
        clean(**args, apply=True)
        assert (tmp_path / "nohup.log.1").read_bytes() == b"before rotation"
        assert log.read_bytes() == b""
        assert log.stat().st_ino == inode
        writer.write(b"after rotation")
        assert log.read_bytes() == b"after rotation"
        clean(**args, apply=True)
        assert (tmp_path / "nohup.log.1").read_bytes() == b"after rotation"
        assert (tmp_path / "nohup.log.2").read_bytes() == b"before rotation"


def test_recent_idle_log_rotates_by_size(tmp_path):
    from vacant_network.maintenance import clean
    log = tmp_path / "nohup.log"
    log.write_text("oversized")
    inode = log.stat().st_ino
    actions = clean(work=tmp_path / "missing", project=tmp_path, max_bytes=4, apply=True)
    assert actions[0]["method"] == "rename"
    assert (tmp_path / "nohup.log.1").stat().st_ino == inode
    assert log.read_bytes() == b""


def test_non_append_writer_is_not_truncated(tmp_path):
    from vacant_network.maintenance import clean
    log = tmp_path / "nohup.log"
    with log.open("wb", buffering=0) as writer:
        writer.write(b"before rotation")
        actions = clean(work=tmp_path / "missing", project=tmp_path, max_bytes=4, apply=True)
        assert actions == [{"action": "skip", "path": str(log), "reason": "non-append writer"}]
        assert not (tmp_path / "nohup.log.1").exists()
        writer.write(b"after rotation")
        assert log.read_bytes() == b"before rotationafter rotation"


@pytest.mark.skipif(os.getuid() == 0, reason="requires non-root permissions")
def test_cleanup_removes_readonly_workspace(tmp_path):
    from vacant_network.maintenance import clean
    work = tmp_path / "work"
    work.mkdir()
    stale = work / "stale"
    stale.mkdir()
    readonly = stale / "readonly"
    readonly.mkdir()
    (readonly / "child").write_text("data")
    readonly.chmod(0o555)
    old(stale)
    try:
        clean(work=work, project=None, age=1, apply=True)
        assert not stale.exists()
    finally:
        if readonly.exists():
            readonly.chmod(0o755)
