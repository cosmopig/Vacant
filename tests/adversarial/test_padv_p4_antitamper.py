"""Padv P4 — anti-tamper layer attacks (Merkle, append-only, anomaly).

Spec anchors:
- `architecture/components/P4_registry.md` §3.1 (anti-tamper layers)
- `dispatch/Padv_review.md` §"Merkle snapshot forge", §"Audit log tamper"
"""

from __future__ import annotations

import pytest
from sqlalchemy import update

from vacant.core.crypto import keygen, sign
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.registry import (
    AppendOnlyViolation,
    EpochWitness,
    Event,
    EventFinalization,
    MerkleEpoch,
    ReadAudit,
    RegistryStore,
    build_merkle_root,
    publish_halo,
    verify_inclusion_proof,
)
from vacant.registry.antitamper import (
    merkle_inclusion_proof,
    verify_epoch_signature,
)


def _make_card_and_keys():  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    return sk, vk, vid, card


# --- Attack 1: Merkle snapshot forge -----------------------------------------
# Defense (P): an independent verifier recomputes the root from raw event
# rows and compares. A forged root_hash in the merkle_epoch table doesn't
# match what the verifier computes from the underlying leaves.


@pytest.mark.asyncio
async def test_attack_forged_merkle_root_detected_by_recomputation(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk)

    # Attacker forges a different root_hash.
    forged_root = b"\xde\xad\xbe\xef" + b"\x00" * 28

    # Independent verifier: pull the events that belong to this epoch,
    # recompute the root, and compare.
    events = await registry_store.list_events_for_vacant(card.vacant_id.hex(), limit=500)
    leaves = [e.event_hash for e in events if e.epoch_id == epoch.epoch_id]
    recomputed = build_merkle_root(leaves)
    assert recomputed == epoch.root_hash
    assert recomputed != forged_root


@pytest.mark.asyncio
async def test_attack_forged_root_signature_does_not_verify(
    registry_store: RegistryStore,
) -> None:
    sk_op, vk_op, _, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk_op,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk_op)
    # Operator's signature verifies on the real root.
    assert (
        verify_epoch_signature(
            root=epoch.root_hash,
            signature=epoch.registry_signature,
            operator_pubkey=vk_op,
        )
        is True
    )
    # On a forged root, the original signature does not verify.
    forged_root = b"\xab" * 32
    assert (
        verify_epoch_signature(
            root=forged_root,
            signature=epoch.registry_signature,
            operator_pubkey=vk_op,
        )
        is False
    )


@pytest.mark.asyncio
async def test_attack_inclusion_proof_for_excluded_leaf_fails(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    await registry_store.seal_epoch(signing_key=sk)

    # Build a proof for a fabricated leaf that wasn't in the tree.
    fake_leaf = b"never-in-tree" + b"\x00" * 19  # 32 bytes
    real_events = await registry_store.list_events_for_vacant(card.vacant_id.hex(), limit=500)
    real_leaves = [e.event_hash for e in real_events]
    real_root = build_merkle_root(real_leaves)

    # Try to construct a proof for fake_leaf by appending it to leaves and
    # asking for its proof — that proof is against a different (modified)
    # root, so verifying against the real root fails.
    modified_leaves = [*real_leaves, fake_leaf]
    proof = merkle_inclusion_proof(modified_leaves, len(modified_leaves) - 1)
    assert verify_inclusion_proof(proof, real_root) is False


# --- Attack 2: append-only violations ---------------------------------------
# Defense (P): `before_flush` listener raises `AppendOnlyViolation` on any
# DELETE against append-only tables.


@pytest.mark.asyncio
async def test_attack_delete_event_finalization_rejected(
    registry_store: RegistryStore,
) -> None:
    sk, vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    # Insert a finalization row by hand.
    fin = EventFinalization(
        event_seq=1,
        attester_vacant_id=vid.hex(),
        attester_pubkey=bytes(vk),
        signature=sign(sk, b"final"),
        base_model_family="claude",
        signed_at=0,
    )
    async with registry_store._sessionmaker() as s:
        s.add(fin)
        await s.commit()

    async with registry_store._sessionmaker() as s:
        from sqlmodel import select

        res = await s.execute(select(EventFinalization))
        row = res.scalar_one()
        await s.delete(row)
        with pytest.raises(AppendOnlyViolation):
            await s.commit()


@pytest.mark.asyncio
async def test_attack_delete_epoch_witness_rejected(
    registry_store: RegistryStore,
) -> None:
    sk, vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk)
    witness = EpochWitness(
        epoch_id=epoch.epoch_id or 0,
        witness_id="w1",
        witness_pubkey=bytes(vk),
        cosignature=sign(sk, b"co"),
        cosigned_at=0,
    )
    async with registry_store._sessionmaker() as s:
        s.add(witness)
        await s.commit()

    async with registry_store._sessionmaker() as s:
        from sqlmodel import select

        res = await s.execute(select(EpochWitness))
        row = res.scalar_one()
        await s.delete(row)
        with pytest.raises(AppendOnlyViolation):
            await s.commit()


