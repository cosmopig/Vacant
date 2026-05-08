"""On-disk layout for local vacants (`~/.vacant/<name>/`).

A *local vacant* is the owner-side handle for a vacant: keypair stored
in the OS keyring (or a plaintext file in `--insecure-demo` mode), a
logbook persisted as `.jsonl`, and a small `meta.json` carrying
visibility state, capability text, and endpoint URL. Higher-level CLI
commands (`vacant init`, `status`, `publish`, `heartbeat`, `attest`,
`call`) read and write through this module.

Layout under `${VACANT_HOME:-~/.vacant}/<name>/`:

    key.json       {"pubkey_hex": "...", "key_storage": "keyring"}     (mode 0600)
                   or {"pubkey_hex": ..., "seed_hex": ..., "key_storage": "plaintext"}
    logbook.jsonl  one JSON-encoded LogEntry per line
    meta.json      LocalMeta — state / endpoint / capability_text / etc.

Key storage (F-D codex final blockers): the Ed25519 *seed* is sensitive
material — controlling it == owning the vacant. The default storage is
the OS keyring (Keychain on macOS, Secret Service on Linux, Credential
Locker on Windows) via the `keyring` package. The on-disk `key.json`
holds only the public key and a `key_storage` discriminator so external
tooling can verify signatures without unlocking the keychain.

If the host has no keyring backend (e.g. headless CI without DBus),
`init_vacant(insecure_demo=False)` raises rather than silently falling
back to plaintext. To opt into plaintext storage explicitly, pass
`insecure_demo=True` (the CLI surface is `vacant init <name>
--insecure-demo`); a stderr WARN is emitted and `key.json` is written
with the seed in the clear under mode 0600.

The `--insecure-demo` mode exists for two purposes only: live demos
where the operator is showing the file layout, and short-lived CI/test
flows. **Do not use it on a host with real network exposure.** See
`SECURITY.md` §"Local key storage" for the full risk model.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import keyring
from keyring.errors import KeyringError
from pydantic import BaseModel

from vacant.core.crypto import SigningKey, keygen
from vacant.core.types import Logbook, LogEntry, VacantId

__all__ = [
    "KEYRING_SERVICE",
    "LocalMeta",
    "LocalVacantError",
    "LocalVacantExists",
    "LocalVacantKeyringUnavailable",
    "LocalVacantNotFound",
    "current_name",
    "envelope_state_file",
    "init_vacant",
    "keyring_backend_available",
    "list_vacant_names",
    "load_envelope_state",
    "load_logbook",
    "load_meta",
    "load_signing_key",
    "save_envelope_state",
    "save_logbook",
    "save_meta",
    "vacant_dir",
    "vacant_home",
]


GENESIS_KIND = "GENESIS"
KEY_FILE = "key.json"
LOGBOOK_FILE = "logbook.jsonl"
META_FILE = "meta.json"
ENVELOPE_STATE_FILE = "envelope_state.json"
"""Per-target chain state for outgoing calls (Pfix3 B6).

