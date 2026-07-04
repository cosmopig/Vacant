"""真實、天然可檢查的任務集：code generation —— verify-fix 的經典適用領域。

為什麼是 code：它**自帶客觀 verifier**（跑測試 = 環境真值，不靠 LLM 互批），
正是 vacant 該發光、也是文獻上 self-repair 真的有效的地方。比起 reverse/caesar3
這種玩具 niche，這裡的「差距」對「agent 真的會做的事」更有代表性。

每題：要模型寫一個叫 `solve` 的函式；verifier = 在受限沙箱跑 `tests`（assert 全過才算對）。
verifier 只回 yes/no、不洩正解 → 不洩答案、不循環。
"""

from __future__ import annotations

import hashlib
import itertools
import random
from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable, Iterator

from .checks import compile_check

Verifier = Callable[[str], bool]

# (name, 需求描述, 測試碼)。測試呼叫模型寫的 solve；assert 全過 → 通過。
_PROBLEMS: list[tuple[str, str, str]] = [
    ("reverse_string",
     "takes a string `s` and returns it reversed. Example: solve('hello') == 'olleh'",
     "assert solve('hello') == 'olleh'\nassert solve('') == ''\nassert solve('a') == 'a'"),

    ("is_prime",
     "takes an int `n` and returns True iff n is prime. Example: solve(17) is True",
     "assert solve(2) is True\nassert solve(1) is False\nassert solve(0) is False\n"
     "assert solve(17) is True\nassert solve(15) is False\nassert solve(97) is True"),

    ("fib",
     "takes an int `n` (n>=0) and returns the nth Fibonacci number, 0-indexed "
     "(solve(0)==0, solve(1)==1). Example: solve(10) == 55",
     "assert solve(0) == 0\nassert solve(1) == 1\nassert solve(10) == 55\nassert solve(20) == 6765"),

    ("fizzbuzz",
     "takes an int `n` and returns a list of strings for 1..n: 'Fizz' if divisible by 3, "
     "'Buzz' if by 5, 'FizzBuzz' if by both, else the number as a string. "
     "Example: solve(5) == ['1','2','Fizz','4','Buzz']",
     "assert solve(5) == ['1','2','Fizz','4','Buzz']\n"
     "assert solve(15)[-1] == 'FizzBuzz'\nassert solve(3) == ['1','2','Fizz']"),

    ("two_sum",
     "takes a list `nums` and an int `target`, returns indices [i, j] (i<j) of two numbers "
     "that add to target. Example: solve([2,7,11,15], 9) == [0,1]",
     "assert solve([2,7,11,15], 9) == [0,1]\nassert solve([3,2,4], 6) == [1,2]\n"
     "assert solve([3,3], 6) == [0,1]"),

    ("gcd",
     "takes two ints `a`, `b` and returns their greatest common divisor. Example: solve(12,8)==4",
     "assert solve(12, 8) == 4\nassert solve(17, 5) == 1\nassert solve(100, 10) == 10\n"
     "assert solve(0, 5) == 5"),

    ("is_palindrome",
     "takes a string `s` and returns True iff it is a palindrome considering only "
     "alphanumeric characters and ignoring case. Example: solve('A man, a plan, a canal: Panama') is True",
     "assert solve('A man, a plan, a canal: Panama') is True\nassert solve('race a car') is False\n"
     "assert solve('') is True\nassert solve('ab_a') is True"),

    ("roman_to_int",
     "takes a Roman numeral string `s` and returns its integer value. Example: solve('MCMXCIV') == 1994",
     "assert solve('III') == 3\nassert solve('IV') == 4\nassert solve('IX') == 9\n"
     "assert solve('LVIII') == 58\nassert solve('MCMXCIV') == 1994"),

    ("flatten",
     "takes an arbitrarily nested list of ints `lst` and returns a flat list of ints, "
     "left to right. Example: solve([1,[2,[3,4]],5]) == [1,2,3,4,5]",
     "assert solve([1,[2,[3,4]],5]) == [1,2,3,4,5]\nassert solve([]) == []\n"
     "assert solve([[[1]]]) == [1]\nassert solve([1,2,3]) == [1,2,3]"),

    ("run_length_encode",
     "takes a string `s` and returns its run-length encoding as char+count, e.g. "
     "solve('aaabbc') == 'a3b2c1'. Empty string returns ''.",
     "assert solve('aaabbc') == 'a3b2c1'\nassert solve('') == ''\nassert solve('abc') == 'a1b1c1'\n"
     "assert solve('aaaa') == 'a4'"),

    ("balanced_brackets",
     "takes a string `s` of brackets among ()[]{} and returns True iff they are balanced "
     "and correctly nested. Example: solve('([]{})') is True, solve('(]') is False",
     "assert solve('([]{})') is True\nassert solve('(]') is False\nassert solve('') is True\n"
     "assert solve('(()') is False\nassert solve('{[()]}') is True"),

    ("merge_sorted",
     "takes two sorted lists `a`, `b` and returns one merged sorted list. "
     "Example: solve([1,3,5],[2,4]) == [1,2,3,4,5]",
     "assert solve([1,3,5],[2,4]) == [1,2,3,4,5]\nassert solve([],[1]) == [1]\n"
     "assert solve([1,2],[]) == [1,2]\nassert solve([1,1],[1]) == [1,1,1]"),
]

