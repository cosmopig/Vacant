"""Aggregation/index tests."""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.registry import (
    HaloMatch,
    NotFoundError,
    RegistryStore,
    Visibility,
    lineage_query,
    publish_halo,
    rank_by_reputation,
    search_capability,
)
from vacant.registry.aggregation import ReputationOracle


async def _publish(
    store: RegistryStore,
    *,
    capability: str,
    state: VacantState = VacantState.ACTIVE,
    family: str = "claude",
    parent_id: str | None = None,
):  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text=capability,
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    rec = await publish_halo(
        store=store,
        card=card,
        runtime_state=state,
        signing_key=sk,
        base_model_family=family,
        parent_id=parent_id,
    )
    return rec, sk, vid


@pytest.mark.asyncio
async def test_search_returns_matching_capability(
    registry_store: RegistryStore,
) -> None:
    await _publish(registry_store, capability="legal-research")
    await _publish(registry_store, capability="image-gen", family="gemini")

    matches = await search_capability(store=registry_store, query="legal-research", limit=10)
    assert len(matches) == 1
    assert "legal-research" in matches[0].declared_capabilities_json


@pytest.mark.asyncio
async def test_search_excludes_local_visibility_by_default(
    registry_store: RegistryStore,
) -> None:
    await _publish(registry_store, capability="local-thing", state=VacantState.LOCAL)
    matches = await search_capability(store=registry_store, query="local-thing", limit=10)
    assert matches == []


@pytest.mark.asyncio
async def test_search_filter_by_family(registry_store: RegistryStore) -> None:
    await _publish(registry_store, capability="x", family="claude")
    await _publish(registry_store, capability="x", family="gemini")
    claude_only = await search_capability(store=registry_store, query="x", family="claude")
    assert len(claude_only) == 1
    assert claude_only[0].base_model_family == "claude"


@pytest.mark.asyncio
async def test_rank_by_reputation_with_zero_oracle_preserves_inputs(
    registry_store: RegistryStore,
) -> None:
    await _publish(registry_store, capability="thing")
    matches = await search_capability(store=registry_store, query="thing", limit=10)
    ranked = await rank_by_reputation(matches)
    assert len(ranked) == len(matches)
    assert all(m.score == 0.0 for m in ranked)


@pytest.mark.asyncio
async def test_rank_by_reputation_with_custom_oracle(
    registry_store: RegistryStore,
) -> None:
    rec_a, _, _ = await _publish(registry_store, capability="x", family="claude")
    rec_b, _, _ = await _publish(registry_store, capability="x", family="gemini")

    class FavorClaudeOracle:
        async def score(self, vacant_id: str, dimensions) -> float:  # type: ignore[no-untyped-def]
            v = await registry_store.get_vacant(vacant_id)
            return 1.0 if v and v.base_model_family == "claude" else 0.0

    matches = await search_capability(store=registry_store, query="x", limit=10)
    ranked = await rank_by_reputation(matches, oracle=FavorClaudeOracle())
    assert ranked[0].score == 1.0
    assert ranked[0].vacant_id == rec_a.vacant_id
    _ = rec_b


@pytest.mark.asyncio
async def test_lineage_descendants(registry_store: RegistryStore) -> None:
    parent_rec, _, _parent_vid = await _publish(registry_store, capability="parent")
    await _publish(
        registry_store,
        capability="child1",
        parent_id=parent_rec.vacant_id,
    )
    await _publish(
        registry_store,
        capability="child2",
        parent_id=parent_rec.vacant_id,
    )
    descendants = await lineage_query(
        store=registry_store, vacant_id=parent_rec.vacant_id, direction="descendants"
    )
    assert len(descendants) == 2


@pytest.mark.asyncio
async def test_lineage_ancestors(registry_store: RegistryStore) -> None:
    g_rec, _, _ = await _publish(registry_store, capability="grandparent")
    p_rec, _, _ = await _publish(registry_store, capability="parent", parent_id=g_rec.vacant_id)
    c_rec, _, _ = await _publish(registry_store, capability="child", parent_id=p_rec.vacant_id)
    chain = await lineage_query(
        store=registry_store, vacant_id=c_rec.vacant_id, direction="ancestors"
    )
    assert chain == [p_rec.vacant_id, g_rec.vacant_id]


@pytest.mark.asyncio
async def test_lineage_unknown_raises(registry_store: RegistryStore) -> None:
    with pytest.raises(NotFoundError):
        await lineage_query(store=registry_store, vacant_id="ghost")


def test_halo_match_immutable() -> None:
    m = HaloMatch(
        vacant_id="aa",
        capability_card_hash=b"\x01",
        capability_card_sig=b"\x02",
        declared_capabilities_json="[]",
        base_model_family="x",
        visibility=Visibility.PUBLIC,
    )
    with pytest.raises(Exception):  # noqa: B017 (frozen-dataclass FrozenInstanceError)
        m.score = 5.0  # type: ignore[misc]


def test_reputation_oracle_protocol_runtime_check() -> None:
    """ReputationOracle is a Protocol — any class with `score` works."""

    class MyOracle:
        async def score(self, vacant_id: str, dimensions) -> float:  # type: ignore[no-untyped-def]
            return 0.5

    o: ReputationOracle = MyOracle()
    assert o is not None
