"""`VacantEnvelope` — A2A-compatible message wrapper with per-pair chain.

Each envelope carries:

- `from_vacant_id` / `to_vacant_id`: the call's endpoints (Ed25519 ids).
- `sequence_no`: per-pair monotonic counter starting at 1.
- `timestamp`: UTC datetime of issuance.
- `prev_envelope_hash`: SHA-equivalent (BLAKE2b) of the prior envelope on
  this `(from, to)` pair. The first envelope on a pair uses
  `EMPTY_PREV_HASH` (32 zero bytes).
- `payload`: an `A2AMessage` carrying the actual request/response.
- `signature`: Ed25519 signature over `signing_payload()`.

The chain is **per-pair** (D009 §B): unlike P0 logbooks (per-vacant) or
P4 events (global), the envelope chain links call-level interactions
between two specific vacants, used by replay protection.

A2A wire format: `to_a2a_jsonrpc(envelope)` produces a JSON-RPC 2.0
`message/send` request whose `params.message.metadata["urn:vacant:v1"]`
carries the envelope's signature, sequence_no, prev_hash, and
caller/callee ids; `from_a2a_jsonrpc(payload)` parses + verifies in
the reverse direction.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vacant.core.constants import (
    A2A_VACANT_METADATA_KEY,
    HASH_DIGEST_BYTES,
)
from vacant.core.crypto import SigningKey, VerifyKey, hash_blake2b, sign, verify
from vacant.core.types import EMPTY_PREV_HASH, VacantId
from vacant.protocol.errors import (
    EnvelopeFormatError,
    EnvelopeSignatureError,
)

__all__ = [
    "A2A_VACANT_METADATA_KEY",
    "A2AMessage",
    "A2APart",
    "SelfEval",
    "VacantEnvelope",
    "from_a2a_jsonrpc",
    "to_a2a_jsonrpc",
]


# --- A2A payload shape ------------------------------------------------------


class A2APart(BaseModel):
    """A single part inside an A2A `message/send` payload.

    For MVP we ship `text` parts only (D009 §F); image/audio/file parts
    are reserved field-shape-wise but not implemented.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["text"] = "text"
    text: str = ""

    def canonical_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text}


class SelfEval(BaseModel):
    """The responder vacant's own 5D self-assessment + scalar confidence.

    technical.html §Layer 1: "Every response includes 5D self-assessment
    + confidence". Carried as structured metadata on the response
    envelope so the reputation aggregator can compute the self/peer gap
    (`record_self_eval_gap` → honesty dim) without a separate round-trip.

    Each dim is in `[0, 1]`. `confidence` is the responder's own scalar
    "how sure am I this answer is correct" in the same range. Both are
    signed by the responder when the envelope is signed (they live in
    the same canonical-JSON `signing_dict`).
    """

    model_config = ConfigDict(frozen=True)

    factual: float = Field(default=0.5, ge=0.0, le=1.0)
    logical: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    honesty: float = Field(default=0.5, ge=0.0, le=1.0)
    adoption: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "factual": float(self.factual),
            "logical": float(self.logical),
            "relevance": float(self.relevance),
            "honesty": float(self.honesty),
            "adoption": float(self.adoption),
            "confidence": float(self.confidence),
        }

    def dims_dict(self) -> dict[str, float]:
        """Just the 5 reputation dims (drops `confidence`).

        Suitable for passing to `Aggregator.record_self_eval_gap`'s
        `self_scores=` argument.
        """
        return {
            "factual": float(self.factual),
            "logical": float(self.logical),
            "relevance": float(self.relevance),
            "honesty": float(self.honesty),
            "adoption": float(self.adoption),
        }


class A2AMessage(BaseModel):
    """A2A `message/send` payload (extracted shape, MVP subset)."""

    model_config = ConfigDict(frozen=True)

    role: Literal["ROLE_USER", "ROLE_AGENT", "ROLE_TOOL"] = "ROLE_USER"
    parts: list[A2APart] = Field(default_factory=list)
    context_id: str | None = None
    message_id: str | None = None
    self_eval: SelfEval | None = None
    """Optional 5D self-assessment + confidence (technical.html §Layer 1).
    Present on responder-side messages; the request-side message typically
    leaves it None. When present, it's part of the canonical signing
    payload so the responder commits cryptographically to their own
    self-assessment — a self-eval cannot be retroactively edited."""

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "parts": [p.canonical_dict() for p in self.parts],
            "contextId": self.context_id,
            "messageId": self.message_id,
            "selfEval": self.self_eval.canonical_dict() if self.self_eval else None,
        }


# --- Envelope ---------------------------------------------------------------


def _utc_iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC).isoformat()


