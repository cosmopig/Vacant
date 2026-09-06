"""suitespec — 驗收套件是**資料**不是程式：`SuiteSpec` ＋ 可信渲染器。

這支在架構裡承重什麼
====================
R451（`DECISION_20260906_R451_FABLE_AUDIT_SUITE_GAUGE.md`）§三 推翻了 R449 §四-3
的部分解：把「壞解被擋」綁進 `commit_suite` 之後，攻擊者仍造得出**通過量具卻交
垃圾**的套件（`stateful`：量具那一發乖、出貨那幾發把判準倒過來）。裁決寫得很精確：

    **量具量的是一次執行，不是一件工件。**

只要驗收碼是**任意 Python** 且跑在 runner 行程裡（`vacant/checks.py` 的 AST
allowlist 只約束**候選碼**），它就能分辨「現在是量具在看」與「現在是出貨」，
有限次測試對它沒有任何約束力。加樁、換樁、比對失敗細節、堵住讀原始碼的管道，
四條都被逐條驗過無效。

R451 §四 的修法（本模組）：**套件不再是程式。**

    SuiteSpec = {v, dialect, entry_point, tests=[{args, expected}], cmp}

供應者交出來的是**一串字面值**；執行器拿 spec 去跑**自己的**渲染器
（`render`），永遠不執行供應者寫的 Python。於是 R451 的三種攻擊
（stateful／targeted 雜湊黑名單／mimic）在這個形態裡**不可表達**——
不是「被擋下來」，是**寫不出來**：validator 只收 `ast.literal_eval` 過得了的
字面值，`import`／呼叫／屬性存取／lambda／comprehension／f-string 一律拒絕，
而渲染器產生的碼裡沒有任何地方讓供應者的字串變成可執行的東西。

剩下**還能表達**的攻擊只有兩類，兩類都在 R452 量過：
  1. **覆蓋不足**——少給幾條測資、挑容易的輸入（`tests` 是供應者給的）。
  2. **比對旗標放寬**——`cmp.atol` 開大、`set_equivalent`／`regex_predicate`
     亂開（只有 mbpp 方言有旗標）。
兩類都還是要先過量具（參考解通過、每個已知壞樁被擋），量到的殘餘見
`ops/gain/replay/peer_exec_suitespec_gate.json`。

紅線與誠實邊界（改碼不得刪）
----------------------------
1. **V/GT 分離沒有破。** 本模組一處都沒有出現 `hidden_check`。`from_task` 的
   `expected` 是拿**參考解**（驗證者側物件，與 `suitegauge` 的量具素材同一類）
   在子行程裡算出來的，不是任何 worker 的產出、不進任何 prompt。
2. **「期望輸出錯」不是攻擊，是需求本身。** 客戶說 2+2=5，系統就該交 5。
   有參考解時量具會抓到（參考解過不了自己的套件），沒有時本來就無從分辨。
   這條寫在這裡，是因為「spec 把期望值寫死」看起來像是新的攻擊面，它不是——
   它把**原本就存在**的那個信任（需求的定義權）從一段可執行的碼搬到一張清單上，
   而清單是人看得懂、可 diff、可重算的。
3. **渲染器是被信任的輸入。** 執行器跑的是自己那份 `render`；`vacant/checks.py`
   沙箱有缺陷的話 k 台機器會一致地錯（peerexec 誠實邊界 §3 的同一條）。本模組
   把信任從「供應者的碼」搬到「大家共用的渲染器」，**不是消滅信任**。
4. **兩個題庫的比較語意不同，所以有 `dialect`。** MBPP+ 的 `__aeq(a, b, atol)`
   有 set/regex 旗標與 atol；LCB 的 `__aeq(a, b)` 是寫死的（數值 1e-6 容差＋
   bool 守衛）、沒有旗標。硬要統一就會偷偷改掉其中一邊的判準，所以照實分兩種
   方言，各自渲染出**與 loader 逐位元組相同**的前置（防呆：
   `tests/test_suitespec.py::test_preludes_are_byte_identical_to_the_loaders`）。
   代價寫清楚：`cmp` 三個欄位對 lcb 方言是**惰性**的，必須是未使用值，
   所以「旗標放寬」這一類攻擊在 lcb 上不可表達（不是被擋，是沒有那個旋鈕）。
"""

