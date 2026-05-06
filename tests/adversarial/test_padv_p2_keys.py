"""Padv P2 — adversarial tests for `vacant.identity.keys`.

Each test assumes the attacker has whatever capability the attack model
labels in its docstring (e.g. "attacker controls the FileVault file") and
asserts that the documented defense layer (P / D / C, per THEORY_V5 §0.2)
catches them.

Spec anchors:
- `architecture/components/P2_identity.md` §3.1 (vacant_id), §3.5 (rotation)
- `architecture/THEORY_V5.md` §6 (38-attack matrix)
- `dispatch/Padv_review.md` §"P2 Identity attacks to consider"
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vacant.core.crypto import (
    SigningKey,
    VerifyKey,
    hash_blake2b,
    keygen,
    sign,
    verify,
)
from vacant.core.types import EMPTY_PREV_HASH, Logbook
from vacant.identity.errors import KeyVaultError
from vacant.identity.keys import (
    KEY_ROTATION_KIND,
    FileVault,
    is_key_revoked,
    revoke_key,
    rotate_key,
)

# --- Attack 1: rotation grindstone --------------------------------------------
# Padv §"Key rotation grindstone": rapid rotations to obscure history.
# Defense (P): every rotation entry is hash-chained + signed; an N-rotation
# burst still produces a verifiable monotone chain — there is no shortcut
# that hides earlier rotations.


def test_attack_rotation_grindstone_chain_remains_verifiable() -> None:
    """20 rapid rotations: the resulting chain must verify against EACH
    pubkey active in its segment, and the prev_hash links must be monotone.
    """
    sk0, vk0 = keygen()
    lb = Logbook()
    lb.append("genesis", {}, sk0)

    current_sk: SigningKey = sk0
    current_vk: VerifyKey = vk0
    pubkeys: list[VerifyKey] = [vk0]
    for _ in range(20):
        rec = rotate_key(old_signing_key=current_sk, logbook=lb)
        # The current pubkey verifies the rotation entry it signed.
        assert lb.entries[-1].verify(current_vk) is True
        # Step keys forward.
        current_sk, current_vk = rec.new_signing_key, rec.new_verify_key
        pubkeys.append(current_vk)

    # prev_hash chain is monotone: each entry's prev_hash matches predecessor's compute_hash.
    expected_prev = EMPTY_PREV_HASH
    for entry in lb.entries:
        assert entry.prev_hash == expected_prev
        expected_prev = entry.compute_hash()

    # Rotation entries appear in order (one per rotation, plus genesis).
    rotations = [e for e in lb.entries if e.kind == KEY_ROTATION_KIND]
    assert len(rotations) == 20
    # Each rotation entry's payload references the preceding pubkey.
    prior_vk = vk0
    for r in rotations:
        assert r.payload["old_pubkey_hash"] == hash_blake2b(bytes(prior_vk)).hex()
        prior_vk_bytes = bytes.fromhex(r.payload["new_pubkey"])
        prior_vk = VerifyKey(prior_vk_bytes)


# --- Attack 2: forged new-key consent ----------------------------------------
# Defense (P): rotation entry binds the new key's *consent* — an attacker who
# knows only the old key cannot forge a valid `new_key_consent` signature
# under the new pubkey.


def test_attack_forged_new_key_consent_does_not_verify() -> None:
    sk_old, _vk_old = keygen()
    lb = Logbook()
    lb.append("genesis", {}, sk_old)
    rec = rotate_key(old_signing_key=sk_old, logbook=lb)
    # Attacker controls the OLD key only; they tamper the consent field,
    # signing with the OLD key (which they have) instead of the new key.
    handoff = (
        bytes.fromhex(rec.entry.payload["old_pubkey_hash"])
        + b"\x1f"
        + bytes.fromhex(rec.entry.payload["new_pubkey_hash"])
    )
    forged_consent = sign(sk_old, handoff)
    # The forged consent does not verify under the *new* pubkey.
    assert verify(rec.new_verify_key, handoff, forged_consent) is False


# --- Attack 3: cross-vacant revocation injection -----------------------------
# Defense (P): logbook is per-vacant + hash-chained + signed. An attacker
# who copies a `KEY_REVOCATION` entry from vacant A's logbook into vacant
# B's logbook breaks the prev_hash chain (so the chain stops verifying).


def test_attack_cross_vacant_revocation_injection_breaks_chain() -> None:
    sk_a, vk_a = keygen()
    lb_a = Logbook()
    lb_a.append("genesis", {}, sk_a)
    revoke_key(signing_key=sk_a, logbook=lb_a, reason="lost laptop")

    sk_b, vk_b = keygen()
    lb_b = Logbook()
    lb_b.append("genesis", {}, sk_b)

    # Attacker steals A's revocation entry and pastes it into B's logbook.
    stolen = lb_a.entries[-1]
    lb_b.entries.append(stolen)

    # Defense: B's chain no longer verifies (signature is for A's key + chain
    # break) and `is_key_revoked` for B's key is still False.
    assert lb_b.verify_chain(vk_b) is False
    assert is_key_revoked(lb_b, vk_b) is False
    # The stolen entry, evaluated alone, is for A — even if grafted in.
    assert is_key_revoked(lb_b, vk_a) is True  # by pubkey hash, but chain is bad


# --- Attack 4: FileVault ciphertext bit-flip ---------------------------------
# Defense (P): Fernet authenticates the ciphertext (HMAC-SHA256). Flipping
# any byte after `store()` causes `load()` to raise `KeyVaultError` rather
# than return a bogus key.


def test_attack_filevault_bitflip_fails_decryption(
    tmp_path: Path, test_keypair: tuple[SigningKey, VerifyKey]
) -> None:
    sk, _ = test_keypair
    vault = FileVault(tmp_path, passphrase="secret")
    vault.store("alice", sk)

    # Tamper exactly one byte past the salt (the first byte of the Fernet token).
    blob_path = tmp_path / "alice.vault"
    blob = bytearray(blob_path.read_bytes())
    blob[20] ^= 0x01
    blob_path.write_bytes(bytes(blob))

    with pytest.raises(KeyVaultError):
        vault.load("alice")


# --- Attack 5: FileVault salt swap -------------------------------------------
# Defense (P): the salt is derived per-store and authenticated as part of
# the encrypted blob's KDF input. Swapping salt bytes from one stored key
# into another's blob yields the wrong KDF output and decryption fails.


def test_attack_filevault_salt_swap_fails(
    tmp_path: Path, test_keypair: tuple[SigningKey, VerifyKey]
) -> None:
    sk_a, _ = test_keypair
    sk_b, _ = keygen()
    vault = FileVault(tmp_path, passphrase="x")
    vault.store("a", sk_a)
    vault.store("b", sk_b)

    a_blob = (tmp_path / "a.vault").read_bytes()
    b_blob = (tmp_path / "b.vault").read_bytes()
    # Splice: a's salt (first 16 bytes) + b's ciphertext.
    spliced = a_blob[:16] + b_blob[16:]
    (tmp_path / "b.vault").write_bytes(spliced)

    with pytest.raises(KeyVaultError):
        vault.load("b")
