"""multiway — 單向管線 vs 多向環境的機制模擬（M1–M5；`06_多向環境架構.md` §4）。

## 這支在架構裡承重什麼

`environment.py` 給的是原語與不變式，本模組給的是**證據**：把同一套真實機制
（`Registry.route` 路由、`Auditor.should_audit` 抽樣、`Registry.apply_slash` 扣分）
跑兩種資訊架構，量三件事：

  1. **共同盲區的殘餘相關性**——多向是否降低它，以及降低的是哪一部分
  2. **總交付品質**——通道加下去有沒有把東西做壞
  3. **人類介入的邊際效益**——一次中途介入 vs 一次末端稽核，何者改變更多後續結果

第 3 件直接對應展覽第 3 拍的宣稱。**如果中途介入沒有比末端稽核更有價值，
展覽就不能那樣講。**

## 相關性的兩個來源，這是本模組的核心設計

評審之間的錯誤相關拆成兩塊，**只有一塊是通道分離改得動的**：

  - **模型家族造成的**（參數 `blindspot` β）：這一類錯誤三位評審必然一起看不見，
    加人、加通道、加密封都沒有用。β 是外生的，通道分離**改不動它**。
  - **架構造成的**：瀑布（評審看得到前面的票 → Bikhchandani 1992、
    Anderson & Holt 1997）與權威（評審看得到目標的信譽 → Chen et al. 2026）。
    這兩條由 `seal_reviews` 與 `hide_reputation` 在**建構上**關掉。

所以「多向降低共同盲區」這句話**是錯的**，正確的說法是：多向拆掉架構造成的
那一部分相關性，於是**殘餘的相關性才真的可歸因於同源**（HUMAN_MECHANISMS §6.2）。
本模組把這兩塊分開量，這也是為什麼 M1 一定要有 β=0 那一列——沒有它就無法宣稱
量到的是哪一塊（分析紀律①：對聚合量下結論前先分解它）。

## 紀律（沿用 entrycost.py）

  - **不另寫玩具模型**：路由、稽核抽樣、扣分走真的實作。模擬的只有
    「誰交付了好東西還是壞東西」「誰看不看得出來」——那本來就是實驗處理。
  - 全確定性：所有隨機都是 `sha256(seed:用途:座標)`，不用 rng，跨 seed 去相關。
  - 每輪落一行 JSONL（鐵律 3）。
  - 攻擊者只有最簡版（見習期外一律作惡）。**時機結構不是本階段的變數**，
    脈衝那條線由 `entrycost.py` 承擔，本模組不碰 `_should_defect`。

## 誠實邊界

  - 這是**機制模擬**，不是生態效果。展場畫面上必須標明。
  - `would_fail`（拒掉的那件事本來會不會失敗）在模擬裡是真值，生產環境沒有。
    生產版的 calibration 需要「拒絕稽核」（抽樣強制退回執行）才算得出來，
    那是有成本的（`environment.CalibrationLedger` 的 docstring 有寫）。
  - 評審準確率 0.7 這個數字沒有外部依據（`04_接下來的步驟.md` §4）。本模組把它
    當**敏感度參數**掃，不當事實。
  - 反例：通道越多，可被表演的表面越多（Power 1997）。M4／M5 是對兩條新通道的
    博弈實測，不是全部；還沒被測到的博弈面寫在 `06 §5`。
"""

from __future__ import annotations

import hashlib
import json
import statistics as st
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import crypto
from .auditor import Auditor
from .body import CapabilityCard
from .envelope import ReviewEnvelope
from .environment import (
    CalibrationLedger,
    Declination,
    Environment,
    assert_channel_separation,
)
from .identity import Identity
from .logbook import Logbook
from .registry import Registry, ReviewRejected
from .reputation import DIMS

SLASH_FACTOR = 0.5          # 與 ecosystem / entrycost 的交付方 provable fault 一致
N_PITS = 6                  # codebench 的六個坑型（此處只用索引，不需要真任務）
MIN_PAIR_ITEMS = 8          # 算一對評審的相關性至少要幾件共審的壞交付


