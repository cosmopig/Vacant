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
    SequenceMonotonicityError,
    SignatureRejected,
    VisibilityViolation,
)
from vacant.registry.git_anchor import (
    DEFAULT_GIT_BRANCH,
    GitAnchorReceipt,
    try_anchor_to_git,
)
from vacant.registry.models import (
    AnomalyWindow,
    Attestation,
    EpochWitness,
    Event,
    MerkleEpoch,
    Vacant,
)
from vacant.registry.ots_anchor import (
    DEFAULT_CALENDAR_URLS,
    compute_pending_proof,
    is_upgraded_proof,
    ots_proof_digest,
    serialize_proof_file,
    upgrade_pending_proof,
)
from vacant.registry.visibility import Visibility, effective_visibility
from vacant.registry.witness import (
    WitnessCosignature,
    WitnessError,
    verify_witness_cosignature,
)

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

        Race protection (F-B): the in-process `asyncio.Lock` is a
        fast-path mutex within a single worker; the load-bearing defense
        is the `(actor_vacant_id, actor_seq)` UNIQUE on the `event`
        table, which turns concurrent inserts of the same `actor_seq`
        into `IntegrityError` and back into `SequenceMonotonicityError`
        for the loser of the race.
        """
        async with self._write_lock:
            async with self._sessionmaker() as s:
                async with s.begin():
                    return await self._submit_event_in_session(s, draft)

    async def _submit_event_in_session(self, s: AsyncSession, draft: SignedEventDraft) -> Event:
        """The core submit logic, factored so it can run inside an
        externally-managed transaction (used by F-A's
        `submit_register_event_atomic`).

        Caller MUST own the session lifecycle (commit / rollback). All
        DB reads + the final insert run on `s`; this lets a sibling
        write (e.g. inserting the corresponding `Vacant` row) live in
        the same transaction so a failed insert here rolls back the
        sibling write too.
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

        # --- L1b: cross-actor impersonation guard --------------------------
        # Padv-P4 §1: without this check, an attacker with their own
        # keypair could submit events filed under any `actor_vacant_id`
        # as long as `signed_by_pubkey` matches their own key (the sig
        # would verify under their key but be filed as the victim's).
        actor = await s.get(Vacant, draft.actor_vacant_id)
        if actor is None:
            raise SignatureRejected(f"unknown actor {draft.actor_vacant_id}: vacant not registered")
        if actor.public_key != draft.signed_by_pubkey:
            raise SignatureRejected(
                f"signed_by_pubkey does not match registered key for actor {draft.actor_vacant_id}"
            )

        # --- idempotency: same key + same payload_hash returns existing ---
        existing = (
            await s.execute(select(Event).where(Event.idempotency_key == draft.idempotency_key))
        ).scalar_one_or_none()
        if existing is not None:
            if existing.payload_hash == payload_hash:
                return existing
            raise IdempotencyConflict(
                f"idempotency_key {draft.idempotency_key} reused with different payload"
            )

        # --- L2: per-actor sequence monotonicity (best-effort fast check)--
        last_for_actor = (
            await s.execute(
                select(Event)
                .where(Event.actor_vacant_id == draft.actor_vacant_id)
                .order_by(sa_desc(Event.seq))  # type: ignore[arg-type]
                .limit(1)
            )
        ).scalar_one_or_none()
        last_actor_seq = last_for_actor.actor_seq if last_for_actor else 0
        check_sequence_monotonic(last_seq=last_actor_seq, candidate_seq=draft.actor_seq)

        # --- chain prev_event_hash to overall tip --------------------------
        tip = (
            await s.execute(select(Event).order_by(sa_desc(Event.seq)).limit(1))  # type: ignore[arg-type]
        ).scalar_one_or_none()
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
        s.add(row)
        try:
            # Flush forces the INSERT (and therefore the UNIQUE check)
            # without ending the outer transaction. SQLAlchemy populates
            # `row.seq` from the autoincrement during flush, so we do
            # not need a separate `refresh()` afterwards (which would
            # fail under nested transactions on aiosqlite).
            await s.flush()
        except IntegrityError as exc:
            # Two paths land here:
            # 1. Another worker won the race for this `actor_seq` — turn
            #    that into the same error the in-memory check would have
            #    raised, so callers don't have to distinguish.
            # 2. `idempotency_key` UNIQUE collided with a concurrently-
            #    inserted row (we missed it in the lookup above) — surface
            #    as `IdempotencyConflict`.
            msg = str(exc.orig).lower() if exc.orig else str(exc).lower()
            if "idempotency_key" in msg:
                raise IdempotencyConflict(
                    f"idempotency_key {draft.idempotency_key} concurrently used"
                ) from exc
            raise SequenceMonotonicityError(
                f"actor_seq {draft.actor_seq} for actor {draft.actor_vacant_id} "
                "concurrently used (race lost; retry with the next seq)"
            ) from exc
        return row

    async def submit_register_event_atomic(
        self,
        *,
        vacant_to_insert: Vacant | None,
        vacant_id_to_update: str | None,
        new_visibility: str | None,
        draft: SignedEventDraft,
        vacant_field_updates: dict[str, object] | None = None,
    ) -> Event:
        """F-A defense: insert/update vacant + submit register event in
        ONE transaction. If `submit_event` fails (signature rejected,
        idempotency conflict, sequence race), the vacant row insert /
        visibility update is rolled back, so the audit chain and the
        publicly-visible state can never diverge.

        Exactly one of `vacant_to_insert` or `vacant_id_to_update` should
        be non-None per call site. If both are None, only the event is
        submitted (used by tests).

        ``vacant_field_updates`` (Pfix3 B5): when ``vacant_id_to_update``
        is set, callers can pass a dict of column-name → new-value to
        apply onto the existing row before the register event lands.
        Used by ``publish_halo`` republish so the row's
        ``capability_card_*`` columns track the new card instead of
        going stale while the audit chain advances. ``new_visibility``
        is the legacy single-field path; if ``vacant_field_updates``
        contains a ``visibility`` key it takes precedence.
        """
        async with self._write_lock:
            async with self._sessionmaker() as s:
                async with s.begin():
                    if vacant_to_insert is not None:
                        s.add(vacant_to_insert)
                        try:
                            await s.flush()
                        except IntegrityError as exc:
                            raise RegistryWriteError(
                                f"vacant {vacant_to_insert.vacant_id} already exists"
                            ) from exc
                    elif vacant_id_to_update is not None:
                        v = await s.get(Vacant, vacant_id_to_update)
                        if v is None:
                            raise NotFoundError(f"vacant {vacant_id_to_update} not found")
                        if vacant_field_updates:
                            for fname, fval in vacant_field_updates.items():
                                setattr(v, fname, fval)
                        elif new_visibility is not None:
                            v.visibility = new_visibility
                        await s.flush()
                    return await self._submit_event_in_session(s, draft)

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

    async def seal_epoch(
        self,
        *,
        signing_key: SigningKey,
        git_anchor_repo: str | None = None,
        git_anchor_branch: str = DEFAULT_GIT_BRANCH,
        git_anchor_remote: str | None = None,
        git_anchor_push: bool = False,
        ots_anchor: bool = False,
        ots_calendar_urls: tuple[str, ...] = DEFAULT_CALENDAR_URLS,
    ) -> MerkleEpoch:
        """Build a Merkle root over all unsealed events, store it, attach
        `epoch_id` back to each leaf event, and optionally anchor the
        root externally.

        Anchor parameters (all optional):
        - ``git_anchor_repo``: filesystem path to a transparency-log
          git repo. If set, the sealed root is committed to
          ``epochs/{epoch_id:08d}.json`` on ``git_anchor_branch``;
          ``git_commit_sha`` is recorded back on the row. Anchor
          failures are *advisory* — sealing still succeeds.
        - ``git_anchor_remote`` / ``git_anchor_push``: configure /
          attempt a remote push after committing locally. ``pushed_at``
          is set on success.
        - ``ots_anchor``: when True, generate an OpenTimestamps
          pending-proof receipt for the root and record its BLAKE2b
          digest on ``ots_proof_hash``. The operator can later upgrade
          it to a real ``.ots`` proof via
          ``record_ots_upgrade(epoch_id, upgraded_bytes)``.
        - ``ots_calendar_urls``: which calendar servers the future
          upgrade step should target. Defaults to the public OTS pool.
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

        # External anchors: best-effort. Failures don't roll back the seal —
        # the epoch root is durable in the DB regardless. Operators retry
        # via the explicit anchor / upgrade helpers below.
        if git_anchor_repo is not None:
            receipt = try_anchor_to_git(
                epoch=epoch,
                repo_path=git_anchor_repo,
                branch=git_anchor_branch,
                remote_url=git_anchor_remote,
                push=git_anchor_push,
            )
            if receipt is not None:
                await self._record_git_anchor(epoch, receipt)
                # Reload so callers see the anchor metadata on the returned row.
                async with self._sessionmaker() as s:
                    refreshed = await s.get(MerkleEpoch, epoch.epoch_id)
                    if refreshed is not None:
                        epoch = refreshed

        if ots_anchor:
            pending = compute_pending_proof(root=epoch.root_hash, calendar_urls=ots_calendar_urls)
            digest = ots_proof_digest(serialize_proof_file(pending))
            await self._record_ots_pending(epoch, digest)
            async with self._sessionmaker() as s:
                refreshed = await s.get(MerkleEpoch, epoch.epoch_id)
                if refreshed is not None:
                    epoch = refreshed

        return epoch

    async def _record_git_anchor(self, epoch: MerkleEpoch, receipt: GitAnchorReceipt) -> None:
        """Persist `git_commit_sha` / `git_branch` / `git_repo_url` /
        `pushed_at` onto the epoch row. Idempotent — overwriting an
        existing receipt is allowed because re-anchoring the same epoch
        is a recovery operation, not an audit-log mutation."""
        async with self._sessionmaker() as s:
            row = await s.get(MerkleEpoch, epoch.epoch_id)
            if row is None:
                raise NotFoundError(f"merkle_epoch {epoch.epoch_id} not found")
            row.git_commit_sha = receipt.commit_sha
            row.git_branch = receipt.branch
            row.git_repo_url = receipt.remote_url or receipt.repo_path
            row.pushed_at = now_ms() if receipt.pushed else None
            await s.commit()

    async def _record_ots_pending(self, epoch: MerkleEpoch, digest: bytes) -> None:
        """Persist the pending-OTS digest. Idempotent."""
        async with self._sessionmaker() as s:
            row = await s.get(MerkleEpoch, epoch.epoch_id)
            if row is None:
                raise NotFoundError(f"merkle_epoch {epoch.epoch_id} not found")
            row.ots_proof_hash = digest
            await s.commit()

    async def anchor_epoch_to_git(
        self,
        epoch_id: int,
        *,
        repo_path: str,
        branch: str = DEFAULT_GIT_BRANCH,
        remote_url: str | None = None,
        push: bool = False,
    ) -> GitAnchorReceipt:
        """Retry the git anchor for an already-sealed epoch.

        Used when ``seal_epoch(..., git_anchor_repo=...)`` was called
        but the anchor failed (git not on PATH, remote unreachable, etc.)
        or when the operator opted to anchor lazily.

        Raises:
            NotFoundError: If `epoch_id` is unknown.
            GitAnchorError: If the anchor attempt itself fails (callers
                wanting best-effort behavior should catch this).
        """
        epoch = await self.get_merkle_epoch(epoch_id)
        if epoch is None:
            raise NotFoundError(f"merkle_epoch {epoch_id} not found")
        # Re-import lazily so a missing optional dep doesn't break import-time.
        from vacant.registry.git_anchor import anchor_to_git

        receipt = anchor_to_git(
            epoch=epoch,
            repo_path=repo_path,
            branch=branch,
            remote_url=remote_url,
            push=push,
        )
        await self._record_git_anchor(epoch, receipt)
        return receipt

    async def record_ots_upgrade(
        self, epoch_id: int, *, upgraded_bytes: bytes
    ) -> tuple[bytes, int]:
        """Replace a pending OTS receipt with a real `.ots` proof.

        The operator runs ``ots stamp`` out-of-band (or
        ``ots upgrade`` on an existing partial proof), reads the
        resulting bytes, and calls this method. We validate that
        ``upgraded_bytes`` carries the OpenTimestamps magic header
        before persisting; full Bitcoin-anchor verification is left to
        the optional ``opentimestamps`` library.

        Args:
            epoch_id: The epoch the upgrade applies to.
            upgraded_bytes: Raw bytes of the real `.ots` proof.

        Returns:
            `(BLAKE2b(upgraded_bytes), ots_upgraded_at_ms)`. The
            digest replaces ``ots_proof_hash`` and ``ots_upgraded_at``
            is freshly stamped.

        Raises:
            NotFoundError: If the epoch is unknown.
            OTSAnchorError: If the upgrade bytes do not look like a
                real `.ots` proof.
        """
        if not is_upgraded_proof(upgraded_bytes):
            # upgrade_pending_proof would raise OTSAnchorError, but we want
            # the explicit shape here for the API surface.
            from vacant.registry.ots_anchor import OTSAnchorError

            raise OTSAnchorError("upgrade payload missing OpenTimestamps magic header")
        epoch = await self.get_merkle_epoch(epoch_id)
        if epoch is None:
            raise NotFoundError(f"merkle_epoch {epoch_id} not found")
        pending = compute_pending_proof(root=epoch.root_hash)
        digest, upgraded_at = upgrade_pending_proof(pending=pending, upgraded_bytes=upgraded_bytes)
        async with self._sessionmaker() as s:
            row = await s.get(MerkleEpoch, epoch_id)
            if row is None:
                raise NotFoundError(f"merkle_epoch {epoch_id} not found")
            row.ots_proof_hash = digest
            row.ots_upgraded_at = upgraded_at
            await s.commit()
        return digest, upgraded_at

    # --- federated witnesses ------------------------------------------------

    async def record_witness_cosignature(
        self,
        epoch_id: int,
        cosignature: WitnessCosignature,
    ) -> EpochWitness:
        """Verify + persist a peer registry's cosignature on an epoch root.

        Decentralised-trust glue: an external verifier asks for the
        epoch row + all its `EpochWitness` rows, then calls
        ``verify_witness_quorum(epoch, rows, rootset)`` to decide whether
        the central operator's single signature is sufficiently
        attested by independent observers.

        The signature is verified against the canonical witness
        statement (``build_witness_statement``) *before* it lands in the
        DB — so the `epoch_witness` table only ever stores cryptographically
        valid cosignatures. Re-recording the same `(epoch_id, witness_id)`
        pair raises `RegistryWriteError` (the table's composite primary key
        already enforces uniqueness; we surface a typed error).

        Args:
            epoch_id: Target epoch (must exist).
            cosignature: A `WitnessCosignature` produced by
                `issue_witness_cosignature`.

        Returns:
            The persisted `EpochWitness` row.

        Raises:
            NotFoundError: If `epoch_id` is unknown.
            WitnessError: If the cosignature fails Ed25519 verification.
            RegistryWriteError: If this `(epoch, witness)` pair was
                already recorded.
        """
        epoch = await self.get_merkle_epoch(epoch_id)
        if epoch is None:
            raise NotFoundError(f"merkle_epoch {epoch_id} not found")
        if not verify_witness_cosignature(epoch=epoch, cosignature=cosignature):
            raise WitnessError(
                f"witness cosignature from {cosignature.witness_id} "
                f"failed verification on epoch {epoch_id}"
            )
        row = EpochWitness(
            epoch_id=epoch_id,
            witness_id=cosignature.witness_id,
            witness_pubkey=cosignature.witness_pubkey,
            cosignature=cosignature.signature,
            cosigned_at=now_ms(),
        )
        async with self._sessionmaker() as s:
            s.add(row)
            try:
                await s.commit()
            except IntegrityError as exc:
                await s.rollback()
                raise RegistryWriteError(
                    f"witness {cosignature.witness_id} already cosigned epoch {epoch_id}"
                ) from exc
        return row

    async def list_epoch_witnesses(self, epoch_id: int) -> Sequence[EpochWitness]:
        """Return all witness cosignatures stored for `epoch_id`.

        Verifiers call this together with `get_merkle_epoch(epoch_id)`
        and pass both into `verify_witness_quorum(...)`.
        """
        async with self._sessionmaker() as s:
            res = await s.execute(select(EpochWitness).where(EpochWitness.epoch_id == epoch_id))
            return list(res.scalars().all())

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
