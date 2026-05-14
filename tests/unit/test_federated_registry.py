"""Unit tests for `FederatedRegistryBackend` — M-of-N quorum reads over
N independent peer registries.

Covers:
- happy path: all peers agree → quorum returns the value
- one peer dissents but threshold still met → still returns value
- threshold not met → `QuorumDisagreement` with observed distribution
- one peer raises → counted as "no answer" but doesn't crash the quorum
- writes are rejected (federated MVP is read-only)
- `record_hash` is deterministic across structurally-equal rows
- construction-time misconfig (threshold > peers, threshold < 1)
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from vacant.core.crypto import keygen
from vacant.core.types import CapabilityCard, SubstrateSpec, VacantId, VacantState
from vacant.registry import (
    FederatedRegistryBackend,
    QuorumDisagreement,
    RegistryError,
    RegistryStore,
    publish_halo,
    record_hash,
)
from vacant.registry.models import Vacant


@pytest_asyncio.fixture
async def peer_pair() -> AsyncIterator[tuple[RegistryStore, RegistryStore]]:
    """Two fresh in-memory `RegistryStore`s. Each test seeds them
    however it likes — the federated layer doesn't replicate writes,
    so peers can be made to agree (by issuing the same writes) or
    disagree (by issuing different writes).
    """
    e1 = create_async_engine("sqlite+aiosqlite:///:memory:")
    e2 = create_async_engine("sqlite+aiosqlite:///:memory:")
    s1, s2 = RegistryStore(e1), RegistryStore(e2)
    await s1.init_schema()
    await s2.init_schema()
    try:
        yield s1, s2
    finally:
        await e1.dispose()
        await e2.dispose()


async def _publish_card_to(store: RegistryStore) -> tuple[VacantId, bytes]:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
    return vid, bytes(vk)


# --- construction -----------------------------------------------------------


@pytest.mark.asyncio
async def test_rejects_zero_threshold(peer_pair: tuple[RegistryStore, RegistryStore]) -> None:
    s1, _ = peer_pair
    with pytest.raises(ValueError):
        FederatedRegistryBackend([s1], threshold=0)


@pytest.mark.asyncio
async def test_rejects_threshold_above_peer_count(
    peer_pair: tuple[RegistryStore, RegistryStore],
) -> None:
    s1, _ = peer_pair
    with pytest.raises(ValueError):
        FederatedRegistryBackend([s1], threshold=2)


# --- record_hash determinism ------------------------------------------------


@pytest.mark.asyncio
async def test_record_hash_stable_for_same_vacant(
    peer_pair: tuple[RegistryStore, RegistryStore],
) -> None:
    """Two peers that successfully replicated the same vacant must
    produce identical `record_hash`es. This is the quorum primitive's
    correctness property: same row → same hash → same vote."""
    s1, s2 = peer_pair
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    for store in (s1, s2):
        await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
    v1 = await s1.get_vacant(vid.hex())
    v2 = await s2.get_vacant(vid.hex())
    assert v1 is not None and v2 is not None
    assert record_hash(v1) == record_hash(v2)


@pytest.mark.asyncio
async def test_record_hash_differs_on_divergent_state(
    peer_pair: tuple[RegistryStore, RegistryStore],
) -> None:
    s1, _ = peer_pair
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(store=s1, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
    v_before = await s1.get_vacant(vid.hex())
    # Mutate visibility in-place (just for hash comparison).
    assert v_before is not None
    v_after = Vacant(**{**v_before.model_dump(), "visibility": "NONE"})
    assert record_hash(v_before) != record_hash(v_after)


# --- quorum reads ------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vacant_with_full_agreement(
    peer_pair: tuple[RegistryStore, RegistryStore],
) -> None:
    s1, s2 = peer_pair
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    for store in (s1, s2):
        await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)

    fed = FederatedRegistryBackend([s1, s2], threshold=2)
    out = await fed.get_vacant(vid.hex())
    assert out is not None
    assert out.vacant_id == vid.hex()


@pytest.mark.asyncio
async def test_threshold_met_with_one_dissenter(
    peer_pair: tuple[RegistryStore, RegistryStore],
) -> None:
    """3-peer setup with 2-of-3 threshold: two peers see the vacant,
    one peer doesn't. Quorum returns the value the majority holds."""
    s1, s2 = peer_pair
    e3 = create_async_engine("sqlite+aiosqlite:///:memory:")
    s3 = RegistryStore(e3)
    try:
        await s3.init_schema()
        sk, vk = keygen()
        vid = VacantId.from_verify_key(vk)
        card = CapabilityCard(
            vacant_id=vid,
            capability_text="x",
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        ).signed(sk)
        # Only s1+s2 see the vacant; s3 doesn't.
        for store in (s1, s2):
            await publish_halo(
                store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk
            )

        fed = FederatedRegistryBackend([s1, s2, s3], threshold=2)
        out = await fed.get_vacant(vid.hex())
        assert out is not None
        assert out.vacant_id == vid.hex()
    finally:
        await e3.dispose()


