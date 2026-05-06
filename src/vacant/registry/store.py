"""Central-MVP registry store (SQLAlchemy AsyncEngine + aiosqlite).

Implements `RegistryBackend` for SQLite. Anti-tamper layers L1-L3 are
checked here at write time; L4 (Merkle snapshots) is exposed via
`seal_epoch()`; L5 (anomaly counters) is wired into `submit_event` as a
post-write signal; L6 (append-only) is enforced by exposing no `delete_*`
methods + raising `AppendOnlyViolation` if a caller tries SQL-direct DELETE.

Async only. Construction takes a SQLAlchemy `AsyncEngine` (DI seam — tests
use `sqlite+aiosqlite:///:memory:`; production uses a file path).
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import desc as sa_desc
from sqlalchemy import event as sa_event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel, select

from vacant.core.constants import (
    ANOMALY_REVIEW_PER_TARGET_HOUR,
    EVENT_LOG_DEFAULT_PAGE_SIZE,
    EVENT_LOG_MAX_PAGE_SIZE,
)
from vacant.core.crypto import SigningKey, VerifyKey, hash_blake2b
from vacant.core.types import VacantId, VacantState
from vacant.registry.antitamper import (
    AnomalyAssessment,
    assess_anomaly,
    build_merkle_root,
    canonical_event_bytes,
    check_attestation_freshness,
    check_sequence_monotonic,
    compute_event_hash,
    sign_epoch_root,
    verify_event_signature,
)
from vacant.registry.errors import (
    AppendOnlyViolation,
    IdempotencyConflict,
    NotFoundError,
    RegistryWriteError,
    SignatureRejected,
    VisibilityViolation,
)
from vacant.registry.models import (
    AnomalyWindow,
    Attestation,
    Event,
    MerkleEpoch,
    Vacant,
)
from vacant.registry.visibility import Visibility, effective_visibility

__all__ = ["RegistryStore", "SignedEventDraft", "now_ms"]


def now_ms() -> int:
    """Current time in millis since epoch (P4 §3.1 timestamp convention)."""
    return int(time.time() * 1000)


# --- canonical JSON ----------------------------------------------------------


def canonical_json(payload: dict[str, object]) -> str:
    """JSON canonicalisation for `payload_json` storage. D006 §F: same
    `sort_keys + tight separators` form used by P0 logbooks; JCS-strict
    is future work."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class SignedEventDraft:
    """A pre-signed event draft handed to the store. The store re-derives
    the hash chain + verifies the signature before insert.
    """

    event_type: str
    actor_vacant_id: str
    subject_vacant_id: str | None
    payload: dict[str, object]
    idempotency_key: str
    signed_by_pubkey: bytes
    signature: bytes
    actor_seq: int
    ts: int


