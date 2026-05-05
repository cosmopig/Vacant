"""SQLModel tables for the central-MVP registry backend.

13 tables per `architecture/components/P4_registry.md` §3.1, mapped onto
SQLModel for typed CRUD + Alembic-generated migrations. Field names that
collide with Python keywords are suffixed `_`.

Schema decisions reconciled in D006:
- Hashes are 32-byte BLAKE2b digests (`HASH_DIGEST_BYTES`), not BLAKE3.
- Timestamps are stored as `int` milliseconds since epoch (matches
  spec §3.1 "all timestamps millis since epoch").
- `vacant_id` stored as the lowercase hex pubkey (matches `VacantId.hex()`).
"""

from __future__ import annotations

from sqlmodel import Column, Field, LargeBinary, SQLModel

__all__ = [
    "AnomalyWindow",
    "Attestation",
    "CompositionLink",
    "EpochWitness",
    "Event",
    "EventFinalization",
    "Freeze",
    "MerkleEpoch",
    "ReadAudit",
    "ReputationSnapshot",
    "Revocation",
    "SinkRecord",
    "Vacant",
]


# --- 1) vacant ---------------------------------------------------------------


class Vacant(SQLModel, table=True):
    """Per-vacant capability-card snapshot. P4 §3.1 table 1."""

    __tablename__ = "vacant"

    vacant_id: str = Field(primary_key=True)
    public_key: bytes = Field(sa_column=Column(LargeBinary, nullable=False, unique=True))
    owner_org: str | None = Field(default=None, index=True)
    base_model: str
    base_model_family: str = Field(index=True)
    parent_id: str | None = Field(default=None, foreign_key="vacant.vacant_id", index=True)
    version: str
    declared_capabilities_json: str
    capability_card_hash: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    capability_card_sig: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    stake_amount: int = 0
    status: str = Field(default="active", index=True)
    visibility: str = Field(default="PUBLIC", index=True)
    registered_at: int
    latest_event_seq: int = 0


# --- 2) attestation ----------------------------------------------------------


class Attestation(SQLModel, table=True):
    """Identity attestation issued by a developer / org / peer / oracle."""

    __tablename__ = "attestation"

    attestation_id: str = Field(primary_key=True)
    vacant_id: str = Field(foreign_key="vacant.vacant_id", index=True)
    attester_kind: str
    attester_pubkey: bytes = Field(sa_column=Column(LargeBinary, nullable=False, index=True))
    attester_signature: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    payload_hash: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    valid_from: int
    valid_until: int | None = None
    revoked_at: int | None = None


# --- 3) event ----------------------------------------------------------------


class Event(SQLModel, table=True):
    """Append-only signed event log. P4 §3.1 table 3."""

    __tablename__ = "event"

    seq: int | None = Field(default=None, primary_key=True)
    event_type: str = Field(index=True)
    actor_vacant_id: str = Field(foreign_key="vacant.vacant_id", index=True)
    subject_vacant_id: str | None = Field(default=None, foreign_key="vacant.vacant_id", index=True)
    payload_json: str
    payload_hash: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    idempotency_key: str = Field(unique=True)
    signed_by_pubkey: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    signature: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    prev_event_hash: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    event_hash: bytes = Field(sa_column=Column(LargeBinary, nullable=False, unique=True))
    actor_seq: int = Field(default=0, index=True)
    """Per-actor monotonic sequence (anti-tamper L2)."""
    ts: int = Field(index=True)
    epoch_id: int | None = Field(default=None, foreign_key="merkle_epoch.epoch_id")
    finalized_at: int | None = None
    finalization_count: int = 0


# --- 4) event_finalization ---------------------------------------------------


class EventFinalization(SQLModel, table=True):
    """N-of-M attestation finalization for an event. P4 §3.1 table 4."""

    __tablename__ = "event_finalization"

    event_seq: int = Field(primary_key=True, foreign_key="event.seq")
    attester_vacant_id: str = Field(primary_key=True, foreign_key="vacant.vacant_id")
    attester_pubkey: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    signature: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    base_model_family: str
    signed_at: int


# --- 5) merkle_epoch ---------------------------------------------------------


class MerkleEpoch(SQLModel, table=True):
    """Periodic Merkle root over the event log. P4 §3.1 table 5."""

    __tablename__ = "merkle_epoch"

    epoch_id: int | None = Field(default=None, primary_key=True)
    first_seq: int
    last_seq: int
    tree_size: int
    root_hash: bytes = Field(sa_column=Column(LargeBinary, nullable=False, unique=True))
    sealed_at: int
    registry_signature: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    git_commit_sha: str | None = None
    git_repo_url: str | None = None
    git_branch: str | None = "transparency-log"
    pushed_at: int | None = None
    ots_proof_hash: bytes | None = Field(default=None, sa_column=Column(LargeBinary, nullable=True))
    ots_upgraded_at: int | None = None


# --- 6) epoch_witness --------------------------------------------------------


