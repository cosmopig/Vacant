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
    """Numerical-sameness identity (Ricoeur *idem*) — wraps an Ed25519 pubkey.

    A `VacantId` is the *unchanging* part of a vacant: the same bytes
    always refer to the same vacant, across substrate changes,
    rotations, graduation, and SUNK transitions. Equality and hashing
    are derived from `pubkey_bytes` so `VacantId` is safe to use as a
    dict key or set member.

    Attributes:
        pubkey_bytes: Raw 32-byte Ed25519 public key. Validated at
            construction time; lengths other than
            `ED25519_PUBLIC_KEY_BYTES` raise `ValidationError`.
    """

    model_config = ConfigDict(frozen=True)

    pubkey_bytes: bytes = Field(
        ..., min_length=ED25519_PUBLIC_KEY_BYTES, max_length=ED25519_PUBLIC_KEY_BYTES
    )

    @classmethod
    def from_verify_key(cls, vk: VerifyKey) -> VacantId:
        """Construct a `VacantId` from a `nacl.signing.VerifyKey`.

        Args:
            vk: An Ed25519 verify key (pubkey side of a `SigningKey`).

        Returns:
            A new `VacantId` whose `pubkey_bytes` are the raw 32 bytes
            of `vk`.
        """
        return cls(pubkey_bytes=bytes(vk))

    def verify_key(self) -> VerifyKey:
        """Re-derive the `VerifyKey` for cryptographic verification.

        Returns:
            The `nacl.signing.VerifyKey` corresponding to this id's
            `pubkey_bytes`. Use this to call `verify()` against any
            signature claimed to be from this vacant.
        """
        return pubkey_from_bytes(self.pubkey_bytes)

    def hex(self) -> str:
        """Hex-encode the full 32-byte public key.

        Returns:
            64-character lowercase hex string.
        """
        return self.pubkey_bytes.hex()

    def short(self) -> str:
        """Hex prefix suitable for log lines / dashboards.

        Returns:
            The first 12 hex characters of `hex()`. Not collision-free;
            never use as an equality key.
        """
        return self.hex()[:12]

    def __str__(self) -> str:
        return f"vacant:{self.short()}"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, VacantId) and self.pubkey_bytes == other.pubkey_bytes

    def __hash__(self) -> int:
        return hash(self.pubkey_bytes)


# --- Logbook ------------------------------------------------------------------


class LogEntry(BaseModel):
    """A single signed line in a vacant's logbook (Ricoeur *ipse*).

    Each entry carries a `kind` tag (e.g. `"BIRTH"`, `"SPAWN"`,
    `"REVIEW_EVENT"`), a UTC timestamp, an arbitrary JSON-serialisable
    payload, the BLAKE2b-256 hash of the previous entry, and an
    Ed25519 signature over the canonical concatenation of the four.
    The hash chain is what gives the logbook its tamper-evident
    property; the signatures pin authorship.

    Attributes:
        kind: Non-empty event tag.
        ts: UTC timestamp; tz-naive datetimes are coerced to UTC.
        payload: JSON-serialisable dict. Encoded canonically (sorted
            keys, no whitespace) before hashing.
        prev_hash: 32-byte BLAKE2b-256 of the previous entry's
            `signing_payload()`. Genesis entries use `EMPTY_PREV_HASH`.
        signature: Ed25519 signature over `signing_payload()`.
    """

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
        """Canonical bytes that get signed and hashed.

        Concatenates `kind | ts (UTC ISO-8601) | canonical_json(payload)
        | prev_hash`, joined with the ASCII `0x1f` separator.
        `signature` itself is *not* part of the payload — it is the
        output of signing it.

        Returns:
            The exact byte-string fed to `sign()` and `verify()`.
        """
        parts = [
            self.kind.encode("utf-8"),
            _utc_iso(self.ts).encode("utf-8"),
            _canonical_json(self.payload),
            self.prev_hash,
        ]
        return b"\x1f".join(parts)

    def compute_hash(self) -> bytes:
        """BLAKE2b-256 over `signing_payload()`.

        Returns:
            The 32-byte digest used as the *next* entry's `prev_hash`.
        """
        return hash_blake2b(self.signing_payload())

    def verify(self, pubkey: VerifyKey) -> bool:
        """Verify `signature` against `pubkey`.

        Args:
            pubkey: The Ed25519 verify-key the entry should have been
                signed under (typically `vacant.identity.verify_key()`).

        Returns:
            `True` iff the signature is valid over `signing_payload()`.
            Never raises on signature mismatch — use `verify_or_raise`
            in `vacant.core.crypto` if you want exceptions.
        """
        return verify(pubkey, self.signing_payload(), self.signature)


