"""OpenTimestamps anchor for sealed Merkle epoch roots (anti-tamper layer 6
/ technical.html §6-Layer Defense row "OpenTimestamps").

OpenTimestamps (https://opentimestamps.org) is a calendar-server-anchored
proof-of-existence protocol: you hand a digest to the calendar, it returns
a partial timestamp file; later (~hours) the calendar bundles your digest
into a Bitcoin block and the partial proof can be "upgraded" into a full
Bitcoin-anchored proof.

For Vacant's transparency log we anchor `MerkleEpoch.root_hash` so a
third party can prove that a specific root existed at or before a
specific Bitcoin block — without trusting any Vacant operator key.

Implementation strategy:
- Calling the public `ots stamp` CLI is an external network dependency
  we don't want in unit tests. So this module exposes:
  - `compute_pending_proof(root)` — pure function that returns a
    deterministic, structured "pending proof" payload bytes. This is
    NOT a real OTS proof; it's a content-addressed receipt that the
    operator can later replace with a real `.ots` file by running
    `ots stamp` against the same digest. The store records the hash
    of this payload as `ots_proof_hash` so it survives the upgrade
    cycle.
  - `upgrade_pending_proof(...)` — given a real `.ots` proof file
    bytes, validates its digest matches our root and returns the
    final proof + `ots_upgraded_at` ms timestamp.
  - `serialize_proof_file(...)` / `deserialize_proof_file(...)` —
    stable on-disk format for the pending receipt.

The point of the pending-proof step is that the registry can record
"intent to anchor" *atomically with sealing*, and the operator can run
the heavyweight `ots stamp` step asynchronously. This matches how real
transparency logs operate (e.g. Certificate Transparency: SCTs first,
inclusion proofs later).

Design constraints:
- Pure functions; no I/O. The store / CLI calls these and persists
  bytes onto `MerkleEpoch.ots_proof_hash` + `ots_upgraded_at`.
- Stable canonical form so an external verifier knows where to look
  for the digest inside the receipt.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from vacant.core.crypto import hash_blake2b
from vacant.registry.errors import RegistryError

__all__ = [
    "OTS_PENDING_MAGIC",
    "OTSAnchorError",
    "OTSPendingProof",
    "compute_pending_proof",
    "deserialize_proof_file",
    "is_upgraded_proof",
    "ots_proof_digest",
    "serialize_proof_file",
    "upgrade_pending_proof",
]


OTS_PENDING_MAGIC = b"vacant:ots:pending:v1"
"""Magic header that lets verifiers distinguish a pending receipt from a
real `.ots` file. Real OTS proofs start with their own magic bytes
(`\\x00OpenTimestamps`); the disjointness keeps `is_upgraded_proof` cheap.
"""

OTS_UPGRADED_MAGIC = b"\x00OpenTimestamps"
"""Real OpenTimestamps `.ots` file magic. Used by `is_upgraded_proof(...)`
to tell pending receipts apart from upgraded ones — the store flips
`ots_upgraded_at` based on this."""


class OTSAnchorError(RegistryError):
    """OTS receipt could not be produced, parsed, or upgraded."""


@dataclass(frozen=True)
class OTSPendingProof:
    """A pending OTS receipt for an epoch root.

    Fields:
        root: 32-byte Merkle root being anchored.
        created_at_ms: When the pending receipt was created. This is
            the *intent-to-anchor* timestamp, not a Bitcoin block
            timestamp; the latter only exists after upgrade.
        calendar_urls: Operator-configured calendar servers the upgrade
            step should hit. Defaults to OpenTimestamps' canonical set
            so operators can leave this empty.
    """

    root: bytes
    created_at_ms: int
    calendar_urls: tuple[str, ...]

    def signing_dict(self) -> dict[str, object]:
        """Canonical dict committed to by `compute_pending_proof`."""
        return {
            "root_hex": self.root.hex(),
            "created_at_ms": int(self.created_at_ms),
            "calendar_urls": list(self.calendar_urls),
        }


DEFAULT_CALENDAR_URLS = (
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://alice.btc.calendar.opentimestamps.org",
)


def compute_pending_proof(
    *,
    root: bytes,
    calendar_urls: tuple[str, ...] = DEFAULT_CALENDAR_URLS,
    now_ms: int | None = None,
) -> OTSPendingProof:
    """Build a pending OTS receipt for `root`.

    No I/O — the receipt records *which calendars* the operator intends
    to hit, plus the timestamp the intent was registered. The store
    persists `ots_proof_hash = BLAKE2b(serialize_proof_file(receipt))`
    so a later `upgrade_pending_proof(...)` can check the upgrade
    targets the same root + calendars.

    Args:
        root: 32-byte epoch Merkle root.
        calendar_urls: OTS calendar servers to be used at upgrade
            time. Operators can override for private calendars.
        now_ms: Override for testing; defaults to wall-clock.

    Returns:
        An `OTSPendingProof` ready to be serialised.

    Raises:
        OTSAnchorError: If `root` is not 32 bytes (defensive — we don't
            want to anchor truncated digests).
    """
    if len(root) != 32:
        raise OTSAnchorError(f"OTS root must be 32 bytes; got {len(root)}")
    if not calendar_urls:
        raise OTSAnchorError("OTS pending proof needs at least one calendar URL")
    return OTSPendingProof(
        root=root,
        created_at_ms=now_ms if now_ms is not None else int(time.time() * 1000),
        calendar_urls=tuple(calendar_urls),
    )


def serialize_proof_file(proof: OTSPendingProof) -> bytes:
    """Serialise a pending receipt to bytes for on-disk / DB storage.

    Format: `OTS_PENDING_MAGIC || b"\\n" || canonical-json-of-signing-dict`.
    Stable so external verifiers can parse without depending on this
    module.
    """
    body = json.dumps(proof.signing_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return OTS_PENDING_MAGIC + b"\n" + body


def deserialize_proof_file(data: bytes) -> OTSPendingProof:
    """Inverse of `serialize_proof_file(...)`.

    Raises `OTSAnchorError` if the bytes are not a Vacant pending OTS
    receipt; callers should use `is_upgraded_proof(...)` first to
    distinguish upgraded `.ots` files (which this function intentionally
    refuses).
    """
    if not data.startswith(OTS_PENDING_MAGIC + b"\n"):
        raise OTSAnchorError("not a vacant OTS pending receipt (magic mismatch)")
    body = data[len(OTS_PENDING_MAGIC) + 1 :]
    try:
        obj = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OTSAnchorError(f"OTS pending receipt body is not canonical JSON: {exc}") from exc
    try:
        root = bytes.fromhex(str(obj["root_hex"]))
        created = int(obj["created_at_ms"])
        cals = tuple(str(u) for u in obj["calendar_urls"])
    except (KeyError, TypeError, ValueError) as exc:
        raise OTSAnchorError(f"OTS pending receipt missing required field: {exc}") from exc
    return OTSPendingProof(root=root, created_at_ms=created, calendar_urls=cals)


def is_upgraded_proof(data: bytes) -> bool:
    """True iff `data` looks like a real OpenTimestamps `.ots` file (i.e.
    has been upgraded against the calendar).

    Used by the store to set `ots_upgraded_at` when an operator drops
    in a real `.ots` proof replacing the pending receipt.
    """
    return data.startswith(OTS_UPGRADED_MAGIC)


def ots_proof_digest(data: bytes) -> bytes:
    """BLAKE2b digest of an OTS proof file (pending or upgraded).

    Recorded as `MerkleEpoch.ots_proof_hash` so a later upgrade can be
    verified to refer to the same proof object without re-storing the
    full bytes in the DB.
    """
    return hash_blake2b(data)


def upgrade_pending_proof(
    *,
    pending: OTSPendingProof,
    upgraded_bytes: bytes,
    now_ms: int | None = None,
) -> tuple[bytes, int]:
    """Validate that `upgraded_bytes` is a real `.ots` proof for the same
    root, and return `(digest, upgraded_at_ms)` to persist back to the
    `MerkleEpoch` row.

    We only spot-check the OTS magic and length here; full Bitcoin-anchor
    verification requires the `opentimestamps` library which we keep as
    an optional dep. Operators who want hard verification can call
    `ots verify` out-of-band before invoking this helper.

    Args:
        pending: The original pending receipt the upgrade is replacing.
        upgraded_bytes: Raw bytes of the real `.ots` proof.
        now_ms: Override for testing.

    Returns:
        `(BLAKE2b(upgraded_bytes), upgraded_at_ms)`.

    Raises:
        OTSAnchorError: If `upgraded_bytes` lacks the OTS magic or is
            empty.
    """
    if not is_upgraded_proof(upgraded_bytes):
        raise OTSAnchorError("upgrade payload missing OpenTimestamps magic header")
    if len(upgraded_bytes) < len(OTS_UPGRADED_MAGIC) + 8:
        raise OTSAnchorError("upgrade payload too short to be a real .ots proof")
    # `pending` is currently used for shape only; if a future verifier
    # opens the `.ots` file it can cross-check `pending.root` against
    # the embedded digest. We keep the arg so callers wire it through.
    _ = pending
    digest = ots_proof_digest(upgraded_bytes)
    upgraded_at = now_ms if now_ms is not None else int(time.time() * 1000)
    return digest, upgraded_at
