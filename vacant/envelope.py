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


# --- ReviewEnvelope（credit-memory v1 改動3）---------------------------------
#
# review 從「無簽章的 in-process 函式呼叫」升級為簽章物件：reviewer 用自己的
# Identity 簽 canonical {reviewer_id, target_id, target_stream_id, branch_id,
# target_head, task_id, substrate, scores, ts_ms}。
#   - 簽章覆蓋 target_stream_id/branch_id/target_head → 舊 review 簽章搬到新
#     stream / 新 head 必驗失敗（擋簽章搬移，by design）。
#   - demo 期一身一 stream → target_stream_id ≡ 由該 vacant logbook 創世 hash
#     衍生（見 logbook.stream_id()）；vacant_id 仍是信譽索引的 key（改動2 後推）。

_REVIEW_FIELDS = (
    "reviewer_id", "target_id", "target_stream_id", "branch_id",
    "target_head", "task_id", "substrate", "scores", "ts_ms",
)


@dataclass
class ReviewEnvelope:
    reviewer_id: str
    target_id: str          # 被評者 vacant_id（信譽索引 key）
    target_stream_id: str   # 被評 memory stream（創世 hash；空鏈時＝vacant_id）
    branch_id: str
    target_head: str        # 評的是「這個鏈頭為止」的歷史 → head 新鮮性檢查用
    task_id: str
    substrate: str
    scores: dict[str, float]
    ts_ms: int
    sig: str  # hex

    def _core(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in _REVIEW_FIELDS}

    @classmethod
    def create(
        cls,
        reviewer: Identity,
        *,
        target_id: str,
        target_stream_id: str,
        branch_id: str,
        target_head: str,
        task_id: str,
        substrate: str,
        scores: dict[str, float],
        ts_ms: int,
    ) -> "ReviewEnvelope":
        env = cls(
            reviewer_id=reviewer.vacant_id,
            target_id=target_id,
            target_stream_id=target_stream_id,
            branch_id=branch_id,
            target_head=target_head,
            task_id=task_id,
            substrate=substrate,
            scores=dict(scores),
            ts_ms=ts_ms,
            sig="",
        )
        env.sig = reviewer.sign(canonical_bytes(env._core())).hex()
        return env

    def verify_sig(self, who: PublicIdentity) -> bool:
        if who.vacant_id != self.reviewer_id:
            return False
        try:
            raw = bytes.fromhex(self.sig)
        except ValueError:
            return False
        return who.verify(canonical_bytes(self._core()), raw)

    def to_json(self) -> dict[str, Any]:
        d = self._core()
        d["sig"] = self.sig
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "ReviewEnvelope":
        """從不可信來源解析＋驗證結構（型別/必填/界線）。壞資料 → ValueError。"""
        if not isinstance(d, dict):
            raise ValueError("review envelope 必須是物件")
        for k in (*_REVIEW_FIELDS, "sig"):
            if k not in d:
                raise ValueError(f"review envelope 缺欄位：{k}")
        for k in ("reviewer_id", "target_id", "target_stream_id", "branch_id",
                  "target_head", "task_id", "substrate", "sig"):
            if not isinstance(d[k], str):
                raise ValueError(f"{k} 必須是字串")
        if not isinstance(d["ts_ms"], int):
            raise ValueError("ts_ms 必須是整數")
        if not isinstance(d["scores"], dict):
            raise ValueError("scores 必須是物件")
        scores: dict[str, float] = {}
        for dim, v in d["scores"].items():
            if not isinstance(dim, str) or not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ValueError("scores 必須是 {維度: 數值}")
            if not 0.0 <= float(v) <= 1.0:
                raise ValueError(f"score {dim}={v} 超出 [0,1]")
            scores[dim] = float(v)
        return cls(
            reviewer_id=d["reviewer_id"], target_id=d["target_id"],
            target_stream_id=d["target_stream_id"], branch_id=d["branch_id"],
            target_head=d["target_head"], task_id=d["task_id"],
            substrate=d["substrate"], scores=scores, ts_ms=d["ts_ms"], sig=d["sig"],
        )


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
