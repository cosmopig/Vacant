"""collusion — 評審端攻擊的機制模擬（ballot-stuffing / slandering / 混合）。

## 這支在架構裡承重什麼

到 2026-08-06 為止，Vacant 測過的所有攻擊都在**交付端**：作惡的是交付者
（whitewash / patient / sybil / pulse ＝ Srivatsa model I）。但 Hoffman, Zage &
Nita-Rotaru（ACM Computing Surveys, 2009）§4 的攻擊分類裡有一整類在**評審端**：

  - **self-promoting / ballot stuffing**：攻擊者用多個身份互相給高分，
    把同夥的信譽抬起來（Hoffman §4.1）。
  - **slandering / bad-mouthing**：給誠實者惡評，把競爭者壓下去，
    自己就能拿到更多路由（Hoffman §4.2）。
  - **orchestrated**：兩者混合、分工輪替（Hoffman §4.3）。

`registry.py` 對這一類宣稱了三～四層防禦（weight 內生、自報同源 floor/k、
行為推斷同源 floor/k、未證明評審邊際遞減）。**在這支之前，沒有一層被真的
攻擊過。** 寫了防禦卻沒攻擊過它，等於不知道它是承重牆還是壁紙——而展場要說
「這套機制擋得住互抬與抹黑」，就必須先真的量過。

紀律（沿用 `entrycost.py` 與 `blayer.py`）：
  - **不另寫玩具模型**。路由走真的 `Registry.route`、評審走真的
    `Registry.record_review`（驗簽＋head 新鮮＋去重＋降權都在裡面）、
    稽核走真的 `Auditor`、扣分走真的 `Reputation.slash`。
    模擬的只有「誰交付好壞」與「誰照共謀劇本投票」——那是實驗處理本身。
  - **防禦要能被逐層拆掉**（`ReviewDefenses`）。「拆掉它數字沒變＝裝飾」
    是 `blayer.py` 的既有驗收紀律，這裡把它搬到評審端。
  - 每一輪落一行 JSONL；每一票的實際採計權重都記下來——只看終局信譽
    分不出「這層沒觸發」與「觸發了但沒用」。

誠實邊界：
  - 這是**機制模擬**，不是生態效果。共謀者的劇本是我們寫死的。
  - 共謀比例不掃到 100%：全員共謀時「誠實者信譽被壓低」是恆等式不是量測
    （脈衝那一輪的紀律 2：不要在退化端點上量效應量）。
  - `collude_prob` 是「共謀強度」的一個**特定**形式（每票獨立以此機率照劇本
    投）。真實共謀者可以用更聰明的形式（例如只在關鍵題上動手），
    本模組給的是攻擊力的**下界**。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import crypto
from .auditor import Auditor
from .body import CapabilityCard
from .envelope import ReviewEnvelope
from .identity import Identity
from .logbook import Logbook
from .registry import Registry, ReviewDefenses, ReviewRejected
from .reputation import DIMS

SLASH_FACTOR = 0.5   # 與 entrycost / ecosystem 的交付方 provable fault 係數一致
# 稽核錨的**評審端**後果（`ecosystem.py` §SLASH_FACTOR_REVIEWER / _FALSE_BLOCK）。
# 這一層不住在 registry 裡，住在 ecosystem 的稽核回寫段——所以只看 registry
# 會漏掉它，而它正是唯一直接對「評審說謊」施加後果的機制。
SLASH_REVIEWER_FALSE_PASS = 0.5   # 誤放行：稽核判 provable fault 而該評審投 PASS → 全五維
SLASH_REVIEWER_FALSE_FAIL = 0.8   # 誤攔：稽核判 pass 而該評審投 FAIL → 只扣 honesty


@dataclass
class CollusionConfig:
    rounds: int = 600
    n_honest: int = 5
    n_colluders: int = 1
    # none | stuff | slander | mixed
    #   none    共謀者照實評審（對照臂：交付端一樣壞，但不動評審）
    #   stuff   ballot-stuffing：對同夥一律給滿分（含壞交付）
    #   slander 抹黑：對圈外人一律給零分（含好交付）
    #   mixed   兩者同時
    mode: str = "stuff"
    # 共謀強度：每一票以此機率照劇本投，否則照實評。1.0＝每次都動手（最顯眼）。
    collude_prob: float = 1.0
    # 共謀者是否自報同一個 controller。False＝零 controller_id 的現實假設
    # （攻擊者沒有義務自報身份），此時 registry 的「自報同源降權」先驗上不觸發。
    shared_controller: bool = False
    # 共謀者是否參加暖身（＝是不是已經站穩的內部人）。
    # False → 全新身份 obs=0，正是 `_reviewer_weight` 宣稱能擋住的那種 Sybil。
    colluder_warmup: bool = True
    warmup: int = 25             # 暖身輪數（讓誠實居民真的「被證明過」）
    reviewers_k: int = 3
    reviewer_accuracy: float = 0.7
    audit_rate: float = 0.2
    probation_m: int = 2
    defect_rate: float = 1.0     # 共謀者被路由時交付壞東西的機率
    blindspot: float = 0.0
    defenses: ReviewDefenses = field(default_factory=ReviewDefenses)
    # 第五層：稽核錨的評審端後果（ecosystem.py 真的有做，registry.py 沒有）。
    # 預設 True＝現行設計。設 False 就是把這一層拆掉的反事實臂。
    # **這一層與前四層性質不同**：前四層是「猜這票可不可信」的先驗降權，
    # 這一層是「事後被客觀事實抓到說謊」的後果——它是唯一有錨的。
    reviewer_slash: bool = True
    seed: str = "c0"

    def digest(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    def collude_frac(self) -> float:
        return self.n_colluders / max(1, self.n_honest + self.n_colluders)


class _Agent:
    def __init__(self, name: str, colluder: bool, controller: str) -> None:
        self.name = name
        self.colluder = colluder
        self.ident = Identity.generate()
        self.book = Logbook()
        self.book.append("GENESIS", {"who": name}, self.ident, ts_ms=0)
        self.ts = 1
        self.card = CapabilityCard(
            vacant_id=self.ident.vacant_id, niches=["code"],
            pub_hex=crypto.pub_to_hex(self.ident.pub), controller=controller,
            stream_id=self.book.stream_id(), genesis=self.book.genesis_proof(),
        )
        self.deliveries = 0

    @property
    def vid(self) -> str:
        return self.ident.vacant_id

    def deliver(self) -> str:
        self.book.append("DELIVER", {"i": self.ts}, self.ident, ts_ms=self.ts)
        self.ts += 1
        self.deliveries += 1
        return self.book.head()


def _h01(s: str) -> float:
    """字串 → [0,1)。確定性、跨 seed 去相關（與 entrycost._h01 同一個理由：
    不要讓不同的隨機事件糾纏在同一條序列上）。"""
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) / 0x1_0000_0000


def _pick_reviewers(pool: list[_Agent], target: _Agent, k: int,
                    seed: str, tag: str) -> list[_Agent]:
    """確定性抽 k 位評審（不含被評者）。

    為什麼不是「前三位誠實居民」（`entrycost._peer_reviews` 的做法）：
    那個做法下共謀者**永遠不會被選為評審**，評審端攻擊在定義上就不可能發生。
    要攻擊評審端，評審席次就必須是全體共享的稀缺資源。"""
    cands = [a for a in pool if a.vid != target.vid]
    ranked = sorted(cands, key=lambda a: hashlib.sha256(
        f"{seed}:rev:{tag}:{a.name}".encode()).hexdigest())
    return ranked[:k]


def _vote(reviewer: _Agent, target: _Agent, *, good: bool, blind: bool,
          cfg: CollusionConfig, tag: str) -> tuple[float, str]:
    """一位評審對一筆交付的分數，以及這一票的性質標籤。

    誠實評審：好交付給 1.0；壞交付以 reviewer_accuracy 抓到給 0.0，
    抓不到給 1.0。落在盲區（同源檢查者共同看不見）則必然給 1.0。
    """
    if reviewer.colluder and cfg.mode != "none":
        u = _h01(f"{cfg.seed}:col:{tag}:{reviewer.name}")
        if u < cfg.collude_prob:
            if target.colluder and cfg.mode in ("stuff", "mixed"):
                return 1.0, "stuff"          # 互抬：同夥一律滿分
            if not target.colluder and cfg.mode in ("slander", "mixed"):
                return 0.0, "slander"        # 抹黑：圈外人一律零分
    if good or blind:
        return 1.0, "honest"
    hit = _h01(f"{cfg.seed}:acc:{tag}:{reviewer.name}") < cfg.reviewer_accuracy
    return (0.0 if hit else 1.0), "honest"


def simulate(cfg: CollusionConfig, *, log_path: Path | None = None) -> dict[str, Any]:
    """跑一次評審端攻擊模擬。每輪落一行 JSONL（若給 log_path）。"""
    reg = Registry(defenses=cfg.defenses)
    auditor = Auditor(rate=cfg.audit_rate, seed=f"audit:{cfg.seed}")

    honest = [_Agent(f"honest_{i}", False, f"h{i}") for i in range(cfg.n_honest)]
    ring_ctl = "ring" if cfg.shared_controller else None
    colluders = [_Agent(f"col_{i}", True, ring_ctl or f"c{i}")
                 for i in range(cfg.n_colluders)]
    for a in honest + colluders:
        reg.announce(a.card)

    warm_pool = honest + (colluders if cfg.colluder_warmup else [])
    _warmup(reg, warm_pool, cfg)
    # 暖身期的降權命中不算數：那是冷啟動，不是攻擊。混在一起會讓
    # 「未證明評審邊際遞減」看起來承重（其實它只是在替新生態收門票）。
    reg.downweight_hits = {k: 0 for k in reg.downweight_hits}

    everyone = honest + colluders
    start = {a.name: reg.standing(a.vid, "sim")[0] for a in everyone}

    stats: dict[str, Any] = {
        "accepted_bad": 0, "caught": 0, "defected": 0,
        "routes_colluder": 0, "routes_honest": 0,
        "reviews_by_colluder": 0, "reviews_by_honest": 0,
        # 實際採計權重的總和，分「誰投的」與「這票是不是共謀票」
        "w_colluder": 0.0, "w_honest": 0.0,
        "w_collusive_votes": 0.0, "n_collusive_votes": 0,
        # 降權命中：分成打到共謀者的 vs 打到誠實者的（**誤傷率**）
        "dw_on_colluder": {"same_controller": 0, "behavior": 0, "unproven": 0},
        "dw_on_honest": {"same_controller": 0, "behavior": 0, "unproven": 0},
        "rejected": 0,
        # 稽核錨的評審端後果命中次數（第五層）
        "reviewer_slash_false_pass": 0, "reviewer_slash_false_fail": 0,
        "reviewer_slash_on_colluder": 0,
    }

    log_f = log_path.open("w", encoding="utf-8") if log_path else None
    try:
        for rnd in range(cfg.rounds):
            card = reg.route("code", "sim")
            if card is None:
                break
            who = next((a for a in everyone if a.vid == card.vacant_id), None)
            if who is None:
                continue
            tag = f"r{rnd}"
            if who.colluder:
                stats["routes_colluder"] += 1
            else:
                stats["routes_honest"] += 1

            bad = bool(who.colluder
                       and _h01(f"{cfg.seed}:bad:{rnd}") < cfg.defect_rate
                       and who.deliveries > cfg.probation_m)
            head = who.deliver()
            reg.note_head(who.vid, who.card.stream_id, "main", head, substrate="sim")

            in_blind = bad and _h01(f"{cfg.seed}:blind:{rnd}") < cfg.blindspot
            task_id = f"{cfg.seed}-t{rnd}"
            audit_ran = auditor.should_audit(
                task_id, forced=who.deliveries <= cfg.probation_m)
            caught = bool(bad and audit_ran and not in_blind)
            if bad:
                stats["defected"] += 1
                if not caught:
                    stats["accepted_bad"] += 1

            cast: list[tuple[_Agent, float]] = []
            for rv in _pick_reviewers(everyone, who, cfg.reviewers_k, cfg.seed, tag):
                score, kind = _vote(rv, who, good=not bad, blind=in_blind,
                                    cfg=cfg, tag=tag)
                before = dict(reg.downweight_hits)
                w = _try_review(reg, rv, who, head, task_id, score)
                if w is None:
                    stats["rejected"] += 1
                    continue
                cast.append((rv, score))
                bucket = "dw_on_colluder" if rv.colluder else "dw_on_honest"
                for layer, n in reg.downweight_hits.items():
                    stats[bucket][layer] += n - before[layer]
                if rv.colluder:
                    stats["reviews_by_colluder"] += 1
                    stats["w_colluder"] += w
                else:
                    stats["reviews_by_honest"] += 1
                    stats["w_honest"] += w
                if kind != "honest":
                    stats["n_collusive_votes"] += 1
                    stats["w_collusive_votes"] += w

            if caught:
                stats["caught"] += 1
                reg.apply_slash(who.vid, "sim", SLASH_FACTOR)

            # 第五層：稽核錨的評審端後果。只有**稽核真的跑了而且看得出來**時
            # 才有錨——落在盲區就什麼都不做（誠實：沒有事實就不該有後果）。
            if cfg.reviewer_slash and audit_ran and not in_blind:
                for rv, score in cast:
                    voted_pass = score >= 0.5
                    if bad and voted_pass:          # 誤放行：全五維 ×0.5
                        reg.apply_slash(rv.vid, "sim", SLASH_REVIEWER_FALSE_PASS)
                        stats["reviewer_slash_false_pass"] += 1
                    elif (not bad) and not voted_pass:   # 誤攔：honesty ×0.8
                        reg.apply_slash(rv.vid, "sim", SLASH_REVIEWER_FALSE_FAIL,
                                        dims=("honesty",))
                        stats["reviewer_slash_false_fail"] += 1
                        if rv.colluder:
                            stats["reviewer_slash_on_colluder"] += 1

            if log_f:
                log_f.write(json.dumps({
                    "round": rnd, "to": who.name, "colluder": who.colluder,
                    "bad": bad, "audit_ran": audit_ran, "caught": caught,
                    "honest_rep": round(sum(reg.standing(h.vid, "sim")[0]
                                            for h in honest) / len(honest), 4),
                    "colluder_rep": (round(sum(reg.standing(c.vid, "sim")[0]
                                               for c in colluders) / len(colluders), 4)
                                     if colluders else None),
                    "accepted_bad": stats["accepted_bad"],
                }, ensure_ascii=False) + "\n")
    finally:
        if log_f:
            log_f.close()

    end = {a.name: reg.standing(a.vid, "sim") for a in everyone}
    h_end = [end[a.name][0] for a in honest]
    c_end = [end[a.name][0] for a in colluders]
    routes = stats["routes_colluder"] + stats["routes_honest"]
    # 行為推斷同源的**證據供給量**：它只在「投票有分歧」的題上算一致率，
    # 而分歧只發生在有人說謊的題上。抹黑一旦把誠實者擠出路由，這種題就消失，
    # 偵測器等於被自己要防的攻擊餓死。這一欄是那個機制的直接證據。
    informative = sum(1 for votes in reg._task_votes.values()
                      if len(set(votes.values())) > 1)
    return {
        "config": asdict(cfg),
        "config_digest": cfg.digest(),
        "mode": cfg.mode,
        "defenses": cfg.defenses.label(),
        "collude_frac": round(cfg.collude_frac(), 4),
        "rounds_run": routes,
        # ── 誠實者被壓低多少 ───────────────────────────────────────────
        "honest_rep_start": round(sum(start[a.name] for a in honest) / len(honest), 4),
        "honest_rep_end": round(sum(h_end) / len(h_end), 4),
        "honest_rep_drop": round(
            sum(start[a.name] for a in honest) / len(honest) - sum(h_end) / len(h_end), 4),
        "honest_rep_min": round(min(h_end), 4),
        "colluder_rep_end": (round(sum(c_end) / len(c_end), 4) if c_end else None),
        # ── 共謀者拿到多少路由 ─────────────────────────────────────────
        "routes_colluder": stats["routes_colluder"],
        "routes_honest": stats["routes_honest"],
        "informative_tasks": informative,
        "route_share_colluder": (round(stats["routes_colluder"] / routes, 4)
                                 if routes else None),
        # 公平基準＝共謀者佔人口的比例。share / frac > 1 表示搶到超額路由。
        "route_share_ratio": (round((stats["routes_colluder"] / routes)
                                    / cfg.collude_frac(), 4)
                              if routes and cfg.collude_frac() else None),
        # ── 壞交付因此多得手多少 ───────────────────────────────────────
        "defected": stats["defected"],
        "accepted_bad": stats["accepted_bad"],
        "caught": stats["caught"],
        # ── 哪一層在承重（權重與降權命中）─────────────────────────────
        "mean_w_colluder": (round(stats["w_colluder"] / stats["reviews_by_colluder"], 4)
                            if stats["reviews_by_colluder"] else None),
        "mean_w_honest": (round(stats["w_honest"] / stats["reviews_by_honest"], 4)
                          if stats["reviews_by_honest"] else None),
        "mean_w_collusive_vote": (round(stats["w_collusive_votes"]
                                        / stats["n_collusive_votes"], 4)
                                  if stats["n_collusive_votes"] else None),
        "n_collusive_votes": stats["n_collusive_votes"],
        "reviews_by_colluder": stats["reviews_by_colluder"],
        "reviews_by_honest": stats["reviews_by_honest"],
        "downweight_on_colluder": stats["dw_on_colluder"],
        "downweight_on_honest": stats["dw_on_honest"],
        # 誤傷率：降權命中裡有多少打在誠實評審身上。>0.5 代表這層主要在打自己人。
        "friendly_fire": _friendly_fire(stats),
        "reviews_rejected": stats["rejected"],
        # 第五層：稽核錨真的抓到幾次說謊的評審，其中幾次打在共謀者身上
        "reviewer_slash_false_fail": stats["reviewer_slash_false_fail"],
        "reviewer_slash_false_pass": stats["reviewer_slash_false_pass"],
        "reviewer_slash_on_colluder": stats["reviewer_slash_on_colluder"],
        "reviewer_slash_precision": (
            round(stats["reviewer_slash_on_colluder"]
                  / stats["reviewer_slash_false_fail"], 4)
            if stats["reviewer_slash_false_fail"] else None),
    }


def _friendly_fire(stats: dict) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for layer in ("same_controller", "behavior", "unproven"):
        c = stats["dw_on_colluder"][layer]
        h = stats["dw_on_honest"][layer]
        out[layer] = round(h / (c + h), 4) if (c + h) else None
    return out


def _warmup(reg: Registry, pool: list[_Agent], cfg: CollusionConfig) -> None:
    """暖身：全員交付好東西、互相誠實評審，讓「已證明」這件事真的成立。

    暖身長度不是裝飾：`UNPROVEN_REVIEWER_OBS=5` 之前每位評審都受 floor/k 壓制，
    暖身太短的話整場都在冷啟動區，量到的就不是「防禦擋不擋得住共謀」，
    而是「這個生態還沒開始」。"""
    for r in range(cfg.warmup):
        for a in pool:
            head = a.deliver()
            reg.note_head(a.vid, a.card.stream_id, "main", head, substrate="sim")
            for b in pool:
                if b is a:
                    continue
                _try_review(reg, b, a, head, f"warm-{r}-{a.name}", 1.0)


def _try_review(reg: Registry, reviewer: _Agent, target: _Agent, head: str,
                task_id: str, score: float) -> float | None:
    env = ReviewEnvelope.create(
        reviewer.ident, target_id=target.vid,
        target_stream_id=target.card.stream_id, branch_id="main",
        target_head=head, task_id=task_id, substrate="sim",
        scores={d: score for d in DIMS}, ts_ms=0)
    try:
        return reg.record_review(env)
    except ReviewRejected:
        return None   # 去重／head 競態：如實略過，不重試（重試等於灌票）
