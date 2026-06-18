"""L1 身分 — keypair + vacant_id，存在「信任庫」裡（閘道擁有，Hermes 看不到）。

架構總規格 §3 L1 / §5：
  - keypair 放閘道、agent 推理看不到（身份不暴露給腦）。
  - 私鑰用 OS 檔案權限保護（0o600）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from . import crypto
from .atomic import atomic_write_bytes, atomic_write_text


@dataclass
class Identity:
    vacant_id: str
    _sk: Ed25519PrivateKey
    _pub: Ed25519PublicKey

    @classmethod
    def generate(cls) -> "Identity":
        sk, pub = crypto.keygen()
        return cls(vacant_id=crypto.vacant_id_from_pubkey(pub), _sk=sk, _pub=pub)

    @property
    def pub(self) -> Ed25519PublicKey:
        return self._pub

    def sign(self, message: bytes) -> bytes:
        return crypto.sign(self._sk, message)

    # --- 存檔 / 載回（信任庫目錄）------------------------------------------
    def save(self, dir_path: Path, *, passphrase: bytes | None = None) -> None:
        dir_path.mkdir(parents=True, exist_ok=True)
        os.chmod(dir_path, 0o700)  # 私鑰目錄收緊
        priv_path = dir_path / "identity.key"
        # 原子寫入私鑰，立即 chmod 0600。passphrase 給定時加密私鑰（production 金鑰保護）。
        atomic_write_bytes(priv_path, crypto.priv_to_pem(self._sk, passphrase=passphrase))
        os.chmod(priv_path, 0o600)
        atomic_write_text(dir_path / "identity.pub", crypto.pub_to_hex(self._pub) + "\n")
        atomic_write_text(dir_path / "vacant_id", self.vacant_id + "\n")

    @classmethod
    def load(cls, dir_path: Path, *, passphrase: bytes | None = None) -> "Identity":
        sk = crypto.priv_from_pem((dir_path / "identity.key").read_bytes(), passphrase=passphrase)
        pub = sk.public_key()
        return cls(vacant_id=crypto.vacant_id_from_pubkey(pub), _sk=sk, _pub=pub)


@dataclass(frozen=True)
class PublicIdentity:
    """別的 vacant 對你的認識：只有 vacant_id + pubkey（用來驗章）。"""

    vacant_id: str
    pub: Ed25519PublicKey

    @classmethod
    def from_hex(cls, vacant_id: str, pub_hex: str) -> "PublicIdentity":
        return cls(vacant_id=vacant_id, pub=crypto.pub_from_hex(pub_hex))

    def verify(self, message: bytes, signature: bytes) -> bool:
        return crypto.verify(self.pub, message, signature)
