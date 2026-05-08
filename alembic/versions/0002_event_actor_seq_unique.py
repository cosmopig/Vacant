"""Add UNIQUE on event.(actor_vacant_id, actor_seq) — F-B race fix.

Revision ID: 0002_event_actor_seq_unique
Revises: 0001_initial
Create Date: 2026-05-06 (rewritten 2026-05-08 for SQLite via batch_alter_table)

The in-process ``asyncio.Lock`` in ``RegistryStore.submit_event`` only
serialises submits within a single worker; under multi-worker
deployment two workers can both read the same
``latest_event_for_actor``, both pass ``check_sequence_monotonic``, and
both try to insert events with the same ``actor_seq``. This migration
adds the DB-level uniqueness so the second insert collides and the
store re-raises it as ``SequenceMonotonicityError``.

Pfix3 B3: SQLite cannot ``ALTER TABLE … ADD CONSTRAINT``. The original
``op.create_unique_constraint(...)`` call therefore failed with
``No support for ALTER of constraints in SQLite dialect`` on
``alembic upgrade head``. Wrapping in ``op.batch_alter_table`` triggers
the SQLite recreate path (copy → drop → rename) which carries the
constraint into the rebuilt table; on dialects that *can* ALTER
in-place it falls through to a normal ALTER.

For a fresh database (the only supported state in the MVP) this
migration is a no-op constraint addition. If a downstream user has
already accumulated duplicates somehow, they need to dedupe before
running this revision — the upgrade will fail loudly, which is
correct behaviour for an audit log.
"""

from __future__ import annotations

from alembic import op

revision: str = "0002_event_actor_seq_unique"
down_revision: str | None = "0001_initial"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("event") as batch_op:
        batch_op.create_unique_constraint(
            "uq_event_actor_seq",
            ["actor_vacant_id", "actor_seq"],
        )


def downgrade() -> None:
    with op.batch_alter_table("event") as batch_op:
        batch_op.drop_constraint("uq_event_actor_seq", type_="unique")
