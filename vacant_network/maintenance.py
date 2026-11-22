"""磁碟維護：只處理明確根目錄的舊工作區、快取與 nohup.log（預設預覽）。"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import stat
import time

from .adapters.workspace import DIR, directory
from .intake.statepaths import work_dir


def _active() -> list[pathlib.Path]:
    paths = [pathlib.Path.cwd()]
    proc = pathlib.Path("/proc")
    if not proc.is_dir():
        raise OSError("cannot inspect active processes on this platform")
    for p in proc.iterdir():
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid != os.getuid():
                continue
            paths.append(pathlib.Path(os.readlink(p / "cwd")))
            for f in (p / "fd").iterdir():
                try:
                    paths.append(pathlib.Path(os.readlink(f)))
                except FileNotFoundError:
                    pass
        except (FileNotFoundError, ProcessLookupError):
            pass
    return paths


def _latest(fd: int) -> float:
    newest = os.fstat(fd).st_mtime
    for name in os.listdir(fd):
        st = os.stat(name, dir_fd=fd, follow_symlinks=False)
        newest = max(newest, st.st_mtime)
        if stat.S_ISDIR(st.st_mode):
            sub = os.open(name, DIR, dir_fd=fd)
            try:
                newest = max(newest, _latest(sub))
            finally:
                os.close(sub)
    return newest


def clean(*, work: pathlib.Path, project: pathlib.Path | None, age: float = 7 * 86400,
          max_bytes: int = 10 * 1024 * 1024, keep: int = 3, apply: bool = False) -> list[dict]:
    if age < 0 or max_bytes < 1 or keep < 1:
        raise ValueError("age >= 0, max_bytes >= 1, keep >= 1 required")
    active = _active()
    cutoff = time.time() - age
    actions = []

    def busy(path):
        return any(p == path or p.is_relative_to(path) for p in active if p.is_absolute())

    def visit(root, fd, prefix="", caches=False):
        for name in os.listdir(fd):
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISDIR(st.st_mode):
                continue
            rel = prefix + name
            child = os.open(name, DIR, dir_fd=fd)
            try:
                selected = not caches or name in {".pytest_cache", "__pycache__"}
                if selected:
                    if _latest(child) < cutoff and not busy(root / rel):
                        actions.append({"action": "remove", "path": str(root / rel)})
                        if apply:
                            now = os.stat(name, dir_fd=fd, follow_symlinks=False)
                            if (now.st_ino, now.st_dev) != (st.st_ino, st.st_dev):
                                raise OSError("cleanup target changed")
                            if not shutil.rmtree.avoids_symlink_attacks:
                                raise OSError("safe rmtree unavailable")
                            shutil.rmtree(name, dir_fd=fd)
                elif name not in {".git", ".venv", "node_modules", "vacant_hm"}:
                    visit(root, child, rel + "/", True)
            finally:
                os.close(child)

    for root, caches in ((work, False), (project, True)):
        if root is None:
            continue
        root = pathlib.Path(os.path.abspath(root))
        if root == pathlib.Path("/") or root == pathlib.Path.home():
            raise ValueError("refusing broad cleanup root")
        try:
            with directory(root) as fd:
                visit(root, fd, caches=caches)
                if not caches:
                    continue
                try:
                    st = os.stat("nohup.log", dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if not stat.S_ISREG(st.st_mode) or st.st_mtime >= cutoff or st.st_size < max_bytes or busy(root / "nohup.log"):
                    continue
                slots = ["nohup.log"] + [f"nohup.log.{i}" for i in range(1, keep + 1)]
                blocked = False
                for name in slots:
                    try:
                        slot = os.stat(name, dir_fd=fd, follow_symlinks=False)
                        if not stat.S_ISREG(slot.st_mode):
                            raise ValueError("log rotation target is not a regular file")
                        blocked = blocked or slot.st_mtime >= cutoff or busy(root / name)
                    except FileNotFoundError:
                        pass
                if blocked:
                    continue
                actions.append({"action": "rotate", "path": str(root / "nohup.log")})
                if apply:
                    for i in range(keep, 0, -1):
                        try:
                            os.replace(slots[i - 1], slots[i], src_dir_fd=fd, dst_dir_fd=fd)
                        except FileNotFoundError:
                            pass
                    log = os.open("nohup.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                  stat.S_IMODE(st.st_mode), dir_fd=fd)
                    os.close(log)
        except FileNotFoundError:
            continue
    return actions


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=pathlib.Path)
    parser.add_argument("--age-days", type=float, default=7)
    parser.add_argument("--max-bytes", type=int, default=10 * 1024 * 1024)
    parser.add_argument("--keep", type=int, default=3)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(clean(work=work_dir(), project=args.project, age=args.age_days * 86400,
                               max_bytes=args.max_bytes, keep=args.keep, apply=args.apply), ensure_ascii=False))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"cleanup refused: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
