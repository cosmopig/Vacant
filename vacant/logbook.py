"""L1 logbook — append-only 簽章事件鏈（hash chain）。架構總規格 §5 ＋ credit-memory v1 改動1。

每筆：{ stream_id, branch_id, seq, prev_hash, ts_ms, type, payload, sig }
  - seq 真正單調遞增（修掉舊 repo「seq 永遠=1」的 bug，見 vacant_critique_2026-06）。
  - prev_hash 串前一筆的 hash → 任何中間竄改都驗不過（tamper-evident）。
  - sig 覆蓋 canonical(stream_id, branch_id, seq, prev_hash, ts_ms, type, payload)。
  - stream_id ＝ 創世事件（seq=1）的 hash（keypair 的衍生物，不是新身份原語）；
    創世事件本身尚無 hash 可引用，其 stream_id 欄位為全零 sentinel。
  - branch_id 預設 "main"；fork 時用後綴（credit-memory v1 §2 改動1）。

誰持 pubkey 都能 verify_chain：重算每筆 hash、檢查 seq 連續、prev_hash 對得上、
stream_id/branch_id 一致、簽章過。這是究責（detects 竄改）的密碼學基礎。

wire-format 與 2026-06 版不相容（簽章涵蓋欄位變了）；舊 ndjson 須重生。
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
# 創世事件的 stream_id 佔位：stream_id＝創世事件自身的 hash，簽創世時尚不存在。
GENESIS_STREAM_ID = "0" * 64
BRANCH_MAIN = "main"
# production 硬化：單筆 payload 上限（防失控/濫用塞爆 logbook）。
MAX_PAYLOAD_BYTES = 64 * 1024


def _core(
    stream_id: str, branch_id: str, seq: int, prev_hash: str, ts_ms: int, etype: str, payload: Any
) -> dict[str, Any]:
    return {
        "stream_id": stream_id,
        "branch_id": branch_id,
        "seq": seq,
        "prev_hash": prev_hash,
        "ts_ms": ts_ms,
        "type": etype,
        "payload": payload,
    }


def _entry_hash(
    stream_id: str, branch_id: str, seq: int, prev_hash: str, ts_ms: int, etype: str, payload: Any
) -> str:
    return hashlib.sha256(
        canonical_bytes(_core(stream_id, branch_id, seq, prev_hash, ts_ms, etype, payload))
    ).hexdigest()


def _signed_bytes(
    stream_id: str, branch_id: str, seq: int, prev_hash: str, ts_ms: int, etype: str, payload: Any
) -> bytes:
    return canonical_bytes(_core(stream_id, branch_id, seq, prev_hash, ts_ms, etype, payload))


@dataclass
class LogEntry:
    stream_id: str
    branch_id: str
    seq: int
    prev_hash: str
    ts_ms: int
    type: str
    payload: Any
    sig: str  # hex

    def to_json(self) -> dict[str, Any]:
        d = _core(
            self.stream_id, self.branch_id, self.seq, self.prev_hash,
            self.ts_ms, self.type, self.payload,
        )
        d["sig"] = self.sig
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "LogEntry":
        try:
            return cls(
                stream_id=d["stream_id"],
                branch_id=d["branch_id"],
                seq=d["seq"],
                prev_hash=d["prev_hash"],
                ts_ms=d["ts_ms"],
                type=d["type"],
                payload=d["payload"],
                sig=d["sig"],
            )
        except KeyError as e:
            raise ValueError(
                f"logbook entry 缺欄位 {e}（2026-07 wire-format：舊版 ndjson 須重生）"
            ) from e

    def hash(self) -> str:
        return _entry_hash(
            self.stream_id, self.branch_id, self.seq, self.prev_hash,
            self.ts_ms, self.type, self.payload,
        )


class ChainError(Exception):
    """logbook 鏈完整性驗證失敗。"""


class Logbook:
    """記憶體中的鏈 + ndjson 持久化。append 由 Identity 簽。"""

    def __init__(self, entries: list[LogEntry] | None = None) -> None:
        self.entries: list[LogEntry] = entries or []

    # --- 身份 / 鏈頭 ---------------------------------------------------------
    def stream_id(self) -> str | None:
        """stream 身份 ＝ 創世事件的 hash。空鏈（尚無創世）→ None。"""
        return self.entries[0].hash() if self.entries else None

    def branch_id(self) -> str:
        return self.entries[0].branch_id if self.entries else BRANCH_MAIN

    def head(self) -> str:
        """當前鏈頭 hash；空鏈回 EMPTY_PREV_HASH sentinel（credit-memory v1 改動1）。"""
        return self.entries[-1].hash() if self.entries else EMPTY_PREV_HASH

    # --- 寫 ----------------------------------------------------------------
    def append(
        self, etype: str, payload: Any, identity: Identity, *, ts_ms: int,
        branch_id: str = BRANCH_MAIN,
    ) -> LogEntry:
        """簽一筆並接上鏈尾。seq = 上一筆 + 1（真正單調）。"""
        if len(canonical_bytes(payload)) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"logbook payload 超過上限 {MAX_PAYLOAD_BYTES} bytes")
        if self.entries:
            last = self.entries[-1]
            seq = last.seq + 1
            prev_hash = last.hash()
            stream_id = self.entries[0].hash()
            branch_id = self.entries[0].branch_id  # 單一鏈內 branch 一致；fork 是另一條鏈
        else:
            seq = 1
            prev_hash = EMPTY_PREV_HASH
            stream_id = GENESIS_STREAM_ID
        sig = identity.sign(
            _signed_bytes(stream_id, branch_id, seq, prev_hash, ts_ms, etype, payload)
        ).hex()
        entry = LogEntry(stream_id, branch_id, seq, prev_hash, ts_ms, etype, payload, sig)
        self.entries.append(entry)
        return entry

    # --- 驗 ----------------------------------------------------------------
    def verify_chain(self, who: PublicIdentity) -> bool:
        """完整驗鏈：seq 連續、prev_hash 串對、stream/branch 一致、每筆簽章過。"""
        if not self.entries:
            return True
        genesis = self.entries[0]
        if genesis.stream_id != GENESIS_STREAM_ID:
            return False
        expected_stream = genesis.hash()
        expected_branch = genesis.branch_id
        prev_hash = EMPTY_PREV_HASH
        expected_seq = 1
        for e in self.entries:
            if e.seq != expected_seq:
                return False
            if e.prev_hash != prev_hash:
                return False
            if e.seq > 1 and (e.stream_id != expected_stream or e.branch_id != expected_branch):
                return False
            if not who.verify(
                _signed_bytes(
                    e.stream_id, e.branch_id, e.seq, e.prev_hash, e.ts_ms, e.type, e.payload
                ),
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
