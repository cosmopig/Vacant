#!/usr/bin/env python3
"""稽核 HMAC 鍵的延後載入：第一次真正算 HMAC 時才讀本機金鑰檔。"""
from __future__ import annotations
import functools, hashlib, hmac, pathlib


@functools.lru_cache(maxsize=1)
def audit_key() -> bytes:
    return (pathlib.Path.home() / ".config/vacant/audit_hmac.key").read_text().strip().encode()


def audit_hmac(text: str, length: int = 20) -> str:
    return hmac.new(audit_key(), text.encode(), hashlib.sha256).hexdigest()[:length]