@dataclass
class MWConfig:
    rounds: int = 300
    n_honest: int = 6
    n_attackers: int = 1
    panel_k: int = 3
    audit_rate: float = 0.2
    probation_m: int = 2

    # ── 模型家族的性質：通道分離改不動的那一塊 ───────────────────────────
    blindspot: float = 0.3          # 落在「同源檢查者都看不見」的錯誤比例
    reviewer_accuracy: float = 0.7  # 盲區外，單一評審抓到壞交付的機率
    false_alarm: float = 0.05       # 好交付被誤判 FAIL 的機率（誤攔成本）

    # ── 架構造成的相關性：通道分離改得動的那一塊 ─────────────────────────
    cascade_p: float = 0.8          # 連續兩票一致後跟票的機率（資訊瀑布）
    authority_w: float = 0.6        # 看得到信譽時，對高信譽目標放水的機率
    authority_theta: float = 0.6    # 「高信譽」的門檻

    # ── 通道開關（add-one-in 分解用；全 False ＝ 現況的單向管線）──────────
    seal_reviews: bool = False      # commit-reveal：切斷瀑布通道
    hide_reputation: bool = False   # 評審期間不揭露信譽：切斷權威通道
    declination: bool = False       # 拒絕原語
    consult: bool = False           # agent↔agent 論證通道
    consult_disqualifies: bool = True   # 諮詢過的人不得評審同一件（結構性反串供）
    consult_gain: float = 0.15      # 拿到論證後成功率的提升
    consult_bias: float = 0.8       # 沒有取消資格時，諮詢者評審同一件會放水的機率

    # ── 人類介入 ──────────────────────────────────────────────────────────
    # none            不介入
    # terminal_random 末端稽核：在 human_round 之後的第一筆交付上加一次稽核（無選擇資訊）
    # terminal_flag   末端＋選擇：等到面板分歧的那一筆，**事後**補稽核（已接受）
    # midcourse_flag  中途介入：面板分歧的那一筆，**接受之前** HALT 並強制稽核
    human: str = "none"
    human_round: int = 100
    human_budget: int = 1

    # ── 拒絕原語的博弈臂 ──────────────────────────────────────────────────
    # none 全員不拒 / honest 依自估能力拒 / cherrypick 只看難度、專挑簡單的
    decliner: str = "none"
    decline_threshold: float = 0.5
    cherry_difficulty: float = 0.5

    seed: str = "m1"

    def digest(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _h01(s: str) -> float:
    """字串 → [0,1)。確定性、跨 seed 去相關（與 entrycost 同一個工具）。"""
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) / 0x1_0000_0000


class _Worker:
    """一個居民：真 identity＋真 logbook＋真能力卡＋**每個坑型不同的能力**。

    能力異質是必要的，不是裝飾：同質生態下路由的效果恰好是零
    （`01_歸因問題` §2 C1a），拒絕原語也失去意義（沒有「這超出我的專長」可言）。
    """

    def __init__(self, name: str, malicious: bool, mode: str = "honest") -> None:
        self.name = name
        self.malicious = malicious
        self.mode = mode                  # honest | cherrypick（拒絕行為）
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
        self.routed = 0
        self.declines = 0
        # 每個坑型的基礎能力 ∈ [0.40, 0.90]，由名字決定（同 seed 同生態）
        self.comp = [0.40 + 0.50 * _h01(f"comp:{name}:{p}") for p in range(N_PITS)]

    @property
    def vid(self) -> str:
        return self.ident.vacant_id

    def deliver(self) -> str:
        self.book.append("DELIVER", {"i": self.ts}, self.ident, ts_ms=self.ts)
        self.ts += 1
        self.deliveries += 1
        return self.book.head()


