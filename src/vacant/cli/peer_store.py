"""Local peer-list store for `vacant peer …` commands.

Where `~/.vacant/<name>/` is per-vacant state, peer state is *per-user*:
the list of remote vacant network peers this machine knows about.
Stored as a single JSON file at `~/.vacant/peers.json`:

    {
      "peers": [
        {
          "label": "seed-tw",
          "endpoint": "https://seed-tw.vacant.network",
          "added_at_ms": 1700000000000
        },
        ...
      ]
    }

The shape is intentionally simple — operators edit it by hand if they
want. The CLI provides `peer add` / `peer list` / `peer remove` /
`peer gossip` / `peer bootstrap` to manipulate it without editing JSON.

A peer is just an A2A endpoint URL — same format `vacant call` already
understands. Peers exchange epoch + halo data via the federated /
gossip backends already in `vacant.registry`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from vacant.cli import local_store as ls

__all__ = [
    "PeerEntry",
    "PeerStore",
    "PeerStoreError",
    "peers_path",
]


class PeerStoreError(Exception):
    """Raised when the peer store can't be read, written, or contains an
    invalid entry."""


@dataclass(frozen=True)
class PeerEntry:
    """One remote vacant network peer.

    Attributes:
        label: Free-form operator label (e.g. `"seed-tw"`, `"alice's box"`).
            Must be unique within the store.
        endpoint: HTTP(S) base URL of the peer's A2A server. We don't
            validate reachability at add time — the operator may add a
            peer before the peer is online.
        added_at_ms: Wall-clock at insertion. Used for "most recently
            added" UX, not for correctness.
    """

    label: str
    endpoint: str
    added_at_ms: int

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "endpoint": self.endpoint,
            "added_at_ms": self.added_at_ms,
        }


def peers_path(home: Path | None = None) -> Path:
    """Return the canonical location of the peer list JSON file.

    `home` overrides `$VACANT_HOME` for tests; production uses the
    default `~/.vacant/` resolution.
    """
    return (home or ls.vacant_home()) / "peers.json"


class PeerStore:
    """Read/write wrapper around `~/.vacant/peers.json`.

    All mutations write atomically (tmp file + rename) so an interrupted
    operation can't corrupt the file. Reads tolerate a missing file
    (returns empty list).
    """

    def __init__(self, *, home: Path | None = None) -> None:
        self._home = home
        self._path = peers_path(home)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[PeerEntry]:
        """Return every peer in insertion order. Missing file → []."""
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PeerStoreError(f"peers.json unreadable: {exc}") from exc
        try:
            return [
                PeerEntry(
                    label=str(p["label"]),
                    endpoint=str(p["endpoint"]),
                    added_at_ms=int(p["added_at_ms"]),
                )
                for p in data.get("peers", [])
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise PeerStoreError(f"peers.json has malformed row: {exc}") from exc

    def save(self, peers: list[PeerEntry]) -> None:
        """Overwrite the peer file with `peers`. Atomic via tmp + rename
        so a crashed write can't half-corrupt the file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        body = json.dumps({"peers": [p.as_dict() for p in peers]}, indent=2, sort_keys=True)
        tmp.write_text(body + "\n", encoding="utf-8")
        tmp.replace(self._path)

    def add(self, label: str, endpoint: str) -> PeerEntry:
        """Append a peer. Raises if `label` is already in use.

        The endpoint is stored *verbatim* — no URL normalisation — so an
        operator who wants to point at `http://localhost:8443/` and
        `http://localhost:8443` as two distinct rows can.
        """
        if not label.strip():
            raise PeerStoreError("peer label cannot be empty")
        if not endpoint.strip():
            raise PeerStoreError("peer endpoint cannot be empty")
        peers = self.load()
        if any(p.label == label for p in peers):
            raise PeerStoreError(f"peer label {label!r} already exists")
        entry = PeerEntry(label=label, endpoint=endpoint, added_at_ms=int(time.time() * 1000))
        peers.append(entry)
        self.save(peers)
        return entry

    def remove(self, label: str) -> PeerEntry:
        """Remove + return the matching peer. Raises if not found."""
        peers = self.load()
        for i, p in enumerate(peers):
            if p.label == label:
                peers.pop(i)
                self.save(peers)
                return p
        raise PeerStoreError(f"peer label {label!r} not found")

    def get(self, label: str) -> PeerEntry | None:
        for p in self.load():
            if p.label == label:
                return p
        return None