_SYSTEM = ("You are a careful Python programmer. Respond with ONLY a single ```python code block "
           "that defines the requested function. No explanation, no tests, no example calls.")


def code_system_prompt() -> str:
    return _SYSTEM


def code_cases(n: int = 12) -> list[tuple[str, Verifier]]:
    """回傳 [(prompt, verifier), ...]；verifier 在受限沙箱跑該題測試。"""
    cases: list[tuple[str, Verifier]] = []
    for i in range(n):
        name, desc, test = _PROBLEMS[i % len(_PROBLEMS)]
        prompt = (f"Write a Python function named `solve` that {desc}. "
                  f"Respond with ONLY a ```python code block defining `solve`.")
        verifier = compile_check({"type": "run_python", "code": test, "timeout": 8})
        cases.append((prompt, verifier))
    return cases


# ============================================================================
# NW-2b：MBPP+ 分族任務載入 —— X1/X3 的正式任務來源（藍圖「沙箱 check ＋ MBPP+ 任務」）
# ============================================================================
#
# 與上面 code_cases() 的差別：上面是 (prompt, verifier callable) 的成對序列，
# 給舊的 Vacant.solve verify-fix demo 用；這裡要的是**可序列化**的任務 spec
# ——{task_id, family, prompt, visible_check, hidden_check}，讓 Auditor（跑
# hidden_check 稽核）與 MemoryManager/X1 runner（依 family 分族取教訓）能共用
# 同一份題庫，且整份任務可以被凍結（freeze_subset）、重放（seed 決定性）。
#
#   visible_check ＝ 題述基礎測資（＝形式化需求 V，等同 MBPP 原生 base tests）；
#   hidden_check  ＝ EvalPlus 擴增隱藏測資（＝評分/稽核用的 GT，不進 prompt，
#                    系統跑中看不到——不然稽核就沒意義了）。
#
# TODO(NW-2 換真資料)：目前環境無法連網下載 EvalPlus 官方 MBPP+ 資料集
# （見 15 號執行手冊）。這裡先把 loader 介面（TaskLoader）與 family／
# freeze_subset 的形狀做出來、跑通，並用一組手刻範例題（BuiltinSampleLoader）
# 頂著——之後接上真資料只需新寫一顆 TaskLoader（見 EvalPlusMBPPLoader 樁），
# freeze_subset/pilot_tasks 呼叫端完全不用改。

_ALPHA = "abcdefghijklmnopqrstuvwxyz"


def _rand_word(rng: random.Random, length: int = 4) -> str:
    """決定性隨機小寫字串（給 empty_input 族造「正常句子」用）。"""
    return "".join(rng.choice(_ALPHA) for _ in range(length))


