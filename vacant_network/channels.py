"""channels — 通道分離的機制模擬（3.1 專長 profile、3.2 commit-reveal 評審）。

## 這支在架構裡承重什麼

人類制度的文獻調研（`參考文獻/2026-08-06_人類運作邏輯/HUMAN_MECHANISMS.md` §0、§6）
的核心發現是一句話：**找到對的專家要求集中資訊、不被互相影響要求切斷資訊、
守住專業邊界要求拒絕權——三者的最佳解互相衝突**，而人類制度同時滿足三者的辦法是
**把不同種類的資訊分開，在不同的通道上傳**（Delphi 傳論證不傳立場、手術核對表傳
角色不傳評價、交互記憶系統傳「誰會什麼」不傳「他覺得答案是什麼」）。

Vacant 原本只有一條通道。本模組是把其中兩條分出來之後的實測：

  3.1 專長 profile（§6.5）— 把「好」與「擅長這個」分開。信譽 key 加一維
      任務族（`codebench.FAMILIES` 六個坑型），路由改成對 (agent, 任務族) 的格子。
      這是 Lewis (2003) 三因子裡的 specialisation，Vacant 原本完全沒有。
  3.2 commit-reveal 評審（§6.2）— 切斷瀑布通道。第一輪只上鏈
      sha256(評語 ‖ nonce)，面板關閉後才揭露。它不只是防作弊，它**改變推論地位**：
      Anderson & Holt (1997) 證明資訊瀑布的相關性不需要共謀就會出現，所以未密封時
      `Registry._behavior_same_source` 量到的相關性混雜了「同源」與「順序」，
      無法分離。密封後沒有可觀察的行動歷史，瀑布通道**由建構關閉**，殘餘的相關性
      才真的可歸因於同源。

## 紀律（沿用 entrycost.py 立下的那套，違反＝結論作廢）

  - **不另寫玩具模型**。路由走真的 `Registry.route`、信譽走真的 `Reputation`、
    評審走真的簽章 `ReviewEnvelope`、密封走真的 `Registry.open_panel/commit_review`
    ＋真的 logbook hash-chain。模擬的只有「這一筆交付好不好」與「評審的私訊號
    對不對」——那本來就是實驗處理，不是機制。
  - 全確定性：所有隨機量都是 `sha256(seed:用途:索引)`，**不用共享的 rng**，
    否則不同參數下的抽樣順序會互相糾纏（entrycost 踩過）。
  - 每輪落一行 JSONL。不聚合就沒有結論，但聚合前的原始紀錄必須留著。
  - 兩臂**等預算**：同樣的輪數、同樣的任務流（任務族由 seed 與輪次決定，
    與路由結果無關），且驗 `deliveries == rounds` 而不是 `<=`
    （`_index/methods.json` 分析紀律第 4 條）。

## 誠實邊界

  - 這是**機制模擬**，不是生態效果。3.1 回答「若 agent 之間真的存在專長差異，
    分族的 key 找不找得到它」，**不**回答「LLM agent 之間到底存不存在這種差異」——
    專長剖面是我們寫死的實驗處理。效應量的上界由 `skill_expert - skill_other`
    直接決定，那個差是設定不是發現。
  - 3.2 量到的「殘餘相關性」是**在本模擬的側通道結構下**的殘餘。密封關掉的是
    面板這一條通道；共用上游模型那條在這裡是用「克隆共用私訊號」建模的，
    真實系統的側通道可能更多。raises-cost，非 prevents。
  - 一致率一律只在**鑑別題**（票不一致的任務）上算，與 `_behavior_same_source`
    同口徑。這條件化本身有選擇效應（在有人不同意的題上算一致率，機械地偏低），
    兩臂同口徑所以比較公平，但**絕對值不可當成「相關係數」讀**。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any

from . import crypto
from .body import CapabilityCard
from .codebench import FAMILIES
from .envelope import ReviewEnvelope
from .identity import Identity
from .logbook import Logbook, review_commitment
from .registry import Registry, ReviewRejected
from .reputation import DIMS

K_REVIEWERS = 3  # 與 ecosystem / entrycost 同口徑


def _h01(s: str) -> float:
    """把字串雜湊成 [0,1)。確定性、跨 seed 去相關。"""
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) / 0x1_0000_0000


def _hint(s: str, n: int) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) % n


class _Resident:
    """一個模擬居民：真的 Identity ＋真的 Logbook ＋真的能力卡。"""

    def __init__(self, name: str) -> None:
        self.name = name
        self.ident = Identity.generate()
        self.book = Logbook()
        self.book.append("GENESIS", {"who": name}, self.ident, ts_ms=0)
        self.ts = 1
        self.card = CapabilityCard(
            vacant_id=self.ident.vacant_id, niches=["code"],
            pub_hex=crypto.pub_to_hex(self.ident.pub),
            # controller 逐人唯一：本模組的同源偵測**必須**走行為推斷那條，
            # 不能靠自報的 controller 欄位（15 §3-A2 的套套邏輯地雷）。
            controller=name,
            stream_id=self.book.stream_id(), genesis=self.book.genesis_proof(),
        )

    @property
    def vid(self) -> str:
        return self.ident.vacant_id

    def deliver(self) -> str:
        self.book.append("DELIVER", {"i": self.ts}, self.ident, ts_ms=self.ts)
        self.ts += 1
        return self.book.head()


# ══════════════════════════════════════════════════════════════════════════
# 3.1 專長 profile
# ══════════════════════════════════════════════════════════════════════════
@dataclass
class SpecConfig:
    rounds: int = 600
    n_agents: int = 6
    # 路由是否使用任務族維度。False＝純量信譽（改動前的一條通道）。
    profile_on: bool = True
    # 虛無對照：False → 所有人在所有族上能力相同（且**總能力守恆**，見 skill()）。
    # 沒有這一臂，「profile 臂數字比較好」無法排除「只是換了一組不同的參數」。
    specialists: bool = True
    skill_expert: float = 0.90
    skill_other: float = 0.35
    # 同儕評審抓對的機率。1.0 是退化端點（評語＝環境真值，資訊白送），
    # 預設 0.9、另跑 0.7 做敏感度；退化端點的數字最漂亮也最沒有資訊
    # （`_index/methods.json` 分析紀律第 2 條）。
    reviewer_accuracy: float = 0.90
    seed: str = "c1"

    def families(self) -> tuple[str, ...]:
        return FAMILIES

    def skill(self, agent_idx: int, family: str) -> float:
        """agent 在某族上的成功率。

        `specialists=False` 時所有人在所有族上都是**同一個平均值**，且該平均值
        等於 specialists=True 的期望成功率——總能力守恆，兩組唯一的差別是
        「能力有沒有結構」。否則虛無對照會變成「把大家調弱再說分族沒用」。"""
        fams = self.families()
        if not self.specialists:
            return (self.skill_expert + (len(fams) - 1) * self.skill_other) / len(fams)
        expert_of = fams[agent_idx % len(fams)]
        return self.skill_expert if family == expert_of else self.skill_other

    def expert_of(self, agent_idx: int) -> str | None:
        return self.families()[agent_idx % len(self.families())] if self.specialists else None

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:12]


def simulate_specialty(cfg: SpecConfig, *, log_path: Path | None = None) -> dict[str, Any]:
    """3.1：跑一次專長 profile 模擬。每輪一行 JSONL。

    任務流是**外生**的：第 r 輪的坑型只由 (seed, r) 決定，與路由結果無關。
    這一點是判準的前提——若路由能挑任務，「品質不變差」就可以靠只挑簡單題
    達成，那個路由器不該過關。"""
    fams = cfg.families()
    reg = Registry()
    agents = [_Resident(f"a{i}") for i in range(cfg.n_agents)]
    for a in agents:
        reg.announce(a.card)
    idx_of = {a.vid: i for i, a in enumerate(agents)}

    log_f = log_path.open("w", encoding="utf-8") if log_path else None
    stats: dict[str, Any] = {
        "deliveries": 0, "successes": 0, "expert_routes": 0,
        "rejected_reviews": 0,
        "per_family_tasks": {f: 0 for f in fams},
        "per_family_expert_routes": {f: 0 for f in fams},
        "per_agent_routes": {a.name: 0 for a in agents},
        "half": [{"n": 0, "expert": 0, "ok": 0}, {"n": 0, "expert": 0, "ok": 0}],
    }
    try:
        for rnd in range(cfg.rounds):
            fam = fams[_hint(f"{cfg.seed}:fam:{rnd}", len(fams))]
            stats["per_family_tasks"][fam] += 1

            card = reg.route("code", "sim", family=(fam if cfg.profile_on else None))
            if card is None:
                break
            i = idx_of[card.vacant_id]
            who = agents[i]

            # 交付結果：同一輪兩臂抽同一個 u（common random numbers），差別只在
            # 「這個 u 拿去和誰的能力比」。這消掉「這一輪本來就難」的共同因素。
            u = _h01(f"{cfg.seed}:out:{rnd}")
            ok = u < cfg.skill(i, fam)
            is_expert = (cfg.expert_of(i) == fam)

            head = who.deliver()
            # profile_off 臂一律掛在總通道 ""：那就是「只有一條通道」的樣子。
            reg.note_head(who.vid, who.card.stream_id, "main", head,
                          substrate="sim", family=(fam if cfg.profile_on else ""))

            n_rev = 0
            for j, rv in enumerate([x for x in agents if x.vid != who.vid][:K_REVIEWERS]):
                correct = _h01(f"{cfg.seed}:rev:{rnd}:{j}") < cfg.reviewer_accuracy
                verdict = ok if correct else (not ok)
                env = ReviewEnvelope.create(
                    rv.ident, target_id=who.vid, target_stream_id=who.card.stream_id,
                    branch_id="main", target_head=head, task_id=f"{cfg.seed}-t{rnd}",
                    substrate="sim", scores={d: (1.0 if verdict else 0.0) for d in DIMS},
                    ts_ms=0, family=(fam if cfg.profile_on else ""))
                try:
                    reg.record_review(env)
                    n_rev += 1
                except ReviewRejected:
                    stats["rejected_reviews"] += 1

            stats["deliveries"] += 1
            stats["successes"] += int(ok)
            stats["expert_routes"] += int(is_expert)
            stats["per_family_expert_routes"][fam] += int(is_expert)
            stats["per_agent_routes"][who.name] += 1
            h = stats["half"][0 if rnd < cfg.rounds // 2 else 1]
            h["n"] += 1
            h["expert"] += int(is_expert)
            h["ok"] += int(ok)

            if log_f:
                log_f.write(json.dumps({
                    "round": rnd, "family": fam, "to": who.name,
                    "is_expert": is_expert, "ok": ok,
                    "reviews_accepted": n_rev,
                    "score_family": round(reg.reputation_of(who.vid, "sim", fam), 4),
                    "score_overall": round(reg.standing(who.vid, "sim")[0], 4),
                    "obs_overall": round(reg.standing(who.vid, "sim")[1], 3),
                }, ensure_ascii=False) + "\n")
    finally:
        if log_f:
            log_f.close()

    return _summarise_specialty(cfg, reg, agents, stats)


def _summarise_specialty(cfg, reg, agents, s) -> dict[str, Any]:
    n = s["deliveries"]
    fams = cfg.families()
    cells = [k for k in reg._rep._cells]
    obs_per_cell = [reg._rep.observations(*k) for k in cells]

    def rate(a: int, b: int) -> float | None:
        return round(a / b, 4) if b else None

    return {
        "cell": "3.1_specialty",
        "config": asdict(cfg),
        "config_digest": cfg.digest(),
        "arm": ("profile_on" if cfg.profile_on else "profile_off"),
        "specialists": cfg.specialists,
        "rounds": cfg.rounds,
        "deliveries": n,
        # 等預算：判準是 == 不是 <=（分析紀律 4）。呼叫端要驗這一欄。
        "budget_exact": n == cfg.rounds,
        "rejected_reviews": s["rejected_reviews"],
        # ── 判準①：路由到擅長這個坑型的 agent 的比例 ────────────────────
        # 虛無對照（specialists=False）沒有「專家」這個東西 → 回 None 而不是 0。
        # 寫 0 會讓表格看起來像「虛無臂的專家命中率是零」，那是把「沒有定義」
        # 讀成「量到了很差」——同一類錯誤上一輪讓我們在退化端點上量效應量。
        "expert_routes": (s["expert_routes"] if cfg.specialists else None),
        "expert_rate": (rate(s["expert_routes"], n) if cfg.specialists else None),
        "chance_rate": round(1.0 / cfg.n_agents, 4),
        # ── 判準②：總交付品質（不得變差）────────────────────────────────
        "quality": rate(s["successes"], n),
        # ── 收斂代價：分族把證據切成 1/6，早期一定比較抖 ──────────────
        "expert_rate_first_half": (rate(s["half"][0]["expert"], s["half"][0]["n"])
                                   if cfg.specialists else None),
        "expert_rate_second_half": (rate(s["half"][1]["expert"], s["half"][1]["n"])
                                    if cfg.specialists else None),
        "quality_first_half": rate(s["half"][0]["ok"], s["half"][0]["n"]),
        "quality_second_half": rate(s["half"][1]["ok"], s["half"][1]["n"]),
        # ── 任務流外生的證據：兩臂的每族題數必須逐位相同 ─────────────
        "per_family_tasks": s["per_family_tasks"],
        "per_family_expert_rate": ({
            f: rate(s["per_family_expert_routes"][f], s["per_family_tasks"][f])
            for f in fams
        } if cfg.specialists else None),
        "per_agent_routes": s["per_agent_routes"],
        # ── 證據稀釋的量：格數與每格平均觀測 ─────────────────────────
        "n_cells": len(cells),
        "obs_per_cell_mean": round(sum(obs_per_cell) / len(obs_per_cell), 3) if cells else 0.0,
        "obs_total": round(sum(obs_per_cell), 3),
    }


# ══════════════════════════════════════════════════════════════════════════
# 3.2 commit-reveal 評審
# ══════════════════════════════════════════════════════════════════════════
@dataclass
class SealConfig:
    rounds: int = 300
    n_reviewers: int = 6
    # 共用同一份私訊號的克隆數（＝真正的同源通道）。0＝完全沒有同源，
    # 此時**任何**被偵測到的相關性都只能是架構造成的。
    n_clones: int = 2
    reviewer_accuracy: float = 0.70
    # 看得到前面的人怎麼投時，跟隨多數的傾向。**兩臂用同一個值**——
    # 密封改變的不是這個傾向，是「有沒有東西可以跟隨」。
    herd: float = 0.60
    sealed: bool = False
    bad_rate: float = 0.40
    seed: str = "s1"

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:12]


def simulate_seal(cfg: SealConfig, *, log_path: Path | None = None) -> dict[str, Any]:
    """3.2：跑一次密封／未密封評審模擬。

    密封臂的「看不到別人」**不是模擬旗標**：每一位評審在下判斷前呼叫真的
    `Registry.visible_votes(task_id)`，面板開啟中它就回空 dict，因為承諾在鏈上、
    內容不在。瀑布通道由建構關閉，不是由假設關閉。"""
    reg = Registry()
    reg.sealed_reviews = cfg.sealed
    target = _Resident("target")
    reviewers = [_Resident(f"r{i}") for i in range(cfg.n_reviewers)]
    for a in [target, *reviewers]:
        reg.announce(a.card)
    clones = {r.name for r in reviewers[: cfg.n_clones]}

    log_f = log_path.open("w", encoding="utf-8") if log_path else None
    votes: dict[str, dict[str, bool]] = {}      # task_id → {reviewer_name: 通過}
    truth: dict[str, bool] = {}                 # task_id → 交付是否真的好
    herd_applied = 0
    rejected = 0
    try:
        for rnd in range(cfg.rounds):
            task_id = f"{cfg.seed}-t{rnd}"
            good = _h01(f"{cfg.seed}:bad:{rnd}") >= cfg.bad_rate
            truth[task_id] = good
            head = target.deliver()
            reg.note_head(target.vid, target.card.stream_id, "main", head, substrate="sim")

            if cfg.sealed:
                reg.open_panel(task_id)

            # 每題重排評審順序：固定順序等於指定一個永久的意見領袖，
            # 那會把瀑布效應與「誰排第一」混在一起。
            order = sorted(reviewers,
                           key=lambda r: hashlib.sha256(f"{task_id}:{r.name}".encode()).hexdigest())
            pending: list[tuple[ReviewEnvelope, str]] = []
            round_votes: dict[str, bool] = {}
            for pos, rv in enumerate(order):
                # 私訊號：克隆共用同一次抽樣（錯誤完全相關）＝真正的同源通道。
                skey = "clone" if rv.name in clones else rv.name
                correct = _h01(f"{cfg.seed}:sig:{rnd}:{skey}") < cfg.reviewer_accuracy
                sig_vote = good if correct else (not good)

                # 瀑布通道：唯一的入口是機制提供的可見票。
                seen = reg.visible_votes(task_id)
                vote = sig_vote
                if seen and _h01(f"{cfg.seed}:herd:{rnd}:{rv.name}") < cfg.herd:
                    yes = sum(1 for v in seen.values() if v)
                    no = len(seen) - yes
                    if yes != no:
                        vote = yes > no
                        if vote != sig_vote:
                            herd_applied += 1

                env = ReviewEnvelope.create(
                    rv.ident, target_id=target.vid, target_stream_id=target.card.stream_id,
                    branch_id="main", target_head=head, task_id=task_id, substrate="sim",
                    scores={d: (1.0 if vote else 0.0) for d in DIMS}, ts_ms=0)
                if cfg.sealed:
                    # nonce 在真部署必須是 secrets.token_hex；這裡確定性以求可重放，
                    # 誠實標明：可重放的 nonce 在真部署等於沒有 hiding。
                    nonce = hashlib.sha256(
                        f"{cfg.seed}:nonce:{rnd}:{rv.name}".encode()).hexdigest()
                    commit = review_commitment(env.to_json(), nonce)
                    # 承諾上自己的鏈：不可否認、不可事後改、有時間次序。
                    rv.book.append("REVIEW_COMMIT", {"task_id": task_id, "commit": commit},
                                   rv.ident, ts_ms=rnd)
                    reg.commit_review(rv.vid, task_id, commit)
                    pending.append((env, nonce))
                else:
                    try:
                        reg.record_review(env)
                    except ReviewRejected:
                        rejected += 1
                round_votes[rv.name] = vote

            if cfg.sealed:
                reg.close_panel(task_id)
                for env, nonce in pending:
                    try:
                        reg.record_review(env, nonce=nonce)
                    except ReviewRejected:
                        rejected += 1

            votes[task_id] = round_votes
            if log_f:
                log_f.write(json.dumps({
                    "round": rnd, "task_id": task_id, "good": good,
                    "sealed": cfg.sealed,
                    "votes": {k: bool(v) for k, v in round_votes.items()},
                    "unanimous": len(set(round_votes.values())) == 1,
                }, ensure_ascii=False) + "\n")
    finally:
        if log_f:
            log_f.close()

    return _summarise_seal(cfg, reg, reviewers, clones, votes, truth,
                           herd_applied, rejected)


def _pair_class(a: str, b: str, clones: set[str]) -> str:
    ca, cb = a in clones, b in clones
    if ca and cb:
        return "clone_clone"
    if ca or cb:
        return "clone_indep"
    return "indep_indep"


def _summarise_seal(cfg, reg, reviewers, clones, votes, truth,
                    herd_applied, rejected) -> dict[str, Any]:
    names = [r.name for r in reviewers]
    informative = [t for t, v in votes.items() if len(set(v.values())) > 1]

    # 一致率分兩種算法都報（分析紀律 1：對聚合量下結論前先分解它）。
    #   conditional — 只在鑑別題上算，與 `_behavior_same_source` 同口徑
    #   raw         — 所有題都算，看得到「密封後全票一致變少」這件事本身
    agree: dict[str, dict[str, list[float]]] = {
        k: {"conditional": [], "raw": []}
        for k in ("clone_clone", "clone_indep", "indep_indep")
    }
    for a, b in combinations(names, 2):
        cls = _pair_class(a, b, clones)
        cond = [t for t in informative if a in votes[t] and b in votes[t]]
        raw = [t for t in votes if a in votes[t] and b in votes[t]]
        if cond:
            agree[cls]["conditional"].append(
                sum(1 for t in cond if votes[t][a] == votes[t][b]) / len(cond))
        if raw:
            agree[cls]["raw"].append(
                sum(1 for t in raw if votes[t][a] == votes[t][b]) / len(raw))

    def m(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 4) if vals else None

    # 「若把鑑別題過濾拿掉會怎樣」的儀器。`_behavior_same_source` 只在票不一致的
    # 任務上算一致率，理由本來是「確定性互審天然全票一致，那是同一個環境真值
    # 不是同一個控制者」。這裡量的是它的**第二個作用**：瀑布製造的相關性大部分
    # 落在全票一致的題上，於是那個過濾同時也吸收掉了瀑布。拿掉它，未密封面板
    # 會把互不相干的評審判成同源。
    raw_indep = agree["indep_indep"]["raw"]
    max_raw_indep = round(max(raw_indep), 4) if raw_indep else None

    # 真的偵測器怎麼判：跑承重路徑本身，不是另寫一份統計。
    flagged = {r.name: reg._behavior_same_source(r.vid) for r in reviewers}
    n_clone = len(clones)
    n_indep = len(names) - n_clone
    tp = sum(1 for n2 in names if n2 in clones and flagged[n2])
    fp = sum(1 for n2 in names if n2 not in clones and flagged[n2])

    # 評審準確率的實際落點：密封與否不該改變「評審有多常說對」的**上游**，
    # 但瀑布會改變下游。兩者都報，否則看不出品質有沒有被順序效應吃掉。
    correct = sum(1 for t, v in votes.items() for who, val in v.items() if val == truth[t])
    total_votes = sum(len(v) for v in votes.values())

    return {
        "cell": "3.2_commit_reveal",
        "config": asdict(cfg),
        "config_digest": cfg.digest(),
        "arm": ("sealed" if cfg.sealed else "open"),
        "rounds": cfg.rounds,
        "rejected_reviews": rejected,
        # 瀑布真的發生了嗎：這是「機制有沒有被觸發」的儀器，不是結論。
        # 密封臂必須恆為 0——不是因為 herd 參數不同，是因為沒有東西可以跟隨。
        "herd_overrides": herd_applied,
        "n_tasks": len(votes),
        "n_informative": len(informative),
        "unanimous_rate": round(1 - len(informative) / len(votes), 4) if votes else None,
        # ── 判準：殘餘的評審相關性 ───────────────────────────────────
        # indep_indep 就是「殘餘」：沒有共用私訊號的兩個人還有多像。
        "agree_indep_indep": m(agree["indep_indep"]["conditional"]),
        "agree_clone_indep": m(agree["clone_indep"]["conditional"]),
        "agree_clone_clone": m(agree["clone_clone"]["conditional"]),
        "agree_indep_indep_raw": m(agree["indep_indep"]["raw"]),
        "agree_clone_clone_raw": m(agree["clone_clone"]["raw"]),
        # 若拿掉鑑別題過濾，最像的一對「互不相干」評審會不會越過同源門檻
        "max_raw_indep_pair": max_raw_indep,
        "raw_would_flag_indep": (max_raw_indep is not None
                                 and max_raw_indep >= Registry.BEHAVIOR_AGREE_RATE),
        # ── 承重偵測器的實際判決（誤報／命中）────────────────────────
        "flagged": flagged,
        "n_clones": n_clone,
        "n_indep": n_indep,
        "true_positives": tp,
        "false_positives": fp,
        "fp_rate": round(fp / n_indep, 4) if n_indep else None,
        "tp_rate": round(tp / n_clone, 4) if n_clone else None,
        "vote_accuracy": round(correct / total_votes, 4) if total_votes else None,
    }


# ══════════════════════════════════════════════════════════════════════════
# 掃描
# ══════════════════════════════════════════════════════════════════════════
@dataclass
class Sweep:
    rows: list[dict[str, Any]] = field(default_factory=list)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for r in self.rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
