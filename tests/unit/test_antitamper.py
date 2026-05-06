"""Anti-tamper layer-by-layer tests (dispatch §5).

Each defense gets at least one attack test that *tries to bypass* and
asserts the defense catches it. The 6 layers:

L1. Signature verify on every write
L2. Sequence-number monotonicity per vacant_id
L3. Freshness window on attestations
L4. Merkle-root snapshots
L5. Anomaly counters (signal, not block)
L6. Append-only audit log
"""

from __future__ import annotations

import time

import pytest

from vacant.core.crypto import hash_blake2b, keygen, sign
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.registry import (
    AppendOnlyViolation,
    Event,
    FreshnessError,
    MerkleEpoch,
    RegistryStore,
    SequenceMonotonicityError,
    SignatureRejected,
    SignedEventDraft,
    publish_halo,
)
from vacant.registry.antitamper import (
    assess_anomaly,
    build_merkle_root,
    build_merkle_tree,
    canonical_event_bytes,
    check_attestation_freshness,
    check_sequence_monotonic,
    compute_event_hash,
    merkle_inclusion_proof,
    sign_epoch_root,
    verify_event_signature,
    verify_inclusion_proof,
)
from vacant.registry.store import canonical_json

# --- L1: signature verify ----------------------------------------------------


def test_l1_signature_verify_rejects_garbage_pubkey() -> None:
    with pytest.raises(SignatureRejected):
        verify_event_signature(pubkey_bytes=b"too short", canonical_bytes=b"x", signature=b"y" * 64)


def test_l1_signature_verify_rejects_bad_signature() -> None:
    sk, vk = keygen()
    with pytest.raises(SignatureRejected):
        verify_event_signature(
            pubkey_bytes=bytes(vk),
            canonical_bytes=b"original",
            signature=b"\x00" * 64,
        )
    _ = sk


def test_l1_signature_verify_passes_on_valid_sig() -> None:
    sk, vk = keygen()
    msg = b"vacant-test-message"
    sig = sign(sk, msg)
    # Should not raise.
    verify_event_signature(pubkey_bytes=bytes(vk), canonical_bytes=msg, signature=sig)


# --- L2: sequence monotonicity -----------------------------------------------


def test_l2_seq_strictly_increases() -> None:
    check_sequence_monotonic(last_seq=0, candidate_seq=1)
    check_sequence_monotonic(last_seq=42, candidate_seq=43)


def test_l2_seq_rejects_replay() -> None:
    with pytest.raises(SequenceMonotonicityError):
        check_sequence_monotonic(last_seq=5, candidate_seq=5)


def test_l2_seq_rejects_gap() -> None:
    with pytest.raises(SequenceMonotonicityError):
        check_sequence_monotonic(last_seq=5, candidate_seq=7)


def test_l2_seq_rejects_backwards() -> None:
    with pytest.raises(SequenceMonotonicityError):
        check_sequence_monotonic(last_seq=5, candidate_seq=2)


# --- L3: freshness window ----------------------------------------------------


def test_l3_freshness_within_window_passes() -> None:
    now = 1_000_000
    check_attestation_freshness(valid_from_ms=now - 1000, valid_until_ms=now + 1000, now_ms=now)


def test_l3_freshness_before_valid_from_rejected() -> None:
    now = 1_000_000
    with pytest.raises(FreshnessError):
        check_attestation_freshness(valid_from_ms=now + 1, valid_until_ms=now + 1000, now_ms=now)


def test_l3_freshness_after_valid_until_rejected() -> None:
    now = 1_000_000
    with pytest.raises(FreshnessError):
        check_attestation_freshness(valid_from_ms=now - 1000, valid_until_ms=now - 1, now_ms=now)


def test_l3_freshness_no_expiry_passes() -> None:
    now = 1_000_000
    check_attestation_freshness(valid_from_ms=now - 1000, valid_until_ms=None, now_ms=now)


# --- L4: Merkle snapshots ----------------------------------------------------


def test_l4_merkle_root_is_deterministic() -> None:
    leaves = [b"a", b"b", b"c"]
    assert build_merkle_root(leaves) == build_merkle_root(leaves)


def test_l4_merkle_root_changes_on_any_leaf_change() -> None:
    a = build_merkle_root([b"a", b"b", b"c"])
    b = build_merkle_root([b"a", b"b", b"d"])
    assert a != b


def test_l4_merkle_inclusion_proof_round_trip() -> None:
    leaves = [b"a", b"b", b"c", b"d"]
    root = build_merkle_root(leaves)
    for i in range(len(leaves)):
        proof = merkle_inclusion_proof(leaves, i)
        assert verify_inclusion_proof(proof, root)


