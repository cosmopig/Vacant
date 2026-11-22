"""Canonical manifest index and aggregate size cache."""
import re
from checks import integer, snapshot


def normalize(path):
    if not isinstance(path, str):
        raise ValueError("unsafe path")
    path = path.replace(chr(92), "/")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise ValueError("unsafe path")
    parts = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise ValueError("unsafe path")
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        raise ValueError("unsafe path")
    return "/".join(parts)


class Manifest:
    def __init__(self):
        self._entries = {}
        self._total = None

    def add(self, path, size, digest):
        path = normalize(path)
        size = integer(size, "size")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            raise ValueError("invalid digest")
        entry = {"path":path, "size":size, "digest":digest.lower()}
        existing = self._entries.get(path)
        if existing is not None:
            if existing != entry:
                raise ValueError("path conflict")
            return
        self._entries[path] = entry
        self._total = None

    def remove(self, path):
        path = normalize(path)
        if path not in self._entries:
            raise KeyError(path)
        del self._entries[path]
        self._total = None

    def entries(self):
        return snapshot([self._entries[path] for path in sorted(self._entries)])

    def total_size(self):
        if self._total is None:
            self._total = sum(row["size"] for row in self._entries.values())
        return self._total

    def count(self):
        return len(self._entries)
