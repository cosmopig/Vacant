"""environment — 多向環境的原語：通道、可見性、與可執行的通道分離不變式。

## 這支在架構裡承重什麼

現在的 Vacant 是一條單向管線（`06_多向環境架構.md` §1）：

    路由派工 → agent 交付 → 同儕評審 → 稽核抽查 → 信譽更新 → 下一次路由

資訊只往一個方向流，每個參與者只有一個介入點而且都在事後。這不只是功能缺失，
它有可量的後果：評審看得到彼此（瀑布通道，Bikhchandani 1992／Anderson & Holt
1997）、信譽對所有人可見（權威壓抑，Chen et al. 2026）、UCB 把流量集中
（中心化拓撲，Becker 2017）——**於是判斷相關，於是一起錯**。
我們量到的「共同盲區」有一部分是這個架構自己造出來的。

本模組把管線換成**環境**：一塊 append-only 的共享看板，多方參與者可以在任何
時點寫入，而**誰在什麼相位讀得到什麼由通道規格決定**。承重的不是「多了幾條
通道」，是**通道之間的隔離**——Delphi 傳論證不傳立場、手術核對表傳角色不傳
評價、TMS 傳「誰會什麼」不傳「他覺得答案是什麼」
（`參考文獻/2026-08-06_人類運作邏輯/HUMAN_MECHANISMS.md` §0、§6.2–6.4）。

### 設計上唯一的硬規定

**每一條通道都必須回答「為什麼這條資訊不併進主通道」。** 沒有答案的通道就是在
製造相關性，不該存在。這條規定在本模組裡是**可執行的**：`ChannelSpec` 的
`why_not_main` 是必填欄位，空字串直接 raise——與 `memory.assert_ks1_clean`
同一種防呆哲學（規格不是註解，是會炸的東西）。

### 誠實邊界

- 通道分離**改不動模型家族的共同盲區 β**。它能拆掉的是「架構造成的那一部分
  相關性」（瀑布、權威、拓撲）。分離之後殘餘的相關性才真的可歸因於同源——
  這正是 HUMAN_MECHANISMS §6.2 的論證，也是 `multiway.py` 要量的東西。
- 本模組只提供原語與不變式，不提供效果。效果由 `multiway.py` 的兩臂實測。
- 通道越多，可被表演的表面越多（Power 1997 的 decoupling）。每條通道的
  可被博弈之處寫在 `06_多向環境架構.md` §5，其中拒絕原語與求助通道的博弈
  已在 `multiway.py` 實測（結論：calibration 維擋不住挑簡單任務）。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

# --- 角色：可見性表的列 ------------------------------------------------------
# worker  被指派做這件事的 agent
# peer    同儕評審（本件的評審面板成員）
# router  路由與 registry（機器讀者，不是參與者）
# auditor 確定性稽核（沙箱重跑；不是模型）
# human   任何時點可介入的人類（展場的觀眾也是這個角色）
ROLES = ("worker", "peer", "router", "auditor", "human")

# --- 相位：可見性表的欄 ------------------------------------------------------
# 一件工作的生命週期。承重的是 SEALED：評審在這一段彼此看不見、也看不到信譽。
PHASES = ("OPEN", "ASSIGNED", "WORKING", "SEALED", "REVEAL", "AUDIT", "CLOSED")
_PHASE_INDEX = {p: i for i, p in enumerate(PHASES)}


class ChannelViolation(Exception):
    """違反通道分離（把該分開的資訊塞進同一條通道，或跨相位偷看）。"""


@dataclass(frozen=True)
class ChannelSpec:
    """一條通道的讀寫權限與**存在理由**。

    `why_not_main` 不是註解，是必填欄位：一條通道如果講不出「為什麼這條資訊
    不能併進主通道」，它就沒有在分離任何東西，只是在多加一條讓判斷互相汙染的
    路徑。建構時空字串直接 raise。
    """

    name: str
    writers: tuple[str, ...]
    readers: tuple[str, ...]
    readable_phases: tuple[str, ...]
    why_not_main: str
    evidence: str = ""          # 支持這條分離的文獻（可空，但通常不該空）

    def __post_init__(self) -> None:
        if not self.why_not_main.strip():
            raise ChannelViolation(
                f"通道 {self.name!r} 沒有回答「為什麼不併進主通道」——"
                "沒有答案的通道是在製造相關性，不要加"
            )
        for r in self.writers + self.readers:
            if r not in ROLES:
                raise ValueError(f"未知角色 {r!r}（通道 {self.name}）")
        for p in self.readable_phases:
            if p not in PHASES:
                raise ValueError(f"未知相位 {p!r}（通道 {self.name}）")


# ── 通道總表 ───────────────────────────────────────────────────────────────
# 這張表就是 `06_多向環境架構.md` §3 的讀寫權限表，程式碼版。文件與程式碼
# 不同步時以本表為準（文件會過期，這張表會被測試打）。
CHANNELS: dict[str, ChannelSpec] = {
    "delivery": ChannelSpec(
        name="delivery",
        writers=("worker",),
        readers=("peer", "router", "auditor", "human"),
        readable_phases=("SEALED", "REVEAL", "AUDIT", "CLOSED"),
        why_not_main="它就是主通道。列在這裡是為了讓其他五條有對照。",
    ),
    "directory": ChannelSpec(
        name="directory",
        writers=("worker", "auditor"),
        readers=("worker", "peer", "router", "human"),
        readable_phases=PHASES,
        why_not_main=(
            "目錄只准帶「誰會什麼」（管轄權宣告＋稽核推導的坑型資格），"
            "**不准帶名次或分數**。併進主通道就是把信譽排行榜公開給參與者，"
            "而那是權威壓抑與中心化拓撲的入口。TMS 的可搬運成分是一張表，"
            "不是一個排名。"
        ),
        evidence="Moreland & Myaskovsky 2000（交出表就複製全部效益）；"
                 "Hollingshead 1998（錯的目錄比沒有更糟）；Becker 2017（毒是中心性）",
    ),
    "declination": ChannelSpec(
        name="declination",
        writers=("worker",),
        readers=("router", "auditor", "human"),
        readable_phases=("ASSIGNED", "WORKING", "SEALED", "REVEAL", "AUDIT", "CLOSED"),
        why_not_main=(
            "拒絕若走主通道，它在帳上就長得像一筆沒交出來的交付＝失敗，"
            "於是沒有人會拒絕（現況正是如此）。而且拒絕**不對同儕廣播**："
            "廣播會讓『我不會』變成地位訊號，問的成本一上升就沒人問了。"
            "喊停必須無聲譽代價，否則它會被心理安全那條機制吃掉。"
        ),
        evidence="Zhang 2023 R-Tuning（接了就做是被訓練出來的編造傾向）；"
                 "Pronovost 2006（承重的是授權喊停）；Borgatti & Cross 2003（問的成本）",
    ),
    "consult": ChannelSpec(
        name="consult",
        writers=("worker",),
        readers=("worker", "auditor", "human"),
        readable_phases=PHASES,
        why_not_main=(
            "求助傳的是**論證**，不是立場。回覆端在結構上沒有分數欄位，"
            "也看不到求助者的草稿；求助者看不到回覆者的身分與信譽。"
            "併進主通道 = 幫忙的人同時當評審 = 同一個訊號被算兩次，"
            "那正是我們想減少的相關性。同儕不可讀：不然它就是廣播。"
        ),
        evidence="Dalkey & Helmer 1963（Delphi 傳論證不傳立場）；"
                 "Lorenz 2011（光給平均值就摧毀獨立性）；Du 2023（增益取決於第一輪獨立）",
    ),
    "intervention": ChannelSpec(
        name="intervention",
        writers=("human",),
        readers=("router", "auditor", "human", "worker", "peer"),
        readable_phases=PHASES,
        why_not_main=(
            "人類介入只帶**注意力**，不帶判決。FLAG 的語意是『往這裡看』，"
            "不是『這是錯的』。帶判決的人類是最大中心度節點，他的錯誤會傳染"
            "給所有人；只帶注意力則是改變抽樣分布、不改變任何人的判斷。"
            "這也是展場第 3 拍能成立的原因：觀眾是**抽樣者**不是裁判。"
        ),
        evidence="Becker 2017（中心節點決定群體對錯）；"
                 "Irving 2018（對抗性選出的 6 像素 88% vs 隨機 6 像素 59%）",
    ),
    "review": ChannelSpec(
        name="review",
        writers=("peer",),
        readers=("auditor", "router", "human"),
        readable_phases=("REVEAL", "AUDIT", "CLOSED"),
        why_not_main=(
            "評審在 SEALED 相位只上鏈 sha256(review‖nonce)，揭露前**沒有任何"
            "可觀察的行動歷史**，瀑布通道由建構關閉。這不只是防作弊，是改變"
            "推論地位：密封之後殘餘的相關性才真的可歸因於同源，"
            "而不是混雜了『評審順序比較後面』。"
        ),
        evidence="Bikhchandani 1992／Anderson & Holt 1997（瀑布不需要共謀）；"
                 "HUMAN_MECHANISMS §6.2",
    ),
}

# ── 明確**不做**的通道（06 §6）。列在程式碼裡，因為它們看起來都很像好主意。 ──
REJECTED_CHANNELS: dict[str, str] = {
    "peer_scores": "agent↔agent 傳分數／立場。Lorenz 2011 證明光給算術平均就"
                   "造成多樣性崩塌而集體誤差沒有改善——這條沒有『為什麼不併進"
                   "主通道』的答案，因為它就是主通道。",
    "public_leaderboard": "同儕可見的信譽排行榜。router 需要它，同儕不需要。"
                          "Campbell's law 的可操作形式：腐化程度是指標所承載的"
                          "決策權重的函數，公開給被評分者就是把權重交到他們手上。",
    "self_justification": "agent 對人類的自由文字辯解通道。Lerner & Tetlock 1999："
                          "被究責者會使用**更多**規範上無關的資訊（dilution effect）；"
                          "Khan 2024：單一顧問設定下，說服力越強裁判越差。"
                          "要辯論就要對立指派，不能是單向解釋。",
    "peer_broadcast": "agent 對 agent 的即時廣播（『這題有坑』）。看起來最有價值，"
                      "製造的相關性也最大：所有下游 agent 的錯誤都條件依賴於"
                      "同一句宣稱。要傳可以，但必須先過確定性稽核——"
                      "那條路已經存在，就是 M2『只有被稽核過的 episode 才蒸餾成教訓』。",
}


# --- 看板 ------------------------------------------------------------------
@dataclass
class Post:
    """看板上的一筆。`sealed=True` 時 payload 不可讀，只有 digest。"""

    tick: int
    channel: str
    role: str
    author: str
    task_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    sealed: bool = False
    digest: str = ""

    def to_json(self) -> dict[str, Any]:
        d = {"tick": self.tick, "channel": self.channel, "role": self.role,
             "author": self.author, "task_id": self.task_id, "sealed": self.sealed}
        if self.sealed:
            d["digest"] = self.digest
        else:
            d["payload"] = self.payload
        return d


# 論證通道的可執行防呆：回覆只准帶理由，不准帶判決。
# 與 KS-1 同一種東西——規格如果只寫在文件裡，它遲早會被繞過。
VERDICT_TOKENS = (
    "pass", "fail", "approve", "reject", "correct", "incorrect", "score",
    "lgtm", "通過", "不通過", "同意", "不同意", "正確", "錯誤",
    "分數", "評分", "接受", "拒收", "沒問題", "有問題",
)
# 數值評分：「8 分」「7/10」。單獨一個「分」會誤傷「部分」「分開」，所以綁數字。
_SCORE_RE = re.compile(r"\d+\s*(分|/\s*\d+)")


def assert_argument_only(text: str) -> None:
    """求助回覆只准是論證，不准夾帶立場。夾帶就 raise（不要繞過）。

    Delphi 的不對稱是整條通道的全部價值：傳理由不傳立場。允許夾帶立場之後，
    這條通道就退化成「多一個人給你答案」，也就是 Lorenz 2011 量到的那個
    摧毀獨立性的最小劑量。

    **誠實邊界**：詞表擋得住直白的夾帶，擋不住改寫過的——與 `assert_ks1_clean`
    的詞表是同一種限制。真正承重的是結構：回覆沒有分數欄位，而且諮詢過的人
    不得評審同一件（`assert_channel_separation` ①）。詞表是防呆不是過濾器。
    """
    low = text.lower()
    hit = [t for t in VERDICT_TOKENS if t in low]
    if _SCORE_RE.search(low):
        hit.append("數值評分")
    if hit:
        raise ChannelViolation(
            f"求助回覆夾帶立場（命中 {hit[:3]}）：consult 通道只傳論證不傳判決"
        )


class Environment:
    """多方共享狀態：append-only 看板 ＋ 每件工作的相位 ＋ 可見性規則。

    這不是訊息佇列——它的承重點是**讀取端**。誰在什麼相位讀得到什麼，
    決定了判斷之間有多少相關性；寫入端反而是次要的。
    """

    def __init__(self) -> None:
        self._board: list[Post] = []
        self._phase: dict[str, str] = {}
        self._tick = 0
        # 諮詢帳：task_id → 諮詢過這件事的 agent 集合。承重用途是**取消評審資格**
        # （看過草稿的人不得評審同一件）——這是結構性的反串供，不是統計偵測。
        self._consulted: dict[str, set[str]] = {}
        # 拒絕帳：(agent, task_id) → Declination
        self._declinations: dict[tuple[str, str], "Declination"] = {}
        self._interventions: list[Post] = []

    # --- 相位 --------------------------------------------------------------
    def phase(self, task_id: str) -> str:
        return self._phase.get(task_id, "OPEN")

    def advance(self, task_id: str, phase: str) -> None:
        """推進相位。只准往前——相位倒退等於把密封的東西退回可讀狀態。"""
        if phase not in PHASES:
            raise ValueError(f"未知相位 {phase!r}")
        cur = self.phase(task_id)
        if _PHASE_INDEX[phase] < _PHASE_INDEX[cur]:
            raise ChannelViolation(f"相位不可倒退：{cur} → {phase}（task {task_id}）")
        self._phase[task_id] = phase

    # --- 寫 ----------------------------------------------------------------
    def post(self, channel: str, role: str, author: str, task_id: str,
             payload: dict[str, Any] | None = None, *, seal: bool = False,
             nonce: str = "") -> Post:
        spec = CHANNELS.get(channel)
        if spec is None:
            hint = REJECTED_CHANNELS.get(channel)
            raise ChannelViolation(
                f"未知通道 {channel!r}" + (f"——這條是刻意不做的：{hint}" if hint else "")
            )
        if role not in spec.writers:
            raise ChannelViolation(f"角色 {role!r} 不得寫入 {channel} 通道")
        self._tick += 1
        payload = payload or {}
        if seal:
            blob = json.dumps(payload, sort_keys=True, ensure_ascii=False) + "|" + nonce
            p = Post(self._tick, channel, role, author, task_id,
                     payload={}, sealed=True,
                     digest=hashlib.sha256(blob.encode()).hexdigest())
        else:
            p = Post(self._tick, channel, role, author, task_id, dict(payload))
        self._board.append(p)
        if channel == "intervention":
            self._interventions.append(p)
        return p

    def reveal(self, post: Post, payload: dict[str, Any], nonce: str) -> None:
        """揭露密封的一筆，比對雜湊。對不上＝事後改稿，拒收。"""
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False) + "|" + nonce
        if hashlib.sha256(blob.encode()).hexdigest() != post.digest:
            raise ChannelViolation("揭露內容與承諾的雜湊不符（評審事後改稿）")
        post.payload = dict(payload)
        post.sealed = False

    # --- 讀 ----------------------------------------------------------------
    def visible(self, reader_role: str, task_id: str | None = None) -> list[Post]:
        """某角色**現在**讀得到的看板內容。密封的一筆一律不吐 payload。

        這個函式就是可見性表的執行版：`06 §3` 的表格如果和它不一致，
        以它為準。
        """
        out = []
        for p in self._board:
            if task_id is not None and p.task_id != task_id:
                continue
            spec = CHANNELS[p.channel]
            if reader_role not in spec.readers:
                continue
            if self.phase(p.task_id) not in spec.readable_phases:
                continue
            out.append(p)
        return out

    def read_reputation(self, reader_role: str, task_id: str) -> None:
        """信譽的讀取閘。**同儕在 CLOSED 之前一律讀不到**。

        這不是隱私考量是效能考量（HUMAN_MECHANISMS §6.4）：Chen et al. 2026
        量到權威 agent 在場會壓抑語意多樣性。信譽供 router 指派、供 registry
        加權，但不供同儕觀看——本函式只負責 raise，真正的值由呼叫端自 registry 取。
        """
        if reader_role == "peer" and self.phase(task_id) != "CLOSED":
            raise ChannelViolation(
                f"評審期間不得讀取信譽（task {task_id} 相位 {self.phase(task_id)}）"
            )
        if reader_role not in ("router", "auditor", "human", "peer"):
            raise ChannelViolation(f"角色 {reader_role!r} 無信譽讀取權")

    # --- 求助（論證通道）----------------------------------------------------
    def consult(self, asker: str, helper: str, task_id: str, question: str,
                answer: str) -> Post:
        """一次求助。回覆走 `assert_argument_only`，並把 helper 記進諮詢帳。

        記帳的用途是**取消評審資格**：看過這件事的人不得評審這件事。
        這是結構性的反串供——不依賴事後統計偵測相關性，也就不會誤傷
        「只是評審順序比較後面」的誠實 agent。代價是面板變小，要量。
        """
        assert_argument_only(answer)
        self._consulted.setdefault(task_id, set()).add(helper)
        return self.post("consult", "worker", asker, task_id,
                         {"question": question, "argument": answer, "helper_anon": True})

    def consulted_on(self, task_id: str) -> set[str]:
        return set(self._consulted.get(task_id, ()))

    # --- 拒絕 --------------------------------------------------------------
    def declare(self, d: "Declination") -> Post:
        self._declinations[(d.agent, d.task_id)] = d
        return self.post("declination", "worker", d.agent, d.task_id, d.to_json())

    def declination(self, agent: str, task_id: str) -> "Declination | None":
        return self._declinations.get((agent, task_id))

    # --- 人類介入 ----------------------------------------------------------
    def flag(self, human: str, task_id: str, note: str = "") -> Post:
        """FLAG＝『往這裡看』。**沒有判決欄位，刻意的**。"""
        return self.post("intervention", "human", human, task_id,
                         {"verb": "FLAG", "note": note})

    def halt(self, human: str, task_id: str, note: str = "") -> Post:
        """HALT＝在交付被接受之前叫停，強制稽核。任何人不分位階都有這個權利。"""
        return self.post("intervention", "human", human, task_id,
                         {"verb": "HALT", "note": note})

    def ask(self, human: str, task_id: str, question: str) -> Post:
        """ASK＝問。回的是收據（誰做的、抽查了幾筆），不是產出本身。"""
        return self.post("intervention", "human", human, task_id,
                         {"verb": "ASK", "question": question})

    @property
    def interventions(self) -> list[Post]:
        return list(self._interventions)

    def board_jsonl(self) -> list[str]:
        return [json.dumps(p.to_json(), ensure_ascii=False) for p in self._board]


# --- 拒絕原語 ---------------------------------------------------------------
# 理由碼綁在坑型／結構上，不是自由文字。Abbott 1988：管轄權主張會用系統獎勵的
# 術語提出——給自由文字就等於邀請 agent 去發明聽起來最好的理由。
DECLINE_REASONS = (
    "out_of_jurisdiction",   # 這不是我宣告的坑型
    "insufficient_context",  # 給的東西不夠做
    "ambiguous_spec",        # 需求本身有歧義（該回去壓成契約）
    "conflict_of_interest",  # 我諮詢過／評審過這條線
)


@dataclass
class Declination:
    """一筆 ACCEPT / DECLINE。**拒絕本身記中性**，不是失敗。"""

    agent: str
    task_id: str
    accepted: bool
    reason: str = ""
    p_ik: float = 0.5    # agent 自估「我做得出來」的機率（Kadavath 2022 的 P(IK)）

    def __post_init__(self) -> None:
        if not self.accepted and self.reason not in DECLINE_REASONS:
            raise ValueError(f"拒絕理由必須是結構碼之一 {DECLINE_REASONS}：{self.reason!r}")

    def to_json(self) -> dict[str, Any]:
        return {"agent": self.agent, "task_id": self.task_id,
                "accepted": self.accepted, "reason": self.reason,
                "p_ik": round(self.p_ik, 4)}


class CalibrationLedger:
    """第六維 `calibration` 的帳（**獨立於 reputation.DIMS**）。

    為什麼不直接加進 `reputation.DIMS`：`ReputationCell.score()` 是五維平均，
    加第六維會改動所有既有格子的分數與 B 層六情境的判準值。把它做成獨立帳，
    路由端才能決定要不要用、用多重，也不會讓一個實驗性的維度污染既有數字。
    正式落地時 `DIMS + ("calibration",)` 是加法式改動，但要重跑 B 層。

    ### 兩種計分規則，因為第一種擋不住博弈

    - `naive_score`：規格書寫法——拒絕了一個本來會失敗的任務 +1、接受了一個
      失敗的任務 −1、拒絕本身中性。
    - `discrimination`：Youden's J ＝ P(拒絕|本來會失敗) − P(拒絕|本來會成功)。
      這才是「你分不分得出自己什麼時候不行」。

    差別是實測出來的（`multiway.py` M4）：只挑簡單任務的 agent 在 naive 下
    拿高分，**而且在 J 下也不一定低**——真正抓得住它的量是 coverage（接受率），
    不是 calibration。這條結論寫在 `06 §5.1`，不要靠直覺推。

    ### 誠實邊界

    `would_fail`（拒掉的那件事本來會不會失敗）在模擬裡是真值，**在生產環境
    拿不到**。生產版只有兩條路：把拒掉的任務重派給別人當影子、或抽樣 δ 比例的
    拒絕強制退回原 agent 執行（「拒絕稽核」）。後者是可執行的，而且要付成本——
    這是非博弈性 calibration 的價碼，不是可以省掉的細節。
    """

    def __init__(self) -> None:
        # agent → [(accepted, would_fail)]
        self._rows: dict[str, list[tuple[bool, bool]]] = {}

    def record(self, agent: str, accepted: bool, would_fail: bool) -> None:
        self._rows.setdefault(agent, []).append((accepted, would_fail))

    def naive_score(self, agent: str) -> float:
        rows = self._rows.get(agent, [])
        if not rows:
            return 0.0
        s = 0
        for accepted, would_fail in rows:
            if not accepted and would_fail:
                s += 1
            elif accepted and would_fail:
                s -= 1
        return s / len(rows)

    def discrimination(self, agent: str) -> float | None:
        """Youden's J。任一邊沒有樣本 → None（退化端點不給數字）。"""
        rows = self._rows.get(agent, [])
        fails = [r for r in rows if r[1]]
        passes = [r for r in rows if not r[1]]
        if not fails or not passes:
            return None
        tpr = sum(1 for a, _ in fails if not a) / len(fails)
        fpr = sum(1 for a, _ in passes if not a) / len(passes)
        return round(tpr - fpr, 4)

    def coverage(self, agent: str) -> float | None:
        """接受率。**這才是抓挑簡單任務的那個量**，不是 calibration。"""
        rows = self._rows.get(agent, [])
        if not rows:
            return None
        return round(sum(1 for a, _ in rows if a) / len(rows), 4)

    def agents(self) -> list[str]:
        return sorted(self._rows)