# --- 主迴圈 -----------------------------------------------------------------
def simulate_mw(cfg: MWConfig, *, log_path: Path | None = None) -> dict[str, Any]:
    """跑一次多向環境模擬。每輪落一行 JSONL（給 log_path 時）。"""
    reg = Registry()
    auditor = Auditor(rate=cfg.audit_rate, seed=f"audit:{cfg.seed}")
    env = Environment()
    calib = CalibrationLedger()

    honest = [_Worker(f"h{i}", malicious=False,
                      mode=("cherrypick" if (cfg.decliner == "cherrypick" and i == 0)
                            else "honest"))
              for i in range(cfg.n_honest)]
    attackers = [_Worker(f"X{i}", malicious=True) for i in range(cfg.n_attackers)]
    for a in honest + attackers:
        reg.announce(a.card)
    _warmup(reg, honest)

    stats: dict[str, Any] = {
        "accepted_total": 0, "accepted_good": 0, "accepted_bad": 0,
        "rejected_good": 0, "rejected_bad": 0, "caught": 0, "blind_passes": 0,
        "defected": 0, "declines": 0, "unassigned": 0, "consults": 0,
        "dispersed": 0, "interventions_fired": 0, "accepted_bad_after_T": 0,
        "fire_round": None,
        # 共同盲區的操作型定義：一筆壞交付上，**全體評審一起放行**幾次。
        # 這才是讓壞東西過關的那個量；逐對相關係數 phi 會被邊際率壓縮，
        # 在兩臂邊際率差很多時不可直接比（退化端點，分析紀律②）。
        "bad_reviewed": 0, "all_miss": 0, "total_votes": 0, "miss_votes": 0,
    }
    # 相關性原料：agent → {round: missed?}，只在**壞交付**上收集
    miss: dict[str, dict[int, bool]] = {}
    route_line: list[str] = []
    log_f = log_path.open("w", encoding="utf-8") if log_path else None

    try:
        for rnd in range(cfg.rounds):
            task_id = f"{cfg.seed}-t{rnd}"
            pit = int(_h01(f"{cfg.seed}:pit:{rnd}") * N_PITS) % N_PITS
            diff = _h01(f"{cfg.seed}:diff:{rnd}")
            env.advance(task_id, "OPEN")

            # ── 1. 派工 ＋ 拒絕原語（agent → 環境）──────────────────────
            who, declined = _assign(reg, env, calib, honest + attackers, cfg,
                                    rnd, task_id, pit, diff)
            stats["declines"] += declined
            if who is None:
                stats["unassigned"] += 1
                route_line.append("_")
                env.advance(task_id, "CLOSED")
                if log_f:
                    log_f.write(json.dumps({"round": rnd, "unassigned": True,
                                            "declines": declined}, ensure_ascii=False) + "\n")
                continue
            who.routed += 1
            env.advance(task_id, "ASSIGNED")
            route_line.append("X" if who.malicious else chr(ord("a") + honest.index(who)))

            # ── 2. 求助（agent ↔ agent，論證通道）───────────────────────
            p_eff, helper = _work(env, honest, who, cfg, rnd, task_id, pit, diff)
            if helper is not None:
                stats["consults"] += 1
            env.advance(task_id, "WORKING")

            # ── 3. 交付 ─────────────────────────────────────────────────
            if who.malicious:
                bad = who.deliveries > cfg.probation_m   # 見習期內作惡＝送分，先熬過
            else:
                bad = _h01(f"{cfg.seed}:out:{rnd}:{who.name}") >= p_eff
            # calibration 的 ACCEPT 那一筆記在這裡（不記在 _assign）：接受之後
            # 才知道求助有沒有發生，而 would_fail 必須用**實際**的成功率算，
            # 否則帳上會出現「本來會失敗但交出了好東西」這種對不起來的紀錄。
            if cfg.declination and not who.malicious:
                calib.record(who.name, True, bad)
            if bad:
                stats["defected"] += 1
            head = who.deliver()
            reg.note_head(who.vid, who.card.stream_id, "main", head, substrate="sim")
            # 共同盲區：錯誤的性質，與誰做的、走哪條通道都無關
            in_blind = bad and _h01(f"{cfg.seed}:blind:{rnd}") < cfg.blindspot

            # ── 4. 密封評審（環境 → 誰看得到什麼）───────────────────────
            env.advance(task_id, "SEALED")
            panel = _panel(honest, who, env, task_id, cfg)
            # 不變式只在**設計被執行**時檢查。`consult_disqualifies=False` 是
            # M5 刻意的違反臂（要量的就是不執行這條規則會怎樣），所以那一臂
            # 不檢查——但它在 summary 裡標成 invariant_enforced=False，
            # 不可以把違反臂的數字跟合規臂混在一起講。
            if cfg.consult_disqualifies:
                assert_channel_separation(env, task_id, tuple(a.name for a in panel))
            rep_now = reg.standing(who.vid, "sim")[0]
            votes = _panel_votes(cfg, rnd, panel, good=not bad, blind=in_blind,
                                 rep_of=rep_now, helper=helper)
            env.advance(task_id, "REVEAL")
            for r, v in zip(panel, votes):
                _try_review(reg, r, who, head, task_id, 1.0 if v else 0.0)
                if bad:
                    miss.setdefault(r.name, {})[rnd] = v      # PASS 一筆壞的＝沒看見
            if bad:
                stats["bad_reviewed"] += 1
                stats["all_miss"] += int(all(votes))
                stats["total_votes"] += len(votes)
                stats["miss_votes"] += sum(1 for v in votes if v)
            panel_pass = sum(votes) * 2 > len(votes)
            dispersed = 0 < sum(votes) < len(votes)
            stats["dispersed"] += int(dispersed)

            # ── 5. 稽核（含人類介入改寫抽樣）────────────────────────────
            env.advance(task_id, "AUDIT")
            fired = _human_fires(cfg, stats, rnd, dispersed)
            if fired:
                stats["interventions_fired"] += 1
                stats["fire_round"] = rnd
                env.halt("visitor", task_id, note="dispersed" if dispersed else "sampled")
            # 常規抽樣（見習期強制）與人類加開的那一次要分開算，否則無法把
            # 「人類介入的效果」與「本來就會被抽到」混在一起——那會系統性
            # 高估介入的價值（分析紀律①：先分解）。
            audit_normal = auditor.should_audit(
                task_id, forced=who.deliveries <= cfg.probation_m)
            audit_ran = audit_normal or fired
            caught_normal = bool(bad and audit_normal and not in_blind)
            caught_human = bool(bad and fired and not audit_normal and not in_blind)
            caught = caught_normal or caught_human
            if bad and audit_ran and in_blind:
                stats["blind_passes"] += 1

            # 語意：常規稽核在**接受之前**跑，抓到＝退件（現行設計就是如此）。
            # 末端稽核（terminal_*）是人類事後補跑的那一次，抓到只扣分不退件；
            # 中途介入（midcourse_flag）是接受之前 HALT，抓到就擋下來。
            blocked_by_human = bool(caught_human and cfg.human == "midcourse_flag")
            accepted = panel_pass and not caught_normal and not blocked_by_human

            if caught:
                stats["caught"] += 1
                reg.apply_slash(who.vid, "sim", SLASH_FACTOR)
            if accepted:
                stats["accepted_total"] += 1
                if bad:
                    stats["accepted_bad"] += 1
                    if rnd >= cfg.human_round:
                        stats["accepted_bad_after_T"] += 1
                else:
                    stats["accepted_good"] += 1
            else:
                if bad:
                    stats["rejected_bad"] += 1
                else:
                    stats["rejected_good"] += 1
            env.advance(task_id, "CLOSED")

            if log_f:
                score, obs = reg.standing(who.vid, "sim")
                log_f.write(json.dumps({
                    "round": rnd, "task": task_id, "pit": pit,
                    "diff": round(diff, 4), "to": who.name,
                    "attacker": who.malicious, "declines": declined,
                    "consulted": helper.name if helper else None,
                    "bad": bad, "blind": in_blind, "votes": votes,
                    "dispersed": dispersed, "panel_pass": panel_pass,
                    "audit_ran": audit_ran, "caught": caught,
                    "human_fired": fired, "blocked": blocked_by_human,
                    "accepted": accepted, "score": round(score, 4),
                    "obs": round(obs, 3),
                }, ensure_ascii=False) + "\n")
    finally:
        if log_f:
            log_f.close()

    return _summarise(cfg, stats, miss, honest, attackers, reg, calib,
                      "".join(route_line))


