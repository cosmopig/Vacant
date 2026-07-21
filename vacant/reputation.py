"""L1 reputation — 五維信譽（Beta posterior），per (stream_id, branch_id, substrate)。

架構總規格 §8；credit-memory v1 **改動2**（06 §2；15 §1 B8 覆核通過）：
  - 信譽的會計單位是 **memory stream 三元組 (stream_id, branch_id, substrate)**，
    不是身體二元組——**credit 跟著記憶走，不跟身體走**（v1 §1）。
    stream_id＝logbook 創世事件（seq=1）的 hash；write-authority 仍是同一把
    Ed25519 key。wipe＝同一把 key、新創世 → 新三元組 → 信用自然歸零，
    不需要額外抹除動作（這正是改動2 的承重語意）。
  - 保留 substrate 在 key 內（v1 §2 裁決）：否則「腦 A 爛靠腦 B 矇混」的
    洗白洞直接復活（THEORY_V5 A3/A5）。
  - 五維：factual / logical / relevance / honesty / adoption。
    每維一個 Beta(α,β)：好評推 α、差評推 β；mean = α/(α+β)。
  - 同源降權：same-controller/substrate/behavior → 權重打折（地板 0.1）。
    *raises-cost，非 prevents*：公開閾值可被繞，誠實標明。
  - 路由：rep_score + UCB 探索額（給新人冷啟動流量）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

DIMS = ("factual", "logical", "relevance", "honesty", "adoption")
SAME_SIGNAL_FLOOR = 0.1  # 同源降權地板（同源評審權重壓到至多此值）
UCB_EPSILON = 1e-9       # UCB 探索項的 pseudocount 下限，防 n=0 除零
DECAY_HALFLIFE_EVENTS = 200  # 12 §4.2 牙齒：decay 半衰期 200 事件（向先驗回歸）


@dataclass
class Beta:
    alpha: float = 1.0  # 先驗：Beta(1,1) = uniform
    beta: float = 1.0
    last_event: int = 0  # 上次異動時的全局事件序號（decay 的時間軸是事件、非牆鐘）

    def update(self, score: float, weight: float) -> None:
        """score∈[0,1]：把 weight 拆給 α / β。"""
        score = max(0.0, min(1.0, score))
        self.alpha += weight * score
        self.beta += weight * (1.0 - score)

    def decayed(self, now: int, halflife: float = DECAY_HALFLIFE_EVENTS) -> tuple[float, float]:
        """牙齒·decay（12 §4.2）：half-life 型向先驗 Beta(1,1) 回歸——信用要一直賺。

        時間單位是**事件筆數**（全網 review 序），不是牆鐘：真跑一題數十秒～數分鐘，
        用 ms 會讓舊信用瞬間歸零。回 (decay 後的 α, β)，不動本體。"""
        age = max(0, now - self.last_event)
        if age == 0:
            return self.alpha, self.beta
        f = 0.5 ** (age / max(1.0, halflife))
        return 1.0 + (self.alpha - 1.0) * f, 1.0 + (self.beta - 1.0) * f

    def commit_decay(self, now: int, halflife: float = DECAY_HALFLIFE_EVENTS) -> None:
        """把 decay 落進本體（更新/slash 前先物化，保證序性一致）。"""
        self.alpha, self.beta = self.decayed(now, halflife)
        self.last_event = now

    def slash(self, factor: float, now: int, halflife: float = DECAY_HALFLIFE_EVENTS) -> None:
        """牙齒·slash（12 §4.2）：provable fault → 乘法扣減（向先驗縮 factor）。

        先物化 decay 再扣：α'=1+(α−1)·factor、β'=1+(β−1)·factor——高信譽者
        一次 slash 可觀測下墜，低信譽者不被誤殺到負（先驗是地板）。"""
        if not 0.0 < factor <= 1.0:
            raise ValueError(f"slash factor 必須在 (0,1]：{factor}")
        self.commit_decay(now, halflife)
        self.alpha = 1.0 + (self.alpha - 1.0) * factor
        self.beta = 1.0 + (self.beta - 1.0) * factor

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def n(self) -> float:
        """有效觀測數（α+β 扣掉 Beta(1,1) 先驗）。

        update() 只增不減、decay 向先驗收斂 → 理論上不會為負；仍夾 max(0) 防呆。
        """
        return max(0.0, (self.alpha - 1.0) + (self.beta - 1.0))


@dataclass
class ReputationCell:
    """單一 (stream_id, branch_id, substrate) 三元組下的五維（改動2）。"""

    dims: dict[str, Beta] = field(default_factory=lambda: {d: Beta() for d in DIMS})

    def update(self, scores: dict[str, float], weight: float, now: int = 0) -> None:
        for d, s in scores.items():
            if d in self.dims:
                self.dims[d].commit_decay(now)
                self.dims[d].update(s, weight)

    def slash(self, factor: float, dims: tuple[str, ...] | None = None, now: int = 0) -> None:
        """對指定維（預設全五維）乘法扣減。"""
        for d in (dims or DIMS):
            if d in self.dims:
                self.dims[d].slash(factor, now)

    def score(self, now: int | None = None) -> float:
        """rep_score = 五維 mean 的平均。給 now → 先看 decay 後的值（牙齒）。"""
        if now is None:
            return sum(self.dims[d].mean for d in DIMS) / len(DIMS)
        return sum(
            (lambda ab: ab[0] / (ab[0] + ab[1]))(self.dims[d].decayed(now)) for d in DIMS
        ) / len(DIMS)

    def observations(self, now: int | None = None) -> float:
        """有效觀測數 = 五維 n 的平均（與 score() 同樣跨維平均）。

        不可用 min：若某維（如 adoption）偶爾沒被評到，min 會把整個 cell 的觀測
        壓成 0 → 在 UCB 被當冷啟動灌爆探索額、在把關被當新人放行。平均較穩健。
        """
        if now is None:
            return sum(self.dims[d].n for d in DIMS) / len(DIMS)

        def _dn(d: str) -> float:
            a, b = self.dims[d].decayed(now)
            return max(0.0, (a - 1.0) + (b - 1.0))

        return sum(_dn(d) for d in DIMS) / len(DIMS)

    def to_json(self) -> dict[str, Any]:
        return {d: [b.alpha, b.beta, b.last_event] for d, b in self.dims.items()}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "ReputationCell":
        cell = cls()
        for dim, vals in d.items():
            a, b = vals[0], vals[1]
            last = vals[2] if len(vals) > 2 else 0
            cell.dims[dim] = Beta(a, b, last)
        return cell


class Reputation:
    """一個 vacant 對「其他 memory stream」的信譽帳本（改動2：三元組 key）。

    key = (stream_id, branch_id, substrate)。空鏈時 stream_id 以 vacant_id 頂替
    （與 ReviewEnvelope 的 target_stream_id 慣例一致，見 envelope.py）。
    event_seq 是全帳本的 review 序號——decay 的時間軸（12 §4.2，向先驗回歸）。"""

    def __init__(self) -> None:
        self._cells: dict[tuple[str, str, str], ReputationCell] = {}
        self.event_seq = 0

    def cell(self, stream_id: str, branch_id: str, substrate: str) -> ReputationCell:
        key = (stream_id, branch_id, substrate)
        if key not in self._cells:
            self._cells[key] = ReputationCell()
        return self._cells[key]

    def record_review(
        self,
        stream_id: str,
        branch_id: str,
        substrate: str,
        scores: dict[str, float],
        *,
        weight: float = 1.0,
        same_signal: bool = False,
    ) -> None:
        """記一筆評審（推進全局事件序）。same_signal=True → 同源降權。

        用 min(weight, FLOOR) 而非直接設 FLOOR：
          - 一般情況 weight=1.0 → 0.1（同源刷分被狠狠打折，raises-cost 非 prevents）。
          - 若呼叫端本就傳了 <0.1 的小權重（如部分分），尊重之、不反而抬高。
        地板的意義是「同源評審不會被完全抹成 0」，但也不準超過 0.1。
        """
        w = min(weight, SAME_SIGNAL_FLOOR) if same_signal else weight
        self.event_seq += 1
        self.cell(stream_id, branch_id, substrate).update(scores, w, self.event_seq)

    def slash(
        self,
        stream_id: str,
        branch_id: str,
        substrate: str,
        factor: float,
        *,
        dims: tuple[str, ...] | None = None,
    ) -> None:
        """牙齒·slash：對某三元組的指定維（預設全維）乘法扣減（12 §4.2）。

        誤放行罰重於誤攔是不對稱係數的落點（PREREG v2 §6 凍結值）；
        本函式只執行扣減，誰該被扣由呼叫端（ecosystem 的稽核錨）判定。"""
        self.cell(stream_id, branch_id, substrate).slash(factor, dims, self.event_seq)

    def score(self, stream_id: str, branch_id: str, substrate: str) -> float:
        return self.cell(stream_id, branch_id, substrate).score(self.event_seq)

    def observations(self, stream_id: str, branch_id: str, substrate: str) -> float:
        return self.cell(stream_id, branch_id, substrate).observations(self.event_seq)

    # --- 持久化 ------------------------------------------------------------
    def to_json(self) -> dict[str, Any]:
        return {
            "event_seq": self.event_seq,
            "cells": {f"{st}␟{br}␟{su}": c.to_json() for (st, br, su), c in self._cells.items()},
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Reputation":
        rep = cls()
        if "cells" in d:
            rep.event_seq = int(d.get("event_seq", 0))
            d = d["cells"]
        for key, cell in d.items():
            st, br, su = key.split("␟", 2)
            rep._cells[(st, br, su)] = ReputationCell.from_json(cell)
        return rep


def ucb_score(rep_score: float, observations: float, total_obs: float, c: float = 0.3) -> float:
    """UCB1：rep_score + c·sqrt(ln(total)/n)。資料少 → 探索額大（給新人流量）。

    c 是探索/利用權衡：太大永遠在試爛貨（不收斂），太小新人被餓死。0.3 在
    冷啟動（n=1）仍給夠大的探索額、又能在數十輪後收斂到證明過的專家。
    """
    n = max(observations, UCB_EPSILON)  # n=0（全新候選）→ 探索項極大 → 必被探索一次
    total = max(total_obs, 1.0)
    return rep_score + c * math.sqrt(math.log(total + 1.0) / n)
