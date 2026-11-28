"""Canonical JSON + script hashing for third-party re-run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_obj(obj: Any) -> str:
    return sha256_bytes(canonical_dumps(obj).encode("utf-8"))