# --- 派工與拒絕 -------------------------------------------------------------
def _assign(reg: Registry, env: Environment, calib: CalibrationLedger,
            pool: list[_Worker], cfg: MWConfig, rnd: int, task_id: str,
            pit: int, diff: float) -> tuple[_Worker | None, int]:
    """走真的 `Registry.route`；被拒就把該候選暫時移出候選池再路由一次。

    暫時移出＝拒絕的真實語意（這一輪我不在候選裡），而且可以完全沿用真的 UCB，
    不必另寫一套排序邏輯。

    `_route_seq` 在 finally 還原成「起點＋1」：見習配額的時脈必須數**任務**不是
    數**嘗試**。不還原的話，拒絕多的臂每輪會多推進時脈好幾格，見習配額
    （每 10 筆一次）就會比別的臂觸發得更頻繁——而配額決定攻擊者多常拿到工作。
    那是 add-one-in 階梯裡一個看不見的混淆，會被誤讀成「拒絕原語改變了防禦力」。
    """
    excluded: list[_Worker] = []
    declined = 0
    seq_start = reg._route_seq
    try:
        for _attempt in range(3):
            card = reg.route("code", "sim")
            if card is None:
                return None, declined
            who = next((a for a in pool if a.vid == card.vacant_id), None)
            if who is None:
                return None, declined
            p_eff = _p_success(who, pit, diff)
            would_fail = _h01(f"{cfg.seed}:out:{rnd}:{who.name}") >= p_eff
            accept = _accepts(who, cfg, p_eff, diff)
            if cfg.declination:
                if not accept:
                    # DECLINE 的反事實：拒掉的這件本來會不會失敗。模擬裡是真值，
                    # 生產環境拿不到——要靠「拒絕稽核」（抽樣強制退回執行）才算得出，
                    # 那是有成本的（見 environment.CalibrationLedger 的誠實邊界）。
                    calib.record(who.name, False, would_fail)
                    who.declines += 1
                    declined += 1
                    env.advance(task_id, "ASSIGNED")
                    env.declare(Declination(
                        agent=who.name, task_id=task_id, accepted=False,
                        reason=("out_of_jurisdiction" if who.mode == "cherrypick"
                                else "insufficient_context"),
                        p_ik=p_eff))
                    excluded.append(who)
                    del reg._cards[who.vid]
                    continue
            return who, declined
        return None, declined
    finally:
        for w in excluded:
            reg._cards[w.vid] = w.card
        reg._route_seq = seq_start + 1     # 時脈數任務，不數嘗試（見 docstring）