def _lines(cases: list[tuple[str, Any]]) -> str:
    """[(呼叫表達式, 期望值), ...] → 逐行 assert 字串（期望值用 repr 內嵌，避免跑期引用未定義名）。"""
    return "\n".join(f"assert {call} == {expected!r}" for call, expected in cases)


# --- 六個坑型分族：每族一個 reference solver + 一個「造題」函式 ----------------
# 造題函式吃 (rng, idx)，回傳 (prompt, visible_tests, hidden_tests)：
#   visible_tests 只含「正常情況」一例（對應題述給的可見例）；
#   hidden_tests  = visible_tests ＋ 該族坑型專屬的邊界/例外情況（EvalPlus 擴增測資的精神）。
# rng 決定性（由 seed:family:idx 播種），同 seed 同 idx 永遠造出同一題。


def _ref_first_max_index(nums: list[int]) -> int:
    best_i, best_v = 0, nums[0]
    for i in range(1, len(nums)):
        if nums[i] > best_v:
            best_v, best_i = nums[i], i
    return best_i


def _family_boundary(rng: random.Random, idx: int) -> tuple[str, str, str]:
    nums = [rng.randint(1, 99) for _ in range(rng.randint(4, 7))]
    visible = _lines([(f"solve({nums!r})", _ref_first_max_index(nums))])
    hidden_extra = _lines([
        ("solve([7])", _ref_first_max_index([7])),                    # 單元素：邊界迴圈不執行
        ("solve([1, 2, 3, 9])", _ref_first_max_index([1, 2, 3, 9])),  # 最大值在最後一個 index
        ("solve([5, 5, 5])", _ref_first_max_index([5, 5, 5])),        # 全相等 → 回第一個
        ("solve([-3, -1, -7])", _ref_first_max_index([-3, -1, -7])),  # 負數
    ])
    prompt = (
        "寫一個 Python 函式 `solve(nums)`：nums 是非空整數 list，回傳「最大值第一次"
        "出現」的索引（0-index）。若有多個相同最大值，回傳最前面那個。"
    )
    return prompt, visible, f"{visible}\n{hidden_extra}"


def _ref_sum_first_odds(n: int) -> int:
    total = 0
    for i in range(n):
        total += 2 * i + 1
    return total


def _family_off_by_one(rng: random.Random, idx: int) -> tuple[str, str, str]:
    n = rng.randint(3, 9)
    visible = _lines([(f"solve({n})", _ref_sum_first_odds(n))])
    hidden_extra = _lines([
        ("solve(0)", _ref_sum_first_odds(0)),          # 圍籬柱：n=0 不能少算/多算
        ("solve(1)", _ref_sum_first_odds(1)),
        (f"solve({n + 1})", _ref_sum_first_odds(n + 1)),
    ])
    prompt = (
        "寫一個 Python 函式 `solve(n)`：n 是非負整數，回傳前 n 個正奇數的總和"
        "（1+3+5+...）。n=0 回傳 0。"
    )
    return prompt, visible, f"{visible}\n{hidden_extra}"


def _family_empty_input(rng: random.Random, idx: int) -> tuple[str, str, str]:
    words = [_rand_word(rng) for _ in range(rng.randint(2, 5))]
    sentence = " ".join(words)
    visible = _lines([(f"solve({sentence!r})", len(words))])
    hidden_extra = _lines([
        ("solve('')", 0),               # 空字串
        ("solve('   ')", 0),            # 純空白
        ("solve('  a  b  ')", 2),       # 頭尾/連續空白
    ])
    prompt = "寫一個 Python 函式 `solve(s)`：s 是字串，回傳以空白分隔的詞數。"
    return prompt, visible, f"{visible}\n{hidden_extra}"