def _canonical_json(obj: dict[str, Any]) -> bytes:
    """Sorted, tight-separator JSON. Matches P0 logbook canonicalisation
    for cross-component consistency (D006 §F)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


class VacantEnvelope(BaseModel):
    """A signed A2A message exchanged directly between two vacants."""

    model_config = ConfigDict(frozen=True)

    from_vacant_id: VacantId
    to_vacant_id: VacantId
    sequence_no: int
    timestamp: datetime
    prev_envelope_hash: bytes = Field(
        default=EMPTY_PREV_HASH,
        min_length=HASH_DIGEST_BYTES,
        max_length=HASH_DIGEST_BYTES,
    )
    payload: A2AMessage
    idempotency_key: str = ""
    signature: bytes = b""

    @field_validator("sequence_no")
    @classmethod
    def _seq_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"sequence_no must be >= 1; got {v}")
        return v

    def signing_dict(self) -> dict[str, Any]:
        """Canonical dict over which the envelope is signed and hashed.

        Excludes `signature` (the field being computed) but includes
        every other field — including `prev_envelope_hash` and
        `sequence_no` so an attacker can't change either after issuance.
        """
        return {
            "from": self.from_vacant_id.hex(),
            "to": self.to_vacant_id.hex(),
            "seq": self.sequence_no,
            "ts": _utc_iso(self.timestamp),
            "prev": self.prev_envelope_hash.hex(),
            "idem": self.idempotency_key,
            "payload": self.payload.canonical_dict(),
        }

    def signing_payload(self) -> bytes:
        return _canonical_json(self.signing_dict())

    def compute_hash(self) -> bytes:
        """BLAKE2b of `signing_payload()` — used as the next envelope's
        `prev_envelope_hash` on this pair."""
        return hash_blake2b(self.signing_payload())

    def signed(self, signing_key: SigningKey) -> VacantEnvelope:
        """Return a copy with `signature` produced by `signing_key`.

        The caller is responsible for ensuring `signing_key` corresponds
        to `from_vacant_id`'s pubkey; the envelope's `verify(pubkey)`
        re-checks at the receiving end.
        """
        sig = sign(signing_key, self.signing_payload())
        return self.model_copy(update={"signature": sig})

    def verify(self, pubkey: VerifyKey) -> bool:
        """True iff `signature` is a valid Ed25519 sig over
        `signing_payload()` for `pubkey`."""
        if not self.signature:
            return False
        return verify(pubkey, self.signing_payload(), self.signature)

    def verify_or_raise(self, pubkey: VerifyKey) -> None:
        if not self.verify(pubkey):
            raise EnvelopeSignatureError(
                f"envelope signature did not verify for sender {self.from_vacant_id.short()}"
            )


# --- A2A JSON-RPC wire format -----------------------------------------------


def to_a2a_jsonrpc(env: VacantEnvelope) -> dict[str, Any]:
    """Encode `env` as an A2A JSON-RPC 2.0 `message/send` request.

    The Vacant-specific fields (caller_signature, sequence_no, prev_hash,
    idempotency_key) are mounted under
    `params.message.metadata[A2A_VACANT_METADATA_KEY]` per P6 §3.2.

    When `env.payload.self_eval` is set (responder's 5D self-assessment
    + confidence, technical.html §Layer 1), it's serialised as
    `params.message.selfEval`. Because `self_eval` is in the canonical
    `signing_dict`, the responder's Ed25519 signature already commits to
    these scores — a verifier doesn't need a second signature pass.
    """
    msg: dict[str, Any] = {
        "role": env.payload.role,
        "parts": [p.canonical_dict() for p in env.payload.parts],
        "contextId": env.payload.context_id,
        "messageId": env.payload.message_id,
        "metadata": {
            A2A_VACANT_METADATA_KEY: {
                "from_vacant_id": env.from_vacant_id.hex(),
                "to_vacant_id": env.to_vacant_id.hex(),
                "sequence_no": env.sequence_no,
                "timestamp": _utc_iso(env.timestamp),
                "prev_envelope_hash": env.prev_envelope_hash.hex(),
                "idempotency_key": env.idempotency_key,
                "caller_signature": env.signature.hex(),
            },
        },
    }
    if env.payload.self_eval is not None:
        msg["selfEval"] = env.payload.self_eval.canonical_dict()
    return {
        "jsonrpc": "2.0",
        "id": env.idempotency_key or env.compute_hash().hex(),
        "method": "message/send",
        "params": {"message": msg},
    }


def from_a2a_jsonrpc(body: dict[str, Any]) -> VacantEnvelope:
    """Parse an A2A JSON-RPC body into a `VacantEnvelope`.

    Raises `EnvelopeFormatError` on missing/invalid fields. Does *not*
    verify the signature — callers should call `verify_or_raise` on the
    returned envelope.
    """
    try:
        msg = body["params"]["message"]
        meta = msg["metadata"][A2A_VACANT_METADATA_KEY]
    except KeyError as exc:
        raise EnvelopeFormatError(f"missing field: {exc}") from exc

    try:
        from_id = VacantId(pubkey_bytes=bytes.fromhex(meta["from_vacant_id"]))
        to_id = VacantId(pubkey_bytes=bytes.fromhex(meta["to_vacant_id"]))
        prev = bytes.fromhex(meta["prev_envelope_hash"])
        sig = bytes.fromhex(meta["caller_signature"])
        ts = datetime.fromisoformat(meta["timestamp"])
        seq = int(meta["sequence_no"])
        idem = str(meta.get("idempotency_key", ""))
    except (ValueError, KeyError, TypeError) as exc:
        raise EnvelopeFormatError(f"invalid metadata: {exc}") from exc

    parts = [A2APart(**p) for p in msg.get("parts", [])]
    self_eval_obj: SelfEval | None = None
    raw_self_eval = msg.get("selfEval")
    if raw_self_eval is not None:
        try:
            self_eval_obj = SelfEval(**raw_self_eval)
        except (TypeError, ValueError) as exc:
            raise EnvelopeFormatError(f"invalid selfEval: {exc}") from exc
    payload = A2AMessage(
        role=msg.get("role", "ROLE_USER"),
        parts=parts,
        context_id=msg.get("contextId"),
        message_id=msg.get("messageId"),
        self_eval=self_eval_obj,
    )

    return VacantEnvelope(
        from_vacant_id=from_id,
        to_vacant_id=to_id,
        sequence_no=seq,
        timestamp=ts,
        prev_envelope_hash=prev,
        payload=payload,
        idempotency_key=idem,
        signature=sig,
    )