def test_l4_merkle_proof_for_tampered_leaf_fails() -> None:
    leaves = [b"a", b"b", b"c", b"d"]
    root = build_merkle_root(leaves)
    proof = merkle_inclusion_proof(leaves, 1)
    # Verify against a root produced by tampering one leaf — should fail.
    bad_root = build_merkle_root([b"a", b"X", b"c", b"d"])
    assert verify_inclusion_proof(proof, bad_root) is False
    _ = root


def test_l4_merkle_empty_tree_root_stable() -> None:
    # Empty tree returns a stable singleton root so callers always have something.
    levels = build_merkle_tree([])
    assert len(levels) == 1


def test_l4_inclusion_proof_index_bounds() -> None:
    leaves = [b"a"]
    with pytest.raises(IndexError):
        merkle_inclusion_proof(leaves, 1)
    with pytest.raises(IndexError):
        merkle_inclusion_proof(leaves, -1)


# --- L4 epoch round-trip via the store ---------------------------------------


def _make_card(sk, vk):  # type: ignore[no-untyped-def]
    return CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)


@pytest.mark.asyncio
async def test_l4_seal_epoch_round_trip(registry_store: RegistryStore) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk)
    assert isinstance(epoch, MerkleEpoch)
    assert epoch.tree_size >= 1
    assert epoch.root_hash and len(epoch.root_hash) == 32

    # Already-sealed events should be excluded next time.
    from vacant.registry.errors import RegistryWriteError

    with pytest.raises(RegistryWriteError):
        await registry_store.seal_epoch(signing_key=sk)


def test_l4_epoch_signature_verifies() -> None:
    sk, vk = keygen()
    root = b"\x42" * 32
    sig = sign_epoch_root(root=root, signing_key=sk)
    from vacant.registry.antitamper import verify_epoch_signature

    assert verify_epoch_signature(root=root, signature=sig, operator_pubkey=vk) is True
    assert verify_epoch_signature(root=b"\x00" * 32, signature=sig, operator_pubkey=vk) is False


# --- L5: anomaly counters ----------------------------------------------------


def test_l5_assess_anomaly_below_threshold() -> None:
    out = assess_anomaly(metric="rep_jump", value=0.1, threshold=0.4)
    assert out.triggered is False


def test_l5_assess_anomaly_at_threshold_triggers() -> None:
    out = assess_anomaly(metric="rep_jump", value=0.4, threshold=0.4)
    assert out.triggered is True


@pytest.mark.asyncio
async def test_l5_record_anomaly_persists_window(registry_store: RegistryStore) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    out = await registry_store.record_anomaly(
        vacant_id=VacantId.from_verify_key(vk).hex(),
        metric="rep_jump",
        value=0.5,
        threshold=0.4,
    )
    assert out.triggered is True


# --- L6: append-only -------------------------------------------------------


@pytest.mark.asyncio
async def test_l6_delete_event_rejected(registry_store: RegistryStore) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )

    # Try to delete the just-emitted register event via the ORM.
    from sqlmodel import select

    async with registry_store._sessionmaker() as s:
        res = await s.execute(select(Event).limit(1))
        row = res.scalar_one()
        await s.delete(row)
        with pytest.raises(AppendOnlyViolation):
            await s.commit()


@pytest.mark.asyncio
async def test_l6_delete_merkle_epoch_rejected(registry_store: RegistryStore) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk)
    async with registry_store._sessionmaker() as s:
        target = await s.get(MerkleEpoch, epoch.epoch_id)
        assert target is not None
        await s.delete(target)
        with pytest.raises(AppendOnlyViolation):
            await s.commit()


# --- canonical event bytes are deterministic --------------------------------


def test_canonical_event_bytes_is_deterministic() -> None:
    args = dict(
        event_type="register",
        actor_vacant_id="aa" * 32,
        subject_vacant_id=None,
        payload_hash=b"\x01" * 32,
        idempotency_key="idem",
        signed_by_pubkey=b"\x02" * 32,
        ts=12345,
        actor_seq=1,
    )
    a = canonical_event_bytes(**args)
    b = canonical_event_bytes(**args)
    assert a == b


def test_compute_event_hash_changes_on_signature_change() -> None:
    canonical = canonical_event_bytes(
        event_type="register",
        actor_vacant_id="aa" * 32,
        subject_vacant_id=None,
        payload_hash=b"\x01" * 32,
        idempotency_key="idem",
        signed_by_pubkey=b"\x02" * 32,
        ts=12345,
        actor_seq=1,
    )
    h1 = compute_event_hash(
        prev_event_hash=b"\x00" * 32, canonical_bytes=canonical, signature=b"\x01" * 64
    )
    h2 = compute_event_hash(
        prev_event_hash=b"\x00" * 32, canonical_bytes=canonical, signature=b"\x02" * 64
    )
    assert h1 != h2


def test_canonical_json_round_trip() -> None:
    a = canonical_json({"b": 2, "a": 1})
    b = canonical_json({"a": 1, "b": 2})
    assert a == b
    _ = time
    _ = hash_blake2b
    _ = SignedEventDraft