# --- 不變式 -----------------------------------------------------------------
def assert_channel_separation(env: Environment, task_id: str,
                              panel: tuple[str, ...]) -> None:
    """一件工作的通道分離不變式。違反＝這一筆的相關性量測不可信。

    三條，全部是結構性的（不靠統計偵測）：
      ① 諮詢過這件事的人不得在評審面板裡（反串供；看過草稿的判斷不獨立）
      ② 拒絕紀錄不得對同儕可見（否則『我不會』變成地位訊號）
      ③ SEALED 相位不得有已揭露的 review（瀑布通道必須由建構關閉）
    """
    overlap = env.consulted_on(task_id) & set(panel)
    if overlap:
        raise ChannelViolation(
            f"評審面板包含諮詢過本件的 agent：{sorted(overlap)}——"
            "看過草稿的人不得評審同一件（結構性反串供）"
        )
    # ② 查的是**規格**不是那一次的查詢結果：visible() 本來就會濾掉，所以只查
    #    結果永遠不會炸。要擋的是「有人把 peer 加進 declination 的 readers」。
    if "peer" in CHANNELS["declination"].readers:
        raise ChannelViolation("declination 通道把 peer 列進讀者——拒絕不得成為地位訊號")
    # ③ 同理：查看板本體，不查 visible()。SEALED 期間不得存在已揭露的 review。
    if env.phase(task_id) == "SEALED":
        leaked = [p for p in env._board
                  if p.task_id == task_id and p.channel == "review" and not p.sealed]
        if leaked:
            raise ChannelViolation(f"SEALED 相位有已揭露的 review×{len(leaked)}——瀑布通道沒關上")
