"""Halo emission — per-vacant `CapabilityCard` publication + revocation.

Per THEORY_V5 §7.1 (Registry ontology), each vacant carries its own
capability card; the registry stores a *signed copy* plus index entries
so direct vacant-to-vacant calls can bypass it. LOCAL-state vacants are
not stored centrally (visibility=NONE).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from vacant.core.crypto import SigningKey, hash_blake2b, sign
from vacant.core.types import CapabilityCard, VacantState
from vacant.protocol.capability_card import serialize as serialize_card
from vacant.registry.antitamper import canonical_event_bytes
from vacant.registry.errors import RegistryWriteError
from vacant.registry.models import Vacant
from vacant.registry.store import RegistryStore, SignedEventDraft, now_ms
from vacant.registry.visibility import Visibility, effective_visibility

__all__ = [
    "HaloRecord",
    "RegisterEventDraftInputs",
    "RevocationRecord",
    "publish_halo",
    "publish_halo_signed",
    "register_event_canonical_bytes",
    "register_event_payload",
    "revoke_halo",
]


@dataclass(frozen=True)
class HaloRecord:
    """Result of a successful `publish_halo`."""

    vacant_id: str
    visibility: Visibility
    event_seq: int
    capability_card_hash: bytes


@dataclass(frozen=True)
class RevocationRecord:
    """Result of a successful `revoke_halo`."""

    vacant_id: str
    event_seq: int
    reason: str


def _capability_card_hash(card: CapabilityCard) -> bytes:
    return hash_blake2b(card.signing_payload())


def _extract_halo_version(payload_json: str | dict[str, Any]) -> int:
    """Pull ``halo_version`` from a register-event payload (Pfix3 B5).

    The event store keeps payloads as JSON strings; decode + extract,
    falling back to 0 on any parse failure so the monotonicity check
    never blocks publish on a malformed historical event.
    """
    try:
        payload = payload_json if isinstance(payload_json, dict) else json.loads(payload_json)
        return int(payload.get("halo_version", 0))
    except (json.JSONDecodeError, ValueError, TypeError):
        return 0


def _check_republish_invariants(
    *,
    existing: Vacant,
    card: CapabilityCard,
    new_parent_id: str | None,
    prev_halo_version: int,
) -> None:
    """Reject a republish that would violate identity-custody or chain
    monotonicity (Pfix3 B5).

    - Public key must match: ``vacant_id`` is derived from the pubkey,
      so this is a defensive check that the new card was signed by the
      same key the existing row records.
    - ``parent_id`` is immutable across republish: changing parent
      breaks the lineage chain that powers cold-start priors.
    - ``halo_version`` must be monotonic: rejects accidental replay of
      a stale signed card.
    """
    if card.vacant_id.pubkey_bytes != existing.public_key:
        raise RegistryWriteError(
            "publish_halo republish: card pubkey does not match existing public_key"
        )
    if new_parent_id != existing.parent_id:
        raise RegistryWriteError(
            "publish_halo republish: parent_id is immutable; "
            f"existing={existing.parent_id!r} new={new_parent_id!r}"
        )
    if card.halo_version < prev_halo_version:
        raise RegistryWriteError(
            "publish_halo republish: halo_version must be monotonic; "
            f"existing={prev_halo_version} new={card.halo_version}"
        )


async def publish_halo(
    *,
    store: RegistryStore,
    card: CapabilityCard,
    runtime_state: VacantState,
    signing_key: SigningKey,
    base_model: str = "unknown",
    base_model_family: str = "unknown",
    owner_org: str | None = None,
    declared_capabilities: list[str] | None = None,
    parent_id: str | None = None,
    version: str = "0.0.1",
    visibility: Visibility = Visibility.PUBLIC,
) -> HaloRecord:
    """Insert / update a vacant's halo + emit a `register` event.

    Visibility rules (D006 §G + dispatch §"Visibility"):
    - LOCAL state forces `Visibility.NONE` regardless of `visibility`.
    - LOCAL halos are stored (so owner/parent direct lookup works) but
      `effective_visibility` returns NONE → discovery filters them out.
    """
    if not card.verify():
        raise RegistryWriteError("publish_halo: capability card signature invalid")

    vacant_id = card.vacant_id.hex()
    eff_vis = effective_visibility(runtime_state, visibility)
    capabilities = declared_capabilities or [card.capability_text]
    capability_card_hash = _capability_card_hash(card)
    capability_card_blob = serialize_card(card)
    ts = now_ms()

    existing = await store.get_vacant(vacant_id)
    vacant_to_insert: Vacant | None = None
    vacant_field_updates: dict[str, object] | None = None
    if existing is None:
        vacant_to_insert = Vacant(
            vacant_id=vacant_id,
            public_key=card.vacant_id.pubkey_bytes,
            owner_org=owner_org,
            base_model=base_model,
            base_model_family=base_model_family,
            parent_id=parent_id,
            version=version,
            declared_capabilities_json=json.dumps(capabilities),
            capability_card_hash=capability_card_hash,
            capability_card_sig=card.signature,
            capability_card_blob=capability_card_blob,
            status="active",
            visibility=eff_vis.value,
            registered_at=ts,
        )
        next_seq = 1
        prev_halo_version = 0
    else:
        # Republish: enforce identity-custody invariants then build a
        # full field-update payload so the row tracks the new card.
        last = await store.latest_event_for_actor(vacant_id)
        prev_halo_version = _extract_halo_version(last.payload_json) if last else 0
        _check_republish_invariants(
            existing=existing,
            card=card,
            new_parent_id=parent_id,
            prev_halo_version=prev_halo_version,
        )
        next_seq = (last.actor_seq if last else 0) + 1
        vacant_field_updates = {
            "capability_card_hash": capability_card_hash,
            "capability_card_sig": card.signature,
            "capability_card_blob": capability_card_blob,
            "declared_capabilities_json": json.dumps(capabilities),
            "base_model": base_model,
            "base_model_family": base_model_family,
            "owner_org": owner_org,
            "version": version,
            "visibility": eff_vis.value,
        }

    # Emit signed `register` event so the publish lands in the audit chain.
    # F-A: vacant insert/update + event submit are bundled into a single
    # DB transaction by `submit_register_event_atomic`. If the event
    # fails (signature reject, idempotency conflict, race lost), the
    # vacant row insert / visibility flip is rolled back together — so
    # the public state and the audit chain can never diverge.
    draft_payload = {
        "vacant_id": vacant_id,
        "card_hash": capability_card_hash.hex(),
        "halo_version": card.halo_version,
        "visibility": eff_vis.value,
    }
    idempotency_key = f"register:{vacant_id}:{ts}:{uuid.uuid4()}"
    canonical_payload = json.dumps(draft_payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_hash = hash_blake2b(canonical_payload)
    canonical = canonical_event_bytes(
        event_type="register",
        actor_vacant_id=vacant_id,
        subject_vacant_id=None,
        payload_hash=payload_hash,
        idempotency_key=idempotency_key,
        signed_by_pubkey=card.vacant_id.pubkey_bytes,
        ts=ts,
        actor_seq=next_seq,
    )
    sig = sign(signing_key, canonical)
    draft = SignedEventDraft(
        event_type="register",
        actor_vacant_id=vacant_id,
        subject_vacant_id=None,
        payload=draft_payload,
        idempotency_key=idempotency_key,
        signed_by_pubkey=card.vacant_id.pubkey_bytes,
        signature=sig,
        actor_seq=next_seq,
        ts=ts,
    )
    event = await store.submit_register_event_atomic(
        vacant_to_insert=vacant_to_insert,
        vacant_id_to_update=None if vacant_to_insert is not None else vacant_id,
        new_visibility=None if vacant_to_insert is not None else eff_vis.value,
        draft=draft,
        vacant_field_updates=vacant_field_updates,
    )

    return HaloRecord(
        vacant_id=vacant_id,
        visibility=eff_vis,
        event_seq=event.seq or 0,
        capability_card_hash=capability_card_hash,
    )


@dataclass(frozen=True)
class RegisterEventDraftInputs:
    """Bag of inputs that name a single ``register`` event draft.

    Both the client (CLI publishing over HTTP) and the server (HTTP
    handler verifying the request) construct the same canonical bytes
    from these fields, so the signature is bit-stable between sides.
    """

    vacant_id: str
    capability_card_hash: bytes
    halo_version: int
    visibility: Visibility
    ts_ms: int
    actor_seq: int
    idempotency_key: str


def register_event_payload(inp: RegisterEventDraftInputs) -> dict[str, object]:
    """Canonical payload dict the ``register`` event carries.

    Mirrors the in-process ``publish_halo`` payload (lines above) so
    HTTP-published rows produce the same audit footprint as direct
    calls."""
    return {
        "vacant_id": inp.vacant_id,
        "card_hash": inp.capability_card_hash.hex(),
        "halo_version": inp.halo_version,
        "visibility": inp.visibility.value,
    }


def register_event_canonical_bytes(
    inp: RegisterEventDraftInputs, *, signed_by_pubkey: bytes
) -> bytes:
    """Canonical Ed25519-signing payload for a ``register`` event.

    The CLI publishes via HTTP by computing this byte-string, signing
    it under the vacant's own key, and POSTing card_blob + the
    signature to ``/v1/halo``. The server reconstructs the same bytes
    and verifies before letting the row land in the audit chain.
    """
    payload_bytes = json.dumps(
        register_event_payload(inp), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    payload_hash = hash_blake2b(payload_bytes)
    return canonical_event_bytes(
        event_type="register",
        actor_vacant_id=inp.vacant_id,
        subject_vacant_id=None,
        payload_hash=payload_hash,
        idempotency_key=inp.idempotency_key,
        signed_by_pubkey=signed_by_pubkey,
        ts=inp.ts_ms,
        actor_seq=inp.actor_seq,
    )


async def publish_halo_signed(
    *,
    store: RegistryStore,
    card: CapabilityCard,
    runtime_state: VacantState,
    visibility: Visibility = Visibility.PUBLIC,
    base_model: str = "unknown",
    base_model_family: str = "unknown",
    owner_org: str | None = None,
    declared_capabilities: list[str] | None = None,
    parent_id: str | None = None,
    version: str = "0.0.1",
    event_ts_ms: int,
    event_actor_seq: int,
    event_idempotency_key: str,
    event_signature: bytes,
) -> HaloRecord:
    """HTTP-friendly variant of `publish_halo`: the caller pre-signs the
    register event so the registry never needs the vacant's private key.

    Server-side flow:

    1. Verify the capability card's own signature.
    2. Insert the vacant row if missing (so ``submit_event``'s actor
       lookup can succeed).
    3. Submit the pre-signed register event via ``store.submit_event``,
       which re-runs L1 signature verification + L2 sequence check.
    """
    if not card.verify():
        raise RegistryWriteError("publish_halo_signed: capability card signature invalid")

    vacant_id = card.vacant_id.hex()
    eff_vis = effective_visibility(runtime_state, visibility)
    capabilities = declared_capabilities or [card.capability_text]
    capability_card_hash = _capability_card_hash(card)
    capability_card_blob = serialize_card(card)

    existing = await store.get_vacant(vacant_id)
    vacant_to_insert: Vacant | None = None
    vacant_field_updates: dict[str, object] | None = None
    if existing is None:
        vacant_to_insert = Vacant(
            vacant_id=vacant_id,
            public_key=card.vacant_id.pubkey_bytes,
            owner_org=owner_org,
            base_model=base_model,
            base_model_family=base_model_family,
            parent_id=parent_id,
            version=version,
            declared_capabilities_json=json.dumps(capabilities),
            capability_card_hash=capability_card_hash,
            capability_card_sig=card.signature,
            capability_card_blob=capability_card_blob,
            status="active",
            visibility=eff_vis.value,
            registered_at=event_ts_ms,
        )
    else:
        # Republish: enforce identity-custody invariants then build a
        # full field-update payload so the row tracks the new card.
        last = await store.latest_event_for_actor(vacant_id)
        prev_halo_version = _extract_halo_version(last.payload_json) if last else 0
        _check_republish_invariants(
            existing=existing,
            card=card,
            new_parent_id=parent_id,
            prev_halo_version=prev_halo_version,
        )
        vacant_field_updates = {
            "capability_card_hash": capability_card_hash,
            "capability_card_sig": card.signature,
            "capability_card_blob": capability_card_blob,
            "declared_capabilities_json": json.dumps(capabilities),
            "base_model": base_model,
            "base_model_family": base_model_family,
            "owner_org": owner_org,
            "version": version,
            "visibility": eff_vis.value,
        }

    inputs = RegisterEventDraftInputs(
        vacant_id=vacant_id,
        capability_card_hash=capability_card_hash,
        halo_version=card.halo_version,
        visibility=eff_vis,
        ts_ms=event_ts_ms,
        actor_seq=event_actor_seq,
        idempotency_key=event_idempotency_key,
    )
    draft = SignedEventDraft(
        event_type="register",
        actor_vacant_id=vacant_id,
        subject_vacant_id=None,
        payload=register_event_payload(inputs),
        idempotency_key=event_idempotency_key,
        signed_by_pubkey=card.vacant_id.pubkey_bytes,
        signature=event_signature,
        actor_seq=event_actor_seq,
        ts=event_ts_ms,
    )
    # F-A: vacant insert/update + register event are submitted in one
    # DB transaction so a failed `submit_event` (bad signature, race
    # lost, idempotency conflict) rolls back the row insert and we
    # never end up with a publicly-visible halo whose register event
    # is missing from the audit chain.
    event = await store.submit_register_event_atomic(
        vacant_to_insert=vacant_to_insert,
        vacant_id_to_update=None if vacant_to_insert is not None else vacant_id,
        new_visibility=None if vacant_to_insert is not None else eff_vis.value,
        draft=draft,
        vacant_field_updates=vacant_field_updates,
    )
    return HaloRecord(
        vacant_id=vacant_id,
        visibility=eff_vis,
        event_seq=event.seq or 0,
        capability_card_hash=capability_card_hash,
    )


async def revoke_halo(
    *,
    store: RegistryStore,
    vacant_id: str,
    reason: str,
    signing_key: SigningKey,
    pubkey_bytes: bytes,
) -> RevocationRecord:
    """Mark a vacant as revoked — emit a signed `revoke` event and flip
    `status` to `revoked`. Append-only: the historical capability card
    stays in the table.
    """
    if not reason.strip():
        raise RegistryWriteError("revoke_halo: reason must be non-empty")
    v = await store.get_vacant(vacant_id)
    if v is None:
        raise RegistryWriteError(f"revoke_halo: vacant {vacant_id} not found")

    ts = now_ms()
    payload: dict[str, Any] = {"vacant_id": vacant_id, "reason": reason}
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_hash = hash_blake2b(payload_bytes)
    last = await store.latest_event_for_actor(vacant_id)
    next_seq = (last.actor_seq if last else 0) + 1
    from vacant.registry.antitamper import canonical_event_bytes

    canonical = canonical_event_bytes(
        event_type="revoke",
        actor_vacant_id=vacant_id,
        subject_vacant_id=None,
        payload_hash=payload_hash,
        idempotency_key=f"revoke:{vacant_id}:{ts}",
        signed_by_pubkey=pubkey_bytes,
        ts=ts,
        actor_seq=next_seq,
    )
    sig = sign(signing_key, canonical)
    draft = SignedEventDraft(
        event_type="revoke",
        actor_vacant_id=vacant_id,
        subject_vacant_id=None,
        payload=payload,
        idempotency_key=f"revoke:{vacant_id}:{ts}",
        signed_by_pubkey=pubkey_bytes,
        signature=sig,
        actor_seq=next_seq,
        ts=ts,
    )
    event = await store.submit_event(draft)
    await store.update_vacant_status(vacant_id, "revoked")
    return RevocationRecord(vacant_id=vacant_id, event_seq=event.seq or 0, reason=reason)
