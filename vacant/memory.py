"""memory — MemoryStream ＋ MemoryManager（10 §3；X1 的實驗處理本身）。

主線一句話（10 §0）：Agent＝身體（凍結的模型）＋記憶（stream）。責任不住在
身體裡，住在被審過的記憶裡。這支模組就是那條記憶：

  - **MemoryStream**：episode 序列＝logbook 上的 EPISODE 事件——寫入即簽章
    上鏈（改動1 之後 stream 有身份、有鏈頭），記憶不可竄改是 X1 的可信前提。
  - **MemoryManager**：實驗處理本身——決定「什麼進 context」：
      M0  什麼都不進（stateless 基線）。
      M1  最近 k 個 episode 原文塞入，無篩選無蒸餾（文獻 R13 預測會傷害長程；
          M1 不是稻草人，是文獻支持的真對照）。
      M2  只有被稽核/被審確認過的 episode 才蒸餾成教訓；檢索 top-k 相關教訓
          ＋其稽核結論入 context；固定 token 預算 B；舊教訓 decay。

KS-1 免疫（10 §4.5）：三臂 prompt 模板逐字相同，唯一差異＝這裡注入的記憶
區塊內容，而那些內容全部由管線真實生成。本模組提供 `assert_ks1_clean` 把
「禁止勸善文」做成可執行防呆——違反即 raise，該 run 作廢。

資訊洩漏防呆（裁決 A4）：教訓允許坑型層級抽象、禁止逐字測資——
`lesson_leaks_test_data` 對 check spec 的字面內容做包含檢查，M2 蒸餾寫入前
必過；交付前抽查（13 A-W2 門）用同一支函式。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .identity import Identity
from .logbook import Logbook, LogEntry

EPISODE_TYPE = "EPISODE"

# KS-1 防呆：prompt / 記憶注入區塊禁止出現的「責任修辭」（10 §4.5、12 §3 KS-1）。
# 這份清單擋的是實驗者手滑寫勸善文，不是擋模型輸出。
KS1_FORBIDDEN = (
    "你有責任", "你會被懲罰", "你將被懲罰", "你要負責", "後果自負",
    "you are responsible", "you will be punished", "you will be held accountable",
)


class KS1Violation(Exception):
    """prompt 模板含責任修辭 → 違反 X1 免疫聲明，該 run 作廢。"""


def assert_ks1_clean(text: str) -> str:
    low = text.lower()
    for phrase in KS1_FORBIDDEN:
        if phrase.lower() in low:
            raise KS1Violation(f"KS-1 防呆：文本含禁止措辭「{phrase}」")
    return text


# --- episode（10 §3 schema）--------------------------------------------------

@dataclass
class Episode:
    """一件被記住的工作：{task_id, spec_digest, answer_digest, reviews, audit,
    outcome, lesson, ts}。簽章與 seq 由 logbook 承擔（寫入即上鏈）。"""

    task_id: str
    spec_digest: str
    answer_digest: str
    reviews: list[dict[str, Any]] = field(default_factory=list)
    audit: dict[str, Any] | None = None   # {ran, passed} | None（未稽核如實記 None）
    outcome: str = ""                     # "pass" | "fail" | "infra_void"
    lesson: str | None = None             # 蒸餾教訓（M2 政策產物；oracle 模式直接給）
    ts_ms: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "spec_digest": self.spec_digest,
            "answer_digest": self.answer_digest,
            "reviews": self.reviews,
            "audit": self.audit,
            "outcome": self.outcome,
            "lesson": self.lesson,
            "ts_ms": self.ts_ms,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Episode":
        return cls(
            task_id=d["task_id"],
            spec_digest=d["spec_digest"],
            answer_digest=d["answer_digest"],
            reviews=d.get("reviews", []),
            audit=d.get("audit"),
            outcome=d.get("outcome", ""),
            lesson=d.get("lesson"),
            ts_ms=d.get("ts_ms", 0),
        )

    @property
    def audited_ok(self) -> bool:
        """被稽核且通過——M2 只蒸餾這種（＋被稽核抓錯的失敗剖析）。"""
        return bool(self.audit and self.audit.get("ran"))


class MemoryStream:
    """episode 序列，掛在一本 logbook 上（寫入即簽章上鏈）。

    一顆身體可以服務 N 條 stream（Resident＝keypair＋stream＋body handle，
    10 §3）；stream 的身份＝logbook 創世 hash（改動1）。"""

    def __init__(self, logbook: Logbook, identity: Identity) -> None:
        self.logbook = logbook
        self.identity = identity

    def append(self, episode: Episode, *, ts_ms: int) -> LogEntry:
        return self.logbook.append(EPISODE_TYPE, episode.to_json(), self.identity, ts_ms=ts_ms)

    def episodes(self) -> list[Episode]:
        return [
            Episode.from_json(e.payload)
            for e in self.logbook.entries
            if e.type == EPISODE_TYPE
        ]


# --- 資訊洩漏防呆（裁決 A4）--------------------------------------------------

_STR_LITERAL = re.compile(r"""(['"])((?:(?!\1).){4,}?)\1""")


def lesson_leaks_test_data(lesson: str, check: dict) -> bool:
    """教訓是否含 check spec 的逐字測資（≥4 字元的字面字串／assert 行）。

    A4 裁決：教訓允許坑型層級抽象、禁止逐字測資內容。這支是機器可查的下界
    （逐字包含）；語意級改寫洩漏由交付前人工抽查把關，誠實標明。"""
    if not lesson:
        return False
    code = str(check.get("code", "") or check.get("value", "") or check.get("pattern", ""))
    if not code:
        return False
    for m in _STR_LITERAL.finditer(code):
        if m.group(2) in lesson:
            return True
    for line in code.splitlines():
        line = line.strip()
        if line.startswith("assert") and len(line) > 12 and line in lesson:
            return True
    return False


# --- MemoryManager（M0/M1/M2 三政策）----------------------------------------

def approx_tokens(text: str) -> int:
    """粗估 token 數（≈ chars/4，中文偏保守）。B 預算的裁切尺。"""
    return (len(text) + 3) // 4


@dataclass
class Lesson:
    text: str
    task_id: str
    verdict: str          # 稽核結論（"audit_pass"/"audit_fail"）——「被審」的印記
    ts_ms: int
    idx: int = 0          # 在 episode 序列中的位置——decay 的時間單位是「筆數」不是牆鐘


class MemoryManager:
    """決定什麼進 context——X1 的實驗操弄就在這個 class 的 policy 參數上。

    - policy="M0"：inject 恆回空字串。
    - policy="M1"：最近 k 個 episode 原文（無篩選無蒸餾）。
    - policy="M2"：僅被稽核 episode 的蒸餾教訓，關鍵詞相關性 top-k，B 預算封頂，
      舊教訓 decay（相關性分數乘 recency 折扣）。
    蒸餾本身（每被審 episode +1 模型呼叫）由 harness 執行；oracle-lesson pilot
    模式直接把正確教訓寫進 episode.lesson（10 §4.2 的一票否決 pilot 用）。
    """

    POLICIES = ("M0", "M1", "M2")

    def __init__(
        self,
        policy: str,
        *,
        budget_tokens: int = 1500,
        k: int = 5,
        decay_halflife: int = 200,
    ) -> None:
        if policy not in self.POLICIES:
            raise ValueError(f"未知記憶政策 {policy}（可選 {self.POLICIES}）")
        self.policy = policy
        self.budget_tokens = budget_tokens
        self.k = k
        self.decay_halflife = decay_halflife

    # -- 注入 -----------------------------------------------------------------
    def inject(self, stream: MemoryStream, task_prompt: str) -> str:
        """回傳記憶區塊（純內容，無任何指令性措辭——KS-1）。"""
        if self.policy == "M0":
            return ""
        if self.policy == "M1":
            block = self._inject_m1(stream)
        else:
            block = self._inject_m2(stream, task_prompt)
        return assert_ks1_clean(block)

    def _inject_m1(self, stream: MemoryStream) -> str:
        eps = stream.episodes()[-self.k:]
        if not eps:
            return ""
        lines = []
        for e in eps:
            lines.append(
                f"- task={e.task_id} outcome={e.outcome} "
                f"audit={e.audit} reviews={e.reviews} lesson={e.lesson or ''}"
            )
        return self._truncate("過往紀錄（原文）：\n" + "\n".join(lines))

    def _inject_m2(self, stream: MemoryStream, task_prompt: str) -> str:
        lessons = self.lessons(stream)
        if not lessons:
            return ""
        newest = max(l.idx for l in lessons)
        scored = sorted(
            lessons,
            key=lambda l: -self._relevance(l.text, task_prompt) * self._decay(l.idx, newest),
        )
        picked = scored[: self.k]
        lines = [f"- [{l.verdict}] {l.text}" for l in picked]
        return self._truncate("過往被稽核確認的教訓：\n" + "\n".join(lines))

    def lessons(self, stream: MemoryStream) -> list[Lesson]:
        """M2 的原料：只有被稽核過的 episode 的蒸餾教訓（「被審」是資格線）。"""
        out = []
        for i, e in enumerate(stream.episodes()):
            if e.lesson and e.audited_ok:
                verdict = "audit_pass" if e.audit.get("passed") else "audit_fail"
                out.append(Lesson(e.lesson, e.task_id, verdict, e.ts_ms, idx=i))
        return out

    # -- 檢索 / decay / 預算 ----------------------------------------------------
    @staticmethod
    def _relevance(lesson_text: str, task_prompt: str) -> float:
        """離線可跑的關鍵詞重疊相關性（無 embedding 依賴；−相關性消融＝隨機取）。"""
        a = set(re.findall(r"[a-zA-Z_]{3,}|[一-鿿]{2,}", lesson_text.lower()))
        b = set(re.findall(r"[a-zA-Z_]{3,}|[一-鿿]{2,}", task_prompt.lower()))
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b) + 1e-6  # +ε：全無重疊時仍保序穩定

    def _decay(self, idx: int, newest_idx: int) -> float:
        """half-life 型 decay，時間單位＝**episode 筆數**（12 §6 decay_halflife=200 事件）。

        不可用牆鐘時間：真跑一題數十秒～數分鐘，用 ms 當單位會讓所有舊教訓
        瞬間衰減到 ~0，相關性排序退化成「只看最新一筆」。"""
        age = max(0, newest_idx - idx)
        return 0.5 ** (age / max(1, self.decay_halflife))

    def _truncate(self, block: str) -> str:
        """B 預算封頂：stream 無限長、工作檯恆為 B（11 §6）。"""
        if approx_tokens(block) <= self.budget_tokens:
            return block
        return block[: self.budget_tokens * 4]

    # -- 寫入 -----------------------------------------------------------------
    def record(
        self,
        stream: MemoryStream,
        *,
        task_id: str,
        spec_digest: str,
        answer_digest: str,
        reviews: list[dict[str, Any]],
        audit: dict[str, Any] | None,
        outcome: str,
        lesson: str | None,
        check: dict | None,
        ts_ms: int,
    ) -> Episode:
        """一件工作結束 → 寫入 episode（M2 的 lesson 過 A4 洩漏防呆）。"""
        if lesson and check and lesson_leaks_test_data(lesson, check):
            raise ValueError(f"A4 防呆：task {task_id} 的教訓含逐字測資，拒絕寫入")
        ep = Episode(
            task_id=task_id,
            spec_digest=spec_digest,
            answer_digest=answer_digest,
            reviews=reviews,
            audit=audit,
            outcome=outcome,
            lesson=lesson,
            ts_ms=ts_ms,
        )
        stream.append(ep, ts_ms=ts_ms)
        return ep
