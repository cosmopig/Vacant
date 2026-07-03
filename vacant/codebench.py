"""真實、天然可檢查的任務集：code generation —— verify-fix 的經典適用領域。

為什麼是 code：它**自帶客觀 verifier**（跑測試 = 環境真值，不靠 LLM 互批），
正是 vacant 該發光、也是文獻上 self-repair 真的有效的地方。比起 reverse/caesar3
這種玩具 niche，這裡的「差距」對「agent 真的會做的事」更有代表性。

每題：要模型寫一個叫 `solve` 的函式；verifier = 在受限沙箱跑 `tests`（assert 全過才算對）。
verifier 只回 yes/no、不洩正解 → 不洩答案、不循環。
"""

from __future__ import annotations

from typing import Callable

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