class EpochWitness(SQLModel, table=True):
    """L6 federated witness cosignature on an epoch root."""

    __tablename__ = "epoch_witness"

    epoch_id: int = Field(primary_key=True, foreign_key="merkle_epoch.epoch_id")
    witness_id: str = Field(primary_key=True)
    witness_pubkey: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    cosignature: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    cosigned_at: int


# --- 7) reputation_snapshot --------------------------------------------------


class ReputationSnapshot(SQLModel, table=True):
    """Per-vacant + per-epoch five-dimensional reputation snapshot."""

    __tablename__ = "reputation_snapshot"

    snapshot_id: str = Field(primary_key=True)
    vacant_id: str = Field(foreign_key="vacant.vacant_id", index=True)
    epoch_id: int = Field(foreign_key="merkle_epoch.epoch_id")
    factual_mean: float | None = None
    factual_lo_ci: float | None = None
    factual_hi_ci: float | None = None
    factual_n: int | None = None
    logical_mean: float | None = None
    logical_lo_ci: float | None = None
    logical_hi_ci: float | None = None
    logical_n: int | None = None
    relevance_mean: float | None = None
    relevance_lo_ci: float | None = None
    relevance_hi_ci: float | None = None
    relevance_n: int | None = None
    honesty_mean: float | None = None
    honesty_lo_ci: float | None = None
    honesty_hi_ci: float | None = None
    honesty_n: int | None = None
    adoption_mean: float | None = None
    adoption_lo_ci: float | None = None
    adoption_hi_ci: float | None = None
    adoption_n: int | None = None
    diversity_index: float | None = None
    sample_status: str  # 'insufficient' | 'partial' | 'sufficient'
    snapshot_hash: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    registry_signature: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    computed_at: int


# --- 8) composition_link -----------------------------------------------------


class CompositionLink(SQLModel, table=True):
    """Bilateral composition agreement between two vacants."""

    __tablename__ = "composition_link"

    link_id: str = Field(primary_key=True)
    vacant_a: str = Field(foreign_key="vacant.vacant_id", index=True)
    vacant_b: str = Field(foreign_key="vacant.vacant_id", index=True)
    agreed_payload_json: str
    sig_a: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    sig_b: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    created_event_seq: int = Field(foreign_key="event.seq")
    created_at: int
    terminated_at: int | None = None
    terminated_event_seq: int | None = None


# --- 9) sink_record ----------------------------------------------------------


class SinkRecord(SQLModel, table=True):
    """Sunk vacant terminal record. P4 §3.1 table 9."""

    __tablename__ = "sink_record"

    vacant_id: str = Field(primary_key=True, foreign_key="vacant.vacant_id")
    sunk_event_seq: int = Field(foreign_key="event.seq")
    sunk_at: int
    reason: str
    reason_detail_json: str | None = None
    replaced_by_vacant_id: str | None = Field(default=None, foreign_key="vacant.vacant_id")
    quorum_signatures_json: str | None = None


# --- 10) freeze --------------------------------------------------------------


class Freeze(SQLModel, table=True):
    """Temporary freeze (anomaly / governance / self)."""

    __tablename__ = "freeze"

    freeze_id: str = Field(primary_key=True)
    vacant_id: str = Field(foreign_key="vacant.vacant_id", index=True)
    frozen_at: int = Field(index=True)
    reason: str
    anomaly_signal_json: str | None = None
    frozen_by_kind: str  # 'anomaly_engine' | 'quorum' | 'self'
    quorum_signatures_json: str | None = None
    lifted_at: int | None = None
    lifted_by_kind: str | None = None


# --- 11) revocation ----------------------------------------------------------


class Revocation(SQLModel, table=True):
    """Public-key revocation record."""

    __tablename__ = "revocation"

    revocation_id: str = Field(primary_key=True)
    vacant_id: str = Field(foreign_key="vacant.vacant_id", index=True)
    revoked_pubkey: bytes = Field(sa_column=Column(LargeBinary, nullable=False, index=True))
    revoked_at: int
    by_kind: str  # 'self' | 'dev_oracle' | 'quorum'
    evidence_event_seq: int | None = Field(default=None, foreign_key="event.seq")
    signatures_json: str


# --- 12) read_audit ----------------------------------------------------------


class ReadAudit(SQLModel, table=True):
    """Optional read-side audit log (P4 §3.1 table 12; off by default)."""

    __tablename__ = "read_audit"

    audit_id: str = Field(primary_key=True)
    requester_pubkey: bytes | None = Field(
        default=None, sa_column=Column(LargeBinary, nullable=True)
    )
    query_kind: str
    query_hash: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    response_root: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    response_signature: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    served_at: int


# --- 13) anomaly_window ------------------------------------------------------


class AnomalyWindow(SQLModel, table=True):
    """Rolling-window anomaly counter (rule-based MVP, P4 §3.2 table)."""

    __tablename__ = "anomaly_window"

    vacant_id: str = Field(primary_key=True, foreign_key="vacant.vacant_id")
    metric: str = Field(primary_key=True)
    window_start: int = Field(primary_key=True)
    window_end: int
    value: float
    threshold: float
    triggered: int = 0


# Re-exports kept lean: callers needing all 13 import the names directly.