def _p_success(who: _Worker, pit: int, diff: float) -> float:
    """這個 agent 在這個坑型、這個難度上做對的機率。"""
    return max(0.05, min(0.95, who.comp[pit] - 0.5 * diff + 0.15))


def _accepts(who: _Worker, cfg: MWConfig, p_eff: float, diff: float) -> bool:
    """ACCEPT / DECLINE。攻擊者永遠接（拒絕對它沒好處）。"""
    if who.malicious or cfg.decliner == "none":
        return True
    if who.mode == "cherrypick":
        # 只看難度，不看自己會不會——這就是「挑簡單任務」的可執行定義
        return diff <= cfg.cherry_difficulty
    return p_eff >= cfg.decline_threshold


# --- 求助（論證通道）--------------------------------------------------------
def _work(env: Environment, honest: list[_Worker], who: _Worker, cfg: MWConfig,
          rnd: int, task_id: str, pit: int, diff: float) -> tuple[float, _Worker | None]:
    """需要時求助一次。傳回 (最終成功率, 幫忙的人)。

    幫忙的人怎麼選：用**目錄**（誰宣告了這個坑型 ＋ 稽核推導的資格），
    不用信譽名次——名次不在目錄通道上（`environment.CHANNELS["directory"]`）。
    這裡以「該坑型能力最高的其他誠實 agent」代表目錄查詢的結果。
    """
    p = _p_success(who, pit, diff)
    if not cfg.consult or who.malicious or p >= 0.55:
        return p, None
    cands = [a for a in honest if a is not who]
    if not cands:
        return p, None
    helper = max(cands, key=lambda a: (a.comp[pit], a.name))
    if helper.comp[pit] <= who.comp[pit]:
        return p, None
    env.consult(who.name, helper.name, task_id,
                question=f"pit{pit} 這一類的邊界條件要注意什麼",
                answer=f"pit{pit} 的邊界條件通常出在輸入為空與極大值兩端，"
                       f"建議先把這兩端列成可檢查的條款再動手")
    return min(0.95, p + cfg.consult_gain), helper