@pytest.mark.asyncio
async def test_threshold_not_met_raises(
    peer_pair: tuple[RegistryStore, RegistryStore],
) -> None:
    """Two peers disagree (one has the vacant, one doesn't); threshold
    2 of 2 → cannot satisfy → `QuorumDisagreement`."""
    s1, s2 = peer_pair
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(store=s1, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
    # s2 doesn't know about this vacant.

    fed = FederatedRegistryBackend([s1, s2], threshold=2)
    with pytest.raises(QuorumDisagreement) as exc_info:
        await fed.get_vacant(vid.hex())
    # Disagreement carries the observed hash distribution.
    assert sum(exc_info.value.observed.values()) == 2


@pytest.mark.asyncio
async def test_peer_error_counts_as_no_answer(
    peer_pair: tuple[RegistryStore, RegistryStore],
) -> None:
    """A peer that raises should not crash the whole quorum read; it
    just contributes "no answer" to the count. With 2 healthy peers
    agreeing + 1 erroring peer at threshold=2, the read succeeds."""
    s1, s2 = peer_pair
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    for store in (s1, s2):
        await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)

    class _BrokenPeer:
        async def get_vacant(self, vacant_id: str) -> Vacant | None:
            del vacant_id
            raise RuntimeError("peer down")

        # Stubs so the Protocol is structurally satisfied at runtime.
        async def init_schema(self) -> None: ...
        async def insert_vacant(self, vacant: Vacant) -> None: ...
        async def update_vacant_status(self, vacant_id: str, status: str) -> None: ...
        async def update_vacant_visibility(self, vacant_id: str, visibility: str) -> None: ...

    broken = _BrokenPeer()
    fed = FederatedRegistryBackend([s1, s2, broken], threshold=2)  # type: ignore[list-item]
    out = await fed.get_vacant(vid.hex())
    assert out is not None
    assert out.vacant_id == vid.hex()


# --- writes are rejected ----------------------------------------------------


@pytest.mark.asyncio
async def test_writes_rejected(peer_pair: tuple[RegistryStore, RegistryStore]) -> None:
    s1, s2 = peer_pair
    fed = FederatedRegistryBackend([s1, s2], threshold=1)
    _sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    v = Vacant(
        vacant_id=vid.hex(),
        public_key=bytes(vk),
        base_model="m",
        base_model_family="f",
        version="0",
        declared_capabilities_json="[]",
        capability_card_hash=b"\x00" * 32,
        capability_card_sig=b"\x00" * 64,
        registered_at=0,
    )
    with pytest.raises(RegistryError):
        await fed.insert_vacant(v)
    with pytest.raises(RegistryError):
        await fed.update_vacant_status(vid.hex(), "active")


@pytest.mark.asyncio
async def test_search_capability_quorum(
    peer_pair: tuple[RegistryStore, RegistryStore],
) -> None:
    """A range read (returns a list) should still quorum-agree on the
    full sequence hash."""
    s1, s2 = peer_pair
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    for store in (s1, s2):
        await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)

    fed = FederatedRegistryBackend([s1, s2], threshold=2)
    rows: Sequence[Vacant] = await fed.search_capability(
        capability=None, family=None, status=None, visibility=None, limit=10
    )
    assert any(r.vacant_id == vid.hex() for r in rows)
