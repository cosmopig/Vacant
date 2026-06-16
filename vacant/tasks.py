"""可檢查任務套件 — 便宜、客觀、非循環的真值錨。架構總規格 §8 / §11。

「可檢查」= 有 check() 能用環境真值判對錯，不必靠互批（避開 oracle 循環）。
這正是 AutoHarness 與 verifier 適用的 scope（誠實邊界 §10：模糊任務才回互批）。

每個 niche 是一族確定性題目；solve() 是正解（環境真值），check() 判對錯。
固定 seed → 可重現（§11）。
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable

# --- niche 正解（環境真值）---------------------------------------------------
def _reverse(s: str) -> str:
    return s[::-1]


def _caesar3(s: str) -> str:
    out = []
    for ch in s:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + 3) % 26 + 97))
        else:
            out.append(ch)
    return "".join(out)


def _sort_chars(s: str) -> str:
    return "".join(sorted(s))


def _sum_digits(s: str) -> str:
    return str(sum(int(c) for c in s if c.isdigit()))


def _vowel_count(s: str) -> str:
    return str(sum(1 for c in s if c in "aeiou"))


_NICHES: dict[str, Callable[[str], str]] = {
    "reverse": _reverse,
    "caesar3": _caesar3,
    "sort_chars": _sort_chars,
    "sum_digits": _sum_digits,
    "vowel_count": _vowel_count,
}

NICHES = tuple(_NICHES.keys())

# 公開的 niche→正解 解算器表。substrate 用它「真的算」（不靠把答案塞進信封），
# 確保 Envelope body 永遠可序列化（無 callable 上線）。
NICHE_SOLVERS = dict(_NICHES)


def _seeded_word(seed: str, length: int = 6) -> str:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(alphabet[int(h[i : i + 2], 16) % len(alphabet)] for i in range(0, length * 2, 2))


def make_task(seq: int, niche: str | None = None, *, seed: str = "vacant") -> dict[str, Any]:
    """造一個可重現的任務。niche=None → 由 seq 輪替挑 niche。"""
    if niche is None:
        niche = NICHES[seq % len(NICHES)]
    solve = _NICHES[niche]
    inp = _seeded_word(f"{seed}:{niche}:{seq}")
    expected = solve(inp)
    task_id = hashlib.sha256(f"{seed}:{niche}:{seq}".encode()).hexdigest()[:12]

    def check(answer: str, _expected: str = expected) -> bool:
        return str(answer) == _expected

    return {
        "task_id": task_id,
        "niche": niche,
        "input": inp,
        "expected": expected,
        "solve": solve,
        "check": check,
        "prompt": f"[{niche}] {inp}",
    }


def task_stream(n: int, *, seed: str = "vacant") -> list[dict[str, Any]]:
    """造 n 個輪替 niche 的任務串（可重現）。"""
    return [make_task(i, seed=seed) for i in range(n)]