# --- 評審面板 ---------------------------------------------------------------
def _panel(honest: list[_Worker], who: _Worker, env: Environment,
           task_id: str, cfg: MWConfig) -> list[_Worker]:
    """挑 K 位評審。諮詢過本件的人依設定被排除（結構性反串供，代價是面板變小）。"""
    banned = env.consulted_on(task_id) if cfg.consult_disqualifies else set()
    return [a for a in honest if a is not who and a.name not in banned][:cfg.panel_k]


def _panel_votes(cfg: MWConfig, rnd: int, panel: list[_Worker], *, good: bool,
                 blind: bool, rep_of: float, helper: _Worker | None) -> list[bool]:
    """一輪評審。True＝PASS。三個來源疊加，其中兩個由通道開關關掉。

    ① 私訊號：好交付以 false_alarm 誤攔；壞交付以 reviewer_accuracy 抓到。
    ② 共同盲區（β）：壞交付落在盲區 → 三位一律看不見。**通道分離改不動這一條。**
    ③ 權威（信譽可見）＋ 瀑布（前面的票可見）：這兩條由 hide_reputation /
       seal_reviews 在建構上關掉。
    另外：沒有取消評審資格時，諮詢過的人以 consult_bias 放水——串供不需要惡意，
    看過草稿本身就足以讓判斷不獨立。
    """
    votes: list[bool] = []
    for i, r in enumerate(panel):
        if good:
            v = not (_h01(f"{cfg.seed}:fa:{rnd}:{i}") < cfg.false_alarm)
        elif blind:
            v = True
        else:
            v = not (_h01(f"{cfg.seed}:rev:{rnd}:{i}") < cfg.reviewer_accuracy)
        if helper is not None and r is helper and not cfg.consult_disqualifies:
            if _h01(f"{cfg.seed}:cons:{rnd}:{i}") < cfg.consult_bias:
                v = True
        if not cfg.hide_reputation and rep_of >= cfg.authority_theta:
            if _h01(f"{cfg.seed}:auth:{rnd}:{i}") < cfg.authority_w:
                v = True
        if not cfg.seal_reviews and i >= 2 and votes[i - 1] == votes[i - 2]:
            if _h01(f"{cfg.seed}:casc:{rnd}:{i}") < cfg.cascade_p:
                v = votes[i - 1]
        votes.append(v)
    return votes


def _try_review(reg: Registry, reviewer: _Worker, target: _Worker, head: str,
                task_id: str, score: float) -> None:
    env = ReviewEnvelope.create(
        reviewer.ident, target_id=target.vid,
        target_stream_id=target.card.stream_id, branch_id="main",
        target_head=head, task_id=task_id, substrate="sim",
        scores={d: score for d in DIMS}, ts_ms=0)
    try:
        reg.record_review(env)
    except ReviewRejected:
        pass


