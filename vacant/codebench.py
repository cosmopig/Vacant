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
import json
import random
from abc import ABC, abstractmethod
from pathlib import Path
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


# ============================================================================
# G1／P1-1：真 EvalPlus MBPP+ 載入 —— 釘版、驗雜湊、V/GT 分離
# ============================================================================
#
# 資料紀律（17 §P1-1 ＋ 24h-lab backlog P0-evalplus-loader-v1 同規）：
#   - 官方包：EvalPlus MBPP+ v0.2.0（378 題），gzip jsonl，SHA-256 釘死在本檔
#     常數；預設建構**必須**驗證此雜湊，禁止以 None 靜默略過（fail-closed）。
#   - V/GT 分離：public projection 只含 {task_id, family, prompt, entry_point}
#     ＋ visible_check（base inputs）；canonical_solution／plus_input／contract／
#     assertion 是 GT，只進 hidden_check（verifier 側），永不進 prompt——
#     GT 隔離的逐路徑負向測試在 tests/test_x1_evalplus.py。
#   - family 是**規則啟發式標籤**（17 §P1-2「可規則化」），供分族抽樣與
#     教訓檢索；它是表面關鍵詞歸類、不是語意真相，誠實標明。

EVALPLUS_MBPP_PLUS_SHA256 = "af43697e8791c4c149bdfd6b489d8b5412507551ac20e28a439f650b8225db63"
EVALPLUS_MBPP_PLUS_COUNT = 378
EVALPLUS_DEFAULT_PATH = ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"

# 必要欄位與型別（v0.2.0 schema；plus_input 容忍 list／dict 差異——官方包實測
# 有兩種形態，dict 視為「單一位置參數＝該 dict」，見 _norm_inputs）。
_EVALPLUS_SCHEMA = {
    "task_id": str,
    "prompt": str,
    "entry_point": str,
    "canonical_solution": str,
    "base_input": list,
    "plus_input": (list, dict),
}

_FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("empty_input", ("empty", "whitespace", "blank")),
    ("off_by_one", ("index", "first", "last", "kth", "nth", "position")),
    ("boundary", ("max", "min", "largest", "smallest", "edge", "corner")),
    ("duplicate_values", ("duplicate", "unique", "distinct")),
    ("negative_numbers", ("negative", "absolute")),
    ("type_coercion", ("convert", "parse", "string to", "cast")),
)


def _label_family(prompt: str, entry_point: str) -> str:
    """規則啟發式分族（P1-2）：表面關鍵詞比對，命中即用；全不命中＝general。

    誠實邊界：這是抽樣組織標籤，不是「這題真的考什麼坑」的語意判定；
    X1 的遷移判準不建立在標籤正確性上（族內遷移由任務序列實測）。"""
    text = (prompt + " " + entry_point).lower()
    for fam, keys in _FAMILY_RULES:
        if any(k in text for k in keys):
            return fam
    return "general"


def _norm_inputs(raw: Any) -> list[list[Any]]:
    """把一個 input 區塊正規化成 list-of-positional-args 的 list。

    list 形：每個元素本身就是一組位置參數（list of lists）。
    dict 形（官方包實測存在的 schema 差異）：整塊視為一次呼叫的單一位置參數。
    """
    if isinstance(raw, dict):
        return [[raw]]
    out: list[list[Any]] = []
    for case in raw:
        out.append(case if isinstance(case, list) else [case])
    return out


def _check_code(entry_point: str, canonical: str, inputs: list[list[Any]], atol: float | None) -> str:
    """產生 run_python 測試碼：期望值由內嵌 canonical 當場算出（不預算答案進碼）。

    canonical 用 exec 進獨立命名空間，避免與候選的同名 entry_point 互踩。
    atol 給定時浮點（含巢狀 list/tuple）以 ≤atol 判等。"""
    lines = [
        "def __aeq(a, b, atol):",
        "    if atol and (isinstance(a, float) or isinstance(b, float)):",
        "        try:",
        "            return abs(a - b) <= atol",
        "        except TypeError:",
        "            return False",
        "    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):",
        "        return len(a) == len(b) and all(__aeq(x, y, atol) for x, y in zip(a, b))",
        "    return a == b",
        "",
        f"__ns: dict = {{}}",
        f"exec({canonical!r}, __ns)",
        f"__canon = __ns[{entry_point!r}]",
        "",
    ]
    for inp in inputs:
        call = f"{entry_point}(*{inp!r})"
        lines.append(f"assert __aeq({call}, __canon(*{inp!r}), {atol!r})")
    return "\n".join(lines)