from __future__ import annotations

import ast
import hashlib
import keyword
import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .canonical import canonical_bytes

SPEC_VERSION = 1
DIALECTS = ("mbpp", "lcb")

#: 尺寸上限。字面值是資料，資料要有界——沒有界的話「一份 spec」可以是一顆
#: 記憶體炸彈，而拒絕服務也是一種交不出貨。
MAX_TESTS = 2000
MAX_LITERAL_CHARS = 200_000
MAX_SPEC_BYTES = 4 * 1024 * 1024
MAX_DEPTH = 40

#: 渲染器會用掉的名字。entry_point 撞到任何一個都會讓渲染出來的碼語意改變，
#: 所以在 validator 就拒絕，不留給沙箱去發現。
RESERVED_NAMES = frozenset({
    "__aeq", "__vacant_re", "__vacant_regex_predicate", "__vacant_set_equivalent",
    "__ns", "__canon", "__tests", "__t", "__got", "_worker", "_vacant_call",
})


class SuiteSpecError(ValueError):
    """spec 不合格 ⇒ **拒絕**，不修正、不猜測。

    刻意用例外而不是回傳 None：一個安靜回 None 的 validator 會讓呼叫端在
    `if spec:` 之外的路徑上繼續渲染，而那正是 fail-open。
    """


# ── 字面值：解析、型別走訪、正規重寫 ────────────────────────────────────────
_ATOMS = (type(None), bool, int, float, complex, str, bytes)


def _check_finite(value: float | complex) -> None:
    if isinstance(value, complex):
        if not (math.isfinite(value.real) and math.isfinite(value.imag)):
            raise SuiteSpecError("nan_or_inf_not_encodable")
        return
    if not math.isfinite(value):
        # `1e999` 是**合法的**字面值卻 parse 成 inf，`float('nan')` 則根本不是
        # 字面值。兩條路都要堵：spec 是要上鏈的資料，而 nan != nan 會讓
        # 「同一份 spec 算出同一個判準」這句話不成立。
        raise SuiteSpecError("nan_or_inf_not_encodable")


def _walk(value: Any, depth: int = 0) -> None:
    """只准出現字面值型別；順便擋掉過深的巢狀（渲染／解析都會遞迴）。"""
    if depth > MAX_DEPTH:
        raise SuiteSpecError("literal_too_deep")
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, str, bytes)):
        return
    if isinstance(value, (float, complex)):
        _check_finite(value)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _walk(item, depth + 1)
        return
    if isinstance(value, set):
        if not value:
            raise SuiteSpecError("empty_set_not_encodable")
        for item in value:
            _walk(item, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _walk(key, depth + 1)
            _walk(item, depth + 1)
        return
    raise SuiteSpecError(f"not_a_literal_type:{type(value).__name__}")


def emit_literal(value: Any, depth: int = 0) -> str:
    """把一個**已驗過**的值寫成確定性的字面值字串。

    為什麼不直接用 `repr`：`repr(set)` 的元素順序跟著 `PYTHONHASHSEED` 走，
    同一份 spec 在兩台機器上會算出不同的 `suite_sha256`——那會讓「第三方可重算」
    這句話直接失效。集合一律照 emit 後的字串排序。dict 保留插入順序（順序來自
    來源字面值，本身是確定性的），不排序，因為混型鍵排不動。
    """
    if depth > MAX_DEPTH:
        raise SuiteSpecError("literal_too_deep")
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, (int, str, bytes)):
        return repr(value)
    if isinstance(value, (float, complex)):
        _check_finite(value)
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(emit_literal(v, depth + 1) for v in value) + "]"
    if isinstance(value, tuple):
        body = ", ".join(emit_literal(v, depth + 1) for v in value)
        return "(" + body + ("," if len(value) == 1 else "") + ")"
    if isinstance(value, set):
        if not value:
            raise SuiteSpecError("empty_set_not_encodable")
        return "{" + ", ".join(sorted(emit_literal(v, depth + 1) for v in value)) + "}"
    if isinstance(value, dict):
        return "{" + ", ".join(
            f"{emit_literal(k, depth + 1)}: {emit_literal(v, depth + 1)}"
            for k, v in value.items()) + "}"
    raise SuiteSpecError(f"not_a_literal_type:{type(value).__name__}")


