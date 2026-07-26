"""entrycost — 身份入場成本的機制模擬（回答「入場該怎麼設計」）。

## 這支在架構裡承重什麼

2026-07-26 獨立審查的結論裡有一項是設計決策的缺席，不是實作疏漏：
**製造一個新身份目前是免費的**。所有已知攻擊都共用這個前提，而在入場成本
為零時，「洗白成本」這個量完全由見習期那三個沒有外生錨定的參數決定。

審查意見書 §5 給了三條可接受的路，但沒有給「選哪條」的依據——那需要實測。
本模組就是那個實測：在**同一套真實機制**（registry 路由＋auditor 稽核＋
reputation 牙齒）下，把三種入場設計各跑一遍，量攻擊者的投資報酬率。

紀律：
  - **不另寫玩具模型**。路由走真的 `Registry.route`、稽核走真的 `Auditor`、
    扣分走真的 `Reputation.slash`。模擬的只有「誰交付了好東西還是壞東西」
    這一件事——那本來就是實驗處理，不是機制。
  - 全確定性、單一 seed 決定一切，可重放。
  - 每一輪落一行 JSONL：誰被路由、交付好壞、有沒有被稽核抓到、扣了什麼、
    攻擊者當下的累計收益與成本。**不聚合就沒有結論可言，但聚合前的原始
    紀錄必須留著。**

誠實邊界：
  - 這是**機制模擬**，不是生態效果。它回答「在這套規則下，攻擊者的最佳策略
    值多少」，不回答「真實世界的攻擊者會不會這樣做」。
  - 攻擊者的策略空間是我們寫死的三種；真實攻擊者可能有更好的策略，
    因此本模組給出的是攻擊成本的**上界的下界**——它證不了安全。
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import crypto
from .auditor import Auditor
from .body import CapabilityCard
from .envelope import ReviewEnvelope
from .identity import Identity
from .logbook import Logbook
from .registry import Registry, ReviewRejected
from .reputation import DIMS

# 攻擊者作惡一次成功（未被抓到）的收益，單位任意但固定——ROI 的分子。
GAIN_PER_ACCEPTED_BAD = 1.0
# 一筆乾淨交付的成本（攻擊者要偽裝就得真的做事）——ROI 的分母之一。
COST_PER_CLEAN_DELIVERY = 1.0
# 造一把新鑰匙的密碼學成本 ≈ 0；入場成本由 EntryPolicy 決定，不由此常數決定。
COST_PER_KEYGEN = 0.0

SLASH_FACTOR = 0.5  # 與 ecosystem 的交付方 provable fault 係數一致


@dataclass
class EntryPolicy:
    """入場成本的三種設計（對應審查意見書 §5 的三條路）。"""

    kind: str = "free"           # free | stake | endorse
    # stake：新身份必須先完成 N 筆**不計酬**的乾淨交付才進入路由池。
    #   這是「外生成本」的一種可模擬形式：成本以工作量計，不需要真的代幣。
    stake_deliveries: int = 0
    # endorse：新身份需要一位 obs ≥ min_obs 的背書者；被背書者出 provable
    #   fault 時，背書者連坐扣分（liability 越小罰越重）。
    endorse_min_obs: float = 1.0
    endorse_liability: float = 0.7

    def label(self) -> str:
        if self.kind == "stake":
            return f"stake({self.stake_deliveries})"
        if self.kind == "endorse":
            return f"endorse(obs≥{self.endorse_min_obs},λ={self.endorse_liability})"
        return "free"


@dataclass
class SimConfig:
    rounds: int = 300
    n_honest: int = 5
    audit_rate: float = 0.2
    probation_m: int = 2
    entry: EntryPolicy = field(default_factory=EntryPolicy)
    strategy: str = "whitewash"   # whitewash | patient | sybil
    # 同儕評審抓到壞交付的機率。1.0＝評審是 oracle（會嚴重高估系統防禦力：
    # 稽核之所以存在，正是因為評審不可信）。LLM-as-judge 文獻顯示評審有
    # 系統性偏誤且會偏好同源生成，實際值遠低於 1.0——這是本模擬最重要的
    # 敏感度參數，預設保守設為 0.7 而非 1.0。
    reviewer_accuracy: float = 0.7
    # 攻擊者人數（先前全部只有 1 個，等於攻擊者佔比 1/6 ~ 17%）。
    n_attackers: int = 1
    # 評審錯誤的相關性 ρ∈[0,1]：0＝三位評審獨立判斷（先前的假設，過於樂觀）；
    # 1＝三位評審同進同退（同源模型的極端情況）。LLM-as-judge 文獻顯示
    # 同源模型的錯誤高度相關，所以獨立性假設會系統性高估防禦力。
    reviewer_correlation: float = 0.0
    # 高價值任務的比例，以及攻擊者是否只在高價值任務上作惡。
    # 「平時乾淨、只在高價值任務上作惡」是最像真實威脅的姿態，先前未建模。
    high_value_ratio: float = 0.2
    selective: bool = False
    # patient 策略：先做 build_rounds 筆乾淨的，再開始作惡
    build_rounds: int = 10
    seed: str = "e1"

    def digest(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]


class _Agent:
    """一個模擬居民：真的 identity＋真的 logbook＋真的能力卡。"""

    def __init__(self, name: str, malicious: bool) -> None:
        self.name = name
        self.malicious = malicious
        self.ident = Identity.generate()
        self.book = Logbook()
        self.book.append("GENESIS", {"who": name}, self.ident, ts_ms=0)
        self.ts = 1
        self.card = CapabilityCard(
            vacant_id=self.ident.vacant_id, niches=["code"],
            pub_hex=crypto.pub_to_hex(self.ident.pub), controller=name,
            stream_id=self.book.stream_id(), genesis=self.book.genesis_proof(),
        )
        self.deliveries = 0
        self.clean_paid = 0     # stake 政策下已繳的乾淨交付數
        self.endorser: str | None = None

    @property
    def vid(self) -> str:
        return self.ident.vacant_id

    def deliver(self) -> str:
        self.book.append("DELIVER", {"i": self.ts}, self.ident, ts_ms=self.ts)
        self.ts += 1
        self.deliveries += 1
        return self.book.head()


def simulate(cfg: SimConfig, *, log_path: Path | None = None) -> dict[str, Any]:
    """跑一次模擬，回傳摘要；每輪的原始紀錄寫進 log_path（若給）。"""
    rng = random.Random(f"{cfg.seed}:{cfg.digest()}")
    reg = Registry()
    auditor = Auditor(rate=cfg.audit_rate, seed=f"audit:{cfg.seed}")

    honest = [_Agent(f"honest_{i}", malicious=False) for i in range(cfg.n_honest)]
    for a in honest:
        reg.announce(a.card)
    # 誠實居民先賺出可背書的紀錄（否則 endorse 政策在第 0 輪無人可背書）
    _warmup(reg, honest, rng)

    attackers = [_spawn_attacker(reg, honest, cfg, gen=g)
                 for g in range(max(1, cfg.n_attackers))]
    attacker = attackers[0]

    log_f = log_path.open("w", encoding="utf-8") if log_path else None
    stats = {"accepted_bad": 0, "caught": 0, "clean_paid": 0,
             "identities": max(1, cfg.n_attackers), "routed_to_attacker": 0,
             "rounds_routable": 0, "blocked_no_endorser": 0,
             "high_value_hits": 0}
    honest_start = {h.name: reg.standing(h.vid, "sim")[0] for h in honest}

    try:
        for rnd in range(cfg.rounds):
            card = reg.route("code", "sim")
            if card is None:
                break
            who = _find(honest + attackers, card.vacant_id)
            if who is None:
                continue

            is_attacker = who.malicious
            if is_attacker:
                stats["routed_to_attacker"] += 1

            # 任務價值：由 (seed, 輪次) 的雜湊決定——確定性可重放，但**跨 seed
            # 去相關**。先前只用輪次，而見習配額正好每 10 輪把任務丟給攻擊者
            # 一次，於是「價值」與「誰被路由」在所有 seed 上同步相關，做出
            # 「無差別攻擊者的高價值得手恆為 0」這種不可能的結果。
            hv = int(hashlib.sha256(f"{cfg.seed}:hv:{rnd}".encode()).hexdigest()[:8], 16)
            high_value = (hv % 10_000) / 10_000.0 < cfg.high_value_ratio
            # 攻擊者依策略決定這一筆要不要作惡；誠實居民恆交付好的。
            bad = is_attacker and _should_defect(who, cfg, stats)
            if bad and cfg.selective and not high_value:
                bad = False          # 選擇性：低價值任務照做，不浪費身份
            head = who.deliver()
            reg.note_head(who.vid, who.card.stream_id, "main", head, substrate="sim")

            # 交付方一律宣稱通過（誤放行正是被測的行為），所以「稽核抽中壞交付」
            # 就等於 provable fault，不需要另外傳 claimed_pass。
            task_id = f"{cfg.seed}-t{rnd}"
            audit_ran = auditor.should_audit(
                task_id, forced=who.deliveries <= cfg.probation_m)
            caught = bool(bad and audit_ran)

            if bad and not caught:
                stats["accepted_bad"] += 1
                if high_value:
                    stats["high_value_hits"] += 1
            if not bad and is_attacker:
                stats["clean_paid"] += 1
                who.clean_paid += 1

            # 同儕評審：稽核抓到就是 FAIL，否則依交付好壞給分（確定性）
            _peer_reviews(reg, honest, who, head, task_id, good=not bad, rng=rng,
                          accuracy=cfg.reviewer_accuracy,
                          correlation=cfg.reviewer_correlation)

            if caught:
                stats["caught"] += 1
                reg.apply_slash(who.vid, "sim", SLASH_FACTOR)
                if cfg.entry.kind == "endorse" and who.endorser:
                    # 背書連坐：讓「替誰背書」變成有代價的決定
                    reg.apply_slash(who.endorser, "sim", cfg.entry.endorse_liability)

            score, obs = reg.standing(who.vid, "sim")
            if log_f:
                log_f.write(json.dumps({
                    "round": rnd, "to": who.name, "attacker": is_attacker,
                    "bad": bad, "audit_ran": audit_ran, "caught": caught,
                    "score": round(score, 4), "obs": round(obs, 3),
                    "deliveries": who.deliveries,
                    "accepted_bad": stats["accepted_bad"],
                    "clean_paid": stats["clean_paid"],
                    "identities": stats["identities"],
                }, ensure_ascii=False) + "\n")

            # 丟棄身份的時機由策略決定
            discard = False
            if cfg.strategy == "sybil":
                discard = True                       # 用完即丟
            elif cfg.strategy == "whitewash" and caught:
                sc, _ = reg.standing(who.vid, "sim")
                discard = sc < 0.35                  # 沉沒了才換
            if discard:
                attacker = _spawn_attacker(reg, honest, cfg, gen=stats["identities"])
                attackers.append(attacker)
                stats["identities"] += 1
                if cfg.entry.kind == "endorse" and attacker.endorser is None:
                    stats["blocked_no_endorser"] += 1
    finally:
        if log_f:
            log_f.close()

    stats["honest_damage"] = round(sum(
        max(0.0, honest_start[h.name] - reg.standing(h.vid, "sim")[0]) for h in honest), 4)
    return _summarise(cfg, stats)


# --- 內部 ------------------------------------------------------------------
def _warmup(reg: Registry, honest: list[_Agent], rng: random.Random) -> None:
    """讓誠實居民先有紀錄：彼此互評 8 輪好評。"""
    for r in range(8):
        for a in honest:
            head = a.deliver()
            reg.note_head(a.vid, a.card.stream_id, "main", head, substrate="sim")
            for b in honest:
                if b is a:
                    continue
                _try_review(reg, b, a, head, f"warm-{r}-{a.name}", 1.0)


def _peer_reviews(reg, honest, target, head, task_id, *, good: bool,
                  rng: random.Random, accuracy: float = 1.0,
                  correlation: float = 0.0) -> None:
    """K=3 位評審。壞交付時每位評審以 accuracy 的機率抓到，沒抓到就投 PASS。

    correlation ρ 控制錯誤的相關性：以機率 ρ 三位評審共用同一次判定
    （同源模型同進同退），以 1−ρ 各自獨立判定。ρ=0 是先前的假設，
    它假設三位評審的錯誤互相獨立——而同源模型並非如此，因此 ρ=0 會
    系統性高估「多找幾個評審」的防禦力。
    """
    shared = None
    if not good and correlation > 0.0 and rng.random() < correlation:
        shared = rng.random() < accuracy      # 同進同退：一次判定，三人共用
    for b in honest[:3]:
        if b.vid == target.vid:
            continue
        if good:
            score = 1.0
        elif shared is not None:
            score = 0.0 if shared else 1.0
        else:
            score = 0.0 if rng.random() < accuracy else 1.0
        _try_review(reg, b, target, head, task_id, score)


def _try_review(reg: Registry, reviewer: _Agent, target: _Agent, head: str,
                task_id: str, score: float) -> None:
    env = ReviewEnvelope.create(
        reviewer.ident, target_id=target.vid,
        target_stream_id=target.card.stream_id, branch_id="main",
        target_head=head, task_id=task_id, substrate="sim",
        scores={d: score for d in DIMS}, ts_ms=0)
    try:
        reg.record_review(env)
    except ReviewRejected:
        pass   # 去重／head 競態：如實略過，不重試（重試等於灌票）


def _spawn_attacker(reg: Registry, honest: list[_Agent], cfg: SimConfig,
                    *, gen: int) -> _Agent:
    a = _Agent(f"attacker_g{gen}", malicious=True)
    reg.announce(a.card)
    if cfg.entry.kind == "endorse":
        # 找一位有足夠紀錄的背書者。找不到＝進不了場（這正是機制的效果）。
        for h in honest:
            _s, obs = reg.standing(h.vid, "sim")
            if obs >= cfg.entry.endorse_min_obs:
                a.endorser = h.vid
                break
    return a


def _find(agents: list[_Agent], vid: str) -> _Agent | None:
    return next((a for a in agents if a.vid == vid), None)


def _should_defect(who: _Agent, cfg: SimConfig, stats: dict) -> bool:
    """攻擊者的策略：決定這一筆要不要交付壞東西。

    三種策略對應三種真實的攻擊姿態：
      whitewash — 立刻作惡，被抓就換身份重來（賭稽核抽不中）
      patient   — 先熬過見習期並累積紀錄，再開始作惡（賭「已證明」的身份被抽查得少）
      sybil     — 每個身份只交付一次就丟棄（賭數量）
    """
    if cfg.entry.kind == "stake" and who.clean_paid < cfg.entry.stake_deliveries:
        return False                      # 還在繳入場費
    if cfg.strategy == "patient":
        # 熬過見習期＋build_rounds 筆乾淨紀錄才開始作惡
        return who.deliveries > max(cfg.build_rounds, cfg.probation_m)
    return True                           # whitewash / sybil：能作惡就作惡


def _summarise(cfg: SimConfig, s: dict) -> dict[str, Any]:
    cost = (s["clean_paid"] * COST_PER_CLEAN_DELIVERY
            + s["identities"] * COST_PER_KEYGEN)
    gain = s["accepted_bad"] * GAIN_PER_ACCEPTED_BAD
    return {
        "config": asdict(cfg),
        "config_digest": cfg.digest(),
        "policy": cfg.entry.label(),
        "strategy": cfg.strategy,
        "rounds": cfg.rounds,
        "routed_to_attacker": s["routed_to_attacker"],
        "accepted_bad": s["accepted_bad"],
        "caught": s["caught"],
        "clean_paid": s["clean_paid"],
        "identities_used": s["identities"],
        "blocked_no_endorser": s["blocked_no_endorser"],
        "high_value_hits": s.get("high_value_hits", 0),
        # 附帶損害：誠實居民因連坐而損失的信譽總量。任何入場設計都要付代價，
        # 只報攻擊者 ROI 不報這一欄，等於只報好處不報成本。
        "honest_damage": s.get("honest_damage", 0.0),
        "gain": gain,
        "cost": cost,
        # ROI：每付出一單位成本能換到幾次成功作惡。cost=0 時回 None——
        # 「無限大」是有意義的結論（入場免費），但不可寫成一個數字。
        "roi": (round(gain / cost, 4) if cost > 0 else None),
        "bad_per_route": (round(s["accepted_bad"] / s["routed_to_attacker"], 4)
                          if s["routed_to_attacker"] else None),
    }
