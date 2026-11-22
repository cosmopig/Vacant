"""工作區複製／回寫的路徑邊界：描述符逐層開啟，不跟隨目的端連結。"""
from __future__ import annotations

import contextlib
import os
import pathlib
import stat
import uuid

DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


@contextlib.contextmanager
def directory(path: pathlib.Path, create: bool = False):
    path = pathlib.Path(os.path.abspath(path))
    fd = os.open("/", DIR)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, dir_fd=fd)
                except FileExistsError:
                    pass
            nxt = os.open(part, DIR, dir_fd=fd)
            os.close(fd)
            fd = nxt
        yield fd
    finally:
        os.close(fd)


@contextlib.contextmanager
def parent(root: pathlib.Path, rel: str, create: bool = False):
    p = pathlib.PurePath(rel)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError("invalid workspace path")
    with directory(root / p.parent, create) as fd:
        yield fd, p.name


def read(root: pathlib.Path, rel: str) -> bytes:
    with parent(root, rel) as (fd, name):
        f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(f, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("not a regular file")
            return stream.read()


def write(root: pathlib.Path, rel: str, data: bytes, mode: int = 0o644):
    with parent(root, rel, True) as (fd, name):
        try:
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISREG(st.st_mode):
                raise ValueError("destination is not a regular file")
        except FileNotFoundError:
            pass
        tmp = ".vacant-copy-" + uuid.uuid4().hex
        f = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=fd)
        try:
            with os.fdopen(f, "wb") as stream:
                stream.write(data)
            os.replace(tmp, name, src_dir_fd=fd, dst_dir_fd=fd)
        finally:
            try:
                os.unlink(tmp, dir_fd=fd)
            except FileNotFoundError:
                pass


def unlink(root: pathlib.Path, rel: str):
    with parent(root, rel) as (fd, name):
        os.unlink(name, dir_fd=fd)


def entries(root: pathlib.Path, skip: set | frozenset, ignore=None):
    with directory(root) as fd:
        def walk(d, prefix):
            for name in sorted(os.listdir(d)):
                if name in skip:
                    continue
                rel = prefix + name
                if ignore and name in ignore(str(root / pathlib.Path(rel).parent), [name]):
                    continue
                st = os.stat(name, dir_fd=d, follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    child = os.open(name, DIR, dir_fd=d)
                    try:
                        yield rel, st, None
                        yield from walk(child, rel + "/")
                    finally:
                        os.close(child)
                elif stat.S_ISLNK(st.st_mode):
                    yield rel, st, os.readlink(name, dir_fd=d)
                elif stat.S_ISREG(st.st_mode):
                    yield rel, st, None
                else:
                    raise ValueError("unsupported workspace entry")
        yield from walk(fd, "")


def copy_workspace(src: pathlib.Path, dest: pathlib.Path, skip: set | frozenset, ignore=None):
    items = list(entries(src, skip, ignore))
    for rel, st, link in items:
        if link is not None:
            target = pathlib.Path(link)
            if target.is_absolute() or not (src / pathlib.Path(rel).parent / target).resolve().is_relative_to(src.resolve()):
                raise ValueError("workspace symlink escapes root: " + rel)
    with directory(dest.parent, True) as fd:
        os.mkdir(dest.name, dir_fd=fd)
    for rel, st, link in items:
        if stat.S_ISDIR(st.st_mode):
            with directory(dest / rel, True):
                pass
        elif link is not None:
            with parent(dest, rel, True) as (fd, name):
                os.symlink(link, name, dir_fd=fd)
        else:
            write(dest, rel, read(src, rel), stat.S_IMODE(st.st_mode))
    for rel, st, link in items:
        if link is not None and not (dest / rel).resolve().is_relative_to(dest.resolve()):
            unlink(dest, rel)
            raise ValueError("copied symlink escapes root: " + rel)