def _family_duplicate_values(rng: random.Random, idx: int) -> tuple[str, str, str]:
    nums = [rng.randint(-5, 5) for _ in range(rng.randint(4, 7))]
    visible = _lines([(f"solve({nums!r})", sorted(set(nums)))])
    hidden_extra = _lines([
        ("solve([])", []),                          # 空 list
        ("solve([5, 5, 5])", [5]),                   # 全重複
        ("solve([-2, -2, 3, 3])", [-2, 3]),          # 負數＋重複
    ])
    prompt = (
        "寫一個 Python 函式 `solve(nums)`：nums 是整數 list，回傳去重後由小到大"
        "排序的 list。"
    )
    return prompt, visible, f"{visible}\n{hidden_extra}"


def _family_negative_numbers(rng: random.Random, idx: int) -> tuple[str, str, str]:
    nums = [rng.randint(-9, 9) for _ in range(rng.randint(3, 6))]
    visible = _lines([(f"solve({nums!r})", sum(abs(x) for x in nums))])
    hidden_extra = _lines([
        ("solve([])", 0),                    # 空 list
        ("solve([-1, -2, -3])", 6),           # 全負數
        ("solve([0, 0, 0])", 0),              # 全零
    ])
    prompt = "寫一個 Python 函式 `solve(nums)`：nums 是整數 list，回傳所有元素絕對值的總和。"
    return prompt, visible, f"{visible}\n{hidden_extra}"


def _family_type_coercion(rng: random.Random, idx: int) -> tuple[str, str, str]:
    n = rng.randint(1, 999)
    visible = _lines([(f"solve({str(n)!r})", n)])
    hidden_extra = _lines([
        ("solve('  42 ')", 42),   # 前後空白
        ("solve('007')", 7),      # 前導 0
        ("solve('-5')", -5),      # 負號
        ("solve('+3')", 3),       # 正號
    ])
    prompt = (
        "寫一個 Python 函式 `solve(s)`：s 是代表整數的字串（可能有前後空白、前導 0、"
        "或 +/- 號），回傳對應的 int。"
    )
    return prompt, visible, f"{visible}\n{hidden_extra}"


_FAMILY_BUILDERS: dict[str, Any] = {
    "boundary": _family_boundary,
    "off_by_one": _family_off_by_one,
    "empty_input": _family_empty_input,
    "duplicate_values": _family_duplicate_values,
    "negative_numbers": _family_negative_numbers,
    "type_coercion": _family_type_coercion,
}

FAMILIES: tuple[str, ...] = tuple(_FAMILY_BUILDERS)


def _mk_task(
    seed: Any, family: str, idx: int, prompt: str, visible_tests: str, hidden_tests: str,
    *, timeout: float = 8,
) -> dict[str, Any]:
    task_id = hashlib.sha256(f"codebench:{seed}:{family}:{idx}".encode()).hexdigest()[:16]
    return {
        "task_id": task_id,
        "family": family,
        "prompt": prompt,
        "visible_check": {"type": "run_python", "code": visible_tests, "timeout": timeout},
        "hidden_check": {"type": "run_python", "code": hidden_tests, "timeout": timeout},
    }


def _iter_pool(seed: Any) -> Iterator[dict[str, Any]]:
    """依 seed 決定性、無限地吐出任務（族間輪替、族內變體遞增）。

    同 seed 永遠同序列——freeze_subset/pilot_tasks 可重放；重跑實驗、斷點續跑
    (16 手冊) 都靠這個性質。"""
    counters = {fam: 0 for fam in FAMILIES}
    while True:
        for fam in FAMILIES:
            idx = counters[fam]
            counters[fam] += 1
            rng = random.Random(f"{seed}:{fam}:{idx}")
            prompt, visible, hidden = _FAMILY_BUILDERS[fam](rng, idx)
            yield _mk_task(seed, fam, idx, prompt, visible, hidden)


class TaskLoader(ABC):
    """任務池來源的介面。freeze_subset/pilot_tasks 只依賴這個抽象，換真 EvalPlus
    資料時只需新寫一顆 TaskLoader，呼叫端（含 Auditor／X1 runner）不用動。"""

    @abstractmethod
    def iter_tasks(self, seed: Any) -> Iterator[dict[str, Any]]:
        """依 seed 決定性、無限地吐出 {task_id, family, prompt, visible_check,
        hidden_check}；同 seed 必須同序列（可重放，見 _iter_pool docstring）。"""
        raise NotImplementedError


