"""Shared, wire-stable core types.

These are the contract every downstream component (P1-P7) imports. They are
deliberately small and frozen-where-possible so that signatures, hash chains,
and equality semantics are unambiguous.

Cross-cutting design notes:

* All cryptographic payloads are hashed/signed over a *canonical byte
  encoding* defined here (not Pydantic's JSON output), so re-serialisation
  through different Pydantic versions cannot break verification.
* `Logbook` is the only mutable type — append-only via `.append()`.
* `verify_*` methods return `bool` and never raise on a benign mismatch;
  callers that want exceptions on failure can wrap with `assert` or use the
  `verify_or_raise` helper from `vacant.core.crypto`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vacant.core.constants import (
    DEFAULT_HALO_VERSION,
    ED25519_PUBLIC_KEY_BYTES,
    HASH_DIGEST_BYTES,
)
from vacant.core.crypto import (
    SigningKey,
    VerifyKey,
    hash_blake2b,
    pubkey_from_bytes,
    sign,
    verify,
)
from vacant.core.errors import HashChainError, TypeIntegrityError

__all__ = [
    "EMPTY_PREV_HASH",
    "BehaviorBundle",
    "CapabilityCard",
    "LogEntry",
    "Logbook",
    "ResidentForm",
    "SubstrateSpec",
    "VacantId",
    "VacantState",
]


EMPTY_PREV_HASH: bytes = b"\x00" * HASH_DIGEST_BYTES
"""Sentinel `prev_hash` used by the genesis (first) `LogEntry`."""


def _canonical_json(payload: dict[str, Any]) -> bytes:
    """Stable JSON encoding for hashing. Sorted keys, no whitespace."""
    try:
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TypeIntegrityError(f"LogEntry.payload must be JSON-serialisable: {exc}") from exc


def _utc_iso(ts: datetime) -> str:
    """ISO-8601 in UTC with explicit offset; deterministic for hashing."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    else:
        ts = ts.astimezone(UTC)
    return ts.isoformat()


# --- Identity -----------------------------------------------------------------


class VacantId(BaseModel):
    """Numerical-sameness identity (Ricoeur idem). Wraps an Ed25519 pubkey."""

    model_config = ConfigDict(frozen=True)

    pubkey_bytes: bytes = Field(
        ..., min_length=ED25519_PUBLIC_KEY_BYTES, max_length=ED25519_PUBLIC_KEY_BYTES
    )

    @classmethod
    def from_verify_key(cls, vk: VerifyKey) -> VacantId:
        return cls(pubkey_bytes=bytes(vk))

    def verify_key(self) -> VerifyKey:
        return pubkey_from_bytes(self.pubkey_bytes)

    def hex(self) -> str:
        return self.pubkey_bytes.hex()

    def short(self) -> str:
        """First 12 hex chars — for log lines / dashboards."""
        return self.hex()[:12]

    def __str__(self) -> str:
        return f"vacant:{self.short()}"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, VacantId) and self.pubkey_bytes == other.pubkey_bytes

    def __hash__(self) -> int:
        return hash(self.pubkey_bytes)


# --- Logbook ------------------------------------------------------------------


class LogEntry(BaseModel):
    """A single signed line in a vacant's logbook (Ricoeur ipse)."""

    model_config = ConfigDict(frozen=True)

    kind: str
    ts: datetime
    payload: dict[str, Any]
    prev_hash: bytes = Field(..., min_length=HASH_DIGEST_BYTES, max_length=HASH_DIGEST_BYTES)
    signature: bytes

    @field_validator("kind")
    @classmethod
    def _kind_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("LogEntry.kind must be non-empty")
        return v

    def signing_payload(self) -> bytes:
        """The exact byte-string that gets signed *and* hashed.

        Includes `kind | ts | payload | prev_hash` — but not `signature`,
        because `signature` is the output of signing this payload.
        """
        parts = [
            self.kind.encode("utf-8"),
            _utc_iso(self.ts).encode("utf-8"),
            _canonical_json(self.payload),
            self.prev_hash,
        ]
        return b"\x1f".join(parts)

    def compute_hash(self) -> bytes:
        """BLAKE2b-256 over `signing_payload()`. Used as the next entry's `prev_hash`."""
        return hash_blake2b(self.signing_payload())

    def verify(self, pubkey: VerifyKey) -> bool:
        """True iff `signature` is a valid Ed25519 sig over `signing_payload()`."""
        return verify(pubkey, self.signing_payload(), self.signature)


class Logbook(BaseModel):
    """Append-only signed history of a vacant's outward behaviour."""

    model_config = ConfigDict(arbitrary_types_allowed=False)

    entries: list[LogEntry] = Field(default_factory=list)

    def latest_hash(self) -> bytes:
        """Hash of the last entry, or `EMPTY_PREV_HASH` if the logbook is empty."""
        if not self.entries:
            return EMPTY_PREV_HASH
        return self.entries[-1].compute_hash()

    def append(
        self,
        kind: str,
        payload: dict[str, Any],
        signing_key: SigningKey,
        ts: datetime | None = None,
    ) -> LogEntry:
        """Build, sign, and append a new entry. Returns the new entry."""
        entry_ts = (ts or datetime.now(UTC)).astimezone(UTC)
        prev = self.latest_hash()
        unsigned = LogEntry(
            kind=kind,
            ts=entry_ts,
            payload=payload,
            prev_hash=prev,
            signature=b"\x00",  # placeholder, replaced below
        )
        sig = sign(signing_key, unsigned.signing_payload())
        signed = unsigned.model_copy(update={"signature": sig})
        self.entries.append(signed)
        return signed

    def verify_chain(self, pubkey: VerifyKey) -> bool:
        """True iff every entry's signature verifies and the prev_hash chain is intact."""
        expected_prev = EMPTY_PREV_HASH
        for entry in self.entries:
            if entry.prev_hash != expected_prev:
                return False
            if not entry.verify(pubkey):
                return False
            expected_prev = entry.compute_hash()
        return True

    def verify_chain_or_raise(self, pubkey: VerifyKey) -> None:
        """Like `verify_chain` but raises `HashChainError` on the first break."""
        expected_prev = EMPTY_PREV_HASH
        for i, entry in enumerate(self.entries):
            if entry.prev_hash != expected_prev:
                raise HashChainError(
                    f"Logbook entry {i} prev_hash mismatch: "
                    f"expected {expected_prev.hex()}, got {entry.prev_hash.hex()}"
                )
            if not entry.verify(pubkey):
                raise HashChainError(f"Logbook entry {i} signature invalid")
            expected_prev = entry.compute_hash()