# --- 人類介入 ---------------------------------------------------------------
def _human_fires(cfg: MWConfig, stats: dict, rnd: int, dispersed: bool) -> bool:
    """這一輪人類要不要介入。**預算是硬的**：用完就不再開火。

    三種臂拆開「選擇資訊」與「時機」兩個因子：
      terminal_random  無選擇資訊 ＋ 事後（human_round 當輪就開）
      terminal_flag    有選擇資訊（面板分歧）＋ 事後
      midcourse_flag   有選擇資訊 ＋ 接受之前
    """
    if cfg.human == "none" or stats["interventions_fired"] >= cfg.human_budget:
        return False
    if rnd < cfg.human_round:
        return False
    if cfg.human == "terminal_random":
        return True
    return dispersed


# --- 暖身 -------------------------------------------------------------------
def _warmup(reg: Registry, honest: list[_Worker]) -> None:
    """誠實居民先互評 6 輪，讓信譽有東西可讀（否則權威通道量不到任何東西）。"""
    for r in range(6):
        for a in honest:
            head = a.deliver()
            reg.note_head(a.vid, a.card.stream_id, "main", head, substrate="sim")
            for b in honest:
                if b is a:
                    continue
                _try_review(reg, b, a, head, f"warm-{r}-{a.name}", 1.0)


# --- 聚合 -------------------------------------------------------------------
def _pair_corr(x: list[bool], y: list[bool]) -> float | None:
    """兩個 0/1 序列的 phi（＝二元 Pearson）。任一邊零變異 → None。

    零變異就是退化端點（某位評審全看不見或全看得見），在那裡算相關係數
    沒有意義——分析紀律②：不要在退化端點上量效應量。
    """
    n = len(x)
    if n < MIN_PAIR_ITEMS:
        return None
    sx, sy = sum(x), sum(y)
    if sx in (0, n) or sy in (0, n):
        return None
    sxy = sum(1 for a, b in zip(x, y) if a and b)
    num = sxy / n - (sx / n) * (sy / n)
    den = ((sx / n) * (1 - sx / n) * (sy / n) * (1 - sy / n)) ** 0.5
    return None if den == 0 else num / den


def _reviewer_corr(miss: dict[str, dict[int, bool]]) -> tuple[float | None, int, float | None]:
    """所有評審對的平均 phi、可用對數、以及整體漏看率。

    漏看率一起回，是為了讓讀者看得到自己在不在退化端點上——只報相關係數
    而不報邊際率，等於把「這個數字有沒有意義」藏起來。
    """
    names = sorted(miss)
    vals, total, missed = [], 0, 0
    for m in miss.values():
        total += len(m)
        missed += sum(1 for v in m.values() if v)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = miss[names[i]], miss[names[j]]
            shared = sorted(set(a) & set(b))
            c = _pair_corr([a[r] for r in shared], [b[r] for r in shared])
            if c is not None:
                vals.append(c)
    return (round(sum(vals) / len(vals), 4) if vals else None,
            len(vals),
            round(missed / total, 4) if total else None)


