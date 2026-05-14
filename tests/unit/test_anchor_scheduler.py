"""C10 — Anchor scheduler background task."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import CapabilityCard, SubstrateSpec, VacantId, VacantState
from vacant.registry import (
    AnchorScheduler,
    AnchorSchedulerStats,
    RegistryStore,
    publish_halo,
)


async def _publish_one(store: RegistryStore) -> None:
    sk, vk = keygen()
    card = CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)


def test_anchor_scheduler_rejects_no_targets(registry_store: RegistryStore) -> None:
    """Constructing without git_repo AND without ots_submit makes no
    sense — the scheduler has nothing to do. Fail at construction."""
    with pytest.raises(ValueError):
        AnchorScheduler(store=registry_store)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.asyncio
async def test_anchor_scheduler_tick_anchors_pending_epochs(
    registry_store: RegistryStore, tmp_path: Path
) -> None:
    sk, _vk = keygen()
    await _publish_one(registry_store)
    epoch = await registry_store.seal_epoch(signing_key=sk)
    assert epoch.git_commit_sha is None

    sched = AnchorScheduler(store=registry_store, git_repo=str(tmp_path / "log"))
    stats = await sched.tick()
    assert stats.ticks == 1
    assert stats.epochs_git_anchored == 1
    refreshed = await registry_store.get_merkle_epoch(int(epoch.epoch_id or 0))
    assert refreshed is not None
    assert refreshed.git_commit_sha is not None


@pytest.mark.asyncio
async def test_anchor_scheduler_tick_noop_when_nothing_pending(
    registry_store: RegistryStore, tmp_path: Path
) -> None:
    """No sealed epochs → the tick should report zero of everything,
    not crash."""
    sched = AnchorScheduler(store=registry_store, git_repo=str(tmp_path / "log"))
    stats = await sched.tick()
    assert stats.ticks == 1
    assert stats.epochs_git_anchored == 0
    assert stats.epochs_git_failed == 0


def test_anchor_scheduler_stats_merge() -> None:
    a = AnchorSchedulerStats(ticks=1, epochs_git_anchored=2, epochs_ots_upgraded=1)
    b = AnchorSchedulerStats(ticks=1, epochs_git_failed=1)
    merged = a.merge(b)
    assert merged.ticks == 2
    assert merged.epochs_git_anchored == 2
    assert merged.epochs_git_failed == 1
    assert merged.epochs_ots_upgraded == 1


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.asyncio
async def test_anchor_scheduler_cumulative_stats_aggregate(
    registry_store: RegistryStore, tmp_path: Path
) -> None:
    """Cumulative stats should sum across ticks."""
    sk, _vk = keygen()
    await _publish_one(registry_store)
    await registry_store.seal_epoch(signing_key=sk)

    sched = AnchorScheduler(store=registry_store, git_repo=str(tmp_path / "log"))
    await sched.tick()  # anchors the one epoch
    await sched.tick()  # no-op (epoch already anchored)
    assert sched.cumulative_stats.ticks == 2
    assert sched.cumulative_stats.epochs_git_anchored == 1
