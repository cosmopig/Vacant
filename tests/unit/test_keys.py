"""Key vault + rotation + revocation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from vacant.core.crypto import SigningKey, VerifyKey, keygen, sign, verify
from vacant.core.types import Logbook
from vacant.identity.errors import KeyNotFoundError, KeyRevokedError, KeyVaultError
from vacant.identity.keys import (
    KEY_REVOCATION_KIND,
    KEY_ROTATION_KIND,
    FileVault,
    InMemoryVault,
    is_key_revoked,
    revoke_key,
    rotate_key,
)

# --- InMemoryVault -----------------------------------------------------------


def test_inmemory_vault_round_trip(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    sk, _vk = test_keypair
    vault = InMemoryVault()
    vault.store("alice", sk)
    assert vault.has("alice")
    loaded = vault.load("alice")
    sig = sign(loaded, b"msg")
    assert verify(sk.verify_key, b"msg", sig)


def test_inmemory_vault_missing_load_raises() -> None:
    vault = InMemoryVault()
    with pytest.raises(KeyNotFoundError):
        vault.load("nope")


def test_inmemory_vault_missing_delete_raises() -> None:
    vault = InMemoryVault()
    with pytest.raises(KeyNotFoundError):
        vault.delete("nope")


def test_inmemory_vault_rejects_empty_id(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    sk, _ = test_keypair
    vault = InMemoryVault()
    with pytest.raises(KeyVaultError):
        vault.store("", sk)


def test_inmemory_vault_delete_then_has_false(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    sk, _ = test_keypair
    vault = InMemoryVault()
    vault.store("a", sk)
    vault.delete("a")
    assert not vault.has("a")


# --- FileVault ---------------------------------------------------------------


def test_filevault_round_trip(tmp_path: Path, test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    sk, _ = test_keypair
    vault = FileVault(tmp_path, passphrase="correct horse battery staple")
    vault.store("alice", sk)
    assert vault.has("alice")
    loaded = vault.load("alice")
    assert bytes(loaded) == bytes(sk)


def test_filevault_wrong_passphrase_fails(
    tmp_path: Path, test_keypair: tuple[SigningKey, VerifyKey]
) -> None:
    sk, _ = test_keypair
    FileVault(tmp_path, passphrase="right").store("a", sk)
    with pytest.raises(KeyVaultError):
        FileVault(tmp_path, passphrase="wrong").load("a")


def test_filevault_missing_load_raises(tmp_path: Path) -> None:
    vault = FileVault(tmp_path, passphrase="x")
    with pytest.raises(KeyNotFoundError):
        vault.load("ghost")


def test_filevault_rejects_empty_passphrase(tmp_path: Path) -> None:
    with pytest.raises(KeyVaultError):
        FileVault(tmp_path, passphrase="")


def test_filevault_rejects_pathish_key_id(
    tmp_path: Path, test_keypair: tuple[SigningKey, VerifyKey]
) -> None:
    sk, _ = test_keypair
    vault = FileVault(tmp_path, passphrase="x")
    with pytest.raises(KeyVaultError):
        vault.store("../escape", sk)


def test_filevault_delete_round_trip(
    tmp_path: Path, test_keypair: tuple[SigningKey, VerifyKey]
) -> None:
    sk, _ = test_keypair
    vault = FileVault(tmp_path, passphrase="x")
    vault.store("a", sk)
    vault.delete("a")
    assert not vault.has("a")
    with pytest.raises(KeyNotFoundError):
        vault.delete("a")


def test_filevault_passphrase_bytes_works(
    tmp_path: Path, test_keypair: tuple[SigningKey, VerifyKey]
) -> None:
    sk, _ = test_keypair
    vault = FileVault(tmp_path, passphrase=b"binary-pass")
    vault.store("a", sk)
    assert bytes(vault.load("a")) == bytes(sk)


# --- Rotation ----------------------------------------------------------------


def test_rotate_key_appends_signed_entry(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    fresh_logbook.append("genesis", {}, sk)
    record = rotate_key(old_signing_key=sk, logbook=fresh_logbook)
    assert record.entry.kind == KEY_ROTATION_KIND
    # Old key still verifies the chain (entry was signed by it).
    assert fresh_logbook.verify_chain(vk) is True
    # The rotation entry exposes both old and new pubkey hashes + new key consent.
    payload = record.entry.payload
    assert "old_pubkey_hash" in payload
    assert "new_pubkey_hash" in payload
    assert "new_pubkey" in payload
    assert "new_key_consent" in payload
    # New key consent verifies under the new pubkey over the canonical handoff payload.
    handoff = (
        bytes.fromhex(payload["old_pubkey_hash"])
        + b"\x1f"
        + bytes.fromhex(payload["new_pubkey_hash"])
    )
    assert verify(record.new_verify_key, handoff, bytes.fromhex(payload["new_key_consent"]))


def test_rotate_key_distinct_keypair(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    fresh_logbook.append("genesis", {}, sk)
    record = rotate_key(old_signing_key=sk, logbook=fresh_logbook)
    assert bytes(record.new_verify_key) != bytes(vk)


# --- Revocation --------------------------------------------------------------


def test_revoke_key_writes_revocation_entry(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    fresh_logbook.append("genesis", {}, sk)
    rec = revoke_key(signing_key=sk, logbook=fresh_logbook, reason="lost laptop")
    assert rec.entry.kind == KEY_REVOCATION_KIND
    assert rec.reason == "lost laptop"
    assert is_key_revoked(fresh_logbook, vk) is True


def test_revoke_key_rejects_empty_reason(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    fresh_logbook.append("genesis", {}, sk)
    with pytest.raises(KeyRevokedError):
        revoke_key(signing_key=sk, logbook=fresh_logbook, reason="   ")


def test_is_key_revoked_false_for_fresh_logbook(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    fresh_logbook.append("genesis", {}, sk)
    assert is_key_revoked(fresh_logbook, vk) is False


def test_is_key_revoked_uses_pubkey_hash(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    other_sk, other_vk = keygen()
    fresh_logbook.append("genesis", {}, sk)
    revoke_key(signing_key=sk, logbook=fresh_logbook, reason="x")
    assert is_key_revoked(fresh_logbook, vk) is True
    assert is_key_revoked(fresh_logbook, other_vk) is False
    _ = other_sk