def _summarise(cfg: MWConfig, s: dict, miss: dict, honest: list[_Worker],
               attackers: list[_Worker], reg: Registry, calib: CalibrationLedger,
               route_line: str) -> dict[str, Any]:
    corr, n_pairs, miss_rate = _reviewer_corr(miss)
    acc = s["accepted_total"]
    # 共同盲區三件套。只報 phi 會誤導：oneway 的邊際漏看率高到接近退化端點，
    # 那裡 phi 被壓縮，看起來反而「比較不相關」。
    #   all_miss_rate  P(全體放行 | 壞交付) —— 操作型的共同盲區
    #   indep_pred     若三位評審獨立，同樣的邊際率會預測多少 —— miss_rate^K
    #   excess         觀測 − 獨立預測。**這才是「相關性」在有意義單位上的量。**
    k = cfg.panel_k
    all_miss_rate = (round(s["all_miss"] / s["bad_reviewed"], 4)
                     if s["bad_reviewed"] else None)
    indep_pred = round(miss_rate ** k, 4) if miss_rate is not None else None
    excess = (round(all_miss_rate - indep_pred, 4)
              if all_miss_rate is not None and indep_pred is not None else None)
    per_agent = {}
    for a in honest + attackers:
        score, obs = reg.standing(a.vid, "sim")
        per_agent[a.name] = {
            "routed": a.routed, "delivered": a.deliveries, "declines": a.declines,
            "rep": round(score, 4), "obs": round(obs, 3),
            "mode": a.mode if not a.malicious else "attacker",
            "calib_naive": round(calib.naive_score(a.name), 4),
            "calib_J": calib.discrimination(a.name),
            "coverage": calib.coverage(a.name),
        }
    return {
        "config": asdict(cfg),
        "config_digest": cfg.digest(),
        "rounds": cfg.rounds,
        # 這一跑有沒有執行通道分離的不變式。False＝刻意的違反臂（M5）。
        "invariant_enforced": bool(cfg.consult_disqualifies),
        # ① 殘餘相關性
        "reviewer_corr": corr,              # 逐對 phi（**跨臂不可直接比**，見上）
        "corr_pairs": n_pairs,
        "reviewer_miss_rate": miss_rate,
        "all_miss_rate": all_miss_rate,     # 操作型共同盲區
        "indep_pred": indep_pred,           # 同邊際率下的獨立預測
        "co_blind_excess": excess,          # 觀測 − 獨立＝相關造成的超額
        # 原始計數。**跨 seed 要 pool 這些計數，不要平均各 seed 的比率**——
        # 單一 run 的壞交付只有數十筆，比率的抽樣噪音大到會蓋過效應
        # （實測：β=0、通道全開時單 run 的 all_miss 可以噪到 0.13，
        #  pool 之後回到理論值 0.027）。
        "bad_reviewed": s["bad_reviewed"],
        "all_miss_n": s["all_miss"],
        "total_votes": s["total_votes"],
        "miss_votes": s["miss_votes"],
        # ② 交付品質
        "accepted_total": acc,
        "accepted_good": s["accepted_good"],
        "accepted_bad": s["accepted_bad"],
        "quality": round(s["accepted_good"] / acc, 4) if acc else None,
        "rejected_good": s["rejected_good"],      # 誤攔成本
        "rejected_bad": s["rejected_bad"],
        "unassigned": s["unassigned"],            # 拒絕原語的覆蓋率代價
        "defected": s["defected"],
        "caught": s["caught"],
        "blind_passes": s["blind_passes"],
        "dispersed": s["dispersed"],              # 面板分歧筆數＝人類可用的選擇訊號量
        "declines": s["declines"],
        "consults": s["consults"],
        # ③ 人類介入
        "interventions_fired": s["interventions_fired"],
        "fire_round": s["fire_round"],
        "accepted_bad_after_T": s["accepted_bad_after_T"],
        "per_agent": per_agent,
        # 展場用：一行路由序列（X＝工作被交給破壞者），與 E10 主視覺同格式
        "route_line": route_line,
    }


def arms() -> dict[str, dict[str, Any]]:
    """兩臂的定義。單向＝現況；多向＝四條通道全開。"""
    return {
        "oneway": dict(seal_reviews=False, hide_reputation=False,
                       declination=False, consult=False),
        "multiway": dict(seal_reviews=True, hide_reputation=True,
                         declination=True, consult=True,
                         consult_disqualifies=True, decliner="honest"),
    }


def mean_sd(vals: list[float]) -> dict[str, Any]:
    v = [x for x in vals if x is not None]
    if not v:
        return {"mean": None, "sd": None, "n": 0}
    return {"mean": round(st.mean(v), 4),
            "sd": round(st.pstdev(v), 4) if len(v) > 1 else 0.0,
            "min": round(min(v), 4), "max": round(max(v), 4), "n": len(v)}
