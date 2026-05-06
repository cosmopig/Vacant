"""Replay protection — per-pair sequence + chain-tip tracking.

P6 §6 / dispatch §6: every `(from_vacant_id, to_vacant_id)` pair has its
own monotonic `sequence_no` counter and `chain_tip` (last envelope's
hash). An incoming envelope is rejected if:

- `sequence_no <= last_seen[(from, to)]`, OR
- `prev_envelope_hash != stored_chain_tip[(from, to)]`.

A new pair starts at `sequence_no = 1` and `chain_tip = EMPTY_PREV_HASH`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import LargeBinary
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
    """SQL row backing `SqliteReplayStore`. Created on first init.

    `from_vid_hex` + `to_vid_hex` form a composite primary key. Row
    update is a single UPDATE/INSERT inside a transaction.
    """

    __tablename__ = "replay_protect"

    from_vid_hex: str = Field(primary_key=True)
    to_vid_hex: str = Field(primary_key=True)
    last_sequence_no: int = 0
    chain_tip: bytes = Field(sa_column=Column(LargeBinary, nullable=False), default=EMPTY_PREV_HASH)


class SqliteReplayStore:
    """SQLAlchemy/aiosqlite-backed replay store."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        self._lock = asyncio.Lock()

    async def init_schema(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(_ReplayRow.metadata.create_all)

    async def get(self, key: PairKey) -> ReplayState:
        async with self._sm() as s:
            row = await s.execute(
                select(_ReplayRow).where(
                    _ReplayRow.from_vid_hex == key.from_vid.hex(),
                    _ReplayRow.to_vid_hex == key.to_vid.hex(),
                )
            )
            r = row.scalar_one_or_none()
            if r is None:
                return ReplayState(last_sequence_no=0, chain_tip=EMPTY_PREV_HASH)
            return ReplayState(last_sequence_no=r.last_sequence_no, chain_tip=r.chain_tip)

    async def check_and_advance(self, env: VacantEnvelope) -> None:
        key = PairKey.from_envelope(env)
        async with self._lock:
            cur = await self.get(key)
            _check(env, cur)
            new_state = ReplayState(last_sequence_no=env.sequence_no, chain_tip=env.compute_hash())
            async with self._sm() as s:
                row = await s.execute(
                    select(_ReplayRow).where(
                        _ReplayRow.from_vid_hex == key.from_vid.hex(),
                        _ReplayRow.to_vid_hex == key.to_vid.hex(),
                    )
                )
                existing = row.scalar_one_or_none()
                if existing is None:
                    s.add(
                        _ReplayRow(
                            from_vid_hex=key.from_vid.hex(),
                            to_vid_hex=key.to_vid.hex(),
                            last_sequence_no=new_state.last_sequence_no,
                            chain_tip=new_state.chain_tip,
                        )
                    )
                else:
                    existing.last_sequence_no = new_state.last_sequence_no
                    existing.chain_tip = new_state.chain_tip
                await s.commit()


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
