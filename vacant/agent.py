"""vacant — 把任何 agent 的『腦』包成「更好、可究責」的 agent。

人話承諾：你的 agent 單次呼叫常會錯、又無法究責。vacant 在外面包一層：
  1) verify-fix 組合：用客觀檢查抓錯、帶回饋重試 → 更準（實測 gemma-12b 67%→83%）。
  2) 簽章 logbook：每次互動 Ed25519 簽章 + hash-chain → 可驗證、可究責。
brain-agnostic（LM Studio / Hermes / 任何 OpenAI 相容端點）。

誠實邊界：accuracy 增益只在「答案可被檢查（verifier 能判對錯）」時成立——
能跑測試/能驗證的任務（code+tests、數學、格式約束…）。不可檢查的主觀任務，
vacant 仍給「可究責」，但不保證更準（規格 §10 oracle 問題）。

`infra_void`（09 §3.5；語意與 `ops/gain/brain_cline.py::InfraVoid` 同一份）：
腦呼叫失敗（端點關著、逾時、畸形回應）**不算成功也不算失敗**，它是
「這一格沒有量到」。`SolveResult.infra_void` 與 `Vacant.bench` 的
`*_void`／`*_measured` 欄位就是為了讓呼叫端分得開「沒量到」與「量到 0」——
把前者渲染成後者，是拿一個沒發生的量測去支撐一個比較數字。

最小用法：
    from vacant import Vacant, LMStudioBrain
    v = Vacant(LMStudioBrain("http://localhost:1234", "your-model"))
    r = v.solve("Reverse the string: hello", verifier=lambda a: a == "olleh")
    print(r.answer, r.verified, r.calls, r.accountable)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable

from .attest import make_attestation
from .body import now_ms
from .brains import Brain
from .composer import Composer
from .identity import Identity, PublicIdentity
from .logbook import Logbook

Verifier = Callable[[str], bool]


@dataclass
class SolveResult:
    answer: str
    verified: bool          # 通過客觀檢查？
    calls: int              # 用掉的腦呼叫次數
    strategy: str
    accountable: bool       # 簽章 logbook 鏈可驗（究責）
    brain: str
    attestation: dict | None = None  # 可攜的簽章通過憑證（離開 vacant 仍可獨立驗）
    ok_calls: int = 0        # 這一格裡「腦真的回了東西」的次數
    failed_calls: int = 0    # 這一格裡呼叫失敗的次數（端點關著／逾時／畸形）
    first_error: str | None = None   # 第一個失敗的原文（診斷用，不進統計）

    @property
    def infra_void(self) -> bool:
        """這一格**沒有量到**（09 §3.5）：一次成功的腦呼叫都沒有。

        承重什麼：`verified is False` 有兩個完全不同的來源——「模型答錯」與
        「根本沒問到模型」。前者是資料，後者是基建故障。把後者混進分子或分母，
        等於用一個沒發生的量測去支撐一個比較數字。呼叫端要先問這一格算不算數，
        再去看 `verified`。
        """
        return self.ok_calls == 0 and self.failed_calls > 0

    @property
    def measured(self) -> bool:
        """這一格算不算數。`infra_void` 的反面，寫成正面是為了讓分母講得出口。"""
        return not self.infra_void

    def __str__(self) -> str:
        if self.infra_void:
            v = "—infra_void（沒量到）"
        else:
            v = "✓verified" if self.verified else "✗unverified"
        a = "✓accountable" if self.accountable else "—"
        return f"{self.answer!r} [{v}, {self.calls} calls, {a}, brain={self.brain}]"


class Vacant:
    """把一個 Brain 包成更好、可究責的 agent。"""

    def __init__(self, brain: Brain, *, k: int = 3, sign: bool = True) -> None:
        self.brain = brain
        self.k = k
        self._identity = Identity.generate() if sign else None
        self.logbook = Logbook()
        self._ok_calls = 0
        self._failed_calls = 0
        self._first_error: str | None = None

    @property
    def vacant_id(self) -> str | None:
        return self._identity.vacant_id if self._identity else None

    def _begin_cell(self) -> None:
        """開一格新的量測。計數歸零——格與格之間不准互相污染。

        「一格」＝一次 `plain` 或一次 `solve`。infra_void 是**逐格**判定的
        （09 §3.5），所以計數器的生命週期必須跟格對齊，不是跟 Vacant 物件對齊。
        """
        self._ok_calls = 0
        self._failed_calls = 0
        self._first_error = None

    def _gen(self, prompt: str) -> str:
        # production 硬化：腦呼叫(網路/逾時/畸形)失敗絕不讓 solve 崩 —— 視為一次失敗嘗試，
        # verify-fix 會自然重試或誠實回報未通過。
        # ⚠ 硬化不等於靜默：失敗**要被數到**，否則「端點關著」與「模型答錯」在
        #   報表上長得一模一樣（09 §3.5 infra_void；同 brain_cline.InfraVoid 語意）。
        try:
            ans = self.brain.generate(prompt)
            if not isinstance(ans, str):
                ans = str(ans)
            self._ok_calls += 1
        except Exception as e:
            ans = f"[brain-error:{type(e).__name__}]"
            self._failed_calls += 1
            if self._first_error is None:
                self._first_error = f"{type(e).__name__}: {e}"
        if self._identity is not None:
            self.logbook.append(
                "INFERENCE",
                {"prompt_sha": hashlib.sha256(prompt.encode()).hexdigest()[:16],
                 "ans_sha": hashlib.sha256((ans or "").encode()).hexdigest()[:16],
                 "brain": self.brain.name},
                self._identity, ts_ms=now_ms(),
            )
        return ans

    def verify_chain(self) -> bool:
        if self._identity is None:
            return False
        return self.logbook.verify_chain(PublicIdentity(self._identity.vacant_id, self._identity.pub))

    def attest(self, prompt: str, answer: str, *, check_desc: str, verified: bool) -> dict | None:
        """對一個（prompt, answer, 是否通過）產生可攜簽章憑證；未簽章身分則 None。"""
        if self._identity is None:
            return None
        return make_attestation(self._identity, prompt=prompt, answer=answer,
                                check=check_desc, verified=verified, ts_ms=now_ms())

    # --- 核心：vacant 加值（verify-fix）-----------------------------------
    def solve(self, prompt: str, verifier: Verifier, *, k: int | None = None,
              check_desc: str = "custom-verifier",
              on_step: Callable[[int, str, bool], None] | None = None) -> SolveResult:
        k = k or self.k
        self._begin_cell()
        r = Composer(lambda fb: self._gen(prompt + fb), verifier).vacant(k, on_step=on_step)
        att = self.attest(prompt, r.answer, check_desc=check_desc, verified=r.correct)
        return SolveResult(r.answer, r.correct, r.calls, "vacant-verifyfix",
                           self.verify_chain(), self.brain.name, att,
                           self._ok_calls, self._failed_calls, self._first_error)

    # --- 對照：裸單次（沒有 vacant 組合）---------------------------------
    def plain(self, prompt: str, verifier: Verifier) -> SolveResult:
        self._begin_cell()
        r = Composer(lambda fb: self._gen(prompt + fb), verifier).plain()
        return SolveResult(r.answer, r.correct, r.calls, "plain",
                           self.verify_chain(), self.brain.name, None,
                           self._ok_calls, self._failed_calls, self._first_error)

    # --- 證明：在你自己的設定上量 plain vs vacant -------------------------
    def bench(self, cases: list[tuple[str, Verifier]], *, k: int | None = None) -> dict:
        """cases: [(prompt, verifier), ...]。回傳 plain vs vacant 的正確率/算力/增益。

        承重什麼：這支是「在你自己的設定上量一次」的唯一入口，所以**分母的定義
        就在這裡**。三種結局要分得開（09 §3.5）：答對 / 答錯 / **沒量到**
        （`infra_void`＝這一格一次成功的腦呼叫都沒有）。沒量到的格子既不進分子
        也不進分母，而且它的格數**單獨回報**——一個把 `infra_void` 折進「答錯」
        的正確率，會把「端點是關的」講成「模型 0%」。

        回傳的鍵：
          - `n`：題數（cases 的長度）
          - `plain_void` / `vacant_void`：各臂沒量到的格數
          - `plain_measured` / `vacant_measured`：各臂**算數**的格數（＝該臂正確率的分母）
          - `paired_measured`：兩臂**都**量到的格數（＝ `gain` 的分母；成對比較的
            分母只能是這一個，否則兩邊在比不同的題目）
          - `plain_acc` / `vacant_acc` / `gain`：分母為 0 時是 `None`，**不是 0.0**
          - `infra_void`：任一臂的 measured 為 0 或 paired_measured 為 0 ⇒ True
            （＝整份報告沒有可印的比較數字）
          - `first_error`：第一個腦呼叫失敗的原文，診斷用，不進任何統計
          - `rows`：`(prompt, plain_ok, vacant_ok, vacant_calls, plain_void, vacant_void)`

        ⚠ 誠實邊界：`*_calls_per` 的分母是**該臂算數的格數**，沒量到那些格子燒掉的
          呼叫不進去——成本要跟它買到的量測配對，否則「算力/題」會被故障灌水。
        """
        k = k or self.k
        plain_hits = vacant_hits = plain_calls = vacant_calls = 0
        plain_void = vacant_void = paired_measured = 0
        paired_plain_hits = paired_vacant_hits = 0
        first_error: str | None = None
        rows = []
        for prompt, verifier in cases:
            p = self.plain(prompt, verifier)
            v = self.solve(prompt, verifier, k=k)
            for r in (p, v):
                if first_error is None and r.first_error is not None:
                    first_error = r.first_error
            if p.infra_void:
                plain_void += 1
            else:
                plain_hits += p.verified
                plain_calls += p.calls
            if v.infra_void:
                vacant_void += 1
            else:
                vacant_hits += v.verified
                vacant_calls += v.calls
            if p.measured and v.measured:
                paired_measured += 1
                paired_plain_hits += p.verified
                paired_vacant_hits += v.verified
            rows.append((prompt[:40], p.verified, v.verified, v.calls,
                         p.infra_void, v.infra_void))
        n = len(cases)
        plain_measured = n - plain_void
        vacant_measured = n - vacant_void

        def _rate(hits: int, denom: int) -> float | None:
            return hits / denom if denom else None

        return {
            "n": n, "brain": self.brain.name, "k": k,
            "plain_void": plain_void, "vacant_void": vacant_void,
            "plain_measured": plain_measured, "vacant_measured": vacant_measured,
            "paired_measured": paired_measured,
            "infra_void": not (plain_measured and vacant_measured and paired_measured),
            "first_error": first_error,
            "plain_acc": _rate(plain_hits, plain_measured),
            "vacant_acc": _rate(vacant_hits, vacant_measured),
            "gain": (_rate(paired_vacant_hits - paired_plain_hits, paired_measured)),
            "plain_calls_per": _rate(plain_calls, plain_measured),
            "vacant_calls_per": _rate(vacant_calls, vacant_measured),
            "rows": rows,
        }


def checkable_cases(n: int = 12, *, seed: str = "vacant") -> list[tuple[str, Verifier]]:
    """從內建可檢查任務套件造 bench 用的 (prompt, verifier)。供開箱即用的示範。"""
    from .tasks import task_stream
    cases: list[tuple[str, Verifier]] = []
    for t in task_stream(n, seed=seed):
        expected = t["expected"]
        prompt = f"Task [{t['niche']}] on input {t['input']!r}. Output ONLY the answer."
        cases.append((prompt, (lambda a, _e=expected: str(a).strip().strip('\"').strip("'") == _e)))
    return cases
