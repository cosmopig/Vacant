"""Unit tests for `vacant.registry.witness` — federated M-of-N witness
cosignatures on epoch roots (decentralised trust layer).

Covers:
- `WitnessRootSet` validation (threshold, dups, key shape)
- `build_witness_statement` binds every epoch field
- `issue_witness_cosignature` round-trips via `verify_witness_cosignature`
- `verify_witness_quorum` requires distinct valid signers
- store integration: `record_witness_cosignature` persists rows;
  duplicate `(epoch, witness)` is rejected; `list_epoch_witnesses` round-trips
- replay attack: a witness's signature on epoch A cannot be replayed
  against epoch B.
"""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import CapabilityCard, SubstrateSpec, VacantId, VacantState
from vacant.registry import (
    MerkleEpoch,
    RegistryStore,
    RegistryWriteError,
    WitnessCosignature,
    WitnessError,
    WitnessRootSet,
    build_witness_statement,
    issue_witness_cosignature,
    publish_halo,
    verify_witness_cosignature,
    verify_witness_quorum,
)


def _make_card(sk, vk):  # type: ignore[no-untyped-def]
    return CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)


def _fake_epoch(*, epoch_id: int = 1, root: bytes = b"\xab" * 32) -> MerkleEpoch:
    return MerkleEpoch(
        epoch_id=epoch_id,
        first_seq=1,
        last_seq=4,
        tree_size=4,
        root_hash=root,
        sealed_at=1_700_000_000_000,
        registry_signature=b"\xcd" * 64,
    )


# --- WitnessRootSet validation ----------------------------------------------


def test_rootset_rejects_zero_threshold() -> None:
    _sk, vk = keygen()
    with pytest.raises(WitnessError):
        WitnessRootSet(threshold=0, keys=(bytes(vk),))


def test_rootset_rejects_threshold_exceeds_keys() -> None:
    _sk, vk = keygen()
    with pytest.raises(WitnessError):
        WitnessRootSet(threshold=3, keys=(bytes(vk),))


def test_rootset_rejects_short_key() -> None:
    with pytest.raises(WitnessError):
        WitnessRootSet(threshold=1, keys=(b"too short",))


def test_rootset_rejects_duplicate_keys() -> None:
    _sk, vk = keygen()
    with pytest.raises(WitnessError):
        WitnessRootSet(threshold=1, keys=(bytes(vk), bytes(vk)))


# --- witness statement & cosignature ----------------------------------------


def test_build_statement_rejects_unpersisted_epoch() -> None:
    bad = MerkleEpoch(
        epoch_id=None,
        first_seq=1,
        last_seq=1,
        tree_size=1,
        root_hash=b"\x00" * 32,
        sealed_at=0,
        registry_signature=b"\x00" * 64,
    )
    with pytest.raises(WitnessError):
        build_witness_statement(bad)


def test_statement_depends_on_root() -> None:
    e1 = _fake_epoch(root=b"\x11" * 32)
    e2 = _fake_epoch(root=b"\x22" * 32)
    assert build_witness_statement(e1) != build_witness_statement(e2)


def test_statement_depends_on_epoch_id() -> None:
    e1 = _fake_epoch(epoch_id=1)
    e2 = _fake_epoch(epoch_id=2)
    assert build_witness_statement(e1) != build_witness_statement(e2)


def test_cosignature_round_trip() -> None:
    sk, vk = keygen()
    epoch = _fake_epoch()
    cos = issue_witness_cosignature(
        epoch=epoch,
        witness_id="witness-a",
        witness_signing_key=sk,
        witness_pubkey=bytes(vk),
    )
    assert verify_witness_cosignature(epoch=epoch, cosignature=cos) is True


def test_cosignature_does_not_verify_on_different_epoch() -> None:
    """Replay protection: a witness's signature on epoch A must NOT
    verify against epoch B with a different root."""
    sk, vk = keygen()
    e1 = _fake_epoch(epoch_id=1, root=b"\x11" * 32)
    e2 = _fake_epoch(epoch_id=2, root=b"\x22" * 32)
    cos = issue_witness_cosignature(
        epoch=e1,
        witness_id="witness-a",
        witness_signing_key=sk,
        witness_pubkey=bytes(vk),
    )
    assert verify_witness_cosignature(epoch=e1, cosignature=cos) is True
    assert verify_witness_cosignature(epoch=e2, cosignature=cos) is False


def test_cosignature_does_not_verify_with_wrong_pubkey() -> None:
    sk1, vk1 = keygen()
    _sk2, vk2 = keygen()
    epoch = _fake_epoch()
    # Sign with sk1 but claim vk2 as the witness — verification must fail.
    cos = issue_witness_cosignature(
        epoch=epoch,
        witness_id="witness-a",
        witness_signing_key=sk1,
        witness_pubkey=bytes(vk2),
    )
    assert verify_witness_cosignature(epoch=epoch, cosignature=cos) is False
    _ = vk1


# --- quorum verification ----------------------------------------------------


def test_quorum_satisfied_at_threshold() -> None:
    keys = [keygen() for _ in range(3)]
    rootset = WitnessRootSet(threshold=2, keys=tuple(bytes(vk) for _sk, vk in keys))
    epoch = _fake_epoch()
    cosignatures = [
        issue_witness_cosignature(
            epoch=epoch,
            witness_id=f"w-{i}",
            witness_signing_key=sk,
            witness_pubkey=bytes(vk),
        )
        for i, (sk, vk) in enumerate(keys[:2])
    ]
    assert verify_witness_quorum(epoch=epoch, cosignatures=cosignatures, rootset=rootset) is True


