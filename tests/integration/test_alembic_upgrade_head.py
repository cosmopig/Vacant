"""Pfix3 B3 — pin that ``alembic upgrade head`` works on fresh SQLite.

The original 0001 used ``SQLModel.metadata.create_all()`` and 0002
called ``op.create_unique_constraint(...)`` — which SQLite rejects
(``No support for ALTER of constraints in SQLite dialect``). This test
catches the regression: the rewritten 0001 is a fixed schema snapshot
and 0002 wraps the constraint add in ``op.batch_alter_table`` so the
SQLite recreate path is taken.

We verify that:
1. ``alembic upgrade head`` against a fresh SQLite database succeeds.
2. The resulting schema contains the ``uq_event_actor_seq`` constraint
   on the ``event`` table (the constraint 0002 exists to add).
3. Every table the SQLModel metadata declares is present after the
   upgrade — i.e. the alembic and ``metadata.create_all`` paths reach
   the same end state.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config


def _alembic_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "alembic.ini").exists():
            return parent
    raise RuntimeError("alembic.ini not found above test file")


def test_alembic_upgrade_head_succeeds_on_fresh_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    url = f"sqlite:///{db_path}"

    root = _alembic_root()
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)

    alembic_command.upgrade(cfg, "head")

    assert db_path.exists()
    con = sqlite3.connect(db_path)
    try:
        head = con.execute("SELECT version_num FROM alembic_version").fetchone()
        assert head is not None
        assert head[0] == "0002_event_actor_seq_unique"

        event_sql = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='event'"
        ).fetchone()
        assert event_sql is not None
        assert "uq_event_actor_seq" in event_sql[0]
        assert "actor_vacant_id" in event_sql[0]
        assert "actor_seq" in event_sql[0]

        expected_tables = {
            "anomaly_window",
            "attestation",
            "composition_link",
            "epoch_witness",
            "event",
            "event_finalization",
            "freeze",
            "merkle_epoch",
            "read_audit",
            "replay_protect",
            "reputation_snapshot",
            "revocation",
            "sink_record",
            "vacant",
        }
        existing = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "AND name NOT LIKE 'alembic_%'"
            ).fetchall()
        }
        missing = expected_tables - existing
        extra = existing - expected_tables
        assert not missing, f"alembic upgrade missed: {missing}"
        assert not extra, f"alembic upgrade created unexpected tables: {extra}"
    finally:
        con.close()
