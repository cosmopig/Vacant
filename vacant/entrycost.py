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
from .reputation import DIMS, slash_n_factor

# 攻擊者作惡一次成功（未被抓到）的收益，單位任意但固定——ROI 的分子。
GAIN_PER_ACCEPTED_BAD = 1.0
# 一筆乾淨交付的成本（攻擊者要偽裝就得真的做事）——ROI 的分母之一。
COST_PER_CLEAN_DELIVERY = 1.0
# 造一把新鑰匙的密碼學成本 ≈ 0；入場成本由 EntryPolicy 決定，不由此常數決定。
COST_PER_KEYGEN = 0.0

SLASH_FACTOR = 0.5  # 與 ecosystem 的交付方 provable fault 係數一致

# 2026-07-26 之後才加進 SimConfig 的欄位。維持預設值時不進 config digest，
# 否則「加一個選用參數」就會改變亂數種子，讓所有既有實驗的數字無故位移。
# 詳見 SimConfig.digest 的說明。
_LATER_FIELDS = ("pulse_burst", "pulse_recover", "audit_accuracy",
                 "blindspot", "defect_budget")

# 亂數種子的**豁免欄位**：這幾個永遠不進 digest（＝不進亂數種子）。
#
# 為什麼（2026-08-07）：digest() 同時是亂數種子，而 `_peer_reviews` 的
# 「這位評審有沒有看出來」是從那條序列抽的。於是掃描懲罰參數時，每換一個值
# 就同時換掉整個隨機世界——量到的差異會混著「懲罰參數的效果」與「換了一組
# 評審運氣」，配對比較直接失效。懲罰參數只影響**被抓之後**怎麼罰，不影響
# 世界怎麼生成，所以把它們釘在同一條序列上是對的。
#
# 代價：兩個只差懲罰參數的設定會算出**相同的 digest**。所以 digest 不能再
# 拿來當「這兩格是不是同一個設定」的判準——那件事用 run_key()（涵蓋全欄位）。
_SEED_EXEMPT_FIELDS = ("slash_n_factor", "slash_factor", "stop_when_budget_spent")


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
    # whitewash | patient | sybil | pulse | repent
    #   repent（2026-08-07 新增）＝**悔改者臂**：熬過見習期後開始作惡，第一次被
    #   稽核抓到（＝吃到一次 slash）之後永久只交好貨，而且**不換身份**。
    #   沒有這一臂就只量得到「排除效果」，量不到「贖回可能」——而 slash 的
    #   λ 取捨曲線的另一個軸正是贖回。它不是攻擊策略，是量測探針。
    strategy: str = "whitewash"
    # ── 脈衝攻擊（2026-08-03 新增）────────────────────────────────────
    # 定義：交替於兩個相位——
    #   放電 burst 筆連續作惡 → 蓄積 recover 筆乾淨交付 → 重複。
    # 它不是「更兇的攻擊」，而是**利用防禦的反應延遲**：稽核是抽樣的、
    # 扣分只在被抓到時發生、而信譽會隨時間向先驗衰減。所以先把信譽養高
    # （養高就被路由得更頻繁），再在系統來不及反應的窗口內集中提領。
    # 既有三種策略是這個參數空間的特例：
    #   burst=∞ ≈ whitewash（一直作惡）  burst=1,recover 大 ≈ 稀疏的 patient
    pulse_burst: int = 3
    pulse_recover: int = 10
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
    # ── 稽核不是 oracle（2026-08-03 新增）──────────────────────────────
    # 先前 caught = bad ∧ audit_ran，等於假設「只要抽中就一定抓到」。
    # 對**確定性重跑**的稽核（現行設計：sandbox 重跑單元測試）那是對的，
    # 所以預設維持 accuracy=1.0、blindspot=0.0，不改變既有結論。
    # 但如果驗收標準本身是模型寫的、或任務沒有客觀檢查，稽核就退化成
    # 「另一個模型在看」——此時它與同源評審共享盲區：
    #   blindspot = 落在「同源檢查者都看不到」的錯誤比例。落在盲區內的
    #     壞交付，評審與稽核**同時**放行，加更多檢查者也沒有用。
    #   audit_accuracy = 盲區外、抽中時稽核抓到的機率。
    # 這一組參數回答的是「若稽核也是模型會怎樣」，不是對現行設計的描述。
    audit_accuracy: float = 1.0
    blindspot: float = 0.0
    # 攻擊預算上限：整場最多作惡幾筆。等預算對照用——把「作惡總量」固定住，
    # 才能把「時機」與「數量」分開，否則脈衝的優勢會跟攻擊次數混在一起。
    defect_budget: int | None = None
    # 預算用完就收工（2026-08-07）。**這不是換一個實驗，是同一場模擬的前綴。**
    #   `defected` 與 `accepted_bad` 在預算用完的那一刻就已經定案（之後 bad 恆為
    #   False），所以等預算比較要的兩個量完全不受影響——判準
    #   `test_early_stop_is_a_strict_prefix` 逐位驗證這件事。
    #   買到的是機時：預算用完之後的攻擊者會一路乾淨交付、被路由 90 次以上，
    #   而每次路由帶三筆評審、評審的同源推斷是歷史長度的二次式。實測 S2 的
    #   一格（30 seeds）從約 7 分鐘掉到不到 1 分鐘。
    #   **代價要誠實標明**：`routed_to_attacker`（曝光）只算到停跑點為止，
    #   所以 S2 的曝光欄不能拿去跟 S1／S3／基線比。
    #   停跑條件刻意也包含「攻擊者已經沒有身份可用」以外的情形都不停——
    #   只認預算，其他理由停跑會讓「這一臂被餓死」跟「這一臂跑完了」混掉。
    stop_when_budget_spent: bool = False
    # ── slash 的取捨參數 λ（2026-08-07 新增）────────────────────────────
    # 見 reputation.Beta.slash。λ 把「均值下降幅度」與「n 上升幅度」解耦：
    # 均值一律變 SLASH_FACTOR 倍（與 λ 無關），n 只上升 λ·Δ。
    #   1.0＝現行行為（罰得重、但赦免通道也一起關小）
    #   0.0＝只動均值不動 n（赦免通道維持原寬）
    # 這是**取捨參數不是修正**，操作點由 examples/iterate_v2.py --only S1 決定。
    slash_n_factor: float = 1.0
    # provable fault 的扣減係數（原本是模組常數 SLASH_FACTOR=0.5）。
    # 提成設定欄位是因為取捨曲線在 factor 這一軸上才看得到：factor=0.5 時
    # 光是均值下降就足以永久排除，λ 動不動 n 都一樣——曲線是平的。
    # 複驗觀測到 slash 0.9 在 177 輪回歸、0.8 在 520 輪回歸，所以有分辨力的
    # 區間在 0.7–0.95，掃描必須涵蓋它，否則會在一個效應為零的點上量效應
    # （分析紀律 2 的同一個坑，換一個軸）。
    slash_factor: float = SLASH_FACTOR
    seed: str = "e1"

    def digest(self) -> str:
        """設定摘要。**只涵蓋非預設值的欄位**——這一點很重要。

        這個摘要同時是亂數種子（`random.Random(f"{seed}:{digest()}")`）。
        如果它涵蓋全部欄位，那麼「為了新實驗而加一個選用參數」就會改變
        digest、進而改變整條隨機序列，讓所有**既有**設定的結果全部位移——
        已發表的 E1–E16 會在下次重跑時對不上，而程式邏輯根本沒動。
        2026-08-03 加入脈衝與盲區參數時就踩到了這個坑。

        做法：**後加的欄位在維持預設值時不進摘要**，其餘欄位照舊全進。
        於是沒有用到新功能的設定會算出與 2026-07-26 完全相同的摘要與
        隨機序列，E1–E16 的數字得以逐位重現；用到新功能的設定則自然
        落在不同的序列上。以後再加參數，把欄位名補進 _LATER_FIELDS 即可。
        """
        d = asdict(self)
        base = asdict(SimConfig())
        for k in _SEED_EXEMPT_FIELDS:
            d.pop(k, None)          # 懲罰參數永遠不進種子（見 _SEED_EXEMPT_FIELDS）
        for k in _LATER_FIELDS:
            if k in d and d[k] == base[k]:
                del d[k]
        blob = json.dumps(d, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    def run_key(self) -> str:
        """涵蓋**全部**欄位的設定指紋。

        `digest()` 是亂數種子，它刻意豁免懲罰參數，所以兩個不同的懲罰設定會
        算出同一個 digest。要回答「這兩格是不是同一個設定」只能問 run_key()。
        manifest 兩個都寫——digest 用來對「隨機世界一不一樣」，run_key 用來對
        「設定一不一樣」。
        """
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
        # 脈衝相位：本週期已放電幾筆、已蓄積幾筆
        self.phase_bad = 0
        self.phase_clean = 0
        # 這個身份有沒有吃過 slash（repent 臂的轉折點；也供贖回儀器定位）
        self.slashed = False

    @property
    def vid(self) -> str:
        return self.ident.vacant_id

    def deliver(self) -> str:
        self.book.append("DELIVER", {"i": self.ts}, self.ident, ts_ms=self.ts)
        self.ts += 1
        self.deliveries += 1
        return self.book.head()


def simulate(cfg: SimConfig, *, log_path: Path | None = None) -> dict[str, Any]:
    """跑一次模擬，回傳摘要；每輪的原始紀錄寫進 log_path（若給）。

    `cfg.slash_n_factor` 在整場模擬期間生效（reputation 的模組層 λ）。它是
    行程層級的全域，所以掃描 λ 請用多行程；同一個行程裡不要並行跑不同 λ。
    """
    with slash_n_factor(cfg.slash_n_factor):
        return _simulate(cfg, log_path=log_path)


def _simulate(cfg: SimConfig, *, log_path: Path | None = None) -> dict[str, Any]:
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
             "high_value_hits": 0, "defected": 0, "blind_passes": 0,
             # ── slash 之後（2026-08-07；1.1 的兩個軸都從這裡讀）────────────
             # 排除軸：被 slash 的那個身份之後還拿到多少工作、還得手多少。
             # 贖回軸：距離下一次被路由要等幾輪（None＝在本場輪數內沒回來）。
             # 只認**第一次**被 slash 的身份：換身份重生是另一條路（whitewash），
             # 混在一起就分不出「這個身份翻不了身」與「他換了個身份」。
             "first_slash_round": None, "slashed_vid": None,
             "routes_after_slash": 0, "accepted_bad_after_slash": 0,
             "first_route_after_slash": None,
             "score_at_slash": None, "obs_at_slash": None,
             # 反應延遲：每一次放電記一筆 {第一次作惡的輪次, 這波得手數,
             # 第一次被抓的輪次}。脈衝之所以有效，機制就在這個間隔裡。
             "bursts": []}
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
            # 贖回／排除的儀器：被 slash 的那個身份，之後還被派到幾次工作
            if stats["slashed_vid"] == who.vid and rnd > stats["first_slash_round"]:
                stats["routes_after_slash"] += 1
                if stats["first_route_after_slash"] is None:
                    stats["first_route_after_slash"] = rnd

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
            if bad and cfg.defect_budget is not None and stats["defected"] >= cfg.defect_budget:
                bad = False          # 預算用完：等預算對照時把總量鎖住
            head = who.deliver()
            reg.note_head(who.vid, who.card.stream_id, "main", head, substrate="sim")

            # 這一筆錯誤是否落在「同源檢查者共同的盲區」。確定性、由 (seed, 輪次)
            # 決定，與誰被路由無關——盲區是**錯誤的性質**，不是攻擊者的選擇。
            in_blind = bad and _h01(f"{cfg.seed}:blind:{rnd}") < cfg.blindspot

            # 交付方一律宣稱通過（誤放行正是被測的行為），所以「稽核抽中壞交付
            # 且看得出來」就等於 provable fault。
            task_id = f"{cfg.seed}-t{rnd}"
            audit_ran = auditor.should_audit(
                task_id, forced=who.deliveries <= cfg.probation_m)
            # 稽核看得出來嗎：落在盲區就看不出來；否則以 audit_accuracy 抓到。
            audit_sees = (not in_blind) and _h01(f"{cfg.seed}:adet:{rnd}") < cfg.audit_accuracy
            caught = bool(bad and audit_ran and audit_sees)
            if bad and audit_ran and in_blind:
                stats["blind_passes"] += 1

            if bad:
                stats["defected"] += 1
                # 放電相位的儀器：這一波從哪一輪開始、得手幾筆、何時第一次被抓
                if not stats["bursts"] or stats["bursts"][-1]["closed"]:
                    stats["bursts"].append({"start": rnd, "hits": 0,
                                            "first_catch": None, "closed": False})
                b = stats["bursts"][-1]
                if not caught:
                    b["hits"] += 1
                elif b["first_catch"] is None:
                    b["first_catch"] = rnd
            elif is_attacker and stats["bursts"] and not stats["bursts"][-1]["closed"]:
                stats["bursts"][-1]["closed"] = True   # 轉入蓄積＝這一波結束

            if bad and not caught:
                stats["accepted_bad"] += 1
                if high_value:
                    stats["high_value_hits"] += 1
                if stats["slashed_vid"] == who.vid:
                    stats["accepted_bad_after_slash"] += 1
            if not bad and is_attacker:
                stats["clean_paid"] += 1
                who.clean_paid += 1

            # 脈衝相位機：依這一輪的**最終** bad 值推進（selective / 預算可能把
            # 原本要作惡的一筆改成乾淨，那就該算進蓄積，不能算成放電）
            if is_attacker and cfg.strategy == "pulse":
                if bad:
                    who.phase_bad += 1
                else:
                    who.phase_clean += 1
                if who.phase_bad >= cfg.pulse_burst and who.phase_clean >= cfg.pulse_recover:
                    who.phase_bad = 0
                    who.phase_clean = 0

            # 同儕評審：落在盲區的壞交付，三位評審一律看不出來（同源共同盲區）
            _peer_reviews(reg, honest, who, head, task_id, good=not bad, rng=rng,
                          accuracy=cfg.reviewer_accuracy,
                          correlation=cfg.reviewer_correlation,
                          blind=in_blind)

            if caught:
                stats["caught"] += 1
                reg.apply_slash(who.vid, "sim", cfg.slash_factor)
                who.slashed = True
                if stats["slashed_vid"] is None:
                    stats["slashed_vid"] = who.vid
                    stats["first_slash_round"] = rnd
                    sc0, ob0 = reg.standing(who.vid, "sim")
                    stats["score_at_slash"] = round(sc0, 4)
                    stats["obs_at_slash"] = round(ob0, 4)
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

            # 預算用完就收工（只在明確要求時）。放在迴圈**尾端**：這一輪
            # 該做的事全部做完才停，所以停跑前的每一步與不早停時逐位相同。
            if (cfg.stop_when_budget_spent and cfg.defect_budget is not None
                    and stats["defected"] >= cfg.defect_budget):
                stats["stopped_early_at"] = rnd
                break
    finally:
        if log_f:
            log_f.close()

    stats["honest_damage"] = round(sum(
        max(0.0, honest_start[h.name] - reg.standing(h.vid, "sim")[0]) for h in honest), 4)
    if stats["slashed_vid"] is not None:
        sc, ob = reg.standing(stats["slashed_vid"], "sim")
        stats["score_final"], stats["obs_final"] = round(sc, 4), round(ob, 4)
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


