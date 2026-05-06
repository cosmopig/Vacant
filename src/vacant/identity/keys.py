"""Keypair lifecycle: vaults + rotation + revocation.

P2 owns the *lifecycle* of Ed25519 keypairs that P0 placed in
`core/crypto.py`. This module exposes:

* `KeyVault` ABC + two concrete impls (`InMemoryVault` for tests,
  `FileVault` for encrypted-at-rest local storage)
* `rotate_key(...)` — atomic rotation that emits a `KEY_ROTATION` log
  entry signed by **both** the old and the new key, so a future verifier
  can reconstruct the chain of custody from the logbook alone.
* `revoke_key(...)` — terminal `KEY_REVOCATION` log entry signed by the
  key being revoked. Subsequent attempts to sign with that key are a
  caller bug; downstream code that consults the logbook can detect the
  revocation by inspecting the trailing entry.

Real HSM / TEE integration (THEORY_V5 §0.1) is intentionally a TODO; the
`KeyVault` ABC is the seam.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from vacant.core.crypto import (
    SigningKey,
    VerifyKey,
    hash_blake2b,
    keygen,
    sign,
)
from vacant.core.types import Logbook, LogEntry
from vacant.identity.errors import KeyNotFoundError, KeyRevokedError, KeyVaultError

__all__ = [
    "KEY_REVOCATION_KIND",
    "KEY_ROTATION_KIND",
    "FileVault",
    "InMemoryVault",
    "KeyVault",
    "RevocationRecord",
    "RotationRecord",
    "revoke_key",
    "rotate_key",
]


KEY_ROTATION_KIND = "KEY_ROTATION"
KEY_REVOCATION_KIND = "KEY_REVOCATION"

# PBKDF2 params for FileVault: NIST SP 800-132 minimum salt length 16 bytes,
# iteration count tracks 2026 OWASP guidance for SHA-256 (>= 600k).
_FILEVAULT_PBKDF2_ITERATIONS = 600_000
_FILEVAULT_SALT_BYTES = 16


# --- KeyVault ABC + impls ----------------------------------------------------


class KeyVault(ABC):
    """Abstract key-of-record store. Real HSM / TEE impls plug in here.

    All operations are sync (vaults are typically tiny local stores;
    making them async forces every caller into asyncio for no
    benefit). I/O-heavy implementations can wrap themselves in
    `asyncio.to_thread` at the call site.
    """

    @abstractmethod
    def store(self, key_id: str, signing_key: SigningKey) -> None:
        """Persist `signing_key` under `key_id`.

        Args:
            key_id: Non-empty identifier. Implementations may impose
                additional restrictions (e.g. `FileVault` rejects
                separators).
            signing_key: The Ed25519 private key to store.

        Raises:
            KeyVaultError: On invalid `key_id` or write failure.
        """

    @abstractmethod
    def load(self, key_id: str) -> SigningKey:
        """Retrieve the signing key registered under `key_id`.

        Args:
            key_id: Identifier previously passed to `store()`.

        Returns:
            The reconstituted `SigningKey`.

        Raises:
            KeyNotFoundError: If `key_id` is not registered.
            KeyVaultError: On decryption / decode failure (e.g.
                wrong passphrase for `FileVault`).
        """

    @abstractmethod
    def delete(self, key_id: str) -> None:
        """Remove `key_id` from the vault.

        Args:
            key_id: Identifier previously passed to `store()`.

        Raises:
            KeyNotFoundError: If `key_id` is not registered.
        """

    @abstractmethod
    def has(self, key_id: str) -> bool:
        """Check whether `key_id` is registered.

        Args:
            key_id: Identifier to look up.

        Returns:
            `True` if `load(key_id)` would succeed, `False` otherwise.
            Implementations should not raise for missing keys here.
        """


class InMemoryVault(KeyVault):
    """Reference impl. Not durable; not thread-safe; for tests + demo."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def store(self, key_id: str, signing_key: SigningKey) -> None:
        if not key_id:
            raise KeyVaultError("key_id must be non-empty")
        self._data[key_id] = bytes(signing_key)

    def load(self, key_id: str) -> SigningKey:
        try:
            seed = self._data[key_id]
        except KeyError as exc:
            raise KeyNotFoundError(key_id) from exc
        return SigningKey(seed)

    def delete(self, key_id: str) -> None:
        if key_id not in self._data:
            raise KeyNotFoundError(key_id)
        del self._data[key_id]

    def has(self, key_id: str) -> bool:
        return key_id in self._data


