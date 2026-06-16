"""密碼學基元 — Ed25519 + vacant_id（唯一的 *prevents* 級保證）。

對應架構總規格 §5：
    Identity   { vacant_id = multibase(multihash(pubkey)), pub, priv(OS 權限保護) }

誠實邊界（§10）：簽章 / hash chain 在 *key custody 假設下* 是 prevents；
一旦私鑰外洩或 controller 有 root，退化為 detects（demo custody）。
"""

from __future__ import annotations

import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# --- multihash / multibase（faithful 子集）----------------------------------
# multihash: <code><length><digest>，sha2-256 的 code = 0x12、length = 0x20。
_SHA2_256_CODE = 0x12
_SHA2_256_LEN = 0x20
# multibase base58btc 前綴 = 'z'
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n > 0:
        n, rem = divmod(n, 58)
        out = _B58_ALPHABET[rem] + out
    # 保留 leading-zero bytes
    pad = len(data) - len(data.lstrip(b"\x00"))
    return _B58_ALPHABET[0] * pad + out


def vacant_id_from_pubkey(pub: Ed25519PublicKey) -> str:
    """vacant_id = multibase(multihash(pubkey))。穩定、可由 pubkey 重算。"""
    raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    digest = hashlib.sha256(raw).digest()
    multihash = bytes([_SHA2_256_CODE, _SHA2_256_LEN]) + digest
    return "z" + _b58encode(multihash)


# --- keygen / sign / verify -------------------------------------------------
def keygen() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    sk = Ed25519PrivateKey.generate()
    return sk, sk.public_key()


def sign(sk: Ed25519PrivateKey, message: bytes) -> bytes:
    return sk.sign(message)


def verify(pub: Ed25519PublicKey, message: bytes, signature: bytes) -> bool:
    try:
        pub.verify(signature, message)
        return True
    except InvalidSignature:
        return False


# --- 序列化（存檔 / 線上）----------------------------------------------------
def priv_to_pem(sk: Ed25519PrivateKey) -> bytes:
    return sk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def priv_from_pem(pem: bytes) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("not an Ed25519 private key")
    return key


def pub_to_hex(pub: Ed25519PublicKey) -> str:
    return pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def pub_from_hex(hex_str: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(hex_str))