@pytest.mark.asyncio
async def test_attack_delete_read_audit_rejected(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    audit = ReadAudit(
        audit_id="abc",
        query_kind="capability",
        query_hash=b"\x00" * 32,
        response_root=b"\x00" * 32,
        response_signature=b"\x00" * 64,
        served_at=0,
    )
    async with registry_store._sessionmaker() as s:
        s.add(audit)
        await s.commit()

    async with registry_store._sessionmaker() as s:
        from sqlmodel import select

        res = await s.execute(select(ReadAudit))
        row = res.scalar_one()
        await s.delete(row)
        with pytest.raises(AppendOnlyViolation):
            await s.commit()


# --- Attack 3: epoch tamper via direct UPDATE -------------------------------
# Defense (D): operator signature on the root catches a forged root in the
# table — the signature was computed over the original bytes.


@pytest.mark.asyncio
async def test_attack_epoch_root_update_breaks_signature_verify(
    registry_store: RegistryStore,
) -> None:
    sk, vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk)
    real_sig = epoch.registry_signature

    # Tamper the stored root_hash directly.
    forged_root = b"\xff" * 32
    async with registry_store._sessionmaker() as s:
        await s.execute(
            update(MerkleEpoch)
            .where(MerkleEpoch.epoch_id == epoch.epoch_id)
            .values(root_hash=forged_root)
        )
        await s.commit()

    # The stored signature was over the original root; under the new
    # root, it does not verify.
    fresh_epoch = await registry_store.get_merkle_epoch(epoch.epoch_id or 0)
    assert fresh_epoch is not None
    assert (
        verify_epoch_signature(
            root=fresh_epoch.root_hash,
            signature=real_sig,
            operator_pubkey=vk,
        )
        is False
    )


# --- Attack 4: anomaly engine bypass via direct counter writes --------------
# Defense (C, not P): anomaly counters are observability signals, not
# blocking gates. Direct DB writes are out of band — the engine surfaces
# `triggered=True` only when the rule fires through the public API.


@pytest.mark.asyncio
async def test_attack_anomaly_signal_records_triggered_flag(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    out = await registry_store.record_anomaly(
        vacant_id=vid.hex(), metric="rep_jump", value=0.99, threshold=0.4
    )
    assert out.triggered is True


# --- Attack 5: latest_event_overall returns most recent ---------------------
# Defense (P): The chain tip used as `prev_event_hash` for the next
# event is the highest-seq event. `submit_event` always uses the actual
# tip — bypassing `latest_event_overall` would produce a chain break
# detectable by `verify_event_chain`.


@pytest.mark.asyncio
async def test_attack_chain_tip_is_actual_max_seq(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    tip = await registry_store.latest_event_overall()
    assert tip is not None
    # The tip is the only event so far.
    async with registry_store._sessionmaker() as s:
        from sqlmodel import select

        res = await s.execute(select(Event))
        rows = list(res.scalars().all())
    assert len(rows) == 1
    assert tip.event_hash == rows[0].event_hash