def parse_literal(text: Any) -> Any:
    """`ast.literal_eval` ＋ 型別走訪。名稱／呼叫／屬性／lambda／推導式全部在這裡死。

    `literal_eval` 自己就會拒絕 Name／Call／Attribute／Lambda／ListComp／
    JoinedStr（f-string）；型別走訪是第二道，擋掉 `1e999`（合法字面值、parse 成
    inf）這種 literal_eval 放行的東西。
    """
    if not isinstance(text, str):
        raise SuiteSpecError(f"literal_must_be_str:{type(text).__name__}")
    if len(text) > MAX_LITERAL_CHARS:
        raise SuiteSpecError("literal_too_long")
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError) as exc:
        raise SuiteSpecError(f"not_a_literal:{type(exc).__name__}") from exc
    _walk(value)
    return value


def canonical_literal(text: Any) -> str:
    """解析 → 重寫。**上鏈的位元組是重寫過的**，不是作者排版過的。

    這條是「資料而不是程式」的一半：同一個值只有一種寫法，所以
    `suite_sha256` 認的是**值**，不是空白與引號的風格。
    """
    return emit_literal(parse_literal(text))


# ── 前置（與 loader 逐位元組相同；漂移防呆在 tests/test_suitespec.py）────────
#: ⚠ 這兩段必須與 `vacant/codebench.py::_check_code` / `_lcb_check_code` 產生的
#:   前置**逐位元組相同**。不共用一份實作是刻意的：`codebench` 是題庫載入器，
#:   `suitespec` 是機制層，機制層不能為了省一段字串就把題庫變成相依。防呆是
#:   `tests/test_suitespec.py::test_preludes_are_byte_identical_to_the_loaders`
#:   ——它拿 loader 真的產生一份出來逐位元組比。
_MBPP_AEQ = (
    "def __aeq(a, b, atol):\n"
    "    if __vacant_set_equivalent:\n"
    "        try:\n"
    "            return set(a) == set(b)\n"
    "        except TypeError:\n"
    "            return False\n"
    "    if __vacant_regex_predicate:\n"
    "        allowed = (bool, type(None), __vacant_re.Match)\n"
    "        if isinstance(a, allowed) and isinstance(b, allowed):\n"
    "            return bool(a) == bool(b)\n"
    "    try:\n"
    "        if a == b:\n"
    "            return True\n"
    "    except (TypeError, ValueError):\n"
    "        pass\n"
    "    if atol and (isinstance(a, float) or isinstance(b, float)):\n"
    "        try:\n"
    "            return abs(a - b) <= atol\n"
    "        except TypeError:\n"
    "            return False\n"
    "    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):\n"
    "        return len(a) == len(b) and all(__aeq(x, y, atol) for x, y in zip(a, b))\n"
    "    return a == b\n"
)

_LCB_AEQ = (
    "def __aeq(a, b):\n"
    "    try:\n"
    "        if a == b:\n"
    "            return True\n"
    "    except (TypeError, ValueError):\n"
    "        pass\n"
    "    if isinstance(a, bool) != isinstance(b, bool):\n"
    "        return False\n"
    "    if isinstance(a, (int, float)) and isinstance(b, (int, float)):\n"
    "        return abs(a - b) <= 1e-6\n"
    "    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):\n"
    "        return len(a) == len(b) and all(__aeq(x, y) for x, y in zip(a, b))\n"
    "    return a == b\n"
)


