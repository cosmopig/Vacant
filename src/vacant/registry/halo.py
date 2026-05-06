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
from vacant.registry.errors import RegistryWriteError
from vacant.registry.models import Vacant
from vacant.registry.store import RegistryStore, SignedEventDraft, now_ms
from vacant.registry.visibility import Visibility, effective_visibility

__all__ = [
    "HaloRecord",
    "RevocationRecord",
    "publish_halo",
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
    if existing is None:
        row = Vacant(
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
        await store.insert_vacant(row)
    else:
        await store.update_vacant_visibility(vacant_id, eff_vis.value)

    # Emit signed `register` event so the publish lands in the audit chain.
    draft_payload = {
        "vacant_id": vacant_id,
        "card_hash": capability_card_hash.hex(),
        "halo_version": card.halo_version,
        "visibility": eff_vis.value,
    }
    last = await store.latest_event_for_actor(vacant_id)
    next_seq = (last.actor_seq if last else 0) + 1
    canonical_payload = json.dumps(draft_payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_hash = hash_blake2b(canonical_payload)
    from vacant.registry.antitamper import canonical_event_bytes

    canonical = canonical_event_bytes(
        event_type="register",
        actor_vacant_id=vacant_id,
        subject_vacant_id=None,
        payload_hash=payload_hash,
        idempotency_key=f"register:{vacant_id}:{ts}:{uuid.uuid4()}",
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
        idempotency_key=f"register:{vacant_id}:{ts}:{uuid.uuid4()}",
        signed_by_pubkey=card.vacant_id.pubkey_bytes,
        signature=sig,
        actor_seq=next_seq,
        ts=ts,
    )
    # Re-derive canonical bytes inside `submit_event`. The signature was
    # produced over the same canonicalisation rules so it'll verify there.
    # We sign a fresh idempotency_key, so update the draft to use the
    # one we signed against.
    draft = SignedEventDraft(
        event_type=draft.event_type,
        actor_vacant_id=draft.actor_vacant_id,
        subject_vacant_id=draft.subject_vacant_id,
        payload=draft.payload,
        idempotency_key=f"register:{vacant_id}:{ts}",
        signed_by_pubkey=draft.signed_by_pubkey,
        signature=sig,  # signed against {idempotency_key=above}: rebuild
        actor_seq=draft.actor_seq,
        ts=draft.ts,
    )
    # Rebuild signature with the final idempotency_key.
    canonical_final = canonical_event_bytes(
        event_type=draft.event_type,
        actor_vacant_id=draft.actor_vacant_id,
        subject_vacant_id=draft.subject_vacant_id,
        payload_hash=payload_hash,
        idempotency_key=draft.idempotency_key,
        signed_by_pubkey=draft.signed_by_pubkey,
        ts=draft.ts,
        actor_seq=draft.actor_seq,
    )
    final_sig = sign(signing_key, canonical_final)
    draft = SignedEventDraft(
        event_type=draft.event_type,
        actor_vacant_id=draft.actor_vacant_id,
        subject_vacant_id=draft.subject_vacant_id,
        payload=draft.payload,
        idempotency_key=draft.idempotency_key,
        signed_by_pubkey=draft.signed_by_pubkey,
        signature=final_sig,
        actor_seq=draft.actor_seq,
        ts=draft.ts,
    )
    event = await store.submit_event(draft)

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
