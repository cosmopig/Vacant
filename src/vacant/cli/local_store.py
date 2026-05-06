"""On-disk layout for local vacants (`~/.vacant/<name>/`).

A *local vacant* is the owner-side handle for a vacant: keypair on disk,
logbook persisted to a `.jsonl` file, plus a small `meta.json` carrying
visibility state, capability text, and endpoint URL. Higher-level CLI
commands (`vacant init`, `status`, `publish`, `heartbeat`, `attest`,
`call`) read and write through this module.

Layout under `${VACANT_HOME:-~/.vacant}/<name>/`:

    key.json       {"pubkey_hex": "...", "seed_hex": "..."}   (mode 0600)
    logbook.jsonl  one JSON-encoded LogEntry per line
    meta.json      LocalMeta — state / endpoint / capability_text / etc.

The key file uses a plain JSON-on-disk format. Production deployments
should swap in `vacant.identity.keys.FileVault` (PBKDF2 + AES-GCM); the
dispatch CLI is intentionally simple so a thesis-defense reviewer can
inspect the on-disk state.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from vacant.core.crypto import SigningKey, keygen
from vacant.core.types import Logbook, LogEntry, VacantId

__all__ = [
    "LocalMeta",
    "LocalVacantError",
    "LocalVacantExists",
    "LocalVacantNotFound",
    "current_name",
    "init_vacant",
    "list_vacant_names",
    "load_logbook",
    "load_meta",
    "load_signing_key",
    "save_logbook",
    "save_meta",
    "vacant_dir",
    "vacant_home",
]


GENESIS_KIND = "GENESIS"
KEY_FILE = "key.json"
LOGBOOK_FILE = "logbook.jsonl"
META_FILE = "meta.json"


class LocalVacantError(RuntimeError):
    """Base class for local-store errors."""


class LocalVacantNotFound(LocalVacantError):
    """The named local vacant does not exist."""


class LocalVacantExists(LocalVacantError):
    """A local vacant with that name already exists."""


class LocalMeta(BaseModel):
    """Sidecar metadata. Visibility / capability / endpoint live here so
    `status` can render them without opening the logbook."""

    vacant_id_hex: str
    state: str = "LOCAL"
    capability_text: str | None = None
    endpoint: str | None = None
    created_at: str
    last_heartbeat_at: str | None = None
    parent_id_hex: str | None = None
    halo_published: bool = False


def vacant_home() -> Path:
    """Resolve the root directory: `$VACANT_HOME` or `~/.vacant`."""
    override = os.environ.get("VACANT_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".vacant"


def vacant_dir(name: str) -> Path:
    """Return the on-disk directory for vacant `name`. Validates the name
    so callers cannot escape the home directory via path traversal."""
    if not name or "/" in name or "\\" in name or "\0" in name or ".." in name:
        raise LocalVacantError(f"invalid local vacant name: {name!r}")
    return vacant_home() / name


def list_vacant_names() -> list[str]:
    """Names of every initialised local vacant, sorted."""
    home = vacant_home()
    if not home.exists():
        return []
    out: list[str] = []
    for p in home.iterdir():
        if p.is_dir() and (p / META_FILE).exists():
            out.append(p.name)
    return sorted(out)


def current_name() -> str:
    """Resolve the active vacant: env `VACANT_NAME`, else the only one.

    Raises `LocalVacantNotFound` if no vacant exists or multiple exist
    without `VACANT_NAME` set.
    """
    explicit = os.environ.get("VACANT_NAME")
    if explicit:
        return explicit
    names = list_vacant_names()
    if len(names) == 1:
        return names[0]
    if not names:
        raise LocalVacantNotFound("no local vacants; run `vacant init <name>` first")
    raise LocalVacantNotFound(
        f"VACANT_NAME not set and multiple vacants exist: {names!r}; "
        "set VACANT_NAME=<name> to select one"
    )


def init_vacant(name: str) -> tuple[VacantId, SigningKey]:
    """Generate a fresh keypair, write key+meta+seed-genesis-logbook.

    Returns the new `VacantId` and `SigningKey`. Raises
    `LocalVacantExists` if the directory already exists.
    """
    d = vacant_dir(name)
    if d.exists():
        raise LocalVacantExists(name)
    d.mkdir(parents=True)

    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)

    key_path = d / KEY_FILE
    key_path.write_text(
        json.dumps({"pubkey_hex": vid.hex(), "seed_hex": bytes(sk).hex()}, sort_keys=True)
    )
    os.chmod(key_path, 0o600)

    lb = Logbook()
    lb.append(GENESIS_KIND, {"name": name, "vacant_id": vid.hex()}, sk)
    save_logbook(name, lb)

    meta = LocalMeta(
        vacant_id_hex=vid.hex(),
        state="LOCAL",
        created_at=datetime.now(UTC).isoformat(),
    )
    save_meta(name, meta)
    return vid, sk


def load_signing_key(name: str) -> SigningKey:
    """Load the Ed25519 signing key for `name`."""
    p = vacant_dir(name) / KEY_FILE
    if not p.exists():
        raise LocalVacantNotFound(name)
    obj = json.loads(p.read_text())
    return SigningKey(bytes.fromhex(obj["seed_hex"]))


def load_meta(name: str) -> LocalMeta:
    p = vacant_dir(name) / META_FILE
    if not p.exists():
        raise LocalVacantNotFound(name)
    return LocalMeta.model_validate_json(p.read_text())


def save_meta(name: str, meta: LocalMeta) -> None:
    d = vacant_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    (d / META_FILE).write_text(meta.model_dump_json())


def _entry_to_dict(entry: LogEntry) -> dict[str, Any]:
    return {
        "kind": entry.kind,
        "ts": entry.ts.isoformat(),
        "payload": entry.payload,
        "prev_hash": entry.prev_hash.hex(),
        "signature": entry.signature.hex(),
    }


def _dict_to_entry(d: dict[str, Any]) -> LogEntry:
    return LogEntry(
        kind=d["kind"],
        ts=datetime.fromisoformat(d["ts"]),
        payload=d["payload"],
        prev_hash=bytes.fromhex(d["prev_hash"]),
        signature=bytes.fromhex(d["signature"]),
    )


def save_logbook(name: str, logbook: Logbook) -> None:
    d = vacant_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    p = d / LOGBOOK_FILE
    if not logbook.entries:
        p.write_text("")
        return
    lines = [json.dumps(_entry_to_dict(e), sort_keys=True) for e in logbook.entries]
    p.write_text("\n".join(lines) + "\n")


def load_logbook(name: str) -> Logbook:
    p = vacant_dir(name) / LOGBOOK_FILE
    if not p.exists():
        raise LocalVacantNotFound(name)
    lb = Logbook()
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        entry = _dict_to_entry(json.loads(line))
        lb.entries.append(entry)
    return lb