Keyed by target ``vacant_id_hex``; tracks the last accepted envelope
on the request (caller → target) and response (target → caller)
chains so the next ``vacant call`` to the same target advances seq +
prev_envelope_hash correctly. Without this file the CLI defaulted
``sequence_no=1`` on every call → second call to a target was
rejected as replay by the server."""

KEYRING_SERVICE = "vacant.cli"
"""`service` argument used for every `keyring.set_password` /
`keyring.get_password` call. Stable across versions so the OS keyring
entry survives upgrades."""

_INSECURE_WARN = (
    "WARN: vacant {name!r} private seed written PLAINTEXT to {path} "
    "(--insecure-demo). The seed controls the vacant; anyone who reads "
    "this file can impersonate it. Use only for local demos / short-"
    "lived CI; never on a system with real network exposure. See "
    "SECURITY.md §Local key storage for the risk model.\n"
)


class LocalVacantError(RuntimeError):
    """Base class for local-store errors."""


class LocalVacantNotFound(LocalVacantError):
    """The named local vacant does not exist."""


class LocalVacantExists(LocalVacantError):
    """A local vacant with that name already exists."""


class LocalVacantKeyringUnavailable(LocalVacantError):
    """The default OS keyring is the `fail` / `null` backend.

    Raised by `init_vacant` when the operator has not opted into
    `insecure_demo=True`. The error message tells the operator how to
    proceed: install a keyring backend or re-run with `--insecure-demo`.
    """


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
    key_storage: str = "plaintext"
    """`keyring` (default, OS keyring) or `plaintext` (--insecure-demo).
    Defaults to `plaintext` so `LocalMeta` files written before F-D
    landed still load cleanly."""


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


def keyring_backend_available() -> bool:
    """True iff the host's default keyring is a real backend.

    The `keyring` library always returns *some* backend from
    `get_keyring()`; on hosts without a working backend it returns
    `keyring.backends.fail.Keyring` (a stub that raises on every
    call). We detect that case by inspecting the module path so
    callers can give a clear error before a write attempt fails.
    """
    try:
        backend = keyring.get_keyring()
    except KeyringError:
        return False
    module = type(backend).__module__
    return not module.endswith(".fail") and not module.endswith(".null")


def init_vacant(name: str, *, insecure_demo: bool = False) -> tuple[VacantId, SigningKey]:
    """Generate a fresh keypair and persist the local-vacant directory.

    Args:
        name: Local vacant name. Validated against path traversal.
        insecure_demo: If True, write the Ed25519 seed in plaintext into
            `key.json` (mode 0600) and emit a stderr WARN. If False
            (default), store the seed in the OS keyring; raise
            `LocalVacantKeyringUnavailable` if no backend is present.

    Returns:
        The new `VacantId` and `SigningKey`.

    Raises:
        LocalVacantExists: If `~/.vacant/<name>/` already exists.
        LocalVacantKeyringUnavailable: If `insecure_demo=False` and the
            host has no working keyring backend.
        LocalVacantError: Any other failure (path traversal, keyring
            write error, …).
    """
    d = vacant_dir(name)
    if d.exists():
        raise LocalVacantExists(name)

    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    seed_hex = bytes(sk).hex()

    if insecure_demo:
        d.mkdir(parents=True)
        key_path = d / KEY_FILE
        key_path.write_text(
            json.dumps(
                {
                    "pubkey_hex": vid.hex(),
                    "seed_hex": seed_hex,
                    "key_storage": "plaintext",
                },
                sort_keys=True,
            )
        )
        os.chmod(key_path, 0o600)
        sys.stderr.write(_INSECURE_WARN.format(name=name, path=key_path))
        key_storage = "plaintext"
    else:
        if not keyring_backend_available():
            raise LocalVacantKeyringUnavailable(
                f"no keyring backend available for vacant {name!r}; "
                "the OS keyring (Keychain on macOS, Secret Service on Linux, "
                "Credential Locker on Windows) is the default storage for the "
                "private seed. Install / unlock a keyring backend, or re-run "
                "`vacant init <name> --insecure-demo` to opt into plaintext "
                "storage. See SECURITY.md §Local key storage for the risk model."
            )
        d.mkdir(parents=True)
        try:
            keyring.set_password(KEYRING_SERVICE, name, seed_hex)
        except KeyringError as exc:
            # Roll back the directory so a partial init doesn't block a
            # retry under a different mode.
            try:
                d.rmdir()
            except OSError:
                pass
            raise LocalVacantError(
                f"keyring store for vacant {name!r} failed: {exc}. "
                "Try `--insecure-demo` if this is a demo / CI host."
            ) from exc
        key_path = d / KEY_FILE
        key_path.write_text(
            json.dumps(
                {"pubkey_hex": vid.hex(), "key_storage": "keyring"},
                sort_keys=True,
            )
        )
        os.chmod(key_path, 0o600)
        key_storage = "keyring"

    lb = Logbook()
    lb.append(GENESIS_KIND, {"name": name, "vacant_id": vid.hex()}, sk)
    save_logbook(name, lb)

    meta = LocalMeta(
        vacant_id_hex=vid.hex(),
        state="LOCAL",
        created_at=datetime.now(UTC).isoformat(),
        key_storage=key_storage,
    )
    save_meta(name, meta)
    return vid, sk


def load_signing_key(name: str) -> SigningKey:
    """Load the Ed25519 signing key for `name`.

    Looks up `key_storage` from `meta.json` (or, for legacy directories
    without it, infers from `key.json`'s `key_storage` field, then falls
    back to the plaintext seed). Raises `LocalVacantNotFound` if the
    directory is missing entirely; raises `LocalVacantError` if the
    keyring entry has gone missing under us (e.g. operator cleared the
    Keychain after init).
    """
    p = vacant_dir(name) / KEY_FILE
    if not p.exists():
        raise LocalVacantNotFound(name)
    obj = json.loads(p.read_text())
    storage = obj.get("key_storage")
    if storage is None:
        # Legacy file: pre-F-D init wrote `seed_hex` without
        # `key_storage`. Treat as plaintext.
        storage = "plaintext" if "seed_hex" in obj else "keyring"

    if storage == "keyring":
        seed_hex = keyring.get_password(KEYRING_SERVICE, name)
        if seed_hex is None:
            raise LocalVacantError(
                f"keyring entry for vacant {name!r} not found "
                f"(service={KEYRING_SERVICE!r}); the OS keyring may have been "
                "cleared, or the vacant was created on a different machine. "
                "Reinitialise with `vacant init` or copy the keyring entry over."
            )
        return SigningKey(bytes.fromhex(seed_hex))

    # Plaintext (--insecure-demo or legacy).
    if "seed_hex" not in obj:
        raise LocalVacantError(
            f"vacant {name!r} key.json declares key_storage={storage!r} "
            "but has no seed_hex on disk; cannot load the signing key"
        )
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


# --- envelope state (Pfix3 B6) ---------------------------------------------


def envelope_state_file(name: str) -> Path:
    return vacant_dir(name) / ENVELOPE_STATE_FILE


def load_envelope_state(name: str) -> dict[str, Any]:
    """Load the per-target chain state for ``vacant call``.

    Returns ``{}`` if the file doesn't exist yet (first call). Schema:

        {
          "<target_vacant_id_hex>": {
            "request":  {"last_seq": int, "last_hash_hex": str},
            "response": {"last_seq": int, "last_hash_hex": str}
          }
        }

    Returned as ``dict[str, Any]`` because the file is JSON: leaf
    values are ints + strs and the caller knows the schema. Strict
    typing would force every read site through casts without buying
    safety beyond the schema docstring above.
    """
    p = envelope_state_file(name)
    if not p.exists():
        return {}
    raw = json.loads(p.read_text())
    if not isinstance(raw, dict):
        return {}
    return raw


def save_envelope_state(name: str, state: dict[str, Any]) -> None:
    """Atomically persist the envelope state. Uses ``tempfile +
    os.replace`` so a crashed write does not leave a half-truncated
    file (would otherwise cause the next call to replay seq=1).
    """
    d = vacant_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    p = envelope_state_file(name)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")))
    os.replace(tmp, p)
