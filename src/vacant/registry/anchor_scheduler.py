"""Periodic anchor scheduler (technical.html §Lifecycle: registry
maintenance cadence).

The decentralised-trust primitives (`git_anchor`, `ots_anchor`,
`witness`) are explicit one-shot calls: an operator (or a registry
admin script) invokes them whenever they want. For production
deployments that's too manual — operators want "anchor every sealed
epoch automatically".

This module provides a `AnchorScheduler` background task that:

1. Periodically polls `RegistryStore` for sealed epochs without a
   `git_commit_sha` (un-anchored) and runs `anchor_epoch_to_git`.
2. Periodically polls for epochs with an `ots_proof_hash` but no
   `ots_upgraded_at` and *optionally* hits an OTS calendar via
   `submit_to_calendars` to upgrade them.

It is intentionally event-driven on top of a polling loop — we don't
need sub-second latency for anchoring, and the polling model lets
operators set the cadence with one number (`interval_s`).

Behaviour:

- **Best-effort.** A network outage or missing `git` binary skips the
  tick; the next tick retries.
- **Idempotent.** Re-running `anchor_epoch_to_git` on an
  already-anchored epoch is harmless (`git_anchor.try_anchor_to_git`
  does an allow-empty commit; the SHA gets refreshed).
- **Stoppable.** `stop()` short-circuits the sleep so shutdown is prompt.

Like `GossipReplicator`, the scheduler is async-loop-shaped:

    sched = AnchorScheduler(
        store=registry_store,
        git_repo="/var/lib/vacant/transparency-log",
        ots_submit=True,
    )
    task = asyncio.create_task(sched.run_forever(interval_s=600))
    ...
    sched.stop()
    await task
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlmodel import select

from vacant.registry.git_anchor import DEFAULT_GIT_BRANCH, GitAnchorError
from vacant.registry.models import MerkleEpoch
from vacant.registry.ots_anchor import (
    DEFAULT_CALENDAR_URLS,
    OTSAnchorError,
    submit_to_calendars,
)
from vacant.registry.store import RegistryStore

__all__ = [
    "AnchorScheduler",
    "AnchorSchedulerStats",
]


_log = logging.getLogger(__name__)


@dataclass
class AnchorSchedulerStats:
    """Outcome counters for a single scheduler tick.

    Tracked separately for git vs OTS so operators / dashboards can
    distinguish a git-only outage (transparency mirror down) from an
    OTS-only outage (calendar pool down).
    """

    ticks: int = 0
    epochs_git_anchored: int = 0
    epochs_git_failed: int = 0
    epochs_ots_upgraded: int = 0
    epochs_ots_failed: int = 0

    def merge(self, other: AnchorSchedulerStats) -> AnchorSchedulerStats:
        return AnchorSchedulerStats(
            ticks=self.ticks + other.ticks,
            epochs_git_anchored=self.epochs_git_anchored + other.epochs_git_anchored,
            epochs_git_failed=self.epochs_git_failed + other.epochs_git_failed,
            epochs_ots_upgraded=self.epochs_ots_upgraded + other.epochs_ots_upgraded,
            epochs_ots_failed=self.epochs_ots_failed + other.epochs_ots_failed,
        )


class AnchorScheduler:
    """Background task that anchors sealed epochs to git + OTS.

    Args:
        store: The local `RegistryStore`.
        git_repo: Path to the transparency-log git repo. `None` disables
            git anchoring (useful when the operator only wants OTS).
        git_branch: Branch on which to commit anchored payloads.
        git_remote: Optional remote URL for `git push`. `None` disables
            pushes.
        git_push: Whether to push after committing. Best-effort: a
            push failure is logged + counted but doesn't crash the tick.
        ots_submit: Whether to submit pending epochs to the live OTS
            calendar pool. Off by default — operators that want fully
            offline operation can run with `ots_anchor=True` at
            sealing time and rely on `record_ots_upgrade` later.
        ots_calendar_urls: Calendars to hit.
    """

    def __init__(
        self,
        *,
        store: RegistryStore,
        git_repo: str | None = None,
        git_branch: str = DEFAULT_GIT_BRANCH,
        git_remote: str | None = None,
        git_push: bool = False,
        ots_submit: bool = False,
        ots_calendar_urls: Sequence[str] = DEFAULT_CALENDAR_URLS,
    ) -> None:
        if git_repo is None and not ots_submit:
            raise ValueError("AnchorScheduler: at least one of git_repo / ots_submit must be set")
        self._store = store
        self._git_repo = git_repo
        self._git_branch = git_branch
        self._git_remote = git_remote
        self._git_push = git_push
        self._ots_submit = ots_submit
        self._ots_urls = tuple(ots_calendar_urls)
        self._stop = asyncio.Event()
        self._cumulative = AnchorSchedulerStats()

    @property
    def cumulative_stats(self) -> AnchorSchedulerStats:
        """Stats summed across every tick this scheduler has run.

        Useful for dashboards. Resets only when the scheduler is
        recreated; we don't expose a zeroing API because monotonic
        counters are the easier shape to reason about.
        """
        return self._cumulative

    async def tick(self) -> AnchorSchedulerStats:
        """Run one anchor cycle. Returns the tick's outcome counters."""
        stats = AnchorSchedulerStats(ticks=1)
        epochs = await self._list_pending_epochs()
        for ep in epochs:
            if self._git_repo and ep.git_commit_sha is None:
                ok = await self._do_git_anchor(int(ep.epoch_id or 0))
                if ok:
                    stats.epochs_git_anchored += 1
                else:
                    stats.epochs_git_failed += 1
            if self._ots_submit and ep.ots_proof_hash is not None and ep.ots_upgraded_at is None:
                ok = await self._do_ots_upgrade(ep)
                if ok:
                    stats.epochs_ots_upgraded += 1
                else:
                    stats.epochs_ots_failed += 1
        self._cumulative = self._cumulative.merge(stats)
        return stats

    async def run_forever(self, *, interval_s: float = 600.0) -> None:
        """Run `tick()` on a loop until `stop()` is signalled.

        `interval_s` defaults to 10 minutes — sealed epochs are
        infrequent enough that this gives a healthy debounce.
        """
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception:
                _log.exception("AnchorScheduler tick raised; continuing")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval_s)
            except TimeoutError:
                continue

    def stop(self) -> None:
        """Signal `run_forever` to exit after its current tick."""
        self._stop.set()

    # --- internals ----------------------------------------------------------

    async def _list_pending_epochs(self) -> list[MerkleEpoch]:
        """Epochs with at least one pending anchor task. Sorted by id.

        We pull every epoch and filter in Python rather than crafting a
        OR-of-NULL SQL — schema readability > query cleverness for a
        cadence-limited operation.
        """
        async with self._store._sessionmaker() as s:
            res = await s.execute(select(MerkleEpoch).order_by(MerkleEpoch.epoch_id))  # type: ignore[arg-type]
            rows = list(res.scalars().all())
        pending: list[MerkleEpoch] = []
        for ep in rows:
            needs_git = self._git_repo is not None and ep.git_commit_sha is None
            needs_ots = (
                self._ots_submit and ep.ots_proof_hash is not None and ep.ots_upgraded_at is None
            )
            if needs_git or needs_ots:
                pending.append(ep)
        return pending

    async def _do_git_anchor(self, epoch_id: int) -> bool:
        """Anchor a single epoch to git. Returns True on success."""
        assert self._git_repo is not None
        try:
            await self._store.anchor_epoch_to_git(
                epoch_id,
                repo_path=self._git_repo,
                branch=self._git_branch,
                remote_url=self._git_remote,
                push=self._git_push,
            )
            return True
        except GitAnchorError as exc:
            _log.warning("AnchorScheduler git anchor failed for epoch %s: %s", epoch_id, exc)
            return False

    async def _do_ots_upgrade(self, ep: MerkleEpoch) -> bool:
        """Submit the epoch's root to live OTS calendars and persist the
        resulting upgraded proof. Returns True on success.

        We accept the first calendar receipt that came back as "real"
        (the magic-header check); calendars that returned a partial
        receipt without the magic header are skipped — the schema
        requires a real `.ots` blob.
        """
        try:
            receipts = await submit_to_calendars(digest=ep.root_hash, calendar_urls=self._ots_urls)
        except OTSAnchorError as exc:
            _log.warning(
                "AnchorScheduler OTS submit failed for epoch %s: %s",
                ep.epoch_id,
                exc,
            )
            return False
        real = next((r for r in receipts if r.is_real), None)
        if real is None:
            return False
        try:
            await self._store.record_ots_upgrade(
                int(ep.epoch_id or 0), upgraded_bytes=real.proof_bytes
            )
            return True
        except OTSAnchorError as exc:
            _log.warning(
                "AnchorScheduler OTS persist failed for epoch %s: %s",
                ep.epoch_id,
                exc,
            )
            return False