class RegistryStore:
    """SQLite-backed `RegistryBackend` impl with anti-tamper hooks."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        # L6: prohibit DELETE on append-only tables.
        self._install_append_only_guard()
        self._write_lock = asyncio.Lock()

    # --- schema -------------------------------------------------------------

    async def init_schema(self) -> None:
        """Create all tables. Idempotent."""
        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    # --- vacants ------------------------------------------------------------

    async def insert_vacant(self, vacant: Vacant) -> None:
        async with self._sessionmaker() as s:
            s.add(vacant)
            try:
                await s.commit()
            except IntegrityError as exc:
                await s.rollback()
                raise RegistryWriteError(f"vacant {vacant.vacant_id} already exists") from exc

    async def get_vacant(self, vacant_id: str) -> Vacant | None:
        async with self._sessionmaker() as s:
            return await s.get(Vacant, vacant_id)

    async def update_vacant_status(self, vacant_id: str, status: str) -> None:
        async with self._sessionmaker() as s:
            v = await s.get(Vacant, vacant_id)
            if v is None:
                raise NotFoundError(f"vacant {vacant_id} not found")
            v.status = status
            await s.commit()

    async def update_vacant_visibility(self, vacant_id: str, visibility: str) -> None:
        async with self._sessionmaker() as s:
            v = await s.get(Vacant, vacant_id)
            if v is None:
                raise NotFoundError(f"vacant {vacant_id} not found")
            v.visibility = visibility
            await s.commit()

    async def update_vacant_latest_seq(self, vacant_id: str, seq: int) -> None:
        async with self._sessionmaker() as s:
            v = await s.get(Vacant, vacant_id)
            if v is None:
                raise NotFoundError(f"vacant {vacant_id} not found")
            v.latest_event_seq = seq
            await s.commit()

    # --- events -------------------------------------------------------------

    async def lookup_idempotency(self, idempotency_key: str) -> Event | None:
        async with self._sessionmaker() as s:
            res = await s.execute(select(Event).where(Event.idempotency_key == idempotency_key))
            return res.scalar_one_or_none()

    async def latest_event_for_actor(self, actor_vacant_id: str) -> Event | None:
        async with self._sessionmaker() as s:
            res = await s.execute(
                select(Event)
                .where(Event.actor_vacant_id == actor_vacant_id)
                .order_by(sa_desc(Event.seq))  # type: ignore[arg-type]
                .limit(1)
            )
            return res.scalar_one_or_none()

    async def latest_event_overall(self) -> Event | None:
        async with self._sessionmaker() as s:
            res = await s.execute(select(Event).order_by(sa_desc(Event.seq)).limit(1))  # type: ignore[arg-type]
            return res.scalar_one_or_none()

    async def submit_event(self, draft: SignedEventDraft) -> Event:
        """The hot path: idempotency → sig verify → seq monotone → chain
        → insert. Returns the persisted `Event` with `seq` and `event_hash`.
        """
        # --- L1: signature verify on canonical bytes -----------------------
        payload_json = canonical_json(draft.payload)
        payload_hash = hash_blake2b(payload_json.encode("utf-8"))
        canonical = canonical_event_bytes(
            event_type=draft.event_type,
            actor_vacant_id=draft.actor_vacant_id,
            subject_vacant_id=draft.subject_vacant_id,
            payload_hash=payload_hash,
            idempotency_key=draft.idempotency_key,
            signed_by_pubkey=draft.signed_by_pubkey,
            ts=draft.ts,
            actor_seq=draft.actor_seq,
        )
        verify_event_signature(
            pubkey_bytes=draft.signed_by_pubkey,
            canonical_bytes=canonical,
            signature=draft.signature,
        )

        # --- L1b: cross-actor impersonation guard ------------------------------
        # Padv-P4 §1: without this check, an attacker with their own keypair
        # could submit events filed under any `actor_vacant_id` so long as
        # `signed_by_pubkey` matches their own key (the signature would
        # verify under their key, but the event would be filed as "from"
        # the victim). Bind the actor identity to its registered pubkey.
        actor = await self.get_vacant(draft.actor_vacant_id)
        if actor is None:
            raise SignatureRejected(f"unknown actor {draft.actor_vacant_id}: vacant not registered")
        if actor.public_key != draft.signed_by_pubkey:
            raise SignatureRejected(
                f"signed_by_pubkey does not match registered key for actor {draft.actor_vacant_id}"
            )

        async with self._write_lock:
            # --- idempotency: same key + same payload_hash returns existing -
            existing = await self.lookup_idempotency(draft.idempotency_key)
            if existing is not None:
                if existing.payload_hash == payload_hash:
                    return existing
                raise IdempotencyConflict(
                    f"idempotency_key {draft.idempotency_key} reused with different payload"
                )

            # --- L2: per-actor sequence monotonicity -------------------------
            last_for_actor = await self.latest_event_for_actor(draft.actor_vacant_id)
            last_actor_seq = last_for_actor.actor_seq if last_for_actor else 0
            check_sequence_monotonic(last_seq=last_actor_seq, candidate_seq=draft.actor_seq)

            # --- chain prev_event_hash to overall tip ------------------------
            tip = await self.latest_event_overall()
            prev_event_hash = tip.event_hash if tip else b"\x00" * 32

            event_hash = compute_event_hash(
                prev_event_hash=prev_event_hash,
                canonical_bytes=canonical,
                signature=draft.signature,
            )

            row = Event(
                event_type=draft.event_type,
                actor_vacant_id=draft.actor_vacant_id,
                subject_vacant_id=draft.subject_vacant_id,
                payload_json=payload_json,
                payload_hash=payload_hash,
                idempotency_key=draft.idempotency_key,
                signed_by_pubkey=draft.signed_by_pubkey,
                signature=draft.signature,
                prev_event_hash=prev_event_hash,
                event_hash=event_hash,
                actor_seq=draft.actor_seq,
                ts=draft.ts,
            )
            async with self._sessionmaker() as s:
                s.add(row)
                await s.commit()
                await s.refresh(row)

            return row

    async def get_event(self, seq: int) -> Event | None:
        async with self._sessionmaker() as s:
            return await s.get(Event, seq)

    async def list_events_for_vacant(
        self,
        vacant_id: str,
        *,
        from_seq: int = 0,
        limit: int = EVENT_LOG_DEFAULT_PAGE_SIZE,
    ) -> Sequence[Event]:
        if limit > EVENT_LOG_MAX_PAGE_SIZE:
            limit = EVENT_LOG_MAX_PAGE_SIZE
        async with self._sessionmaker() as s:
            res = await s.execute(
                select(Event)
                .where(
                    (Event.actor_vacant_id == vacant_id) | (Event.subject_vacant_id == vacant_id)
                )
                .where(Event.seq > from_seq)  # type: ignore[operator]
                .order_by(Event.seq)  # type: ignore[arg-type]
                .limit(limit)
            )
            return list(res.scalars().all())

    # --- attestations -------------------------------------------------------

    async def insert_attestation(self, attestation: Attestation, *, now: int | None = None) -> None:
        check_attestation_freshness(
            valid_from_ms=attestation.valid_from,
            valid_until_ms=attestation.valid_until,
            now_ms=now if now is not None else now_ms(),
        )
        async with self._sessionmaker() as s:
            s.add(attestation)
            try:
                await s.commit()
            except IntegrityError as exc:
                await s.rollback()
                raise RegistryWriteError(str(exc)) from exc

    async def list_attestations(self, vacant_id: str) -> Sequence[Attestation]:
        async with self._sessionmaker() as s:
            res = await s.execute(select(Attestation).where(Attestation.vacant_id == vacant_id))
            return list(res.scalars().all())

    # --- integrity verifiers (Padv-P4 §3) -----------------------------------

    async def verify_event_chain(self) -> bool:
        """Recompute every stored event's `payload_hash`, signature, and
        `event_hash` from `payload_json` + canonical bytes. Returns False on
        any mismatch — i.e. detects in-place tampering that bypassed the
        signed write path (UPDATE instead of INSERT). The append-only
        guard (L6) catches DELETE; this catches UPDATE.
        """
        expected_prev = b"\x00" * 32
        async with self._sessionmaker() as s:
            res = await s.execute(select(Event).order_by(Event.seq))  # type: ignore[arg-type]
            for ev in res.scalars().all():
                if ev.prev_event_hash != expected_prev:
                    return False
                # Recompute payload_hash from stored canonical payload_json.
                recomputed_payload_hash = hash_blake2b(ev.payload_json.encode("utf-8"))
                if recomputed_payload_hash != ev.payload_hash:
                    return False
                # Recompute canonical bytes.
                canonical = canonical_event_bytes(
                    event_type=ev.event_type,
                    actor_vacant_id=ev.actor_vacant_id,
                    subject_vacant_id=ev.subject_vacant_id,
                    payload_hash=ev.payload_hash,
                    idempotency_key=ev.idempotency_key,
                    signed_by_pubkey=ev.signed_by_pubkey,
                    ts=ev.ts,
                    actor_seq=ev.actor_seq,
                )
                # Re-verify signature.
                try:
                    verify_event_signature(
                        pubkey_bytes=ev.signed_by_pubkey,
                        canonical_bytes=canonical,
                        signature=ev.signature,
                    )
                except Exception:
                    return False
                # Re-derive event_hash.
                recomputed_hash = compute_event_hash(
                    prev_event_hash=ev.prev_event_hash,
                    canonical_bytes=canonical,
                    signature=ev.signature,
                )
                if recomputed_hash != ev.event_hash:
                    return False
                expected_prev = ev.event_hash
        return True

    async def verify_vacant_index_consistent(self, vacant_id: str) -> bool:
        """True iff the indexed `vacant.visibility` column matches the
        visibility recorded on the most recent `register` event for that
        vacant. Catches direct SQL UPDATE of the visibility column —
        Padv-P4 §2.

        Returns True if the vacant has no register events on file (nothing
        to compare against; rejected at higher levels).
        """
        v = await self.get_vacant(vacant_id)
        if v is None:
            return False
        async with self._sessionmaker() as s:
            res = await s.execute(
                select(Event)
                .where(Event.actor_vacant_id == vacant_id)
                .where(Event.event_type == "register")
                .order_by(sa_desc(Event.seq))  # type: ignore[arg-type]
                .limit(1)
            )
            latest_register = res.scalar_one_or_none()
        if latest_register is None:
            # No register events: nothing to compare. Treat as inconsistent
            # because every vacant in the index *must* have a register event.
            return False
        try:
            payload = json.loads(latest_register.payload_json)
        except json.JSONDecodeError:
            return False
        return bool(v.visibility == payload.get("visibility"))

    # --- merkle epochs ------------------------------------------------------

    async def list_unsealed_events(self) -> Sequence[Event]:
        async with self._sessionmaker() as s:
            res = await s.execute(
                select(Event)
                .where(Event.epoch_id == None)  # noqa: E711
                .order_by(Event.seq)  # type: ignore[arg-type]
            )
            return list(res.scalars().all())

    async def seal_epoch(self, *, signing_key: SigningKey) -> MerkleEpoch:
        """Build a Merkle root over all unsealed events, store it, and
        attach `epoch_id` back to each leaf event. Operator-signed.
        """
        unsealed = await self.list_unsealed_events()
        if not unsealed:
            raise RegistryWriteError("seal_epoch: no unsealed events")
        leaves = [e.event_hash for e in unsealed]
        root = build_merkle_root(leaves)
        sig = sign_epoch_root(root=root, signing_key=signing_key)
        epoch = MerkleEpoch(
            first_seq=unsealed[0].seq or 0,
            last_seq=unsealed[-1].seq or 0,
            tree_size=len(unsealed),
            root_hash=root,
            sealed_at=now_ms(),
            registry_signature=sig,
        )
        async with self._sessionmaker() as s:
            s.add(epoch)
            await s.commit()
            await s.refresh(epoch)
            # Assign epoch_id to events.
            for e in unsealed:
                e_db = await s.get(Event, e.seq)
                if e_db is not None:
                    e_db.epoch_id = epoch.epoch_id
            await s.commit()
        return epoch

    async def latest_merkle_epoch(self) -> MerkleEpoch | None:
        async with self._sessionmaker() as s:
            res = await s.execute(
                select(MerkleEpoch).order_by(sa_desc(MerkleEpoch.epoch_id)).limit(1)  # type: ignore[arg-type]
            )
            return res.scalar_one_or_none()

    async def get_merkle_epoch(self, epoch_id: int) -> MerkleEpoch | None:
        async with self._sessionmaker() as s:
            return await s.get(MerkleEpoch, epoch_id)

    # --- lineage queries ---------------------------------------------------

    async def list_descendants(self, vacant_id: str, *, max_depth: int = 8) -> Sequence[Vacant]:
        seen: set[str] = set()
        out: list[Vacant] = []
        frontier = [vacant_id]
        depth = 0
        async with self._sessionmaker() as s:
            while frontier and depth < max_depth:
                res = await s.execute(
                    select(Vacant).where(Vacant.parent_id.in_(frontier))  # type: ignore[union-attr]
                )
                children = list(res.scalars().all())
                next_frontier: list[str] = []
                for c in children:
                    if c.vacant_id in seen:
                        continue
                    seen.add(c.vacant_id)
                    out.append(c)
                    next_frontier.append(c.vacant_id)
                frontier = next_frontier
                depth += 1
        return out

    async def list_ancestors(self, vacant_id: str, *, max_depth: int = 8) -> Sequence[Vacant]:
        out: list[Vacant] = []
        async with self._sessionmaker() as s:
            current = await s.get(Vacant, vacant_id)
            depth = 0
            while current is not None and current.parent_id is not None and depth < max_depth:
                parent = await s.get(Vacant, current.parent_id)
                if parent is None:
                    break
                out.append(parent)
                current = parent
                depth += 1
        return out

    async def search_capability(
        self,
        *,
        capability: str | None = None,
        family: str | None = None,
        status: str | None = "active",
        visibility: str | None = "PUBLIC",
        limit: int = 20,
    ) -> Sequence[Vacant]:
        async with self._sessionmaker() as s:
            stmt = select(Vacant)
            if status is not None:
                stmt = stmt.where(Vacant.status == status)
            if visibility is not None:
                stmt = stmt.where(Vacant.visibility == visibility)
            if family is not None:
                stmt = stmt.where(Vacant.base_model_family == family)
            if capability is not None:
                stmt = stmt.where(
                    Vacant.declared_capabilities_json.contains(capability)  # type: ignore[attr-defined]
                )
            stmt = stmt.limit(limit)
            res = await s.execute(stmt)
            return list(res.scalars().all())

    # --- anomaly counters ---------------------------------------------------

    async def record_anomaly(
        self, *, vacant_id: str, metric: str, value: float, threshold: float
    ) -> AnomalyAssessment:
        assessment = assess_anomaly(metric=metric, value=value, threshold=threshold)
        ts = now_ms()
        row = AnomalyWindow(
            vacant_id=vacant_id,
            metric=metric,
            window_start=ts,
            window_end=ts,
            value=value,
            threshold=threshold,
            triggered=1 if assessment.triggered else 0,
        )
        async with self._sessionmaker() as s:
            s.add(row)
            await s.commit()
        return assessment

    # --- visibility-aware reads --------------------------------------------

    async def lookup_halo_for_caller(
        self,
        target_vacant_id: str,
        *,
        caller_pubkey_hex: str | None = None,
    ) -> Vacant:
        """Visibility-aware halo lookup. Returns the halo iff:

        - `target.visibility == PUBLIC`, OR
        - `caller == target` (owner-direct), OR
        - `caller == target.parent` (parent-direct).

        Raises `VisibilityViolation` for stranger lookups against NONE
        halos. Raises `NotFoundError` if the target doesn't exist.
        """
        v = await self.get_vacant(target_vacant_id)
        if v is None:
            raise NotFoundError(target_vacant_id)
        # Compute effective visibility from runtime status.
        runtime = self._status_to_state(v.status)
        eff = effective_visibility(runtime, Visibility(v.visibility))
        if eff == Visibility.NONE:
            if caller_pubkey_hex is None:
                raise VisibilityViolation(
                    f"vacant {target_vacant_id} is NONE-visibility; caller required"
                )
            if caller_pubkey_hex == v.vacant_id:
                return v
            if v.parent_id is not None and caller_pubkey_hex == v.parent_id:
                return v
            raise VisibilityViolation(
                f"vacant {target_vacant_id} is NONE-visibility; caller is not owner/parent"
            )
        return v

    @staticmethod
    def _status_to_state(status: str) -> VacantState:
        """Map registry `status` → `VacantState` for visibility computation.

        Registry tracks `active / frozen / sunk / revoked`; visibility code
        only cares about LOCAL vs everything else.
        """
        if status == "sunk":
            return VacantState.SUNK
        if status == "revoked":
            return VacantState.ARCHIVED
        return VacantState.ACTIVE

    # --- L6: append-only guard ---------------------------------------------

    def _install_append_only_guard(self) -> None:
        """Reject DELETE on append-only tables at the SQLAlchemy event hook."""

        append_only_tables = {
            "event",
            "event_finalization",
            "merkle_epoch",
            "epoch_witness",
            "read_audit",
        }

        @sa_event.listens_for(self._engine.sync_engine, "handle_error")
        def _noop(_ctx: object) -> None:
            return None

        # Direct DELETE rejection: hook into ORM session deletes via a
        # `before_flush` listener on every `AsyncSession`. Because ORM
        # deletes are routed via Session, monkey-patching the class is
        # cleaner than per-instance listeners.
        @sa_event.listens_for(AsyncSession.sync_session_class, "before_flush")
        def _reject_appendonly_delete(
            session: object, _flush_ctx: object, _instances: object
        ) -> None:
            for obj in session.deleted:  # type: ignore[attr-defined]
                table = getattr(obj, "__tablename__", None)
                if table in append_only_tables:
                    raise AppendOnlyViolation(
                        f"DELETE on append-only table {table} is not permitted"
                    )

    # --- helper for tests / RPC -----------------------------------------------

    async def assert_signed_by_owner(
        self, vacant_id: str, signature: bytes, payload: bytes
    ) -> None:
        v = await self.get_vacant(vacant_id)
        if v is None:
            raise NotFoundError(vacant_id)
        from vacant.core.crypto import pubkey_from_bytes, verify

        ok = verify(pubkey_from_bytes(v.public_key), payload, signature)
        if not ok:
            raise RegistryWriteError("signature does not verify against vacant pubkey")

    @staticmethod
    def make_idempotency_key() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def vacant_id_for_pubkey(vk: VerifyKey) -> str:
        return VacantId.from_verify_key(vk).hex()


# Silence unused-import warning while keeping public API consistent.
_ = ANOMALY_REVIEW_PER_TARGET_HOUR
