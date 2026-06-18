"""L1 logbook — append-only 簽章事件鏈（hash chain）。架構總規格 §5。

每筆：{ seq, prev_hash, ts_ms, type, payload, sig }
  - seq 真正單調遞增（修掉舊 repo「seq 永遠=1」的 bug，見 vacant_critique_2026-06）。
  - prev_hash 串前一筆的 hash → 任何中間竄改都驗不過（tamper-evident）。
  - sig 覆蓋 canonical(seq, prev_hash, ts_ms, type, payload)。

誰持 pubkey 都能 verify_chain：重算每筆 hash、檢查 seq 連續、prev_hash 對得上、簽章過。
這是究責（detects 竄改）的密碼學基礎。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .atomic import atomic_write_bytes
from .canonical import canonical_bytes
from .identity import Identity, PublicIdentity

# 創世 prev_hash（全零）；對應 EMPTY_PREV_HASH。
EMPTY_PREV_HASH = "0" * 64
# production 硬化：單筆 payload 上限（防失控/濫用塞爆 logbook）。
MAX_PAYLOAD_BYTES = 64 * 1024


def _entry_hash(seq: int, prev_hash: str, ts_ms: int, etype: str, payload: Any) -> str:
    body = canonical_bytes(
        {"seq": seq, "prev_hash": prev_hash, "ts_ms": ts_ms, "type": etype, "payload": payload}
    )
    return hashlib.sha256(body).hexdigest()


def _signed_bytes(seq: int, prev_hash: str, ts_ms: int, etype: str, payload: Any) -> bytes:
    return canonical_bytes(
        {"seq": seq, "prev_hash": prev_hash, "ts_ms": ts_ms, "type": etype, "payload": payload}
    )


@dataclass
class LogEntry:
    seq: int
    prev_hash: str
    ts_ms: int
    type: str
    payload: Any
    sig: str  # hex

    def to_json(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "prev_hash": self.prev_hash,
            "ts_ms": self.ts_ms,
            "type": self.type,
            "payload": self.payload,
            "sig": self.sig,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "LogEntry":
        return cls(
            seq=d["seq"],
            prev_hash=d["prev_hash"],
            ts_ms=d["ts_ms"],
            type=d["type"],
            payload=d["payload"],
            sig=d["sig"],
        )

    def hash(self) -> str:
        return _entry_hash(self.seq, self.prev_hash, self.ts_ms, self.type, self.payload)


class ChainError(Exception):
    """logbook 鏈完整性驗證失敗。"""


class Logbook:
    """記憶體中的鏈 + ndjson 持久化。append 由 Identity 簽。"""

    def __init__(self, entries: list[LogEntry] | None = None) -> None:
        self.entries: list[LogEntry] = entries or []

    # --- 寫 ----------------------------------------------------------------
    def append(self, etype: str, payload: Any, identity: Identity, *, ts_ms: int) -> LogEntry:
        """簽一筆並接上鏈尾。seq = 上一筆 + 1（真正單調）。"""
        if len(canonical_bytes(payload)) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"logbook payload 超過上限 {MAX_PAYLOAD_BYTES} bytes")
        if self.entries:
            last = self.entries[-1]
            seq = last.seq + 1
            prev_hash = last.hash()
        else:
            seq = 1
            prev_hash = EMPTY_PREV_HASH
        sig = identity.sign(_signed_bytes(seq, prev_hash, ts_ms, etype, payload)).hex()
        entry = LogEntry(seq, prev_hash, ts_ms, etype, payload, sig)
        self.entries.append(entry)
        return entry

    # --- 驗 ----------------------------------------------------------------
    def verify_chain(self, who: PublicIdentity) -> bool:
        """完整驗鏈：seq 連續、prev_hash 串對、每筆簽章過。任何竄改都被抓。"""
        prev_hash = EMPTY_PREV_HASH
        expected_seq = 1
        for e in self.entries:
            if e.seq != expected_seq:
                return False
            if e.prev_hash != prev_hash:
                return False
            if not who.verify(
                _signed_bytes(e.seq, e.prev_hash, e.ts_ms, e.type, e.payload),
                bytes.fromhex(e.sig),
            ):
                return False
            prev_hash = e.hash()
            expected_seq += 1
        return True

    # --- 持久化 ------------------------------------------------------------
    def save(self, path: Path) -> None:
        # 原子寫入：崩潰也只會留下舊的或新的完整 ndjson，不會半截壞鏈。
        blob = b"".join(canonical_bytes(e.to_json()) + b"\n" for e in self.entries)
        atomic_write_bytes(path, blob)

    @classmethod
    def load(cls, path: Path) -> "Logbook":
        if not path.exists():
            return cls()
        entries = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    import json

                    entries.append(LogEntry.from_json(json.loads(line)))
        return cls(entries)

    def __len__(self) -> int:
        return len(self.entries)
