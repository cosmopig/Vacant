"""vacant — 把任何 agent 的『腦』包成「更好、可究責」的 agent。

人話承諾：你的 agent 單次呼叫常會錯、又無法究責。vacant 在外面包一層：
  1) verify-fix 組合：用客觀檢查抓錯、帶回饋重試 → 更準（實測 gemma-12b 67%→83%）。
  2) 簽章 logbook：每次互動 Ed25519 簽章 + hash-chain → 可驗證、可究責。
brain-agnostic（LM Studio / Hermes / 任何 OpenAI 相容端點）。

誠實邊界：accuracy 增益只在「答案可被檢查（verifier 能判對錯）」時成立——
能跑測試/能驗證的任務（code+tests、數學、格式約束…）。不可檢查的主觀任務，
vacant 仍給「可究責」，但不保證更準（規格 §10 oracle 問題）。

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

    def __str__(self) -> str:
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

    @property
    def vacant_id(self) -> str | None:
        return self._identity.vacant_id if self._identity else None

    def _gen(self, prompt: str) -> str:
        # production 硬化：腦呼叫(網路/逾時/畸形)失敗絕不讓 solve 崩 —— 視為一次失敗嘗試，
        # verify-fix 會自然重試或誠實回報未通過。
        try:
            ans = self.brain.generate(prompt)
            if not isinstance(ans, str):
                ans = str(ans)
        except Exception as e:
            ans = f"[brain-error:{type(e).__name__}]"
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
        r = Composer(lambda fb: self._gen(prompt + fb), verifier).vacant(k, on_step=on_step)
        att = self.attest(prompt, r.answer, check_desc=check_desc, verified=r.correct)
        return SolveResult(r.answer, r.correct, r.calls, "vacant-verifyfix",
                           self.verify_chain(), self.brain.name, att)

    # --- 對照：裸單次（沒有 vacant 組合）---------------------------------
    def plain(self, prompt: str, verifier: Verifier) -> SolveResult:
        r = Composer(lambda fb: self._gen(prompt + fb), verifier).plain()
        return SolveResult(r.answer, r.correct, r.calls, "plain",
                           self.verify_chain(), self.brain.name)

    # --- 證明：在你自己的設定上量 plain vs vacant -------------------------
    def bench(self, cases: list[tuple[str, Verifier]], *, k: int | None = None) -> dict:
        """cases: [(prompt, verifier), ...]。回傳 plain vs vacant 的正確率/算力/增益。"""
        k = k or self.k
        plain_hits = vacant_hits = plain_calls = vacant_calls = 0
        rows = []
        for prompt, verifier in cases:
            p = self.plain(prompt, verifier)
            v = self.solve(prompt, verifier, k=k)
            plain_hits += p.verified; vacant_hits += v.verified
            plain_calls += p.calls; vacant_calls += v.calls
            rows.append((prompt[:40], p.verified, v.verified, v.calls))
        n = max(len(cases), 1)
        return {
            "n": n, "brain": self.brain.name, "k": k,
            "plain_acc": plain_hits / n, "vacant_acc": vacant_hits / n,
            "gain": (vacant_hits - plain_hits) / n,
            "plain_calls_per": plain_calls / n, "vacant_calls_per": vacant_calls / n,
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