def _h01(s: str) -> float:
    """把字串雜湊成 [0,1)。確定性、跨 seed 去相關——不要用 rng，
    否則同一組參數在不同 seed 下的抽樣順序會與別的隨機事件糾纏。"""
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) / 0x1_0000_0000


def _peer_reviews(reg, honest, target, head, task_id, *, good: bool,
                  rng: random.Random, accuracy: float = 1.0,
                  correlation: float = 0.0, blind: bool = False) -> None:
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
        if good or blind:
            # blind：這個錯誤落在同源檢查者的共同盲區，三位評審都看不出來。
            # 這與 correlation 不同——correlation 是「有時會一起錯」，
            # blind 是「這一類錯誤他們必然一起錯，加人也沒用」。
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
    if cfg.strategy == "pulse":
        # 見習期內強制稽核，這時候作惡等於送分——先熬過去。
        if who.deliveries <= cfg.probation_m:
            return False
        # 放電中就繼續放電；放完就轉蓄積（相位機在主迴圈推進）
        return who.phase_bad < cfg.pulse_burst
    if cfg.strategy == "repent":
        # 悔改者：熬過見習期就開始作惡，被抓一次之後**永久**只交好貨。
        # 它量的不是攻擊力，是「真的改邪歸正的 agent 要多少輪才回得到路由」。
        if who.slashed:
            return False
        return who.deliveries > cfg.probation_m
    return True                           # whitewash / sybil：能作惡就作惡


