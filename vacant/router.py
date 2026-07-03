"""Router — trust on/off 的單開關路由面（12 §1／裁決 B2：沿用現有 UCB，Thompson 延後）。

`trust on`  → registry.route（rep_score ＋ UCB 探索額，既有實作）。
`trust off` → registry.route_random（確定性隨機，同一工具同一介面，一個布林差）。

這就是「掛勾」的產品化表示：off 模式＝隨機路由、無信譽訊號進選擇；
demo 與批次實驗（X3 的 A0 臂）共用同一條開關。probation 強制稽核的
路由端掛點（權重上限）依裁決 B2 與牙齒一起後推。
"""

from __future__ import annotations

from .body import CapabilityCard
from .registry import Registry


class Router:
    def __init__(self, registry: Registry, *, trust_on: bool = True) -> None:
        self.registry = registry
        self.trust_on = trust_on

    def toggle(self, on: bool) -> None:
        self.trust_on = on

    def pick(self, niche: str, substrate: str, *, seed: str = "") -> CapabilityCard | None:
        """選一個交付者。on＝UCB 信譽路由；off＝確定性隨機（seed 供重現）。"""
        if self.trust_on:
            return self.registry.route(niche, substrate)
        return self.registry.route_random(niche, seed=seed)