def mbpp_prelude(regex_predicate: bool, set_equivalent: bool) -> str:
    return (
        "import re as __vacant_re\n"
        f"__vacant_regex_predicate = {bool(regex_predicate)!r}\n"
        f"__vacant_set_equivalent = {bool(set_equivalent)!r}\n"
        + _MBPP_AEQ + "\n"
    )


def lcb_prelude() -> str:
    return _LCB_AEQ + "\n"


# ── SuiteSpec ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SuiteTest:
    """一條測資 ＝ 一組位置引數 ＋ 一個期望值，兩個都是**正規化後**的字面值字串。"""

    args: str
    expected: str

    def to_json(self) -> dict[str, str]:
        return {"args": self.args, "expected": self.expected}


@dataclass(frozen=True)
class SuiteSpec:
    """驗收套件的**資料**形態。`suite_sha256` 算在這份資料上，不是算在渲染出來的碼上。

    為什麼 hash 算在資料上：渲染器可以升級（例如修一個 `__aeq` 的 bug），而
    「客戶承諾的是哪一份驗收」不該因為渲染器換版就改變。收據上兩個都留：
    `suite_sha256`（資料）與 `render_sha256`（這一次實際跑了什麼碼）。
    """

    entry_point: str
    tests: tuple[SuiteTest, ...]
    dialect: str = "mbpp"
    atol: float | None = None
    set_equivalent: bool = False
    regex_predicate: bool = False

    # -- 序列化 ------------------------------------------------------------
    def to_json(self) -> dict[str, Any]:
        return {
            "v": SPEC_VERSION,
            "dialect": self.dialect,
            "entry_point": self.entry_point,
            "tests": [t.to_json() for t in self.tests],
            "cmp": {
                "atol": self.atol,
                "set_equivalent": bool(self.set_equivalent),
                "regex_predicate": bool(self.regex_predicate),
            },
        }

    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self.to_json())

    @property
    def suite_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @property
    def n_tests(self) -> int:
        return len(self.tests)

    # -- 渲染 --------------------------------------------------------------
    def render(self) -> str:
        return render(self)

    @property
    def render_sha256(self) -> str:
        return hashlib.sha256(self.render().encode("utf-8")).hexdigest()