class FileVault(KeyVault):
    """File-backed vault, AES-GCM under PBKDF2 via `cryptography.fernet`.

    The passphrase is supplied at construction (callers should source it
    from an env var or OS keyring; the vault never logs or stringifies
    it). Each `key_id` becomes one file `<root>/<key_id>.vault`. PBKDF2
    iteration count tracks 2026 OWASP guidance for SHA-256 (>= 600k);
    rotating that constant requires re-encrypting existing blobs.

    Args:
        root: Directory to write vault files into. Created if missing.
        passphrase: Non-empty secret. `str` is encoded as UTF-8.

    Raises:
        KeyVaultError: If `passphrase` is empty.
    """

    SUFFIX = ".vault"

    def __init__(self, root: os.PathLike[str] | str, passphrase: bytes | str) -> None:
        from pathlib import Path

        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._pass = passphrase.encode("utf-8") if isinstance(passphrase, str) else passphrase
        if not self._pass:
            raise KeyVaultError("FileVault: passphrase must be non-empty")

    def _path(self, key_id: str) -> os.PathLike[str]:
        if "/" in key_id or "\\" in key_id or "\0" in key_id or not key_id:
            raise KeyVaultError(f"FileVault: invalid key_id {key_id!r}")
        return self._root / f"{key_id}{self.SUFFIX}"

    def _cipher(self, salt: bytes) -> Fernet:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=_FILEVAULT_PBKDF2_ITERATIONS,
        )
        # Fernet needs a urlsafe-base64 32-byte key.
        import base64

        return Fernet(base64.urlsafe_b64encode(kdf.derive(self._pass)))

    def store(self, key_id: str, signing_key: SigningKey) -> None:
        path = self._path(key_id)
        salt = os.urandom(_FILEVAULT_SALT_BYTES)
        token = self._cipher(salt).encrypt(bytes(signing_key))
        # Write atomically: tmp file + rename (POSIX guarantees atomicity).
        from pathlib import Path

        p = Path(path)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(salt + token)
        os.replace(tmp, p)

    def load(self, key_id: str) -> SigningKey:
        from pathlib import Path

        p = Path(self._path(key_id))
        if not p.exists():
            raise KeyNotFoundError(key_id)
        blob = p.read_bytes()
        if len(blob) < _FILEVAULT_SALT_BYTES + 1:
            raise KeyVaultError(f"FileVault: corrupt blob for {key_id!r}")
        salt, token = blob[:_FILEVAULT_SALT_BYTES], blob[_FILEVAULT_SALT_BYTES:]
        try:
            seed = self._cipher(salt).decrypt(token)
        except InvalidToken as exc:
            raise KeyVaultError(
                f"FileVault: could not decrypt {key_id!r} (wrong passphrase?)"
            ) from exc
        return SigningKey(seed)

    def delete(self, key_id: str) -> None:
        from pathlib import Path

        p = Path(self._path(key_id))
        if not p.exists():
            raise KeyNotFoundError(key_id)
        p.unlink()

    def has(self, key_id: str) -> bool:
        from pathlib import Path

        return Path(self._path(key_id)).exists()


# --- Rotation ----------------------------------------------------------------


@dataclass(frozen=True)
class RotationRecord:
    """Result of `rotate_key`.

    Attributes:
        new_signing_key: The freshly-generated private key. Caller is
            responsible for storing it in the vault under whatever
            `key_id` they want.
        new_verify_key: Public side of `new_signing_key`.
        entry: The `KEY_ROTATION` log entry that was appended to the
            logbook in this same call. Its `payload` carries the
            old/new pubkey hashes and the new key's consent signature.
    """

    new_signing_key: SigningKey
    new_verify_key: VerifyKey
    entry: LogEntry


def _pubkey_hash(vk: VerifyKey) -> bytes:
    return hash_blake2b(bytes(vk))


