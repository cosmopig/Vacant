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


# ============================================================================
# NW-2b：MBPP+ 分族任務載入（{task_id, family, prompt, visible_check, hidden_check}）
# ============================================================================
#
# 與上面舊 code_cases() 的測試同構：一樣驗「好解全過、壞解全 fail」，只是這裡任務
# 是可序列化 dict（visible_check/hidden_check 是 check-spec，要先 compile_check）。
# 額外驗 loader 的關鍵性質：同 seed 可重放、不同 seed 不同題、freeze_subset 的
# n 與 exclude_saturated、以及沙箱逾時不會把整個 test run 卡死。

import time

import pytest

from vacant.checks import compile_check
from vacant.codebench import (
    FAMILIES,
    BuiltinSampleLoader,
    EvalPlusMBPPLoader,
    TaskLoader,
    freeze_subset,
    pilot_tasks,
)

# 每族一個人工確認過的正確參考解（good）。要求：對該族任何變體的 visible_check
# 與 hidden_check 都要通過——因為變體只換測資的具體數值，不換函式簽名/語意。
_FAMILY_REF: dict[str, str] = {
    "boundary": (
        "def solve(nums):\n"
        "    best_i, best_v = 0, nums[0]\n"
        "    for i in range(1, len(nums)):\n"
        "        if nums[i] > best_v:\n"
        "            best_v, best_i = nums[i], i\n"
        "    return best_i\n"
    ),
    "off_by_one": (
        "def solve(n):\n"
        "    total = 0\n"
        "    for i in range(n):\n"
        "        total += 2 * i + 1\n"
        "    return total\n"
    ),
    "empty_input": "def solve(s):\n    return len(s.split())\n",
    "duplicate_values": "def solve(nums):\n    return sorted(set(nums))\n",
    "negative_numbers": "def solve(nums):\n    return sum(abs(x) for x in nums)\n",
    "type_coercion": "def solve(s):\n    return int(s.strip())\n",
}

# 一律通不過任何族 hidden_check 的空殼壞解（缺一個非 None 的正確回傳值）。
_BAD_CODE = "def solve(*a, **k):\n    return None\n"


def _fenced(code: str) -> str:
    return f"```python\n{code}\n```"


def test_task_shape_has_required_keys():
    for task in pilot_tasks(seed="shape", n=12):
        assert set(task) == {"task_id", "family", "prompt", "visible_check", "hidden_check"}
        assert task["family"] in FAMILIES
        assert isinstance(task["task_id"], str) and task["task_id"]
        assert isinstance(task["prompt"], str) and task["prompt"]
        assert task["visible_check"]["type"] == "run_python"
        assert task["hidden_check"]["type"] == "run_python"


def test_pilot_tasks_reproducible_given_same_seed():
    a = pilot_tasks(seed="repro-seed", n=24)
    b = pilot_tasks(seed="repro-seed", n=24)
    assert [t["task_id"] for t in a] == [t["task_id"] for t in b]
    assert [t["prompt"] for t in a] == [t["prompt"] for t in b]


def test_different_seed_gives_different_task_ids():
    a = pilot_tasks(seed="seed-A", n=12)
    b = pilot_tasks(seed="seed-B", n=12)
    assert {t["task_id"] for t in a}.isdisjoint({t["task_id"] for t in b})


def test_families_rotate_round_robin():
    tasks = pilot_tasks(seed="rotate", n=len(FAMILIES) * 2)
    seen = [t["family"] for t in tasks]
    assert seen[: len(FAMILIES)] == list(FAMILIES)
    assert seen[len(FAMILIES):] == list(FAMILIES)


def test_freeze_subset_respects_n_and_is_reproducible():
    a = freeze_subset("frozen-seed", n=40)
    b = freeze_subset("frozen-seed", n=40)
    assert len(a) == 40
    assert [t["task_id"] for t in a] == [t["task_id"] for t in b]


def test_freeze_subset_excludes_by_task_id_and_family():
    pool = freeze_subset("excl-seed", n=30)
    one_id = pool[0]["task_id"]
    without_id = freeze_subset("excl-seed", n=30, exclude_saturated={one_id})
    assert one_id not in {t["task_id"] for t in without_id}

    without_family = freeze_subset("excl-seed", n=30, exclude_saturated={"boundary"})
    assert all(t["family"] != "boundary" for t in without_family)


def test_good_code_passes_visible_and_hidden_for_every_family_multiple_variants():
    """好解全過（>=10 例）：對每族取 6 個變體（6*6=36 例），visible/hidden 都要過。"""
    tasks = pilot_tasks(seed="good-check", n=len(FAMILIES) * 6)
    checked = 0
    for task in tasks:
        good = _fenced(_FAMILY_REF[task["family"]])
        assert compile_check(task["visible_check"])(good), (task["task_id"], "visible")
        assert compile_check(task["hidden_check"])(good), (task["task_id"], "hidden")
        checked += 1
    assert checked >= 10


def test_bad_code_fails_hidden_for_every_family_multiple_variants():
    """壞解全 fail（>=10 例）：空殼解對每族每個變體的 hidden_check 都要 fail。"""
    tasks = pilot_tasks(seed="bad-check", n=len(FAMILIES) * 6)
    checked = 0
    for task in tasks:
        assert not compile_check(task["hidden_check"])(_fenced(_BAD_CODE)), task["task_id"]
        checked += 1
    assert checked >= 10


def test_sandbox_timeout_on_generated_task_does_not_hang():
    """套用到 codebench 產出的真實 check-spec 上：無窮迴圈候選碼逾時要回 False，
    且不能把 pytest 卡住。"""
    task = pilot_tasks(seed="timeout-check", n=1)[0]
    slow_check = dict(task["hidden_check"], timeout=1)
    infinite = _fenced("def solve(*a, **k):\n    while True:\n        pass\n")
    t0 = time.monotonic()
    assert compile_check(slow_check)(infinite) is False
    assert time.monotonic() - t0 < 5


def test_evalplus_loader_fail_closed_without_pack():
    """真 EvalPlus loader 已接上（G1）：官方包缺席＝建構即 fail-closed，
    不能悄悄回假資料（詳盡驗證見 tests/test_evalplus_loader.py）。"""
    with pytest.raises(FileNotFoundError):
        EvalPlusMBPPLoader("/nonexistent/mbppplus.jsonl", expected_sha256="deadbeef")


def test_builtin_loader_is_a_task_loader():
    assert isinstance(BuiltinSampleLoader(), TaskLoader)


def test_task_loader_is_abstract():
    with pytest.raises(TypeError):
        TaskLoader()  # type: ignore[abstract]
