"""L1 vacant 身體 — 兩個持久庫，都綁 vacant_id。架構總規格 §3 L1 / §5。

磁碟佈局（一個睡著的 vacant 就只是這些檔）：

    <root>/<name>/
     ├─ trust/                信任庫（閘道擁有；Hermes 看不到）
     │   ├─ identity.key      Ed25519 私鑰（0o600）
     │   ├─ identity.pub      公鑰 hex
     │   ├─ vacant_id         multibase(multihash(pubkey))
     │   ├─ logbook.ndjson    append-only 簽章鏈
     │   ├─ reputation.json   五維 Beta posterior
     │   └─ capability_card.json  niches + endpoint
     └─ home/                 能力庫 = HERMES_HOME（agent 擁有；我們只綁不改）
         ├─ skills.json       已習得 niche
         └─ memory.ndjson     累積記憶

關鍵：keypair 在 trust/、agent 推理碰不到（身份不暴露給腦）；
能力狀態在 home/、是 agent 自己的 HOME，我們只負責「綁對 HOME」。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .atomic import atomic_write_text
from .identity import Identity, PublicIdentity
from .logbook import Logbook
from .reputation import Reputation


def now_ms() -> int:
    return time.time_ns() // 1_000_000


@dataclass
class CapabilityCard:
    """能力卡（halo 的內容）：別人據此發現你。"""

    vacant_id: str
    niches: list[str] = field(default_factory=list)
    endpoint: str = "in-process"
    pub_hex: str = ""
    controller: str = ""   # 同源降權用：同一 controller 的 vacant 互評降權

    def to_json(self) -> dict[str, Any]:
        return {
            "vacant_id": self.vacant_id,
            "niches": self.niches,
            "endpoint": self.endpoint,
            "pub_hex": self.pub_hex,
            "controller": self.controller,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "CapabilityCard":
        return cls(
            vacant_id=d["vacant_id"],
            niches=d.get("niches", []),
            endpoint=d.get("endpoint", "in-process"),
            pub_hex=d.get("pub_hex", ""),
            controller=d.get("controller", ""),
        )


class VacantBody:
    """一個 vacant 的持久身體。睡著時 = 磁碟上的這包檔；醒著時 = 載進 RAM。"""

    def __init__(
        self,
        name: str,
        root: Path,
        identity: Identity,
        logbook: Logbook,
        reputation: Reputation,
        card: CapabilityCard,
    ) -> None:
        self.name = name
        self.root = root
        self.identity = identity
        self.logbook = logbook
        self.reputation = reputation
        self.card = card

    # --- 目錄 --------------------------------------------------------------
    @property
    def dir(self) -> Path:
        return self.root / self.name

    @property
    def trust_dir(self) -> Path:
        return self.dir / "trust"

    @property
    def home_dir(self) -> Path:
        """HERMES_HOME：綁給 substrate 的能力庫。"""
        return self.dir / "home"

    # --- 建立 / 載入 / 寫回 ------------------------------------------------
    @classmethod
    def create(
        cls,
        name: str,
        root: Path,
        *,
        niches: list[str] | None = None,
        controller: str = "",
        endpoint: str = "in-process",
    ) -> "VacantBody":
        identity = Identity.generate()
        from . import crypto

        card = CapabilityCard(
            vacant_id=identity.vacant_id,
            niches=niches or [],
            endpoint=endpoint,
            pub_hex=crypto.pub_to_hex(identity.pub),
            controller=controller,
        )
        body = cls(name, root, identity, Logbook(), Reputation(), card)
        body.persist()
        body.home_dir.mkdir(parents=True, exist_ok=True)
        return body

    @classmethod
    def load(cls, name: str, root: Path) -> "VacantBody":
        trust = root / name / "trust"
        identity = Identity.load(trust)
        logbook = Logbook.load(trust / "logbook.ndjson")
        rep_path = trust / "reputation.json"
        reputation = (
            Reputation.from_json(json.loads(rep_path.read_text(encoding="utf-8")))
            if rep_path.exists()
            else Reputation()
        )
        card = CapabilityCard.from_json(
            json.loads((trust / "capability_card.json").read_text(encoding="utf-8"))
        )
        return cls(name, root, identity, logbook, reputation, card)

    @property
    def lock_path(self) -> Path:
        """並發鎖檔：序列化同一身體的 load→改→persist（見 atomic.file_lock）。"""
        return self.dir / ".lock"

    def persist(self) -> None:
        """把活著時的狀態寫回硬碟（vacant 回睡）。所有檔案原子寫入（防崩潰半截）。"""
        self.identity.save(self.trust_dir)
        self.logbook.save(self.trust_dir / "logbook.ndjson")
        atomic_write_text(self.trust_dir / "reputation.json",
                          json.dumps(self.reputation.to_json(), ensure_ascii=False))
        atomic_write_text(self.trust_dir / "capability_card.json",
                          json.dumps(self.card.to_json(), ensure_ascii=False))

    # --- 便利 --------------------------------------------------------------
    def public_identity(self) -> PublicIdentity:
        return PublicIdentity(self.identity.vacant_id, self.identity.pub)

    def log(self, etype: str, payload: Any) -> None:
        self.logbook.append(etype, payload, self.identity, ts_ms=now_ms())
