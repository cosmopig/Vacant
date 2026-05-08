"""Replay protection — per-pair sequence + chain-tip tracking.

P6 §6 / dispatch §6: every `(from_vacant_id, to_vacant_id)` pair has its
own monotonic `sequence_no` counter and `chain_tip` (last envelope's
hash). An incoming envelope is rejected if:

- `sequence_no <= last_seen[(from, to)]`, OR
- `prev_envelope_hash != stored_chain_tip[(from, to)]`.

A new pair starts at `sequence_no = 1` and `chain_tip = EMPTY_PREV_HASH`.

Race protection (F-C). The MVP previously stored one row per `(from,
to)` pair with `last_sequence_no` updated in place, plus an in-process
`asyncio.Lock`. Under multi-worker deployment two workers could both
read the same `last_sequence_no = N`, both pass the monotonicity
check, and both try to advance to `N + 1`. The fix: store one row
**per accepted envelope**, with composite primary key
`(from_vid_hex, to_vid_hex, sequence_no)`. Concurrent writes claiming
the same triple collide on the PK at INSERT time and surface as
`IntegrityError`, which the store re-raises as
`ReplayDetectedError`. The "current state" of a pair is simply the
row with the largest `sequence_no` for that pair.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import LargeBinary
from sqlalchemy import desc as sa_desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import Column, Field, SQLModel, select

from vacant.core.types import EMPTY_PREV_HASH, VacantId
from vacant.protocol.envelope import VacantEnvelope
from vacant.protocol.errors import ChainForkError, ReplayDetectedError

__all__ = [
    "InMemoryReplayStore",
    "PairKey",
    "ReplayState",
    "ReplayStore",
    "SqliteReplayStore",
    "check_envelope",
]


@dataclass(frozen=True)
class PairKey:
    """Unordered (sender, recipient) pair key for the replay store."""

    from_vid: VacantId
    to_vid: VacantId

    @classmethod
    def from_envelope(cls, env: VacantEnvelope) -> PairKey:
        return cls(from_vid=env.from_vacant_id, to_vid=env.to_vacant_id)


@dataclass(frozen=True)
class ReplayState:
    """Replay store state for one pair."""

    last_sequence_no: int
    """Last accepted envelope's sequence_no on this pair (0 = none yet)."""
    chain_tip: bytes
    """Hash of the last accepted envelope (or EMPTY_PREV_HASH for new pair)."""


class ReplayStore(Protocol):
    """Backend contract. Both impls must be safe under concurrent writes."""

    async def get(self, key: PairKey) -> ReplayState: ...

    async def check_and_advance(
        self,
        env: VacantEnvelope,
    ) -> None:
        """Advance the per-pair state for `env`, raising
        `ReplayDetectedError` / `ChainForkError` on rejection."""
        ...


# --- in-memory impl ---------------------------------------------------------


class InMemoryReplayStore:
    """Reference impl backed by a dict. Used by tests + demo orchestrator.

    Not durable; not shared across processes. The `SqliteReplayStore`
    wraps the same contract over SQLAlchemy.
    """

    def __init__(self) -> None:
        self._state: dict[PairKey, ReplayState] = {}
        self._lock = asyncio.Lock()

    def seed(self, key: PairKey, state: ReplayState) -> None:
        """Pre-load the per-pair state from disk / another snapshot.

        Used by the CLI (Pfix3 B6) to rehydrate the response chain on
        ``vacant call`` so a target's reply seq=N+1 is recognised after
        a process restart. Synchronous (no lock): callers must seed
        before the store sees concurrent traffic.
        """
        self._state[key] = state

    async def get(self, key: PairKey) -> ReplayState:
        async with self._lock:
            return self._state.get(key, ReplayState(last_sequence_no=0, chain_tip=EMPTY_PREV_HASH))

    async def check_and_advance(self, env: VacantEnvelope) -> None:
        key = PairKey.from_envelope(env)
        async with self._lock:
            cur = self._state.get(key, ReplayState(last_sequence_no=0, chain_tip=EMPTY_PREV_HASH))
            _check(env, cur)
            self._state[key] = ReplayState(
                last_sequence_no=env.sequence_no,
                chain_tip=env.compute_hash(),
            )


# --- SQLite impl -----------------------------------------------------------