# --- Substrate / Behavior / Capability ---------------------------------------


class SubstrateSpec(BaseModel):
    """Multi-substrate declaration (THEORY_V5 §2)."""

    model_config = ConfigDict(frozen=True)

    allowed_substrates: list[str] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=dict)

    @field_validator("allowed_substrates")
    @classmethod
    def _no_blank_substrates(cls, v: list[str]) -> list[str]:
        for s in v:
            if not s or not s.strip():
                raise ValueError("allowed_substrates must not contain blank strings")
        return v

    def canonical_bytes(self) -> bytes:
        return _canonical_json(
            {
                "allowed_substrates": list(self.allowed_substrates),
                "policy": self.policy,
            }
        )


class BehaviorBundle(BaseModel):
    """System prompt + policy DSL + tool whitelist (Ricoeur character)."""

    model_config = ConfigDict(frozen=True)

    system_prompt: str
    policy_dsl: str = ""
    tool_whitelist: list[str] = Field(default_factory=list)
    bundle_hash: bytes = Field(default=b"")

    @model_validator(mode="after")
    def _ensure_hash(self) -> Self:
        computed = self._compute_bundle_hash()
        if not self.bundle_hash:
            object.__setattr__(self, "bundle_hash", computed)
        elif self.bundle_hash != computed:
            raise TypeIntegrityError("BehaviorBundle.bundle_hash does not match content")
        return self

    def _compute_bundle_hash(self) -> bytes:
        body = _canonical_json(
            {
                "system_prompt": self.system_prompt,
                "policy_dsl": self.policy_dsl,
                "tool_whitelist": sorted(self.tool_whitelist),
            }
        )
        return hash_blake2b(body)


class CapabilityCard(BaseModel):
    """The `halo` — public capability announcement (THEORY_V5 §7.1)."""

    model_config = ConfigDict(frozen=True)

    vacant_id: VacantId
    capability_text: str
    substrate_spec: SubstrateSpec
    halo_version: int = DEFAULT_HALO_VERSION
    endpoint: str | None = None
    """A2A endpoint URL for direct calls. None for LOCAL or yet-to-be-deployed
    vacants. P6 dispatch reads this field to POST envelopes directly. The
    endpoint is part of the signing payload so it can't be substituted post-
    issuance (D009 §A)."""
    signature: bytes = b""

    @field_validator("halo_version")
    @classmethod
    def _halo_version_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("halo_version must be >= 1")
        return v

    def signing_payload(self) -> bytes:
        parts = [
            self.vacant_id.pubkey_bytes,
            self.capability_text.encode("utf-8"),
            self.substrate_spec.canonical_bytes(),
            self.halo_version.to_bytes(8, "big"),
            (self.endpoint or "").encode("utf-8"),
        ]
        return b"\x1f".join(parts)

    def signed(self, signing_key: SigningKey) -> CapabilityCard:
        """Return a copy with `signature` filled in by `signing_key`."""
        sig = sign(signing_key, self.signing_payload())
        return self.model_copy(update={"signature": sig})

    def verify(self) -> bool:
        if not self.signature:
            return False
        return verify(self.vacant_id.verify_key(), self.signing_payload(), self.signature)


# --- State machine + composite form ------------------------------------------


class VacantState(StrEnum):
    """5-state lifecycle plus the LOCAL visibility flag (CLAUDE.md §LOCAL)."""

    LOCAL = "LOCAL"
    ACTIVE = "ACTIVE"
    HIBERNATING = "HIBERNATING"
    STALE = "STALE"
    SUNK = "SUNK"
    ARCHIVED = "ARCHIVED"


class ResidentForm(BaseModel):
    """The full 6-component vacant. Only `runtime_state` is mutable in P0."""

    model_config = ConfigDict(arbitrary_types_allowed=False)

    identity: VacantId
    logbook: Logbook
    behavior_bundle: BehaviorBundle
    substrate_spec: SubstrateSpec
    runtime_state: VacantState = VacantState.LOCAL
    capability_card: CapabilityCard | None = None
    parent_id: VacantId | None = None
    """Lineage anchor (THEORY_V5 §4.3). None for root / Path-Zero vacants.
    Secondary parents (D4 lineage-merge) live in the BIRTH log entry payload —
    see D003 ADR."""

    def verify_self(self) -> bool:
        """Cross-component integrity check."""
        pubkey = self.identity.verify_key()
        if not self.logbook.verify_chain(pubkey):
            return False
        card = self.capability_card
        if card is not None:
            if card.vacant_id != self.identity:
                return False
            if not card.verify():
                return False
        return True