def validate(obj: Any) -> SuiteSpec:
    """把任意輸入變成一份可用的 `SuiteSpec`，或丟 `SuiteSpecError`。

    fail-closed，缺一不可（每一條都對應一個 `tests/test_suitespec.py` 的測試）：
      - `v` 是本版
      - `dialect` 在白名單裡
      - `entry_point` 是識別字、不是關鍵字、不撞渲染器用掉的名字、不以 `__` 開頭
      - `tests` 至少 **1** 條（0 條＝什麼都不驗＝R449 §三-3 那一格，直接拒絕；
        量具那一層也會擋，但這裡先擋，因為 0 條連跑都不必跑）
      - 每條 `args` 是**列表或元組**字面值（位置引數），`expected` 是任意字面值
      - lcb 方言的 `cmp` 三欄必須是未使用值（那個方言的比較器寫死在前置裡）
      - 全部字面值重寫過（**上鏈的是重寫後的位元組**）
      - canonical bytes 不超過上限
    """
    if isinstance(obj, SuiteSpec):
        obj = obj.to_json()
    if isinstance(obj, (bytes, bytearray)):
        import json  # noqa: PLC0415
        try:
            obj = json.loads(bytes(obj).decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise SuiteSpecError(f"not_canonical_json:{type(exc).__name__}") from exc
    if isinstance(obj, str):
        # 這就是被拆掉的那道門：一段驗收 Python 原始碼從這裡進不來。
        raise SuiteSpecError("raw_code_suite_not_accepted")
    if not isinstance(obj, Mapping):
        raise SuiteSpecError(f"spec_must_be_mapping:{type(obj).__name__}")
    if obj.get("v") != SPEC_VERSION:
        raise SuiteSpecError(f"bad_version:{obj.get('v')!r}")
    dialect = obj.get("dialect", "mbpp")
    if dialect not in DIALECTS:
        raise SuiteSpecError(f"unknown_dialect:{dialect!r}")

    ep = obj.get("entry_point")
    if not isinstance(ep, str) or not ep.isidentifier():
        raise SuiteSpecError("entry_point_not_identifier")
    if keyword.iskeyword(ep) or ep.startswith("__") or ep in RESERVED_NAMES:
        raise SuiteSpecError("entry_point_reserved")

    raw_tests = obj.get("tests")
    if not isinstance(raw_tests, Sequence) or isinstance(raw_tests, (str, bytes)):
        raise SuiteSpecError("tests_must_be_list")
    if not raw_tests:
        raise SuiteSpecError("empty_suite_rejected")
    if len(raw_tests) > MAX_TESTS:
        raise SuiteSpecError("too_many_tests")
    tests: list[SuiteTest] = []
    for i, t in enumerate(raw_tests):
        if not isinstance(t, Mapping):
            raise SuiteSpecError(f"test_{i}_not_mapping")
        if set(t) - {"args", "expected"}:
            raise SuiteSpecError(f"test_{i}_unknown_keys:{sorted(set(t) - {'args', 'expected'})}")
        args_val = parse_literal(t.get("args"))
        if not isinstance(args_val, (list, tuple)):
            raise SuiteSpecError(f"test_{i}_args_not_positional")
        tests.append(SuiteTest(emit_literal(list(args_val)),
                               canonical_literal(t.get("expected"))))

    cmp = obj.get("cmp") or {}
    if not isinstance(cmp, Mapping):
        raise SuiteSpecError("cmp_must_be_mapping")
    if set(cmp) - {"atol", "set_equivalent", "regex_predicate"}:
        raise SuiteSpecError("cmp_unknown_keys")
    atol = cmp.get("atol")
    if atol is not None:
        if isinstance(atol, bool) or not isinstance(atol, (int, float)):
            raise SuiteSpecError("atol_must_be_number_or_null")
        atol = float(atol)
        if not math.isfinite(atol) or atol < 0:
            raise SuiteSpecError("atol_not_finite_nonnegative")
    seteq = cmp.get("set_equivalent", False)
    rxp = cmp.get("regex_predicate", False)
    if not isinstance(seteq, bool) or not isinstance(rxp, bool):
        raise SuiteSpecError("cmp_flags_must_be_bool")
    if dialect == "lcb" and (atol is not None or seteq or rxp):
        # lcb 的比較器寫死在前置裡（1e-6＋bool 守衛），沒有旋鈕。給了值就是
        # 這份 spec 在說謊——它會渲染出一段跟宣告不符的碼。
        raise SuiteSpecError("lcb_dialect_has_no_cmp_knobs")

    spec = SuiteSpec(entry_point=ep, tests=tuple(tests), dialect=dialect,
                     atol=atol, set_equivalent=seteq, regex_predicate=rxp)
    if len(spec.canonical_bytes()) > MAX_SPEC_BYTES:
        raise SuiteSpecError("spec_too_large")
    return spec


def render(spec: SuiteSpec) -> str:
    """spec → 驗收碼。**確定性**：同一份 spec 在任何機器、任何行程得到同一份碼。

    前置與 loader 逐位元組相同（`test_preludes_are_byte_identical_to_the_loaders`），
    差別只有一處而且是重點：loader 把**參考解**塞進套件裡當場算期望值
    （`exec(canonical); __canon(*args)`），這裡的期望值是**事先算好的字面值**。
    於是渲染出來的碼裡**沒有任何一個位元組來自供應者的 Python**。
    """
    if not isinstance(spec, SuiteSpec):
        spec = validate(spec)
    if spec.dialect == "mbpp":
        lines = [mbpp_prelude(spec.regex_predicate, spec.set_equivalent).rstrip("\n"), ""]
        for t in spec.tests:
            lines.append(
                f"assert __aeq({spec.entry_point}(*{t.args}), {t.expected}, {spec.atol!r})")
        return "\n".join(lines)
    if spec.dialect == "lcb":
        tests_lit = "[" + ", ".join(
            "{'args': " + t.args + ", 'expected': " + t.expected + "}"
            for t in spec.tests) + "]"
        return "\n".join([
            lcb_prelude().rstrip("\n"),
            "",
            f"__tests = {tests_lit}",
            "for __t in __tests:",
            f"    __got = {spec.entry_point}(*__t['args'])",
            "    assert __aeq(__got, __t['expected']), (",
            '        f"args={__t[\'args\']!r} got={__got!r} want={__t[\'expected\']!r}")',
        ])
    raise SuiteSpecError(f"unknown_dialect:{spec.dialect!r}")


# ── 從既有題庫轉過來（loader 的碼本來就是從資料渲染的）──────────────────────
@dataclass(frozen=True)
class Conversion:
    """一次轉換的結果。`spec is None` ⇒ 轉不了，`reason` 說為什麼。

    「轉不了」必須跟「轉出來是空的」分開報：前者是這一題沒有 spec 形態，
    後者是一份會被 validator 拒絕的 spec。混在一起就會出現「N/371 無損」
    這種把失敗算成成功的數字（06-30 稽核紀律）。
    """

    task_id: Any
    spec: "SuiteSpec | None"
    reason: str = ""
    reference: str = ""
    n_tests: int = 0


def _parse_mbpp(check_code: str) -> dict[str, Any]:
    """MBPP+ 形狀：固定前置 ＋ `__ns`/`exec(參考解)`/`__canon` ＋ 一串 assert。"""
    for rxp in (False, True):
        for seq in (False, True):
            head = mbpp_prelude(rxp, seq)
            if check_code.startswith(head):
                flags, rest = (rxp, seq), check_code[len(head):]
                break
        else:
            continue
        break
    else:
        raise SuiteSpecError("mbpp_prelude_mismatch")
    tree = ast.parse(rest)
    body = list(tree.body)
    if len(body) < 4:
        raise SuiteSpecError("mbpp_body_too_short")
    ann, ex, canon = body[0], body[1], body[2]
    if not (isinstance(ann, ast.AnnAssign) and isinstance(ann.target, ast.Name)
            and ann.target.id == "__ns"):
        raise SuiteSpecError("mbpp_missing_ns")
    if not (isinstance(ex, ast.Expr) and isinstance(ex.value, ast.Call)
            and isinstance(ex.value.func, ast.Name) and ex.value.func.id == "exec"
            and len(ex.value.args) == 2
            and isinstance(ex.value.args[0], ast.Constant)
            and isinstance(ex.value.args[0].value, str)):
        raise SuiteSpecError("mbpp_missing_exec_reference")
    reference = ex.value.args[0].value
    if not (isinstance(canon, ast.Assign) and isinstance(canon.targets[0], ast.Name)
            and canon.targets[0].id == "__canon"):
        raise SuiteSpecError("mbpp_missing_canon")

    entry: str | None = None
    atols: set[Any] = set()
    args: list[str] = []
    for node in body[3:]:
        if not isinstance(node, ast.Assert):
            raise SuiteSpecError(f"mbpp_unexpected_statement:{type(node).__name__}")
        call = node.test
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "__aeq" and len(call.args) == 3):
            raise SuiteSpecError("mbpp_assert_shape")
        got, want, tol = call.args
        if not (isinstance(got, ast.Call) and isinstance(got.func, ast.Name)
                and len(got.args) == 1 and isinstance(got.args[0], ast.Starred)):
            raise SuiteSpecError("mbpp_call_shape")
        if entry is None:
            entry = got.func.id
        elif entry != got.func.id:
            raise SuiteSpecError("mbpp_entry_point_drift")
        if not (isinstance(want, ast.Call) and isinstance(want.func, ast.Name)
                and want.func.id == "__canon"):
            raise SuiteSpecError("mbpp_expected_not_canon")
        atols.add(ast.literal_eval(tol))
        args.append(canonical_literal(ast.unparse(got.args[0].value)))
    if entry is None:
        raise SuiteSpecError("mbpp_no_tests")
    if len(atols) != 1:
        raise SuiteSpecError("mbpp_atol_drift")
    return {"dialect": "mbpp", "entry_point": entry, "args": args,
            "atol": atols.pop(), "regex_predicate": flags[0],
            "set_equivalent": flags[1], "reference": reference}