class EvalPlusMBPPLoader(TaskLoader):
    """真 EvalPlus MBPP+ v0.2.0 載入（G1／17 §P1-1）。

    建構即 fail-closed 驗證：檔案存在 → sha256 符合釘值 → gzip/jsonl 可解析 →
    恰 expected_count 題 → task_id 唯一 → schema 型別全對。任何一步不符即
    raise，**不產生半殘題庫**（壞資料跑實驗比沒資料更糟）。

    參數：
      path            官方 gzip jsonl（預設 EVALPLUS_DEFAULT_PATH；可用
                      VACANT_EVALPLUS_PATH 環境變數覆寫）。
      expected_sha256 預設＝官方釘值，**不可傳 None 略過**；測試 fixture 必須
                      顯式傳入 fixture 自身的 sha256（這是唯一的合法覆寫）。
      expected_count  預設 378；fixture 同理顯式覆寫。
    """

    def __init__(
        self,
        path: str | None = None,
        *,
        expected_sha256: str | None = None,
        expected_count: int = EVALPLUS_MBPP_PLUS_COUNT,
    ) -> None:
        import os
        self.path = path or os.environ.get("VACANT_EVALPLUS_PATH", EVALPLUS_DEFAULT_PATH)
        if expected_sha256 is None and self.path == EVALPLUS_DEFAULT_PATH:
            expected_sha256 = EVALPLUS_MBPP_PLUS_SHA256
        if expected_sha256 is None:
            raise ValueError(
                "expected_sha256 不可為 None（fail-closed：官方包用預設釘值，"
                "測試 fixture 須顯式傳入其自身 sha256）"
            )
        self.expected_sha256 = expected_sha256
        self.expected_count = expected_count
        self._records = self._load_verified()

    # -- 驗證載入（建構時一次做完）---------------------------------------------
    def _load_verified(self) -> list[dict[str, Any]]:
        import gzip
        p = Path(self.path)
        if not p.exists():
            raise FileNotFoundError(
                f"EvalPlus 官方包不存在：{p}（下載 MBPP+ v0.2.0 並放到 "
                f"{EVALPLUS_DEFAULT_PATH}，或設 VACANT_EVALPLUS_PATH；"
                "無真資料時請用 BuiltinSampleLoader 並如實標注）"
            )
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != self.expected_sha256:
            raise ValueError(
                f"EvalPlus 包 sha256 不符：got {got} want {self.expected_sha256}"
                "（版本飄移或檔案受損，拒收）"
            )
        records: list[dict[str, Any]] = []
        opener = gzip.open if p.suffix == ".gz" else open
        with opener(p, "rt", encoding="utf-8") as f:  # type: ignore[arg-type]
            for ln, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError as e:
                    raise ValueError(f"第 {ln} 行不是合法 JSON：{e}") from e
                self._validate_record(rec, ln)
                records.append(rec)
        if len(records) != self.expected_count:
            raise ValueError(
                f"題數不符：got {len(records)} want {self.expected_count}（非官方 v0.2.0 包？）"
            )
        ids = [r["task_id"] for r in records]
        if len(set(ids)) != len(ids):
            raise ValueError("task_id 有重複（資料污染，拒收）")
        return records

    @staticmethod
    def _validate_record(rec: Any, ln: int) -> None:
        if not isinstance(rec, dict):
            raise ValueError(f"第 {ln} 行不是 JSON object")
        for field_name, types in _EVALPLUS_SCHEMA.items():
            if field_name not in rec:
                raise ValueError(f"第 {ln} 行缺欄位 {field_name}")
            if not isinstance(rec[field_name], types):
                raise ValueError(
                    f"第 {ln} 行欄位 {field_name} 型別錯（want {types}）"
                )

    # -- TaskLoader 介面 ---------------------------------------------------------
    def iter_tasks(self, seed: Any) -> Iterator[dict[str, Any]]:
        """依 seed 決定性排序吐出全部 378 題（sha256(seed:task_id) 排序，可重放）。

        有限池：378 題用完即止（freeze_subset n≤378 適用；要無限變體請用
        BuiltinSampleLoader）。GT 只進 hidden_check；public_view() 是 prompt 側
        唯一合法投影。"""
        ordered = sorted(
            self._records,
            key=lambda r: hashlib.sha256(f"{seed}:{r['task_id']}".encode()).hexdigest(),
        )
        for rec in ordered:
            base = _norm_inputs(rec["base_input"])
            plus = _norm_inputs(rec["plus_input"])
            atol = rec.get("atol")
            atol = float(atol) if isinstance(atol, (int, float)) else None
            yield {
                "task_id": f"mbppplus_{rec['task_id']}",
                "family": _label_family(rec["prompt"], rec["entry_point"]),
                "prompt": rec["prompt"],
                "entry_point": rec["entry_point"],
                "visible_check": {
                    "type": "run_python",
                    "code": _check_code(rec["entry_point"], rec["canonical_solution"], base, atol),
                    "timeout": 8,
                },
                "hidden_check": {
                    "type": "run_python",
                    "code": _check_code(rec["entry_point"], rec["canonical_solution"], base + plus, atol),
                    "timeout": 8,
                },
            }

    @staticmethod
    def public_view(task: dict[str, Any]) -> dict[str, Any]:
        """prompt 側唯一合法投影：task_id／family／prompt／entry_point（無任何 GT）。"""
        return {k: task[k] for k in ("task_id", "family", "prompt", "entry_point")}


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