class BuiltinSampleLoader(TaskLoader):
    """內建範例題（TODO(NW-2) 換真資料，見本節最上方說明）。

    六個坑型分族、族內用 seed 決定性造出不重複變體，足以撐起 freeze_subset 的
    n 需求——但誠實說明：這是「同一顆 reference solver 配不同隨機測資」的變體，
    不是真的 215 道不同 MBPP 題目，只用來讓 loader 介面／family 分族／
    freeze_subset 的形狀可 import、可測、可重放；正式 X1 跑分前必須換成真
    EvalPlus 資料（見 EvalPlusMBPPLoader）。
    """

    def iter_tasks(self, seed: Any) -> Iterator[dict[str, Any]]:
        yield from _iter_pool(seed)


class EvalPlusMBPPLoader(TaskLoader):
    """TODO(NW-2)：真 EvalPlus MBPP+ 資料載入（尚未實作——目前環境無法連網下載）。

    預期流程（换資料時照著填）：
      1) 離線下載 evalplus 釋出的 MBPPPlus 資料集（jsonl），釘住版本號；
      2) 用 sha256 驗證檔案完整性（比對 expected_sha256，資料被竄改/版本飄移即拒收）；
      3) 逐題轉成 {task_id, family, prompt, visible_check, hidden_check}——
         family 依題目性質分類（邊界/off-by-one/空輸入…，可規則化或人工標）；
         visible_check 用題目自帶的 base tests，hidden_check 用 plus 擴增 tests。

    目前 iter_tasks() 只丟 NotImplementedError，避免有人誤以為這裡已經接了真
    資料（沙箱/family/freeze_subset 的正確性用 BuiltinSampleLoader 測，換資料
    後行為不變——這是本樁存在的意義）。
    """

    def __init__(self, path: str, *, expected_sha256: str | None = None) -> None:
        self.path = path
        self.expected_sha256 = expected_sha256

    def iter_tasks(self, seed: Any) -> Iterator[dict[str, Any]]:  # pragma: no cover - 無真資料可測
        raise NotImplementedError(
            "EvalPlusMBPPLoader 尚未接上真資料（見 class docstring 的換資料流程）；"
            "目前請用 BuiltinSampleLoader（freeze_subset/pilot_tasks 預設值）。"
        )


def pilot_tasks(seed: Any = "pilot", n: int = 12, *, loader: TaskLoader | None = None) -> list[dict[str, Any]]:
    """pilot 用：不要求 n>=215，快速取一批任務（各族輪流出現）。"""
    loader = loader or BuiltinSampleLoader()
    return list(itertools.islice(loader.iter_tasks(seed), n))


def freeze_subset(
    seed: Any, n: int = 215, *, exclude_saturated: Iterable[str] = (), loader: TaskLoader | None = None,
) -> list[dict[str, Any]]:
    """凍結正式子集：seed 決定性 → 可重放；n 依研究設計建議 >=215（見藍圖 NW-5
    power 計算，T>=215 @ +8pp 才有足夠檢定力）。exclude_saturated 排除 pilot
    後發現的「天花板題」（各臂都通過、沒有鑑別力）——可傳 task_id 或整個 family
    名稱（family 命中即整族排除）。

    本函式刻意不對 n 做 hard 下限檢查：正式跑的 n>=215 是呼叫端（X1 runner）的
    紀律，pilot／單元測試需要能用小 n 快速跑通，不該被這裡擋。
    """
    loader = loader or BuiltinSampleLoader()
    excluded = set(exclude_saturated)
    out: list[dict[str, Any]] = []
    for task in loader.iter_tasks(seed):
        if task["task_id"] in excluded or task["family"] in excluded:
            continue
        out.append(task)
        if len(out) >= n:
            break
    return out
