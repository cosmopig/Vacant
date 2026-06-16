"""L4 Registry / halo — 發現（按 capability）+ 信譽索引（路由用）。架構總規格 §3 L4 / §8。

關鍵立場（CLAUDE.md / §7.1）：Registry 是聚合 / 索引層，**不是中央路由器**，也不是
實體。每個 vacant 自帶公告（halo）；Registry 只把這些公告聚起來、把簽章 review 聚成
信譽索引供路由查詢。查到後點對點直連（流量不繞 Registry）。

路由 = 把稀少訊號放大成選擇：rep_score + UCB 探索額（給新人冷啟動流量）。
同源降權在 record_review 端處理（raises-cost，非 prevents）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from . import crypto
from .body import CapabilityCard
from .reputation import DIMS, Reputation, ucb_score


@dataclass
class Announcement:
    card: CapabilityCard


class Registry:
    """halo 聚合 + 信譽索引。純查詢，不持有流量。"""

    def __init__(self) -> None:
        self._cards: dict[str, CapabilityCard] = {}
        self._rep = Reputation()  # 聚合：per (target, substrate) 的網路級信譽

    # --- halo：公告 / 發現 -------------------------------------------------
    def announce(self, card: CapabilityCard) -> None:
        """登錄一張能力卡（halo 公告）。**先驗身份綁定再收**。

        vacant_id = multibase(multihash(pubkey)) 是密碼學綁定。若不在此重算驗證，
        攻擊者可公告「別人的 vacant_id + 自己的 pubkey」污染 registry → 因為 ingress
        正是用 registry 的 pub_hex 驗章（gateway.py），等於開了冒名後門。
        （Codex 獨立審查抓到的 Bug 1，已修。）
        """
        if not card.pub_hex:
            raise ValueError("公告缺 pub_hex，無法驗證身份綁定")
        derived = crypto.vacant_id_from_pubkey(crypto.pub_from_hex(card.pub_hex))
        if derived != card.vacant_id:
            raise ValueError(
                f"身份綁定不符：pubkey 推導出 {derived[:16]}…，公告卻自稱 {card.vacant_id[:16]}…"
            )
        self._cards[card.vacant_id] = card

    def discover(self, niche: str) -> list[CapabilityCard]:
        """按能力匹配（MVP：niche 標籤精確比對；規模大再上 embedding 最近鄰）。"""
        return [c for c in self._cards.values() if niche in c.niches]

    def card(self, vacant_id: str) -> CapabilityCard | None:
        return self._cards.get(vacant_id)

    # --- 信譽索引 ----------------------------------------------------------
    def _same_signal(self, reviewer_id: str, target_id: str) -> bool:
        """同源偵測：同一 controller 互評 → 降權（raises-cost，閾值公開可被繞）。"""
        rc = self._cards.get(reviewer_id)
        tc = self._cards.get(target_id)
        if rc and tc and rc.controller and rc.controller == tc.controller:
            return True
        return False

    def record_review(
        self,
        reviewer_id: str,
        target_id: str,
        substrate: str,
        scores: dict[str, float],
        *,
        weight: float = 1.0,
    ) -> None:
        same = self._same_signal(reviewer_id, target_id)
        self._rep.record_review(target_id, substrate, scores, weight=weight, same_signal=same)

    def reputation_of(self, target_id: str, substrate: str) -> float:
        return self._rep.score(target_id, substrate)

    def standing(self, vacant_id: str, substrate: str | None = None) -> tuple[float, float]:
        """某 vacant 的信譽：(score, observations)。

        供 ingress 信譽把關用（被呼叫方判斷要不要接這個 caller 的活）。
          - 給 substrate → 只看「在這顆腦上」的信譽（與 egress 路由同口徑；避免在腦 A
            上爛、卻靠腦 B 的好成績矇混過關）。
          - 不給 → 跨 substrate 平均（較寬鬆，僅供概覽）。
        無任何觀測 → 回 (中性 0.5, 0)，讓新人靠探索通過（不誤殺冷啟動）。
        """
        cells = [
            (t, s)
            for (t, s) in self._rep._cells
            if t == vacant_id and (substrate is None or s == substrate)
        ]
        if not cells:
            return 0.5, 0.0
        scores = [self._rep.score(t, s) for (t, s) in cells]
        obs = sum(self._rep.observations(t, s) for (t, s) in cells)
        return sum(scores) / len(scores), obs

    # --- 路由（UCB）-------------------------------------------------------
    def route(
        self, niche: str, substrate: str, *, explore_c: float = 0.3
    ) -> CapabilityCard | None:
        """在能解此 niche 的候選裡，用 UCB 挑一個（rep + 探索額）。"""
        cands = self.discover(niche)
        if not cands:
            return None
        total_obs = sum(self._rep.observations(c.vacant_id, substrate) for c in cands)

        def key(c: CapabilityCard) -> float:
            rep = self._rep.score(c.vacant_id, substrate)
            obs = self._rep.observations(c.vacant_id, substrate)
            return ucb_score(rep, obs, total_obs, c=explore_c)

        return max(cands, key=key)

    def route_random(self, niche: str, *, seed: str = "") -> CapabilityCard | None:
        """C1 對照：無信譽、隨機路由（確定性以利重現）。"""
        cands = self.discover(niche)
        if not cands:
            return None
        idx = int(hashlib.sha256(f"{niche}:{seed}".encode()).hexdigest(), 16) % len(cands)
        return sorted(cands, key=lambda c: c.vacant_id)[idx]

    def leaderboard(self, niche: str, substrate: str) -> list[tuple[str, float]]:
        cands = self.discover(niche)
        return sorted(
            ((c.vacant_id, self._rep.score(c.vacant_id, substrate)) for c in cands),
            key=lambda x: -x[1],
        )
