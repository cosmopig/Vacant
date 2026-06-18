"""Production 硬化：原子寫入 + 跨程序檔案鎖。

- atomic_write_*：寫入暫存檔 → fsync → os.replace（同檔系統上的原子 rename）。
  保證任何時刻檔案要嘛是舊的完整內容、要嘛是新的完整內容，**不會半截**（防崩潰中斷）。
- file_lock：POSIX flock 諮詢鎖（序列化同一 vacant 身體的 load→改→persist），
  在無 fcntl 的平台（如 Windows）優雅退化為 no-op（並非保證，記於 README）。
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Iterator

try:
    import fcntl  # POSIX only
    _HAVE_FCNTL = True
except ImportError:  # pragma: no cover - Windows
    _HAVE_FCNTL = False


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic on same filesystem
    finally:
        with contextlib.suppress(FileNotFoundError):
            if tmp.exists():
                tmp.unlink()


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


@contextlib.contextmanager
def file_lock(lock_path: Path, *, timeout: float = 10.0) -> Iterator[None]:
    """諮詢式排他鎖（同一 vacant 身體的並發保護）。timeout 內取不到 → TimeoutError。"""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if not _HAVE_FCNTL:
        # 無 fcntl 平台：盡力而為（不保證），交由上層序列化（規格 §4.4）
        yield
        return
    import time as _t
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    deadline = None
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if deadline is None:
                    # 用 monotonic-ish busy wait（環境禁 Date.now 僅限 workflow，本地 time 可用）
                    deadline = _t.time() + timeout
                if _t.time() >= deadline:
                    raise TimeoutError(f"取鎖逾時：{lock_path}")
                _t.sleep(0.05)
        yield
    finally:
        with contextlib.suppress(Exception):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