def test_quorum_insufficient_when_below_threshold() -> None:
    keys = [keygen() for _ in range(3)]
    rootset = WitnessRootSet(threshold=2, keys=tuple(bytes(vk) for _sk, vk in keys))
    epoch = _fake_epoch()
    cosignatures = [
        issue_witness_cosignature(
            epoch=epoch,
            witness_id="w-0",
            witness_signing_key=keys[0][0],
            witness_pubkey=bytes(keys[0][1]),
        )
    ]
    assert verify_witness_quorum(epoch=epoch, cosignatures=cosignatures, rootset=rootset) is False


def test_quorum_ignores_signers_outside_rootset() -> None:
    """A witness whose pubkey isn't in the configured set contributes zero
    toward quorum, even with a valid signature."""
    in_keys = [keygen() for _ in range(2)]
    rootset = WitnessRootSet(threshold=2, keys=tuple(bytes(vk) for _sk, vk in in_keys))
    out_sk, out_vk = keygen()
    epoch = _fake_epoch()
    cosignatures = [
        issue_witness_cosignature(
            epoch=epoch,
            witness_id="outsider",
            witness_signing_key=out_sk,
            witness_pubkey=bytes(out_vk),
        ),
        issue_witness_cosignature(
            epoch=epoch,
            witness_id="w-0",
            witness_signing_key=in_keys[0][0],
            witness_pubkey=bytes(in_keys[0][1]),
        ),
    ]
    # Threshold is 2 but only one in-set signer is present.
    assert verify_witness_quorum(epoch=epoch, cosignatures=cosignatures, rootset=rootset) is False


def test_quorum_counts_each_signer_once() -> None:
    """Same witness submitting the same cosignature multiple times must
    not satisfy a threshold > 1. This is the classic Sybil guard the
    federated layer is supposed to provide."""
    keys = [keygen() for _ in range(2)]
    rootset = WitnessRootSet(threshold=2, keys=tuple(bytes(vk) for _sk, vk in keys))
    epoch = _fake_epoch()
    repeat = issue_witness_cosignature(
        epoch=epoch,
        witness_id="w-0",
        witness_signing_key=keys[0][0],
        witness_pubkey=bytes(keys[0][1]),
    )
    assert (
        verify_witness_quorum(epoch=epoch, cosignatures=[repeat, repeat, repeat], rootset=rootset)
        is False
    )


# --- store integration ------------------------------------------------------


@pytest.mark.asyncio
async def test_record_witness_persists_row(
    registry_store: RegistryStore,
) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk)

    w_sk, w_vk = keygen()
    cos = issue_witness_cosignature(
        epoch=epoch,
        witness_id="witness-a",
        witness_signing_key=w_sk,
        witness_pubkey=bytes(w_vk),
    )
    row = await registry_store.record_witness_cosignature(int(epoch.epoch_id or 0), cos)
    assert row.witness_id == "witness-a"
    assert row.cosignature == cos.signature

    rows = await registry_store.list_epoch_witnesses(int(epoch.epoch_id or 0))
    assert len(rows) == 1
    assert rows[0].witness_pubkey == bytes(w_vk)


@pytest.mark.asyncio
async def test_record_witness_rejects_invalid_signature(
    registry_store: RegistryStore,
) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk)
    _, w_vk = keygen()
    bogus = WitnessCosignature(
        witness_id="forger",
        witness_pubkey=bytes(w_vk),
        signature=b"\x00" * 64,  # not a real sig
    )
    with pytest.raises(WitnessError):
        await registry_store.record_witness_cosignature(int(epoch.epoch_id or 0), bogus)


@pytest.mark.asyncio
async def test_record_witness_duplicate_rejected(
    registry_store: RegistryStore,
) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk)

    w_sk, w_vk = keygen()
    cos = issue_witness_cosignature(
        epoch=epoch,
        witness_id="witness-a",
        witness_signing_key=w_sk,
        witness_pubkey=bytes(w_vk),
    )
    await registry_store.record_witness_cosignature(int(epoch.epoch_id or 0), cos)
    with pytest.raises(RegistryWriteError):
        await registry_store.record_witness_cosignature(int(epoch.epoch_id or 0), cos)


@pytest.mark.asyncio
async def test_store_quorum_round_trip(registry_store: RegistryStore) -> None:
    """End-to-end: 2-of-3 witnesses cosign a real sealed epoch, and a
    verifier reading from the store gets quorum=True. This is the
    happy-path decentralised-trust assertion the technical.html row 4
    asks for."""
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk)

    witness_keys = [keygen() for _ in range(3)]
    rootset = WitnessRootSet(threshold=2, keys=tuple(bytes(vk) for _sk, vk in witness_keys))
    for i, (w_sk, w_vk) in enumerate(witness_keys[:2]):
        cos = issue_witness_cosignature(
            epoch=epoch,
            witness_id=f"witness-{i}",
            witness_signing_key=w_sk,
            witness_pubkey=bytes(w_vk),
        )
        await registry_store.record_witness_cosignature(int(epoch.epoch_id or 0), cos)

    persisted = await registry_store.list_epoch_witnesses(int(epoch.epoch_id or 0))
    assert verify_witness_quorum(epoch=epoch, cosignatures=persisted, rootset=rootset) is True
