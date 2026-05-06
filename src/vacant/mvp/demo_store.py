"""SQLite-backed event store for the P7 demo (Pfix2 §B1).

Scenarios append events as they run; the dashboard reads them back to
plot real time series instead of recomputing each session. A single
event row is `(id, scenario, ts, kind, payload_json)`.

Kinds:
  - `call`         -- a vacant call (success/failure)
  - `review`       -- a reputation review record
  - `spawn`        -- a self-replication spawn (D1/D2/D3/D5)
  - `state_change` -- runtime state transition
  - `halo_publish` -- capability-card halo publish
  - `metric`       -- a snapshot of one of the 8 P7 metrics

The store is a thin wrapper over `sqlite3` (sync — these are short
write bursts during scenario runs, not a hot path) with a deliberate
single-table schema. Scenarios call `record(...)` directly; the
dashboard calls `read(...)` to materialise.

Path resolution:
  - explicit `path=` argument wins
  - else `VACANT_DEMO_DB_PATH` environment variable
  - else `var/demo.db` under the repo root (or `:memory:` when running
    a one-shot run; see `default_path`)
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "EVENT_KINDS",
    "DemoEvent",
    "DemoStore",
    "default_path",
]


EVENT_KINDS: tuple[str, ...] = (
    "call",
    "review",
    "spawn",
    "state_change",
    "halo_publish",
    "metric",
)


def default_path() -> str:
    """Return the resolved default demo-db path.

    `var/demo.db` is rooted at the repo (the cwd that contains a
    `pyproject.toml`); falls back to `:memory:` if the marker is not
    found, so unit tests don't accidentally write to a developer's
    `var/` directory.
    """
    env = os.environ.get("VACANT_DEMO_DB_PATH")
    if env:
        return env
    here = Path.cwd()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").exists():
            target = candidate / "var" / "demo.db"
            target.parent.mkdir(parents=True, exist_ok=True)
            return str(target)
    return ":memory:"


@dataclass(frozen=True)
class DemoEvent:
    """One row from the events table."""

    id: int
    scenario: str
    ts: float
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)


class DemoStore:
    """Thin SQLite event store. Synchronous; safe for short bursts.

    Use as a context manager (`with DemoStore(...) as s: ...`) to ensure
    the connection is closed; or call `.close()` explicitly.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario TEXT NOT NULL,
            ts REAL NOT NULL,
            kind TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_scenario_ts ON events (scenario, ts);
        CREATE INDEX IF NOT EXISTS idx_events_kind ON events (kind);
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = path or default_path()
        self._conn = sqlite3.connect(self._path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(self._SCHEMA)
        self._conn.commit()

    # --- lifecycle -----------------------------------------------------

    @property
    def path(self) -> str:
        return self._path

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> DemoStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- write ---------------------------------------------------------

    def record(
        self,
        *,
        scenario: str,
        kind: str,
        payload: dict[str, Any] | None = None,
        ts: float | None = None,
    ) -> int:
        """Append one event; return its rowid."""
        if kind not in EVENT_KINDS:
            raise ValueError(f"unknown kind {kind!r}; allowed: {EVENT_KINDS}")
        when = ts if ts is not None else time.time()
        body = json.dumps(payload or {}, sort_keys=True, default=str)
        cur = self._conn.execute(
            "INSERT INTO events (scenario, ts, kind, payload_json) VALUES (?, ?, ?, ?)",
            (scenario, when, kind, body),
        )
        self._conn.commit()
        rowid = cur.lastrowid
        assert rowid is not None
        return rowid

    def record_batch(
        self,
        scenario: str,
        rows: Iterable[tuple[str, dict[str, Any]]],
        *,
        ts_start: float | None = None,
        ts_step: float = 0.0,
    ) -> int:
        """Append many events for one scenario in a single transaction.

        `ts_step > 0` synthesises a monotonic timeline starting at
        `ts_start` (default `time.time()`) — useful for replaying a
        scenario into the store while keeping ordering deterministic.
        Returns the number of rows inserted.
        """
        when = ts_start if ts_start is not None else time.time()
        n = 0
        with self._tx():
            for kind, payload in rows:
                if kind not in EVENT_KINDS:
                    raise ValueError(f"unknown kind {kind!r}")
                body = json.dumps(payload, sort_keys=True, default=str)
                self._conn.execute(
                    "INSERT INTO events (scenario, ts, kind, payload_json) VALUES (?, ?, ?, ?)",
                    (scenario, when, kind, body),
                )
                n += 1
                when += ts_step
        return n

    def clear(self, scenario: str | None = None) -> int:
        """Delete events; return the row count removed."""
        with self._tx():
            if scenario is None:
                cur = self._conn.execute("DELETE FROM events")
            else:
                cur = self._conn.execute("DELETE FROM events WHERE scenario = ?", (scenario,))
        return cur.rowcount

    # --- read ----------------------------------------------------------

    def read(
        self,
        *,
        scenario: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[DemoEvent]:
        """Read events ordered by (scenario, ts ASC, id ASC)."""
        clauses: list[str] = []
        params: list[Any] = []
        if scenario is not None:
            clauses.append("scenario = ?")
            params.append(scenario)
        if kind is not None:
            if kind not in EVENT_KINDS:
                raise ValueError(f"unknown kind {kind!r}")
            clauses.append("kind = ?")
            params.append(kind)
        sql = "SELECT id, scenario, ts, kind, payload_json FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY ts ASC, id ASC"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        rows = self._conn.execute(sql, params).fetchall()
        return [
            DemoEvent(
                id=int(r[0]),
                scenario=str(r[1]),
                ts=float(r[2]),
                kind=str(r[3]),
                payload=json.loads(r[4]),
            )
            for r in rows
        ]

    def metric_series(self, scenario: str, metric_name: str) -> list[tuple[float, Any]]:
        """Return `(ts, value)` pairs for one named metric, in time order.

        `metric` events are expected to carry payloads
        `{"name": "<metric>", "value": <number-or-dict>}`.
        """
        rows = self._conn.execute(
            """
            SELECT ts, payload_json
            FROM events
            WHERE scenario = ? AND kind = 'metric'
            ORDER BY ts ASC, id ASC
            """,
            (scenario,),
        ).fetchall()
        out: list[tuple[float, Any]] = []
        for ts, payload_json in rows:
            payload = json.loads(payload_json)
            if payload.get("name") == metric_name:
                out.append((float(ts), payload.get("value")))
        return out

    def scenarios(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT scenario FROM events ORDER BY scenario"
        ).fetchall()
        return [str(r[0]) for r in rows]

    def count(self, *, scenario: str | None = None) -> int:
        if scenario is None:
            (n,) = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
        else:
            (n,) = self._conn.execute(
                "SELECT COUNT(*) FROM events WHERE scenario = ?", (scenario,)
            ).fetchone()
        return int(n)

    # --- internals -----------------------------------------------------

    @contextmanager
    def _tx(self):  # type: ignore[no-untyped-def]
        try:
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