def _summarise(cfg: SimConfig, s: dict) -> dict[str, Any]:
    cost = (s["clean_paid"] * COST_PER_CLEAN_DELIVERY
            + s["identities"] * COST_PER_KEYGEN)
    gain = s["accepted_bad"] * GAIN_PER_ACCEPTED_BAD

    # ── 反應延遲 ──────────────────────────────────────────────────────
    # 脈衝攻擊的機制就在這裡：從一波開始作惡，到系統第一次抓到，中間
    # 有幾筆已經進去了？這個數字若大於 1，代表「抓到」這件事本身來不及
    # 阻止當下這一波——防禦是事後的，不是即時的。
    bursts = s.get("bursts", [])
    lags, per_burst_hits = [], []
    for b in bursts:
        per_burst_hits.append(b["hits"])
        if b["first_catch"] is not None:
            lags.append(b["first_catch"] - b["start"])
    n_b = len(bursts)
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
        # 作惡總筆數（含被抓到的）。與 accepted_bad 的差＝被擋下來的。
        "defected": s.get("defected", 0),
        # 落在同源盲區、抽中了也看不出來的筆數
        "blind_passes": s.get("blind_passes", 0),
        # 放電波次與反應延遲
        "n_bursts": n_b,
        "hits_per_burst": (round(sum(per_burst_hits) / n_b, 3) if n_b else None),
        "max_burst_hits": (max(per_burst_hits) if per_burst_hits else 0),
        # 一波裡「第一次作惡」到「第一次被抓」相隔幾輪；沒被抓過的波不計入
        "react_lag_mean": (round(sum(lags) / len(lags), 3) if lags else None),
        "bursts_never_caught": sum(1 for b in bursts if b["first_catch"] is None),
        # ── slash 之後（2026-08-07）：排除軸與贖回軸 ───────────────────────
        # 沒有任何身份被 slash 過 → 全部 None／0，聚合時要**排掉**這些 seed
        # 而不是當 0 算（「沒被抓過」與「被抓了但沒回來」是兩回事）。
        "first_slash_round": s.get("first_slash_round"),
        "routes_after_slash": s.get("routes_after_slash", 0),
        "accepted_bad_after_slash": s.get("accepted_bad_after_slash", 0),
        # 距離下一次被路由要等幾輪。None＝在本場輪數內沒有再被路由過（右設限）。
        "rounds_to_next_route": (
            s["first_route_after_slash"] - s["first_slash_round"]
            if s.get("first_route_after_slash") is not None else None),
        # 被 slash 那一刻／整場結束時，該身份的信譽分與有效觀測數。
        # obs 是回歸時間的指數係數，所以 obs_at_slash 就是 λ 這條軸的直接讀數。
        "score_at_slash": s.get("score_at_slash"),
        "obs_at_slash": s.get("obs_at_slash"),
        "score_final": s.get("score_final"),
        "obs_final": s.get("obs_final"),
        # 被 slash 之後還剩幾輪可用來翻身（右設限的分母，報「沒回來」時必須一起報）
        "rounds_after_slash": (cfg.rounds - s["first_slash_round"]
                               if s.get("first_slash_round") is not None else None),
        # 早停在第幾輪（None＝跑滿）。曝光欄只到這一輪為止，讀表的人要看得到。
        "stopped_early_at": s.get("stopped_early_at"),
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