def _parse_lcb(check_code: str) -> dict[str, Any]:
    """LCB 形狀：固定前置 ＋ `__tests = [...]` ＋ 固定 for 迴圈。"""
    head = lcb_prelude()
    if not check_code.startswith(head):
        raise SuiteSpecError("lcb_prelude_mismatch")
    rest = check_code[len(head):]
    tree = ast.parse(rest)
    body = list(tree.body)
    if len(body) != 2:
        raise SuiteSpecError("lcb_body_shape")
    assign, loop = body
    if not (isinstance(assign, ast.Assign) and isinstance(assign.targets[0], ast.Name)
            and assign.targets[0].id == "__tests"):
        raise SuiteSpecError("lcb_missing_tests")
    rows = ast.literal_eval(assign.value)
    if not isinstance(rows, list) or not rows:
        raise SuiteSpecError("lcb_tests_empty")
    if not isinstance(loop, ast.For):
        raise SuiteSpecError("lcb_missing_loop")
    called = {node.func.id for node in ast.walk(loop)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    called.discard("__aeq")
    if len(called) != 1:
        raise SuiteSpecError(f"lcb_entry_point_ambiguous:{sorted(called)}")
    entry = called.pop()
    tests = []
    for r in rows:
        if not isinstance(r, Mapping) or set(r) != {"args", "expected"}:
            raise SuiteSpecError("lcb_test_row_shape")
        a = r["args"]
        if not isinstance(a, (list, tuple)):
            raise SuiteSpecError("lcb_args_not_positional")
        tests.append({"args": emit_literal(list(a)), "expected": emit_literal(r["expected"])})
    return {"dialect": "lcb", "entry_point": entry, "tests": tests}


def parse_check_code(check_code: str) -> dict[str, Any]:
    """認出兩種題庫的形狀，或丟 `SuiteSpecError`。

    這支同時是**攻擊變體的驗屍檯**：R451 的 stateful／targeted／mimic 三份
    驗收碼餵進來都會在這裡死（前置不符／出現 `Import`／assert 形狀不對），
    而且理由字串會說出是哪一條——「不可表達」是可以被測試釘住的性質，
    不是一句宣稱（`tests/test_suitespec.py::test_r451_attack_suites_have_no_encoding`）。
    """
    if not isinstance(check_code, str):
        raise SuiteSpecError("check_code_must_be_str")
    try:
        return _parse_mbpp(check_code)
    except SuiteSpecError as mb:
        try:
            return _parse_lcb(check_code)
        except SuiteSpecError as lc:
            raise SuiteSpecError(f"unrecognized_suite_shape(mbpp:{mb};lcb:{lc})") from lc


#: `compute(reference, entry_point, args_literals) -> list[(ok, literal_or_reason)]`
ExpectedComputer = Callable[[str, str, Sequence[str]], list[tuple[bool, str]]]


def subprocess_expected(reference: str, entry_point: str,
                        args_literals: Sequence[str],
                        *, timeout_s: float = 30.0) -> list[tuple[bool, str]]:
    """在**子行程**裡把參考解跑過每一組輸入，回傳期望值的字面值。

    為什麼是子行程：參考解是真的要被執行的程式碼（驗證者側，但仍然是程式）。
    在轉換工具自己的行程裡跑，一個無窮迴圈就會把整份普查卡住；子行程有 timeout、
    崩潰只死自己。這與 loader 的做法（在沙箱裡 exec 參考解）是同一條紀律，
    差別只在**跑一次算好**而不是每次驗收都重跑。
    """
    import json  # noqa: PLC0415
    import pathlib  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    root = str(pathlib.Path(__file__).resolve().parents[1])
    script = (
        "import ast, json, sys\n"
        f"sys.path.insert(0, {root!r})\n"
        "from vacant.suitespec import emit_literal, SuiteSpecError\n"
        "payload = json.loads(sys.stdin.read())\n"
        "ns = {}\n"
        "out = []\n"
        "try:\n"
        "    exec(payload['ref'], ns)\n"
        "    fn = ns[payload['entry']]\n"
        "except BaseException as exc:\n"
        "    print(json.dumps({'fatal': type(exc).__name__})); raise SystemExit(0)\n"
        "for lit in payload['args']:\n"
        "    try:\n"
        "        val = fn(*ast.literal_eval(lit))\n"
        "    except BaseException as exc:\n"
        "        out.append([False, 'reference_raised:' + type(exc).__name__]); continue\n"
        "    try:\n"
        "        out.append([True, emit_literal(val)])\n"
        "    except SuiteSpecError as exc:\n"
        "        out.append([False, 'expected_' + str(exc)])\n"
        "    except BaseException as exc:\n"
        "        out.append([False, 'emit_failed:' + type(exc).__name__])\n"
        "print(json.dumps({'out': out}))\n"
    )
    payload = json.dumps({"ref": reference, "entry": entry_point,
                          "args": list(args_literals)})
    try:
        proc = subprocess.run([sys.executable, "-I", "-c", script], input=payload,
                              capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return [(False, "reference_timeout")] * len(args_literals)
    if proc.returncode != 0 or not proc.stdout.strip():
        return [(False, "reference_subprocess_failed")] * len(args_literals)
    try:
        got = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return [(False, "reference_output_unreadable")] * len(args_literals)
    if "fatal" in got:
        return [(False, "reference_load_failed:" + str(got["fatal"]))] * len(args_literals)
    return [(bool(a), str(b)) for a, b in got["out"]]


def from_task(task: Mapping[str, Any], *,
              compute: ExpectedComputer | None = None,
              timeout_s: float = 30.0) -> Conversion:
    """把一題（`gain_run.load_tasks` 的形狀）轉成 `SuiteSpec`。

    MBPP+：期望值要**算**（參考解嵌在套件裡，`parse_check_code` 取得出來）。
    LCB：期望值本來就在 `__tests` 裡，**零執行**。

    轉不了的照實回 `Conversion(spec=None, reason=...)`，不補、不猜、不 fudge。
    """
    tid = task.get("task_id")
    code = ((task.get("visible_check") or {}).get("code")) or ""
    try:
        parsed = parse_check_code(code)
    except SuiteSpecError as exc:
        return Conversion(tid, None, f"unparsable:{exc}")
    if parsed["dialect"] == "lcb":
        try:
            spec = validate({"v": SPEC_VERSION, "dialect": "lcb",
                             "entry_point": parsed["entry_point"],
                             "tests": parsed["tests"], "cmp": {}})
        except SuiteSpecError as exc:
            return Conversion(tid, None, f"invalid_spec:{exc}")
        return Conversion(tid, spec, "", "", spec.n_tests)

    run = compute or (lambda r, e, a: subprocess_expected(r, e, a, timeout_s=timeout_s))
    results = run(parsed["reference"], parsed["entry_point"], parsed["args"])
    if len(results) != len(parsed["args"]):
        return Conversion(tid, None, "expected_computer_arity_mismatch",
                          parsed["reference"])
    tests = []
    for (ok, lit), args in zip(results, parsed["args"]):
        if not ok:
            return Conversion(tid, None, lit, parsed["reference"])
        tests.append({"args": args, "expected": lit})
    try:
        spec = validate({
            "v": SPEC_VERSION, "dialect": "mbpp",
            "entry_point": parsed["entry_point"], "tests": tests,
            "cmp": {"atol": parsed["atol"],
                    "set_equivalent": parsed["set_equivalent"],
                    "regex_predicate": parsed["regex_predicate"]},
        })
    except SuiteSpecError as exc:
        return Conversion(tid, None, f"invalid_spec:{exc}", parsed["reference"])
    return Conversion(tid, spec, "", parsed["reference"], spec.n_tests)
