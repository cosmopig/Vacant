"""Aggregation/index layer over the central store.

`search_capability` does substring + filter matching on the index columns;
`rank_by_reputation` defers to a `ReputationOracle` Protocol that P3
plugs in. For now the default oracle returns 0.0 for everyone, so
ordering falls back to insertion order — but the API is stable.

`lineage_query` walks the lineage edge in either direction.

Result objects always include the halo signature so consumers can
verify the card independently of the registry's say-so (THEORY_V5 §7.1
trust-anchor-not-trust-origin).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from vacant.core.types import CapabilityCard
from vacant.protocol.capability_card import deserialize as deserialize_card
from vacant.protocol.errors import EnvelopeFormatError, UnsupportedHaloVersionError
from vacant.registry.errors import NotFoundError
from vacant.registry.models import Vacant
from vacant.registry.store import RegistryStore
from vacant.registry.visibility import Visibility

__all__ = [
    "DEFAULT_REPUTATION_ORACLE",
    "HaloMatch",
    "ReputationOracle",
    "lineage_query",
    "rank_by_reputation",
    "search_capability",
]


@dataclass(frozen=True)
class HaloMatch:
    """A single search/rank result.

    Carries the halo signature *and* the full signed `CapabilityCard`
    (D015 §C) so the caller can verify the card and dispatch directly to
    `card.endpoint` in a single round-trip — no registry rehydration.
    `capability_card` is optional only for legacy rows written before
    the blob column existed; new rows always carry one.
    """

    vacant_id: str
    capability_card_hash: bytes
    capability_card_sig: bytes
    declared_capabilities_json: str
    base_model_family: str
    visibility: Visibility
    score: float = 0.0
    capability_card: CapabilityCard | None = None


class ReputationOracle(Protocol):
    """P3 plugs in here; for P4 we ship a stub that returns 0.0."""

    async def score(self, vacant_id: str, dimensions: Sequence[str]) -> float: ...


class _ZeroOracle:
    async def score(self, vacant_id: str, dimensions: Sequence[str]) -> float:
        _ = (vacant_id, dimensions)
        return 0.0


DEFAULT_REPUTATION_ORACLE: ReputationOracle = _ZeroOracle()


def _deserialize_card_safe(blob: bytes) -> CapabilityCard | None:
    if not blob:
        return None
    try:
        return deserialize_card(blob)
    except (EnvelopeFormatError, UnsupportedHaloVersionError):
        # Legacy / malformed row: caller can fall back to the index columns.
        return None


def _to_match(v: Vacant, score: float = 0.0) -> HaloMatch:
    return HaloMatch(
        vacant_id=v.vacant_id,
        capability_card_hash=v.capability_card_hash,
        capability_card_sig=v.capability_card_sig,
        declared_capabilities_json=v.declared_capabilities_json,
        base_model_family=v.base_model_family,
        visibility=Visibility(v.visibility),
        score=score,
        capability_card=_deserialize_card_safe(v.capability_card_blob),
    )


async def search_capability(
    *,
    store: RegistryStore,
    query: str | None = None,
    family: str | None = None,
    limit: int = 20,
    include_local: bool = False,
) -> list[HaloMatch]:
    """Search the registry index. NONE-visibility halos are excluded by
    default — `include_local=True` is for owner/parent direct paths and
    callers must additionally enforce that the requester is the owner.
    """
    visibility_filter = None if include_local else Visibility.PUBLIC.value
    rows = await store.search_capability(
        capability=query,
        family=family,
        status="active",
        visibility=visibility_filter,
        limit=limit,
    )
    return [_to_match(r) for r in rows]


async def rank_by_reputation(
    matches: Sequence[HaloMatch],
    *,
    dimensions: Sequence[str] = ("factual", "logical", "relevance"),
    oracle: ReputationOracle = DEFAULT_REPUTATION_ORACLE,
) -> list[HaloMatch]:
    """Re-score and sort `matches` using `oracle`. Stable for ties."""
    scored: list[HaloMatch] = []
    for m in matches:
        s = await oracle.score(m.vacant_id, dimensions)
        scored.append(
            HaloMatch(
                vacant_id=m.vacant_id,
                capability_card_hash=m.capability_card_hash,
                capability_card_sig=m.capability_card_sig,
                declared_capabilities_json=m.declared_capabilities_json,
                base_model_family=m.base_model_family,
                visibility=m.visibility,
                score=s,
                capability_card=m.capability_card,
            )
        )
    scored.sort(key=lambda m: m.score, reverse=True)
    return scored


async def lineage_query(
    *,
    store: RegistryStore,
    vacant_id: str,
    direction: Literal["descendants", "ancestors"] = "descendants",
    depth: int = 8,
) -> list[str]:
    """Walk the lineage edge and return a list of vacant_ids."""
    target = await store.get_vacant(vacant_id)
    if target is None:
        raise NotFoundError(vacant_id)
    if direction == "descendants":
        rows = await store.list_descendants(vacant_id, max_depth=depth)
    else:
        rows = await store.list_ancestors(vacant_id, max_depth=depth)
    return [r.vacant_id for r in rows]
