"""Add UNIQUE on event.(actor_vacant_id, actor_seq) — F-B race fix.

Revision ID: 0002_event_actor_seq_unique
Revises: 0001_initial
Create Date: 2026-05-06

The in-process `asyncio.Lock` in `RegistryStore.submit_event` only
serialises submits within a single worker; under multi-worker
deployment two workers can both read the same
`latest_event_for_actor`, both pass `check_sequence_monotonic`, and
both try to insert events with the same `actor_seq`. This migration
adds the DB-level uniqueness so the second insert collides and the
store re-raises it as `SequenceMonotonicityError`.

For a fresh database (the only supported state in the MVP) this
migration is a no-op constraint addition. If a downstream user has
already accumulated duplicates somehow, they need to dedupe before
running this revision — the upgrade will fail loudly, which is
correct behaviour for an audit log.
"""

from __future__ import annotations

revision: str = "0002_event_actor_seq_unique"
down_revision: str | None = "0001_initial"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    from alembic import op

    op.create_unique_constraint(
        "uq_event_actor_seq",
        "event",
        ["actor_vacant_id", "actor_seq"],
    )


def downgrade() -> None:
    from alembic import op

    op.drop_constraint("uq_event_actor_seq", "event", type_="unique")