class Logbook(BaseModel):
    """Append-only signed history of a vacant's outward behaviour.

    The logbook is the only **mutable** core type — it grows by
    appending to `entries`. Existing entries are never edited; tampering
    with one breaks both the signature and the hash chain to the next
    entry. Use `verify_chain` (or the raising variant) to confirm an
    incoming logbook is intact before consuming it.

    Attributes:
        entries: Ordered list of `LogEntry`. Index 0 is genesis;
            `entries[i].prev_hash == entries[i-1].compute_hash()` for
            every `i > 0`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=False)

    entries: list[LogEntry] = Field(default_factory=list)

    def latest_hash(self) -> bytes:
        """Compute the hash that the next entry should use as `prev_hash`.

        Returns:
            `entries[-1].compute_hash()` if the logbook has any entries;
            `EMPTY_PREV_HASH` (32 zero bytes) otherwise.
        """
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
        """Build, sign, and append a new entry.

        Args:
            kind: Non-empty event tag (e.g. `"BIRTH"`, `"SPAWN"`).
            payload: JSON-serialisable dict; non-serialisable contents
                raise `TypeIntegrityError` at canonicalisation time.
            signing_key: The vacant's private Ed25519 key. The
                resulting `signature` will verify against the matching
                `verify_key`.
            ts: Optional explicit timestamp (coerced to UTC). Defaults
                to `datetime.now(UTC)` for fresh entries.

        Returns:
            The newly-appended (signed) `LogEntry`. Mutates `self.entries`.
        """
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
        """Verify every signature and that the hash chain is intact.

        Args:
            pubkey: The vacant's Ed25519 verify-key. *Every* entry must
                verify against this single key — keys do not rotate
                within a single logbook.

        Returns:
            `True` iff (1) every `entries[i].prev_hash` equals the
            previous entry's `compute_hash()` (or `EMPTY_PREV_HASH` for
            the genesis), AND (2) every `entries[i].verify(pubkey)`
            returns `True`. Never raises.
        """
        expected_prev = EMPTY_PREV_HASH
        for entry in self.entries:
            if entry.prev_hash != expected_prev:
                return False
            if not entry.verify(pubkey):
                return False
            expected_prev = entry.compute_hash()
        return True

    def verify_chain_or_raise(self, pubkey: VerifyKey) -> None:
        """Strict variant of `verify_chain` that names the failing entry.

        Args:
            pubkey: As for `verify_chain`.

        Raises:
            HashChainError: On the first broken hash link or invalid
                signature. The message includes the entry index and,
                for hash mismatches, the expected vs actual hash.
        """
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
    """Multi-substrate declaration (THEORY_V5 §2).

    Lists which substrates a vacant is willing to be invoked under
    (e.g. `"anthropic:claude-sonnet-4-6"`, `"openai:gpt-4o"`,
    `"client-inherited"`) plus an opaque `policy` dict the dispatcher
    can use for substrate-specific gating. Substrate is a *resource*,
    not the *identity* — switching substrates does not change
    `vacant_id`.

    Attributes:
        allowed_substrates: Non-empty substrate identifiers. Blank
            strings raise `ValidationError`.
        policy: Free-form per-substrate config (rate limits, model
            overrides, …).
    """

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
        """Stable byte encoding for hashing into a `CapabilityCard`.

        Returns:
            Canonical JSON (sorted keys, no whitespace) of
            `{allowed_substrates, policy}`. Used inside
            `CapabilityCard.signing_payload()` so the substrate spec is
            covered by the halo signature.
        """
        return _canonical_json(
            {
                "allowed_substrates": list(self.allowed_substrates),
                "policy": self.policy,
            }
        )


class BehaviorBundle(BaseModel):
    """System prompt + policy DSL + tool whitelist (Ricoeur *character*).

    The `bundle_hash` is computed and self-validated at construction:
    pass an empty `bundle_hash` and it gets filled in; pass a non-empty
    one that doesn't match the content and `TypeIntegrityError` fires.
    Downstream code that wants to detect "did the behaviour change
    silently?" compares `bundle_hash` rather than serialising fields.

    Attributes:
        system_prompt: The prompt the substrate sees as its system
            message.
        policy_dsl: Optional policy DSL string (P5 future). Empty by
            default.
        tool_whitelist: List of tool names the vacant is allowed to
            invoke. Hash is order-independent (sorted internally).
        bundle_hash: BLAKE2b-256 over a canonical JSON of the three
            fields. Auto-computed when left empty.
    """

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
    """The *halo* — a vacant's self-published capability announcement.

    Spec: THEORY_V5 §7.1. Each vacant carries its own halo; the
    "Registry" is an aggregation/index over halos and is **never** a
    routed-through component. Discovery hands a halo to the caller; the
    caller then dispatches directly to `endpoint`.

    Attributes:
        vacant_id: The vacant the halo is *about*. Anyone can mint a
            card claiming to be `vacant_id`, but `verify()` will only
            return `True` if `signature` was produced by the matching
            private key.
        capability_text: Human-readable capability announcement (e.g.
            "I translate technical English to Traditional Chinese").
        substrate_spec: Which substrates this vacant accepts. Covered
            by the signature.
        halo_version: Monotonic counter for halo revisions. Must be
            >= 1.
        endpoint: A2A endpoint URL for direct dispatch. `None` for
            LOCAL or not-yet-deployed vacants. Part of the signing
            payload so an attacker can't substitute the endpoint
            post-issuance (D009 §A).
        signature: Ed25519 signature over `signing_payload()`.
    """

    model_config = ConfigDict(frozen=True)

    vacant_id: VacantId
    capability_text: str
    substrate_spec: SubstrateSpec
    halo_version: int = DEFAULT_HALO_VERSION
    endpoint: str | None = None
    signature: bytes = b""

    @field_validator("halo_version")
    @classmethod
    def _halo_version_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("halo_version must be >= 1")
        return v

    def signing_payload(self) -> bytes:
        """Canonical bytes that get signed.

        Concatenates `pubkey | capability_text | substrate_spec |
        halo_version | endpoint`, joined with `0x1f`. `signature`
        itself is not included.

        Returns:
            The exact byte-string fed to `sign()` / `verify()`.
        """
        parts = [
            self.vacant_id.pubkey_bytes,
            self.capability_text.encode("utf-8"),
            self.substrate_spec.canonical_bytes(),
            self.halo_version.to_bytes(8, "big"),
            (self.endpoint or "").encode("utf-8"),
        ]
        return b"\x1f".join(parts)

    def signed(self, signing_key: SigningKey) -> CapabilityCard:
        """Return a copy of this card with `signature` filled in.

        Args:
            signing_key: The vacant's private Ed25519 key. Must match
                the public key embedded in `vacant_id` or downstream
                `verify()` calls will fail.

        Returns:
            A new `CapabilityCard` (the model is frozen) with a valid
            `signature`.
        """
        sig = sign(signing_key, self.signing_payload())
        return self.model_copy(update={"signature": sig})

    def verify(self) -> bool:
        """Verify the signature against the embedded public key.

        Returns:
            `True` iff `signature` is non-empty AND validates as an
            Ed25519 signature over `signing_payload()` under
            `vacant_id.verify_key()`. Empty signatures (un-signed
            drafts) return `False` rather than raising.
        """
        if not self.signature:
            return False
        return verify(self.vacant_id.verify_key(), self.signing_payload(), self.signature)


# --- State machine + composite form ------------------------------------------


class VacantState(StrEnum):
    """The 6 lifecycle states a vacant can be in (CLAUDE.md §LOCAL).

    `LOCAL` is the default for newly-spawned vacants; it is fully
    runnable but never appears in the public registry index. The state
    machine in `vacant.runtime.state_machine` defines the legal
    transitions; predicates `can_review` / `can_be_called` /
    `is_runnable` derive admission rules from the state.
    """

    LOCAL = "LOCAL"
    ACTIVE = "ACTIVE"
    HIBERNATING = "HIBERNATING"
    STALE = "STALE"
    SUNK = "SUNK"
    ARCHIVED = "ARCHIVED"


class ResidentForm(BaseModel):
    """The full 6-component vacant — identity through behaviour through halo.

    `ResidentForm` is the in-memory representation of a vacant. P0
    treats most of it as immutable; only `runtime_state` mutates as
    the lifecycle progresses. P1 onward also append to `logbook` via
    the explicit `append()` API.

    Attributes:
        identity: `VacantId` (pubkey).
        logbook: Append-only signed history.
        behavior_bundle: System prompt + policy DSL + tool whitelist.
        substrate_spec: Allowed substrate set.
        runtime_state: One of `VacantState`. Defaults to `LOCAL`.
        capability_card: The signed halo. `None` until P4 publishes
            it.
        parent_id: Lineage anchor (THEORY_V5 §4.3). `None` for root /
            Path-Zero vacants. Secondary parents (D4 lineage-merge)
            live in the BIRTH log entry payload — see D003 ADR.
    """

    model_config = ConfigDict(arbitrary_types_allowed=False)

    identity: VacantId
    logbook: Logbook
    behavior_bundle: BehaviorBundle
    substrate_spec: SubstrateSpec
    runtime_state: VacantState = VacantState.LOCAL
    capability_card: CapabilityCard | None = None
    parent_id: VacantId | None = None

    def verify_self(self) -> bool:
        """Cross-component integrity check.

        Verifies (1) the logbook hash chain + every signature against
        `identity.verify_key()`, and (2) if a `capability_card` is
        attached, that its `vacant_id` matches `identity` and its
        signature verifies.

        Returns:
            `True` iff every checked component is intact. `False` if
            any signature, hash link, or identity mismatch is found.
            Never raises — callers that need exception semantics can
            wrap with `Logbook.verify_chain_or_raise`.
        """
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
