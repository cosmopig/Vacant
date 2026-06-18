"""組合執行器 Composer（架構規格 §9）—— 讓 vacant 在「同一顆腦」上比單次更好。

機制（共識定案 §2）：能力來自組合，組合衝破單次天花板：
  - 互查迴圈 generate → verify → fix（「模型檢查比生成強」）
  - 取最好 best-of-N
trust 層提供三樣關鍵：路由到有履歷的專家、**客觀 verifier**（可檢查任務的非循環
真值，只回 yes/no、不洩答案）、簽章記帳。

誠實邊界：
  - verifier 的「便宜客觀真值」只在**可檢查任務**成立；不可檢查任務退回 peer review
    （oracle 問題，規格 §10）。
  - 公平比較必須**等算力**（規格 §5）：plain×1 / naive×K（自一致多數決，無驗證）/
    vacant×K（verify-fix）。若 vacant×K > naive×K，增益歸功於「驗證結構」而非「呼叫更多次」。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable


@dataclass
class ComposeResult:
    answer: str
    correct: bool
    calls: int        # 實際用掉的腦呼叫次數
    strategy: str


class Composer:
    """brain-agnostic：generate 呼叫腦（經 vacant gateway→已路由/簽章），check 是客觀 verifier。

    generate(feedback: str) -> str
        以 base prompt + feedback 呼叫腦，回原始答案字串。
    check(answer: str) -> bool
        客觀判對錯（可檢查任務：環境真值；只回 yes/no，不把答案餵回模型）。
    """

    def __init__(self, generate: Callable[[str], str], check: Callable[[str], bool]) -> None:
        self._generate = generate
        self._check = check

    # --- C0：裸單次（無 vacant 組合）------------------------------------
    def plain(self) -> ComposeResult:
        a = self._generate("")
        return ComposeResult(a, self._check(a), 1, "plain")

    # --- C1：等算力 naive（K 次取多數決＝自一致，無驗證）----------------
    def naive(self, k: int) -> ComposeResult:
        ans = [self._generate("") for _ in range(k)]
        a = Counter(ans).most_common(1)[0][0]
        return ComposeResult(a, self._check(a), k, "naive-majority")

    # --- C3：vacant verify-fix（互查迴圈：錯了就帶回饋重試，驗證過即收）--
    def vacant(self, k: int) -> ComposeResult:
        tried: list[str] = []
        for i in range(k):
            if not tried:
                fb = ""
            else:
                # 只告知「先前答案是錯的」+ 列出已試過的（避免重複），不洩漏正解。
                shown = ", ".join(repr(t) for t in tried[-3:])
                fb = (f" Your previous answer(s) {shown} were WRONG. "
                      f"Reconsider carefully and give a DIFFERENT, correct answer.")
            a = self._generate(fb)
            if self._check(a):
                return ComposeResult(a, True, i + 1, "vacant-verifyfix")
            tried.append(a)
        return ComposeResult(tried[-1], False, k, "vacant-verifyfix")

    # --- best-of-N（取最好；驗證當篩選器，非解題）-----------------------
    def best_of_n(self, n: int) -> ComposeResult:
        tried: list[str] = []
        for i in range(n):
            a = self._generate("" if not tried else " Give a different answer than before.")
            if self._check(a):
                return ComposeResult(a, True, i + 1, "vacant-best-of-n")
            tried.append(a)
        return ComposeResult(tried[-1], False, n, "vacant-best-of-n")
