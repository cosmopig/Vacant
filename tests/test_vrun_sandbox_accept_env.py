"""驗收環境的兩個明講開關（2026-09-24 BigCodeBench-Hard 建庫實測抓到）：
寫死的 PATH 找不到題目要的函式庫、512 MiB 的 RLIMIT_AS 連 import matplotlib 都炸 ⇒ 連參考解都被拒交。"""
import importlib
import os

from vacant_network.vrun import sandbox


def test_accept_path_default_is_unchanged(monkeypatch):
    monkeypatch.delenv("VACANT_ACCEPT_PATH_PREPEND", raising=False)
    assert sandbox.accept_path() == "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    assert sandbox._clean_env(__import__("pathlib").Path("/w"))["PATH"] == sandbox.accept_path()


def test_accept_path_prepend_goes_first(monkeypatch):
    monkeypatch.setenv("VACANT_ACCEPT_PATH_PREPEND", os.pathsep.join(["/opt/venv/bin", "", "/x/bin"]))
    p = sandbox.accept_path().split(os.pathsep)
    assert p[:2] == ["/opt/venv/bin", "/x/bin"] and p[-1] == "/bin"
    assert sandbox._clean_env(__import__("pathlib").Path("/w"))["PATH"].startswith("/opt/venv/bin:")


def test_memory_default_and_override(monkeypatch):
    try:
        monkeypatch.delenv("VACANT_ACCEPT_MEMORY_MB", raising=False)
        importlib.reload(sandbox)
        assert sandbox.DEFAULT_MEMORY_BYTES == 512 * 1024 * 1024
        monkeypatch.setenv("VACANT_ACCEPT_MEMORY_MB", "2048")
        importlib.reload(sandbox)
        assert sandbox.DEFAULT_MEMORY_BYTES == 2048 * 1024 * 1024
    finally:
        monkeypatch.delenv("VACANT_ACCEPT_MEMORY_MB", raising=False)
        importlib.reload(sandbox)
