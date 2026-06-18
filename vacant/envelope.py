"""L2 Envelope — 每筆 A2A 訊息的簽章信封。架構總規格 §5。

Envelope { v, from, to, seq, prev_hash, ts_ms, kind, body, sig }
  - seq 真正單調（per from→to channel）+ prev_hash → 防 replay / 防亂序（修舊 seq=1 bug）。
  - body 是黑箱：閘道只簽 / 驗 / 記，不解讀 body 語意（§2.2、§10 末）。
  - sig = ed25519(canonical(除 sig 外所有欄位))。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .canonical import canonical_bytes
from .identity import Identity, PublicIdentity

PROTOCOL_VERSION = 1
EMPTY_PREV_HASH = "0" * 64
MAX_BODY_BYTES = 256 * 1024  # production：拒收過大 body（防 DoS/濫用）
_HEX64 = frozenset("0123456789abcdef")

Kind = str  # "call" | "result" | "review"


def _envelope_core(
    v: int, frm: str, to: str, seq: int, prev_hash: str, ts_ms: int, kind: Kind, body: Any
) -> dict[str, Any]:
    return {
        "v": v,
        "from": frm,
        "to": to,
        "seq": seq,
        "prev_hash": prev_hash,
        "ts_ms": ts_ms,
        "kind": kind,
        "body": body,
    }


@dataclass
class Envelope:
    v: int
    frm: str
    to: str
    seq: int
    prev_hash: str
    ts_ms: int
    kind: Kind
    body: Any
    sig: str  # hex

    @classmethod
    def create(
        cls,
        sender: Identity,
        *,
        to: str,
        seq: int,
        prev_hash: str,
        ts_ms: int,
        kind: Kind,
        body: Any,
    ) -> "Envelope":
        core = _envelope_core(
            PROTOCOL_VERSION, sender.vacant_id, to, seq, prev_hash, ts_ms, kind, body
        )
        sig = sender.sign(canonical_bytes(core)).hex()
        return cls(
            v=PROTOCOL_VERSION,
            frm=sender.vacant_id,
            to=to,
            seq=seq,
            prev_hash=prev_hash,
            ts_ms=ts_ms,
            kind=kind,
            body=body,
            sig=sig,
        )

    def _core(self) -> dict[str, Any]:
        return _envelope_core(
            self.v, self.frm, self.to, self.seq, self.prev_hash, self.ts_ms, self.kind, self.body
        )

    def hash(self) -> str:
        return hashlib.sha256(canonical_bytes(self._core())).hexdigest()

    def verify_sig(self, who: PublicIdentity) -> bool:
        if who.vacant_id != self.frm:
            return False
        return who.verify(canonical_bytes(self._core()), bytes.fromhex(self.sig))

    def to_json(self) -> dict[str, Any]:
        d = self._core()
        d["sig"] = self.sig
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Envelope":
        """從不可信來源解析 + **驗證結構**（型別/必填/界線）。壞資料 → ValueError，
        絕不讓畸形輸入往下游崩潰（production 硬化：不可信邊界）。"""
        if not isinstance(d, dict):
            raise ValueError("envelope 必須是物件")
        for k in ("v", "from", "to", "seq", "prev_hash", "ts_ms", "kind", "body", "sig"):
            if k not in d:
                raise ValueError(f"envelope 缺欄位：{k}")
        if not isinstance(d["v"], int) or not isinstance(d["seq"], int) or not isinstance(d["ts_ms"], int):
            raise ValueError("v/seq/ts_ms 必須是整數")
        if d["seq"] < 1:
            raise ValueError("seq 必須 >= 1")
        for k in ("from", "to", "kind", "prev_hash", "sig"):
            if not isinstance(d[k], str):
                raise ValueError(f"{k} 必須是字串")
        ph = d["prev_hash"]
        if len(ph) != 64 or not set(ph.lower()) <= _HEX64:
            raise ValueError("prev_hash 必須是 64 字 hex")
        try:
            bytes.fromhex(d["sig"])
        except ValueError:
            raise ValueError("sig 必須是 hex")
        if len(canonical_bytes(d["body"])) > MAX_BODY_BYTES:
            raise ValueError(f"body 超過上限 {MAX_BODY_BYTES} bytes")
        return cls(
            v=d["v"], frm=d["from"], to=d["to"], seq=d["seq"], prev_hash=ph,
            ts_ms=d["ts_ms"], kind=d["kind"], body=d["body"], sig=d["sig"],
        )


class ReplayError(Exception):
    """seq 未前進或 prev_hash 不接 → 重放 / 亂序攻擊。"""


class ChannelGuard:
    """接收端的 per-sender 重放防護：記住每個 from 的最後 (seq, hash)。

    架構總規格 §10：replay 是 *prevents* 級（協議拒收 + seq 單調）。
    """

    def __init__(self) -> None:
        self._last_seq: dict[str, int] = {}
        self._last_hash: dict[str, str] = {}

    def accept(self, env: Envelope) -> None:
        """通過 → 更新狀態；否則 raise ReplayError。呼叫前須先 verify_sig。"""
        last_seq = self._last_seq.get(env.frm, 0)
        if env.seq <= last_seq:
            raise ReplayError(
                f"seq 未前進：from={env.frm[:12]} seq={env.seq} <= last={last_seq}"
            )
        expected_prev = self._last_hash.get(env.frm, EMPTY_PREV_HASH)
        if env.prev_hash != expected_prev:
            raise ReplayError(
                f"prev_hash 不接：from={env.frm[:12]} got={env.prev_hash[:12]} "
                f"want={expected_prev[:12]}"
            )
        self._last_seq[env.frm] = env.seq
        self._last_hash[env.frm] = env.hash()

    def next_seq(self, to: str) -> tuple[int, str]:
        """送方視角：給某對象的下一個 (seq, prev_hash)。"""
        seq = self._last_seq.get(to, 0) + 1
        prev = self._last_hash.get(to, EMPTY_PREV_HASH)
        return seq, prev

    def record_sent(self, env: Envelope) -> None:
        self._last_seq[env.to] = env.seq
        self._last_hash[env.to] = env.hash()

    # --- 持久化（production：跨程序/重啟仍防 replay）-----------------------
    def to_json(self) -> dict[str, Any]:
        return {"seq": self._last_seq, "hash": self._last_hash}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "ChannelGuard":
        g = cls()
        g._last_seq = {str(k): int(v) for k, v in (d.get("seq") or {}).items()}
        g._last_hash = {str(k): str(v) for k, v in (d.get("hash") or {}).items()}
        return g
