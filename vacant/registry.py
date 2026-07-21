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
from .envelope import ReviewEnvelope
from .identity import PublicIdentity
from .reputation import DIMS, SAME_SIGNAL_FLOOR, Reputation, ucb_score

# weight 內生（credit-memory v1 改動3.3）：reviewer 自身信譽 × 觀測飽和度。
#   - 全新 Sybil reviewer（obs=0）→ weight ≈ REVIEWER_WEIGHT_FLOOR（近零）。
#   - 冷啟動不死鎖：地板讓初期 review 仍有微小貢獻（raises-cost，非 prevents——
#     地板是常數優勢，配非線性同源降權後同一 controller 的總貢獻只有 log 級成長）。
REVIEWER_WEIGHT_FLOOR = 0.05
REVIEWER_SATURATION_OBS = 5.0  # obs/(obs+此值)：約 5 筆被審觀測後 weight 才接近自身信譽


class ReviewRejected(Exception):
    """ReviewEnvelope 未過驗收（驗簽 / head 新鮮 / 重放）→ 整筆拒收。"""


@dataclass
class Announcement:
    card: CapabilityCard


class Registry:
    """halo 聚合 + 信譽索引。純查詢，不持有流量。"""

    def __init__(self) -> None:
        self._cards: dict[str, CapabilityCard] = {}
        self._rep = Reputation()  # 聚合：per (stream_id, branch_id, substrate) 的網路級信譽（改動2）
        # 改動3 狀態：目標鏈頭（head 新鮮性）、review 去重、同源計數（非線性降權）
        # target_id → (stream_id, branch_id, head)：vacant_id 只是「現在指向哪條
        # stream」的解析表；信譽本體掛在 stream 三元組上（credit 跟記憶走）。
        self._heads: dict[str, tuple[str, str, str]] = {}
        self._seen_reviews: set[tuple[str, str, str]] = set()  # (reviewer, stream, head)
        self._same_source_k: dict[tuple[str, str], int] = {}   # (controller, target) → 次數

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

    def note_head(self, target_id: str, stream_id: str, branch_id: str, head: str) -> None:
        """記下對某 target 最新觀察到的 (stream_id, branch_id, chain head)。

        head 新鮮性檢查的比對基準：in-process 模擬裡由 gateway 在收到簽章 result
        時回報（上機後即 result envelope 附帶的 chain_head）。改動2：這筆記錄同時
        是 vacant_id → 當前 stream 三元組的**唯一解析表**（信譽查找都經它）。"""
        self._heads[target_id] = (stream_id, branch_id, head)

    def _resolve(self, target_id: str) -> tuple[str, str] | None:
        """vacant_id → 當前 (stream_id, branch_id)；未觀察過其鏈頭 → None。"""
        h = self._heads.get(target_id)
        return (h[0], h[1]) if h else None

    def _reviewer_weight(self, reviewer_id: str, substrate: str) -> float:
        """weight 內生：reviewer 自身信譽 × 觀測飽和 → 不接受外部注入。"""
        score, obs = self.standing(reviewer_id, substrate)
        saturation = obs / (obs + REVIEWER_SATURATION_OBS)
        return max(REVIEWER_WEIGHT_FLOOR, score * saturation)

    def record_review(self, env: ReviewEnvelope) -> float:
        """只收已驗簽的 ReviewEnvelope（credit-memory v1 改動3）。回傳實際採計權重。

        驗收順序：①驗簽（reviewer halo 公告的 pub_hex）→ ②head 新鮮（target_head
        必須等於最新觀察到的鏈頭）→ ③(reviewer, stream, head) 去重防重放 →
        ④weight 內生 ＋ 同源非線性降權（第 k 筆 ~ floor/k，總貢獻 log 級）→ 寫入。
        任一步失敗 raise ReviewRejected，reputation 完全不動。
        """
        # ① 驗簽：reviewer 必須已在 halo 公告（announce 已驗身份綁定）
        rcard = self._cards.get(env.reviewer_id)
        if rcard is None or not rcard.pub_hex:
            raise ReviewRejected(f"reviewer 未在 halo 公告：{env.reviewer_id[:16]}…")
        reviewer_pub = PublicIdentity.from_hex(env.reviewer_id, rcard.pub_hex)
        if not env.verify_sig(reviewer_pub):
            raise ReviewRejected(f"review 驗簽失敗：reviewer {env.reviewer_id[:16]}…")

        # ② head 新鮮：評的必須是「目標當前鏈頭為止」的歷史
        known = self._heads.get(env.target_id)
        if known is None:
            raise ReviewRejected(
                f"無 {env.target_id[:16]}… 的已知鏈頭（須先觀察到其簽章交付）"
            )
        known_stream, known_branch, known_head = known
        if env.target_stream_id != known_stream or env.target_head != known_head:
            raise ReviewRejected(
                f"target_head 不新鮮：got {env.target_head[:12]} want {known_head[:12]}"
            )

        # ③ 去重防重放
        dedup_key = (env.reviewer_id, env.target_stream_id, env.target_head)
        if dedup_key in self._seen_reviews:
            raise ReviewRejected(f"重複 review：{env.reviewer_id[:12]}…@head {env.target_head[:12]}")
        self._seen_reviews.add(dedup_key)

        # ④ weight 內生 ＋ 同源非線性降權（floor/k 取代純地板，v1 改動3.4）
        weight = self._reviewer_weight(env.reviewer_id, env.substrate)
        if self._same_signal(env.reviewer_id, env.target_id):
            controller = self._cards[env.reviewer_id].controller
            k = self._same_source_k.get((controller, env.target_id), 0) + 1
            self._same_source_k[(controller, env.target_id)] = k
            weight = min(weight, SAME_SIGNAL_FLOOR / k)

        # 改動2：信譽寫進被評者的 stream 三元組（credit 跟記憶走，不跟身體走）
        self._rep.record_review(
            env.target_stream_id, env.branch_id, env.substrate, env.scores, weight=weight)
        return weight

    # --- 狀態持久化（信譽/鏈頭/去重/同源計數；halo 卡由呼叫端重新 announce）------
    def state_to_json(self) -> dict[str, Any]:
        return {
            "rep": self._rep.to_json(),
            "heads": {t: list(v) for t, v in self._heads.items()},
            "seen_reviews": [list(k) for k in self._seen_reviews],
            "same_source_k": {f"{c}␟{t}": v for (c, t), v in self._same_source_k.items()},
        }

    def state_from_json(self, d: dict[str, Any]) -> None:
        from .reputation import Reputation
        self._rep = Reputation.from_json(d.get("rep", {}))
        self._heads = {}
        for t, v in d.get("heads", {}).items():
            if len(v) == 2:  # 改動2 前的 (stream, head) 舊檔 → branch 補 "main"
                self._heads[t] = (v[0], "main", v[1])
            else:
                self._heads[t] = (v[0], v[1], v[2])
        self._seen_reviews = {tuple(k) for k in d.get("seen_reviews", [])}
        self._same_source_k = {}
        for key, v in d.get("same_source_k", {}).items():
            c, t = key.split("␟", 1)
            self._same_source_k[(c, t)] = int(v)

    def forget_target(self, target_id: str) -> None:
        """wipe demo 用（12 §7 時刻 4）：抹掉某 target 當前 stream 的信譽格與鏈頭記錄。

        語意＝「同一把 key、信用歸零」：歸屬（idem）在 keypair 續存，值得被託付
        的那部分（被審歷史的聚合）隨記憶抹除一起消失。改動2 之後這個語意大部分
        由 key 結構自然達成（新創世＝新三元組＝空格）；這裡清掉舊格與解析表避免
        孤兒資料殘留。只供 demo/測試；正式實驗的信用不可抹（那是 X4 攻防的前提）。"""
        old = self._heads.pop(target_id, None)
        if old is not None:
            old_stream, old_branch = old[0], old[1]
            self._rep._cells = {
                k: v for k, v in self._rep._cells.items()
                if not (k[0] == old_stream and k[1] == old_branch)
            }
            self._seen_reviews = {k for k in self._seen_reviews if k[1] != old_stream}

    def reputation_of(self, target_id: str, substrate: str) -> float:
        """某 vacant 當前 stream 的信譽分（改動2）；未觀察過其鏈 → 中性 0.5。"""
        resolved = self._resolve(target_id)
        if resolved is None:
            return 0.5
        return self._rep.score(resolved[0], resolved[1], substrate)

    def standing(self, vacant_id: str, substrate: str | None = None) -> tuple[float, float]:
        """某 vacant **當前 stream** 的信譽：(score, observations)（改動2）。

        供 ingress 信譽把關用（被呼叫方判斷要不要接這個 caller 的活）。
          - 給 substrate → 只看「在這顆腦上」的信譽（與 egress 路由同口徑；避免在腦 A
            上爛、卻靠腦 B 的好成績矇混過關）。
          - 不給 → 跨 substrate 平均（較寬鬆，僅供概覽）。
        未觀察過鏈頭／該 stream 無任何觀測 → 回 (中性 0.5, 0)，讓新人靠探索通過。
        """
        resolved = self._resolve(vacant_id)
        if resolved is None:
            return 0.5, 0.0
        stream_id, branch_id = resolved
        cells = [
            (st, su)
            for (st, br, su) in self._rep._cells
            if st == stream_id and br == branch_id and (substrate is None or su == substrate)
        ]
        if not cells:
            return 0.5, 0.0
        scores = [self._rep.score(st, branch_id, su) for (st, su) in cells]
        obs = sum(self._rep.observations(st, branch_id, su) for (st, su) in cells)
        return sum(scores) / len(scores), obs

    # --- 路由（UCB）-------------------------------------------------------
    def _score_obs(self, target_id: str, substrate: str) -> tuple[float, float]:
        """路由用：vacant_id → 當前 stream 的 (rep_score, obs)；未知 → (0.5, 0)。"""
        resolved = self._resolve(target_id)
        if resolved is None:
            return 0.5, 0.0
        return (self._rep.score(resolved[0], resolved[1], substrate),
                self._rep.observations(resolved[0], resolved[1], substrate))

    def route(
        self, niche: str, substrate: str, *, explore_c: float = 0.3
    ) -> CapabilityCard | None:
        """在能解此 niche 的候選裡，用 UCB 挑一個（rep + 探索額）。"""
        cands = self.discover(niche)
        if not cands:
            return None
        total_obs = sum(self._score_obs(c.vacant_id, substrate)[1] for c in cands)

        def key(c: CapabilityCard) -> float:
            rep, obs = self._score_obs(c.vacant_id, substrate)
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
            ((c.vacant_id, self._score_obs(c.vacant_id, substrate)[0]) for c in cands),
            key=lambda x: -x[1],
        )