def rotate_key(
    *,
    old_signing_key: SigningKey,
    logbook: Logbook,
) -> RotationRecord:
    """Rotate to a fresh keypair, atomically appending a chain-of-custody entry.

    The new entry is signed by both keys: the old key proves it
    consented to handing off custody (it owns the entry signature); the
    new key proves it accepted (its consent signature lives inside the
    payload). Without the new-side consent, a leaked old key could
    rotate-to-attacker against an unwilling target. With it, a future
    verifier can reconstruct the entire rotation chain from the logbook
    alone — no out-of-band state needed.

    Args:
        old_signing_key: The currently-active private key. Will sign
            the resulting log entry.
        logbook: The vacant's logbook. A new `KEY_ROTATION` entry is
            appended in-place.

    Returns:
        A `RotationRecord` carrying the new keypair and the appended
        log entry. The caller MUST persist `new_signing_key` (e.g.
        `vault.store(key_id, record.new_signing_key)`) and stop using
        `old_signing_key` for new entries.
    """
    old_vk = old_signing_key.verify_key
    new_sk, new_vk = keygen()

    old_pubkey_hash = _pubkey_hash(old_vk)
    new_pubkey_hash = _pubkey_hash(new_vk)
    handoff_payload = old_pubkey_hash + b"\x1f" + new_pubkey_hash
    new_key_consent = sign(new_sk, handoff_payload)

    payload = {
        "old_pubkey_hash": old_pubkey_hash.hex(),
        "new_pubkey_hash": new_pubkey_hash.hex(),
        "new_pubkey": bytes(new_vk).hex(),
        "new_key_consent": new_key_consent.hex(),
    }
    entry = logbook.append(KEY_ROTATION_KIND, payload, old_signing_key)
    return RotationRecord(new_signing_key=new_sk, new_verify_key=new_vk, entry=entry)


# --- Revocation --------------------------------------------------------------


@dataclass(frozen=True)
class RevocationRecord:
    """Terminal record for a revoked key.

    Attributes:
        entry: The appended `KEY_REVOCATION` log entry.
        reason: Free-form explanation (echoed from the call site).
    """

    entry: LogEntry
    reason: str


def revoke_key(
    *,
    signing_key: SigningKey,
    logbook: Logbook,
    reason: str,
) -> RevocationRecord:
    """Append a terminal `KEY_REVOCATION` entry signed by the key itself.

    The signing key remains cryptographically capable of producing
    valid signatures after this call — that's precisely why the
    revocation is published into the auditable logbook: future
    verifiers consult `is_key_revoked()` and reject any subsequent
    signatures from this key. Callers MUST stop signing with the
    revoked key; this is a contract, not a runtime guard.

    Args:
        signing_key: The key being revoked. Signs its own revocation.
        logbook: The vacant's logbook. A new `KEY_REVOCATION` entry is
            appended in-place.
        reason: Non-empty explanation. Stored verbatim in the entry
            payload.

    Returns:
        A `RevocationRecord` carrying the appended entry and the
        reason.

    Raises:
        KeyRevokedError: If `reason` is blank or whitespace-only.
    """
    if not reason.strip():
        raise KeyRevokedError("revoke_key: reason must be non-empty")
    payload = {
        "pubkey_hash": _pubkey_hash(signing_key.verify_key).hex(),
        "reason": reason,
    }
    entry = logbook.append(KEY_REVOCATION_KIND, payload, signing_key)
    return RevocationRecord(entry=entry, reason=reason)


def is_key_revoked(logbook: Logbook, vk: VerifyKey) -> bool:
    """Check the logbook for a `KEY_REVOCATION` entry naming `vk`.

    Args:
        logbook: A logbook that has already been verified
            (`verify_chain` / `verify_chain_or_raise`); this function
            does not re-verify, it only scans the kind + payload.
        vk: The verify-key whose pubkey_hash is being checked.

    Returns:
        `True` iff at least one entry of kind `KEY_REVOCATION` whose
        payload's `pubkey_hash` matches `vk` appears anywhere in
        `logbook.entries`. Order is irrelevant — once revoked, always
        revoked.
    """
    target = _pubkey_hash(vk).hex()
    for entry in logbook.entries:
        if entry.kind == KEY_REVOCATION_KIND and entry.payload.get("pubkey_hash") == target:
            return True
    return False
