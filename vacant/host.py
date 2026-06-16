"""Host — 一台機器上實際常駐的東西。底層技術規格 §0/§1。

程序模型：host（唯一常駐）持有
  - 一份共享 substrate（模 model-server：數千 vacant 串行共用一顆腦）
  - 一個 waker（vacant_id→HOME 映射 + 喚醒）
  - 一個 registry（halo 聚合 + 信譽索引）
  - 每個 vacant 一個薄 gateway（sidecar）

vacant 本身睡在硬碟；host 按需喚醒。這支 Host 類別把 §6.2「生成 vacant」一條龍
（鑄身份→建身體→掛閘道→公告）封成 `mint()`，給測試 / demo / CLI 共用。
"""

from __future__ import annotations

from pathlib import Path

from .body import VacantBody
from .gateway import Gateway
from .registry import Registry
from .substrate import EchoSubstrate, Substrate
from .waker import Waker


class Host:
    def __init__(self, root: Path, substrate: Substrate | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.substrate: Substrate = substrate or EchoSubstrate()
        self.waker = Waker(self.root, self.substrate)
        self.registry = Registry()
        self.gateways: dict[str, Gateway] = {}      # vacant_id → gateway
        self._name_to_id: dict[str, str] = {}

    def mint(
        self,
        name: str,
        niches: list[str],
        *,
        controller: str = "",
    ) -> Gateway:
        """§6.2 生成 vacant：鑄身份 → 建身體 → 註冊 HOME → 公告 halo → 掛閘道。"""
        body = VacantBody.create(name, self.root, niches=niches, controller=controller)
        self.waker.register(body)
        self.registry.announce(body.card)
        gw = Gateway(name, body.identity.vacant_id, self.root, self.waker, self.registry)
        # 與既有節點點對點連線（in-process 模網路；上機為 peer gateway 握手）
        for other in self.gateways.values():
            gw.connect(other)
        self.gateways[body.identity.vacant_id] = gw
        self._name_to_id[name] = body.identity.vacant_id
        return gw

    def adopt(self, name: str) -> Gateway:
        """把硬碟上已存在的 vacant 身體接進這個 host（不重建身份）。"""
        body = VacantBody.load(name, self.root)
        self.waker.register(body)
        self.registry.announce(body.card)
        gw = Gateway(name, body.identity.vacant_id, self.root, self.waker, self.registry)
        for other in self.gateways.values():
            gw.connect(other)
        self.gateways[body.identity.vacant_id] = gw
        self._name_to_id[name] = body.identity.vacant_id
        return gw

    def has(self, name: str) -> bool:
        return name in self._name_to_id

    def gateway(self, name: str) -> Gateway:
        return self.gateways[self._name_to_id[name]]

    def body(self, name: str) -> VacantBody:
        """從硬碟載入某 vacant 的當前身體（睡著的狀態）。"""
        return VacantBody.load(name, self.root)

    def vacant_id(self, name: str) -> str:
        return self._name_to_id[name]
