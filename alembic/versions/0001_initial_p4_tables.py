"""initial p4 tables — fixed schema snapshot.

Pre-Pfix3 this file delegated to ``SQLModel.metadata.create_all()``,
which made the migration mutate every time ``models.py`` changed and
caused ``alembic upgrade head`` to fail on SQLite once the 0002
follow-up tried to ALTER an already-created constraint. This version
freezes the schema explicitly so the upgrade path is dialect-stable
and idempotent.

The ``uq_event_actor_seq`` UniqueConstraint is intentionally **not**
declared here. 0002 adds it via ``op.batch_alter_table`` so the SQLite
recreate path is taken (SQLite cannot ALTER constraints in place).

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-08 (regenerated from metadata for Pfix3 B3)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "merkle_epoch",
        sa.Column("epoch_id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("first_seq", sa.Integer(), nullable=False),
        sa.Column("last_seq", sa.Integer(), nullable=False),
        sa.Column("tree_size", sa.Integer(), nullable=False),
        sa.Column("root_hash", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("sealed_at", sa.Integer(), nullable=False),
        sa.Column("registry_signature", sa.LargeBinary(), nullable=False),
        sa.Column("git_commit_sha", sa.String(), nullable=True),
        sa.Column("git_repo_url", sa.String(), nullable=True),
        sa.Column("git_branch", sa.String(), nullable=True),
        sa.Column("pushed_at", sa.Integer(), nullable=True),
        sa.Column("ots_proof_hash", sa.LargeBinary(), nullable=True),
        sa.Column("ots_upgraded_at", sa.Integer(), nullable=True),
    )
    op.create_table(
        "read_audit",
        sa.Column("audit_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("requester_pubkey", sa.LargeBinary(), nullable=True),
        sa.Column("query_kind", sa.String(), nullable=False),
        sa.Column("query_hash", sa.LargeBinary(), nullable=False),
        sa.Column("response_root", sa.LargeBinary(), nullable=False),
        sa.Column("response_signature", sa.LargeBinary(), nullable=False),
        sa.Column("served_at", sa.Integer(), nullable=False),
    )
    op.create_table(
        "replay_protect",
        sa.Column("from_vid_hex", sa.String(), nullable=False, primary_key=True),
        sa.Column("to_vid_hex", sa.String(), nullable=False, primary_key=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("chain_tip", sa.LargeBinary(), nullable=False),
    )
    op.create_table(
        "vacant",
        sa.Column("vacant_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("public_key", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("owner_org", sa.String(), nullable=True),
        sa.Column("base_model", sa.String(), nullable=False),
        sa.Column("base_model_family", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), sa.ForeignKey("vacant.vacant_id"), nullable=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("declared_capabilities_json", sa.String(), nullable=False),
        sa.Column("capability_card_hash", sa.LargeBinary(), nullable=False),
        sa.Column("capability_card_sig", sa.LargeBinary(), nullable=False),
        sa.Column("capability_card_blob", sa.LargeBinary(), nullable=False),
        sa.Column("stake_amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("visibility", sa.String(), nullable=False),
        sa.Column("registered_at", sa.Integer(), nullable=False),
        sa.Column("latest_event_seq", sa.Integer(), nullable=False),
    )
    op.create_index("ix_vacant_status", "vacant", ["status"])
    op.create_index("ix_vacant_parent_id", "vacant", ["parent_id"])
    op.create_index("ix_vacant_owner_org", "vacant", ["owner_org"])
    op.create_index("ix_vacant_visibility", "vacant", ["visibility"])
    op.create_index("ix_vacant_base_model_family", "vacant", ["base_model_family"])
    op.create_table(
        "anomaly_window",
        sa.Column(
            "vacant_id",
            sa.String(),
            sa.ForeignKey("vacant.vacant_id"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("metric", sa.String(), nullable=False, primary_key=True),
        sa.Column("window_start", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("window_end", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("triggered", sa.Integer(), nullable=False),
    )
    op.create_table(
        "attestation",
        sa.Column("attestation_id", sa.String(), nullable=False, primary_key=True),
        sa.Column(
            "vacant_id", sa.String(), sa.ForeignKey("vacant.vacant_id"), nullable=False
        ),
        sa.Column("attester_kind", sa.String(), nullable=False),
        sa.Column("attester_pubkey", sa.LargeBinary(), nullable=False),
        sa.Column("attester_signature", sa.LargeBinary(), nullable=False),
        sa.Column("payload_hash", sa.LargeBinary(), nullable=False),
        sa.Column("valid_from", sa.Integer(), nullable=False),
        sa.Column("valid_until", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
    )
    op.create_index("ix_attestation_attester_pubkey", "attestation", ["attester_pubkey"])
    op.create_index("ix_attestation_vacant_id", "attestation", ["vacant_id"])
    op.create_table(
        "epoch_witness",
        sa.Column(
            "epoch_id",
            sa.Integer(),
            sa.ForeignKey("merkle_epoch.epoch_id"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("witness_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("witness_pubkey", sa.LargeBinary(), nullable=False),
        sa.Column("cosignature", sa.LargeBinary(), nullable=False),
        sa.Column("cosigned_at", sa.Integer(), nullable=False),
    )
    op.create_table(
        "event",
        sa.Column("seq", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "actor_vacant_id",
            sa.String(),
            sa.ForeignKey("vacant.vacant_id"),
            nullable=False,
        ),
        sa.Column(
            "subject_vacant_id",
            sa.String(),
            sa.ForeignKey("vacant.vacant_id"),
            nullable=True,
        ),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column("payload_hash", sa.LargeBinary(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False, unique=True),
        sa.Column("signed_by_pubkey", sa.LargeBinary(), nullable=False),
        sa.Column("signature", sa.LargeBinary(), nullable=False),
        sa.Column("prev_event_hash", sa.LargeBinary(), nullable=False),
        sa.Column("event_hash", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("actor_seq", sa.Integer(), nullable=False),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column(
            "epoch_id", sa.Integer(), sa.ForeignKey("merkle_epoch.epoch_id"), nullable=True
        ),
        sa.Column("finalized_at", sa.Integer(), nullable=True),
        sa.Column("finalization_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_event_event_type", "event", ["event_type"])
    op.create_index("ix_event_subject_vacant_id", "event", ["subject_vacant_id"])
    op.create_index("ix_event_actor_seq", "event", ["actor_seq"])
    op.create_index("ix_event_actor_vacant_id", "event", ["actor_vacant_id"])
    op.create_index("ix_event_ts", "event", ["ts"])
    op.create_table(
        "freeze",
        sa.Column("freeze_id", sa.String(), nullable=False, primary_key=True),
        sa.Column(
            "vacant_id", sa.String(), sa.ForeignKey("vacant.vacant_id"), nullable=False
        ),
        sa.Column("frozen_at", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("anomaly_signal_json", sa.String(), nullable=True),
        sa.Column("frozen_by_kind", sa.String(), nullable=False),
        sa.Column("quorum_signatures_json", sa.String(), nullable=True),
        sa.Column("lifted_at", sa.Integer(), nullable=True),
        sa.Column("lifted_by_kind", sa.String(), nullable=True),
    )
    op.create_index("ix_freeze_frozen_at", "freeze", ["frozen_at"])
    op.create_index("ix_freeze_vacant_id", "freeze", ["vacant_id"])
    op.create_table(
        "reputation_snapshot",
        sa.Column("snapshot_id", sa.String(), nullable=False, primary_key=True),
        sa.Column(
            "vacant_id", sa.String(), sa.ForeignKey("vacant.vacant_id"), nullable=False
        ),
        sa.Column(
            "epoch_id",
            sa.Integer(),
            sa.ForeignKey("merkle_epoch.epoch_id"),
            nullable=False,
        ),
        sa.Column("factual_mean", sa.Float(), nullable=True),
        sa.Column("factual_lo_ci", sa.Float(), nullable=True),
        sa.Column("factual_hi_ci", sa.Float(), nullable=True),
        sa.Column("factual_n", sa.Integer(), nullable=True),
        sa.Column("logical_mean", sa.Float(), nullable=True),
        sa.Column("logical_lo_ci", sa.Float(), nullable=True),
        sa.Column("logical_hi_ci", sa.Float(), nullable=True),
        sa.Column("logical_n", sa.Integer(), nullable=True),
        sa.Column("relevance_mean", sa.Float(), nullable=True),
        sa.Column("relevance_lo_ci", sa.Float(), nullable=True),
        sa.Column("relevance_hi_ci", sa.Float(), nullable=True),
        sa.Column("relevance_n", sa.Integer(), nullable=True),
        sa.Column("honesty_mean", sa.Float(), nullable=True),
        sa.Column("honesty_lo_ci", sa.Float(), nullable=True),
        sa.Column("honesty_hi_ci", sa.Float(), nullable=True),
        sa.Column("honesty_n", sa.Integer(), nullable=True),
        sa.Column("adoption_mean", sa.Float(), nullable=True),
        sa.Column("adoption_lo_ci", sa.Float(), nullable=True),
        sa.Column("adoption_hi_ci", sa.Float(), nullable=True),
        sa.Column("adoption_n", sa.Integer(), nullable=True),
        sa.Column("diversity_index", sa.Float(), nullable=True),
        sa.Column("sample_status", sa.String(), nullable=False),
        sa.Column("snapshot_hash", sa.LargeBinary(), nullable=False),
        sa.Column("registry_signature", sa.LargeBinary(), nullable=False),
        sa.Column("computed_at", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_reputation_snapshot_vacant_id", "reputation_snapshot", ["vacant_id"]
    )
    op.create_table(
        "composition_link",
        sa.Column("link_id", sa.String(), nullable=False, primary_key=True),
        sa.Column(
            "vacant_a", sa.String(), sa.ForeignKey("vacant.vacant_id"), nullable=False
        ),
        sa.Column(
            "vacant_b", sa.String(), sa.ForeignKey("vacant.vacant_id"), nullable=False
        ),
        sa.Column("agreed_payload_json", sa.String(), nullable=False),
        sa.Column("sig_a", sa.LargeBinary(), nullable=False),
        sa.Column("sig_b", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_event_seq", sa.Integer(), sa.ForeignKey("event.seq"), nullable=False
        ),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("terminated_at", sa.Integer(), nullable=True),
        sa.Column("terminated_event_seq", sa.Integer(), nullable=True),
    )
    op.create_index("ix_composition_link_vacant_b", "composition_link", ["vacant_b"])
    op.create_index("ix_composition_link_vacant_a", "composition_link", ["vacant_a"])
    op.create_table(
        "event_finalization",
        sa.Column(
            "event_seq",
            sa.Integer(),
            sa.ForeignKey("event.seq"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "attester_vacant_id",
            sa.String(),
            sa.ForeignKey("vacant.vacant_id"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("attester_pubkey", sa.LargeBinary(), nullable=False),
        sa.Column("signature", sa.LargeBinary(), nullable=False),
        sa.Column("base_model_family", sa.String(), nullable=False),
        sa.Column("signed_at", sa.Integer(), nullable=False),
    )
    op.create_table(
        "revocation",
        sa.Column("revocation_id", sa.String(), nullable=False, primary_key=True),
        sa.Column(
            "vacant_id", sa.String(), sa.ForeignKey("vacant.vacant_id"), nullable=False
        ),
        sa.Column("revoked_pubkey", sa.LargeBinary(), nullable=False),
        sa.Column("revoked_at", sa.Integer(), nullable=False),
        sa.Column("by_kind", sa.String(), nullable=False),
        sa.Column(
            "evidence_event_seq",
            sa.Integer(),
            sa.ForeignKey("event.seq"),
            nullable=True,
        ),
        sa.Column("signatures_json", sa.String(), nullable=False),
    )
    op.create_index("ix_revocation_vacant_id", "revocation", ["vacant_id"])
    op.create_index("ix_revocation_revoked_pubkey", "revocation", ["revoked_pubkey"])
    op.create_table(
        "sink_record",
        sa.Column(
            "vacant_id",
            sa.String(),
            sa.ForeignKey("vacant.vacant_id"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "sunk_event_seq", sa.Integer(), sa.ForeignKey("event.seq"), nullable=False
        ),
        sa.Column("sunk_at", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("reason_detail_json", sa.String(), nullable=True),
        sa.Column(
            "replaced_by_vacant_id",
            sa.String(),
            sa.ForeignKey("vacant.vacant_id"),
            nullable=True,
        ),
        sa.Column("quorum_signatures_json", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("sink_record")
    op.drop_index("ix_revocation_revoked_pubkey", table_name="revocation")
    op.drop_index("ix_revocation_vacant_id", table_name="revocation")
    op.drop_table("revocation")
    op.drop_table("event_finalization")
    op.drop_index("ix_composition_link_vacant_a", table_name="composition_link")
    op.drop_index("ix_composition_link_vacant_b", table_name="composition_link")
    op.drop_table("composition_link")
    op.drop_index("ix_reputation_snapshot_vacant_id", table_name="reputation_snapshot")
    op.drop_table("reputation_snapshot")
    op.drop_index("ix_freeze_vacant_id", table_name="freeze")
    op.drop_index("ix_freeze_frozen_at", table_name="freeze")
    op.drop_table("freeze")
    op.drop_index("ix_event_ts", table_name="event")
    op.drop_index("ix_event_actor_vacant_id", table_name="event")
    op.drop_index("ix_event_actor_seq", table_name="event")
    op.drop_index("ix_event_subject_vacant_id", table_name="event")
    op.drop_index("ix_event_event_type", table_name="event")
    op.drop_table("event")
    op.drop_table("epoch_witness")
    op.drop_index("ix_attestation_vacant_id", table_name="attestation")
    op.drop_index("ix_attestation_attester_pubkey", table_name="attestation")
    op.drop_table("attestation")
    op.drop_table("anomaly_window")
    op.drop_index("ix_vacant_base_model_family", table_name="vacant")
    op.drop_index("ix_vacant_visibility", table_name="vacant")
    op.drop_index("ix_vacant_owner_org", table_name="vacant")
    op.drop_index("ix_vacant_parent_id", table_name="vacant")
    op.drop_index("ix_vacant_status", table_name="vacant")
    op.drop_table("vacant")
    op.drop_table("replay_protect")
    op.drop_table("read_audit")
    op.drop_table("merkle_epoch")