class _ReplayRow(SQLModel, table=True):
    """One accepted envelope per row, keyed by `(from, to, sequence_no)`.

    F-C: the previous schema stored one row per pair with
    `last_sequence_no` updated in place; concurrent writers could both
    pass the monotonicity check and both try to advance. The composite
    PK `(from_vid_hex, to_vid_hex, sequence_no)` makes that race
    impossible — the second insert collides at the DB level. The
    "current state" of a pair is the row with the maximum
    `sequence_no` for that pair.
    """

    __tablename__ = "replay_protect"

    from_vid_hex: str = Field(primary_key=True)
    to_vid_hex: str = Field(primary_key=True)
    sequence_no: int = Field(primary_key=True)
    chain_tip: bytes = Field(sa_column=Column(LargeBinary, nullable=False), default=EMPTY_PREV_HASH)


class SqliteReplayStore:
    """SQLAlchemy/aiosqlite-backed replay store with PK-enforced uniqueness."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        self._lock = asyncio.Lock()

    async def init_schema(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(_ReplayRow.metadata.create_all)

    async def get(self, key: PairKey) -> ReplayState:
        """Read the latest row for a pair (largest `sequence_no`).

        The PK already guarantees no duplicate `(from, to, seq)` so the
        ordering is well-defined. New pairs return the empty state.
        """
        async with self._sm() as s:
            row = await s.execute(
                select(_ReplayRow)
                .where(
                    _ReplayRow.from_vid_hex == key.from_vid.hex(),
                    _ReplayRow.to_vid_hex == key.to_vid.hex(),
                )
                .order_by(sa_desc(_ReplayRow.sequence_no))  # type: ignore[arg-type]
                .limit(1)
            )
            r = row.scalar_one_or_none()
            if r is None:
                return ReplayState(last_sequence_no=0, chain_tip=EMPTY_PREV_HASH)
            return ReplayState(last_sequence_no=r.sequence_no, chain_tip=r.chain_tip)

    async def check_and_advance(self, env: VacantEnvelope) -> None:
        """Validate the envelope and atomically record its acceptance.

        The fast-path check uses the in-process `_lock` to avoid wasted
        work; the load-bearing race defense is the PK uniqueness on
        `(from, to, sequence_no)`. If two workers (or two coroutines
        that both hold their own copy of `_lock`) both pass `_check`
        and both try to insert the same triple, the second INSERT
        raises `IntegrityError` and we surface it as
        `ReplayDetectedError`.
        """
        key = PairKey.from_envelope(env)
        async with self._lock:
            cur = await self.get(key)
            _check(env, cur)
            row = _ReplayRow(
                from_vid_hex=key.from_vid.hex(),
                to_vid_hex=key.to_vid.hex(),
                sequence_no=env.sequence_no,
                chain_tip=env.compute_hash(),
            )
            async with self._sm() as s:
                s.add(row)
                try:
                    await s.commit()
                except IntegrityError as exc:
                    await s.rollback()
                    raise ReplayDetectedError(
                        f"replay/race: envelope (from={key.from_vid.short()}, "
                        f"to={key.to_vid.short()}, seq={env.sequence_no}) "
                        "already accepted (PK collision; concurrent writer beat us)"
                    ) from exc


# --- shared check ----------------------------------------------------------


def _check(env: VacantEnvelope, current: ReplayState) -> None:
    if env.sequence_no <= current.last_sequence_no:
        raise ReplayDetectedError(
            f"replay/out-of-order envelope: seq {env.sequence_no} "
            f"<= last_seen {current.last_sequence_no}"
        )
    if env.sequence_no != current.last_sequence_no + 1:
        # Strict +1 monotonicity, matching P4 §3 spec ("tolerance: 0").
        raise ReplayDetectedError(
            f"non-monotonic sequence_no: expected {current.last_sequence_no + 1}, "
            f"got {env.sequence_no}"
        )
    if env.prev_envelope_hash != current.chain_tip:
        raise ChainForkError(
            f"prev_envelope_hash mismatch: expected {current.chain_tip.hex()}, "
            f"got {env.prev_envelope_hash.hex()}"
        )


async def check_envelope(store: ReplayStore, env: VacantEnvelope) -> None:
    """Convenience wrapper: delegate to `store.check_and_advance`."""
    await store.check_and_advance(env)
