"""真實 code-gen 任務集：每題的 verifier（跑測試）對正解 PASS、對錯解 FAIL（P1）。

這支同時驗證『題庫可解 + 測試字串正確』——若哪題的 test 寫錯，參考解會驗不過而爆出來。
"""

from __future__ import annotations

from vacant.codebench import _PROBLEMS, code_cases

# 每題一個正確參考解（人工確認）。測試要求：參考解通過自己的 verifier。
_REF = {
    "reverse_string": """
def solve(s):
    return s[::-1]
""",
    "is_prime": """
def solve(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True
""",
    "fib": """
def solve(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
""",
    "fizzbuzz": """
def solve(n):
    out = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            out.append('FizzBuzz')
        elif i % 3 == 0:
            out.append('Fizz')
        elif i % 5 == 0:
            out.append('Buzz')
        else:
            out.append(str(i))
    return out
""",
    "two_sum": """
def solve(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        if target - x in seen:
            return [seen[target - x], i]
        seen[x] = i
""",
    "gcd": """
def solve(a, b):
    while b:
        a, b = b, a % b
    return a
""",
    "is_palindrome": """
def solve(s):
    t = [c.lower() for c in s if c.isalnum()]
    return t == t[::-1]
""",
    "roman_to_int": """
def solve(s):
    m = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
    total, prev = 0, 0
    for c in reversed(s):
        v = m[c]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total
""",
    "flatten": """
def solve(lst):
    out = []
    for x in lst:
        if isinstance(x, list):
            out.extend(solve(x))
        else:
            out.append(x)
    return out
""",
    "run_length_encode": """
def solve(s):
    if not s:
        return ''
    out, prev, cnt = [], s[0], 1
    for c in s[1:]:
        if c == prev:
            cnt += 1
        else:
            out.append(prev + str(cnt))
            prev, cnt = c, 1
    out.append(prev + str(cnt))
    return ''.join(out)
""",
    "balanced_brackets": """
def solve(s):
    pairs = {')':'(', ']':'[', '}':'{'}
    st = []
    for c in s:
        if c in '([{':
            st.append(c)
        elif c in ')]}':
            if not st or st.pop() != pairs[c]:
                return False
    return not st
""",
    "merge_sorted": """
def solve(a, b):
    i = j = 0
    out = []
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i]); i += 1
        else:
            out.append(b[j]); j += 1
    out.extend(a[i:]); out.extend(b[j:])
    return out
""",
}


def test_code_cases_shape():
    cases = code_cases(3)
    assert len(cases) == 3
    prompt, verifier = cases[0]
    assert isinstance(prompt, str) and callable(verifier)


def test_every_problem_has_a_passing_reference_and_rejects_garbage():
    cases = code_cases(len(_PROBLEMS))
    for (name, _desc, _test), (_prompt, verifier) in zip(_PROBLEMS, cases):
        ref = _REF[name]
        assert verifier(f"```python\n{ref}\n```"), f"{name}: 參考解竟驗不過（測試字串可能寫錯）"
        assert not verifier("```python\ndef solve(*a, **k):\n    return None\n```"), \
            f"{name}: 空殼解竟通過（verifier 太鬆）"
