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

⚠ **round452b：上面那段在 1cfec80 上是假的，補洞紀錄留在這裡不刪。**
`entry_point` 當時是**套件**的欄位，validator 只要求它是識別字、非關鍵字、
不以 `__` 開頭、不在 `RESERVED_NAMES` 裡——`exec` 四條全過。而 `render` 把它當
**裸名字**寫進碼裡，驗收碼又是貼在 `vacant/checks.py` runner 的 module scope 跑的，
所以 `entry_point="exec"` ＋ `args=["<任意 Python 原始碼>"]` 渲染出來就是

    assert __aeq(exec(*['<payload>']), None, atol)

一次任意程式執行（builtins 與 runner 自己的 `os`／`subprocess`／`sys` 全在）。
實測：368/371 過 commit、假交付 31.52%，與 R451 的 raw-code targeted 逐位元相同
（`ops/gain/replay/r452b_smuggle_gate.py`）。修法是結構性的兩步：

  (a) **entry_point 屬於題目不屬於套件**——`validate(spec, entry_point=題目的)`，
      不符即 `entry_point_mismatch`；`peerexec` 每一道門都強制帶著它。
  (b) **渲染器改成命名空間查找**——`entry_binding()` 產生
      `__entry = __vacant_ns['<名字>']`，名字只以 repr 過的字串鍵出現，
      不再是一個會沿著 module → builtins 解析的識別字。

`ENTRY_POINT_BLACKLIST` 是**防禦縱深**，不是修法。教訓寫成一句話：
「不可表達」是**渲染出來的碼**的性質，不是 validator 的性質；validator 擋住了
所有 `Call`／`Name`／`Attribute` 節點，卻讓一個**識別字**原樣走進了可執行位置。

⚠ **round452c：又兩個洞，補在這裡不刪。** 兩個都不是任意程式執行，兩個都是
攻擊者（`ops/gain/replay/r452c_channel_hunt.py`）在 b3c8514 上實測出來的：

  (i) **非 SuiteSpecError 穿門**（探針 C）。`expected = "0x" + "f"*4000` 是一份
      **完全合法**的 spec：`ast.literal_eval` 收 16 進位字面值，而 CPython 的
      `int_max_str_digits` 只擋十進位轉換，所以長度上限與型別走訪都放行；
      到 `emit_literal` 的 `repr()` 才炸，丟的是**裸 `ValueError`**。
      `peerexec` 每一道門只 `except SuiteSpecError` ⇒ 11/11 道門噴 traceback。
      這不是走私，是**相關失效**：k 台執行器吃同一份 spec 會一起倒，
      而拒絕服務也是一種交不出貨。修法兩層：`MAX_INT_BITS`（資料有界，
      `int_too_large`）＋ `_no_escape`（兜底，`literal_unencodable`）。
  (ii) **`entry_point=None` 的綁定失效**（探針 I）。舊碼把 `None` 當「跳過檢查」，
      而 `task.get("entry_point")` 在一個**沒有那個欄位**的題目上正好回 `None`
      ⇒ R452b 的修法整條變回 no-op。修法：哨符 `_UNBOUND` ＝未綁定，
      `None` ＝沒有東西可以綁 ⇒ `entry_point_unbound`。

剩下**還能表達**的攻擊仍然只有兩類：
  1. **覆蓋不足**——少給幾條測資、挑容易的輸入（`tests` 是供應者給的）。
  2. **比對旗標放寬**——`cmp.atol` 開大、`set_equivalent`／`regex_predicate`
     亂開（只有 mbpp 方言有旗標）。
兩類都還是要先過量具（參考解通過、每個已知壞樁被擋）。殘餘**要用兩個數字講，
不准縮成一個**（`ops/gain/replay/peer_exec_suitespec_gate_r452c.json`，
`g_r446_eq5_mbpp`、368 題可轉換、k=3）：

  - **可實現**（`generic_gauged`）：供應者只用**自己手上就有的東西**挑測資
    ——spec 自己的 `expected` 有多泛、參考解、已知壞樁，零候選可見度、
    零 hidden 可見度，過不了量具就換下一條。假交付 **17.93% → 20.65%
    （+2.72pp）**，交付正確率 −0.82pp。
  - **事後諸葛上限**（`weak_oracle`）：看得到 5 份已歸檔候選與 hidden 標籤，
    挑最傷的那一條。假交付 **+4.35pp**、交付 −1.63pp。真實供應者拿不到這份
    資料，所以它是上限不是會發生的攻擊。

  ⚠ 舊講法「殘餘＝−8.70pp」（`weak_first`）**要停用**：那一格是「盲挑第 0 條」，
    它掉的 8.70pp 裡有一大半是**量具把它擋掉**（committed 331/371 vs 366），
    也就是機制在生效，不是攻擊者的收穫。看假交付才看得到攻擊者要的東西：
    `weak_first` 的假交付只 +1.36pp，比會挑的 `generic_gauged` 還低。

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
import builtins
import hashlib
import keyword
import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .canonical import canonical_bytes
from .checks import CANDIDATE_NS_NAME, RENDERED_SUITE_NAMES

SPEC_VERSION = 1
DIALECTS = ("mbpp", "lcb")

#: 尺寸上限。字面值是資料，資料要有界——沒有界的話「一份 spec」可以是一顆
#: 記憶體炸彈，而拒絕服務也是一種交不出貨。
MAX_TESTS = 2000
MAX_LITERAL_CHARS = 200_000
MAX_SPEC_BYTES = 4 * 1024 * 1024
MAX_DEPTH = 40

#: 整數的**值**上限（位元數），round452c 新增。前面三個上限量的都是**原始碼長度**，
#: 而 `0x` ／ `0b` ／ `0o` 開頭的字面值可以用很短的原文寫出很大的值——
#: `"0x" + "f"*4000` 只有 4002 個字元（遠低於 `MAX_LITERAL_CHARS`），
#: 卻是一個 16000 位元的整數，`repr()` 它會撞上 CPython 的
#: `sys.get_int_max_str_digits()`（預設 4300 位十進位）而丟一個**裸 ValueError**。
#: 4096 位元 ≒ 1234 位十進位，穩穩落在那條線以下，所以「已驗過的值 repr 得出來」
#: 這句話才成立（`emit_literal` 的前提）。
#:
#: ⚠ 這是**能力上的取捨**，寫在這裡不要事後當成 bug：一題真的需要
#: 4096 位元以上整數的驗收（大數運算）在這個形態裡表達不出來，會被拒成
#: `int_too_large`。用「拒絕一種罕見的合法需求」換掉「任何供應者都能用 4KB
#: 讓 k 台執行器一起丟 traceback」，這條交換是刻意的。
MAX_INT_BITS = 4096

#: 渲染器會用掉的名字。entry_point 撞到任何一個都會讓渲染出來的碼語意改變，
#: 所以在 validator 就拒絕，不留給沙箱去發現。
#:
#: round452c：渲染器那一半改成從 `vacant/checks.py` 的 `RENDERED_SUITE_NAMES` 取，
#: 兩個檔案共用同一張表——沙箱那側用它擋**候選**的 proxy 撞名，這裡用它擋
#: **供應者**的 entry_point 撞名。反向漂移防呆見
#: `tests/test_suitespec.py::test_every_renderer_name_is_reserved_on_the_sandbox_side`。
RESERVED_NAMES = RENDERED_SUITE_NAMES | frozenset({"_worker", "_vacant_call"})

#: `vacant/checks.py::_test_runner_source` 的 runner 模板在 module scope 綁定的
#: 每一個名字（import 進來的與自己定義的）。漂移防呆是
#: `tests/test_suitespec.py::test_entry_point_blacklist_covers_the_runner_template`
#: ——它 AST 走訪真的模板，任何新名字沒進這裡就會吵。
RUNNER_TEMPLATE_NAMES = frozenset({
    "ast", "builtins", "json", "math", "os", "selectors", "subprocess", "sys", "time",
    "_nonce", "_wire_tag", "_wire_encode", "_wire_decode", "_worker_env",
    "_read_fd", "_write_fd", "_worker", "_protocol", "_selector",
    "_ready_deadline", "ready", "line", "response", "_vacant_call",
    CANDIDATE_NS_NAME,
})

#: `dir(builtins)` 裡**題目可以合法擁有**的名字：純取值／聚合語意，拿到它也變不出
#: 執行、匯入、屬性或 IO 的能力。其餘 builtins 一律拒（default-deny）。
#:
#: 為什麼要有這個小白名單而不是整個 `dir(builtins)` 一刀切：真的 MBPP+ 題庫裡
#: `mbppplus_Mbpp/126` 的 entry_point 就是 `sum`——那是**題目**（客戶的需求）自己
#: 擁有的名字，不是供應者選的。一刀切會把一題合法的題目擋掉，等於讓這層防禦縱深
#: 變成功能退化，而它明明不是修法本身（修法是下面 `render` 的命名空間查找）。
TASK_OWNABLE_BUILTINS = frozenset({
    "abs", "all", "any", "ascii", "bin", "bool", "bytes", "chr", "complex",
    "divmod", "filter", "float", "format", "frozenset", "hash", "hex", "id",
    "int", "len", "list", "map", "max", "min", "next", "oct", "ord", "pow",
    "range", "repr", "reversed", "round", "set", "slice", "sorted", "str",
    "sum", "tuple", "zip",
})

#: 防禦縱深（**不是**修法）：entry_point 的黑名單。
#:
#: 修法是 `render` 不再用裸名字解析 entry point——名字只以 repr 過的字串鍵出現在
#: `__vacant_ns[...]` 裡，所以撞到 builtins 或 runner 的名字在**結構上**已經無害。
#: 這個黑名單留著是因為「結構上無害」這句話依賴另一個檔案（`vacant/checks.py`）
#: 的模板，而兩個檔案會各自演化。一層擋不住的時候另一層還在，才叫縱深。
ENTRY_POINT_BLACKLIST = (
    RESERVED_NAMES
    | (frozenset(dir(builtins)) - TASK_OWNABLE_BUILTINS)
    | RUNNER_TEMPLATE_NAMES
)


class SuiteSpecError(ValueError):
    """spec 不合格 ⇒ **拒絕**，不修正、不猜測。

    刻意用例外而不是回傳 None：一個安靜回 None 的 validator 會讓呼叫端在
    `if spec:` 之外的路徑上繼續渲染，而那正是 fail-open。
    """


# ── 字面值：解析、型別走訪、正規重寫 ────────────────────────────────────────
_ATOMS = (type(None), bool, int, float, complex, str, bytes)

#: 這一層**准許**逃出去的例外只有 `SuiteSpecError`。其餘這些（含它們的子類：
#: `OverflowError`／`UnicodeError` 分別在 `ArithmeticError`／`ValueError` 底下）
#: 一律翻譯成 `literal_unencodable`。
_UNENCODABLE = (ValueError, TypeError, ArithmeticError, RecursionError, MemoryError)


def _no_escape(fn: Callable[..., Any], *args: Any, **kw: Any) -> Any:
    """跑 `fn`，保證只有 `SuiteSpecError` 出得來（round452c 的防禦縱深）。

    為什麼需要這一層：`peerexec` **每一道門**都只 `except SuiteSpecError`
    （`select_by_quorum`／`suite_gate` 的理由通道、`commit_suite` 的拒絕路徑），
    所以只要 validator 丟出別的型別，例外就會穿過整條路徑變成一個 traceback。
    攻擊者實測過這條：一份**完全合法**的 spec（`expected = "0x" + "f"*4000`）
    在 1cfec80…b3c8514 上讓 11/11 道門全部噴 `ValueError`
    （`ops/gain/replay/r452c_channel_hunt.py` 探針 C）。那不是任意程式執行，
    是**相關失效**：k 台執行器吃同一份 spec 會一起倒，而拒絕服務也是一種交不出貨。

    修法是兩層。第一層是資料本身有界（`MAX_INT_BITS`，`_walk` 擋在 parse 階段）；
    這一層是**兜底**——任何沒被想到的 `repr`／遞迴／記憶體錯誤都變成一次
    fail-closed 的拒絕，理由字串 `literal_unencodable`。

    ⚠ 誠實邊界：兜底會把**程式碼的 bug** 也講成「這份 spec 不合格」。方向是對的
    （拒交而不是崩潰），代價是 validator 自己壞掉的時候看起來像資料壞掉——
    所以原始例外用 `raise ... from exc` 留在 `__cause__`，不要拿掉。
    """
    try:
        return fn(*args, **kw)
    except SuiteSpecError:
        raise
    except _UNENCODABLE as exc:
        raise SuiteSpecError("literal_unencodable") from exc


def _check_int(value: int) -> None:
    """整數的值要有界，否則 `emit_literal` 的 `repr()` 會丟一個裸 ValueError。

    `ast.literal_eval` 收 `0x`／`0b`／`0o` 字面值，而 CPython 的
    `int_max_str_digits` 只擋**十進位轉換**、不擋這幾種進位的 parse——所以
    「原始碼很短、值很大」是走得通的，長度上限攔不住它。見 `MAX_INT_BITS`。
    """
    if value.bit_length() > MAX_INT_BITS:
        raise SuiteSpecError("int_too_large")


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
    if isinstance(value, int):
        _check_int(value)
        return
    if isinstance(value, (str, bytes)):
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


def _emit_literal(value: Any, depth: int = 0) -> str:
    if depth > MAX_DEPTH:
        raise SuiteSpecError("literal_too_deep")
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, int):
        _check_int(value)
        return repr(value)
    if isinstance(value, (str, bytes)):
        return repr(value)
    if isinstance(value, (float, complex)):
        _check_finite(value)
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_emit_literal(v, depth + 1) for v in value) + "]"
    if isinstance(value, tuple):
        body = ", ".join(_emit_literal(v, depth + 1) for v in value)
        return "(" + body + ("," if len(value) == 1 else "") + ")"
    if isinstance(value, set):
        if not value:
            raise SuiteSpecError("empty_set_not_encodable")
        return "{" + ", ".join(sorted(_emit_literal(v, depth + 1) for v in value)) + "}"
    if isinstance(value, dict):
        return "{" + ", ".join(
            f"{_emit_literal(k, depth + 1)}: {_emit_literal(v, depth + 1)}"
            for k, v in value.items()) + "}"
    raise SuiteSpecError(f"not_a_literal_type:{type(value).__name__}")


def emit_literal(value: Any, depth: int = 0) -> str:
    """把一個**已驗過**的值寫成確定性的字面值字串。

    為什麼不直接用 `repr`：`repr(set)` 的元素順序跟著 `PYTHONHASHSEED` 走，
    同一份 spec 在兩台機器上會算出不同的 `suite_sha256`——那會讓「第三方可重算」
    這句話直接失效。集合一律照 emit 後的字串排序。dict 保留插入順序（順序來自
    來源字面值，本身是確定性的），不排序，因為混型鍵排不動。

    round452c：整個遞迴包在 `_no_escape` 裡（`repr(巨大整數)` 會丟裸 ValueError），
    所以這支對外只丟 `SuiteSpecError`。`from_task` 也靠這條——參考解**算出來的**
    期望值沒有經過 validator，是這裡第一次碰到它。
    """
    return _no_escape(_emit_literal, value, depth)


def _parse_literal(text: Any) -> Any:
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


def parse_literal(text: Any) -> Any:
    """`ast.literal_eval` ＋ 型別走訪。名稱／呼叫／屬性／lambda／推導式全部在這裡死。

    `literal_eval` 自己就會拒絕 Name／Call／Attribute／Lambda／ListComp／
    JoinedStr（f-string）；型別走訪是第二道，擋掉 `1e999`（合法字面值、parse 成
    inf）與 `0x` ＋ 4000 個 `f`（合法字面值、值大到 `repr` 不出來）這種
    literal_eval 放行的東西。
    """
    return _no_escape(_parse_literal, text)


def canonical_literal(text: Any) -> str:
    """解析 → 重寫。**上鏈的位元組是重寫過的**，不是作者排版過的。

    這條是「資料而不是程式」的一半：同一個值只有一種寫法，所以
    `suite_sha256` 認的是**值**，不是空白與引號的風格。
    """
    return _no_escape(lambda t: _emit_literal(_parse_literal(t)), text)


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


class _Unbound:
    """`validate` 的「這次呼叫**沒有**題目可以綁」哨符型別（round452c）。"""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - 只為了錯誤訊息好看
        return "<unbound>"


#: round452c：`entry_point` 的預設值從 `None` 改成哨符。
#:
#: 為什麼這不是潔癖：`None` 同時是「呼叫端刻意不綁」與「`task.get("entry_point")`
#: 在一個沒有那個欄位的題目上回傳的東西」。舊碼寫的是
#: `if entry_point is not None and ep != entry_point`，於是第二種情況**靜默地
#: 跳過整個綁定**——`Executor.attest`／`select_by_quorum`／`challenge_rerun`
#: 三支都用 `task.get("entry_point")`，一個少了欄位的題目就讓 R452b 的修法
#: 整條變回 no-op（攻擊者實測：`ops/gain/replay/r452c_channel_hunt.py` 探針 I，
#: 一份 `entry_point="helper"` 的套件在沒有欄位的題目上一路過到 `suite_gate`）。
#:
#: 現在：哨符＝未綁定（只留給工具與測試），`None`＝**沒有東西可以綁 ⇒ 拒**。
_UNBOUND = _Unbound()


def validate(obj: Any, *, entry_point: Any = _UNBOUND) -> SuiteSpec:
    """把任意輸入變成一份可用的 `SuiteSpec`，或丟 `SuiteSpecError`。

    `entry_point` ＝ **題目**（`task["entry_point"]`）宣告的進入點。round452b 起
    這不是一個可選的額外檢查，而是規格：entry_point 屬於題目，不屬於套件。
    給了就必須相符，不符丟 `entry_point_mismatch`；`peerexec` 那一側每一道門都
    強制帶著它進來（`as_suite_spec`），所以「不給」這條路只留給還沒綁題目的
    工具與測試——而「不給」現在是**省略這個參數**（哨符 `_UNBOUND`），不是傳
    `None`。傳 `None` ＝ 題目沒有宣告進入點 ＝ 沒有東西可以綁 ⇒
    `entry_point_unbound`（round452c）。

    round452c 的第二件事：整支包在 `_no_escape` 裡，**只有 `SuiteSpecError` 出得去**。
    呼叫端（`peerexec` 的每一道門）只 catch 這一個型別，所以任何別的例外等於
    穿門而過的 traceback，那是相關失效不是拒絕。

    fail-closed，缺一不可（每一條都對應一個 `tests/test_suitespec.py` 的測試）：
      - `v` 是本版
      - `dialect` 在白名單裡
      - `entry_point` 是識別字、不是關鍵字、不撞渲染器用掉的名字、不以 `__` 開頭、
        不在 `ENTRY_POINT_BLACKLIST` 裡（防禦縱深），且與題目宣告的相符
      - `tests` 至少 **1** 條（0 條＝什麼都不驗＝R449 §三-3 那一格，直接拒絕；
        量具那一層也會擋，但這裡先擋，因為 0 條連跑都不必跑）
      - 每條 `args` 是**列表或元組**字面值（位置引數），`expected` 是任意字面值
      - lcb 方言的 `cmp` 三欄必須是未使用值（那個方言的比較器寫死在前置裡）
      - 全部字面值重寫過（**上鏈的是重寫後的位元組**）
      - canonical bytes 不超過上限
    """
    return _no_escape(_validate, obj, entry_point)


def _validate(obj: Any, entry_point: Any) -> SuiteSpec:
    """`validate` 的本體。**不要直接呼叫**——外面那層是例外型別的閘。"""
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
    if entry_point is None:
        # round452c：`None` ＝ 題目那一格是空的（多半是 `task.get("entry_point")`
        # 打在一個沒有那個欄位的題目上）。**沒有東西可以綁 ⇒ 拒**，不准當成
        # 「這次不檢查」。與 `mismatch` 分開報，是因為兩者要修的地方不同：
        # mismatch 是套件在說謊，unbound 是題目資料不全。
        raise SuiteSpecError("entry_point_unbound")
    if entry_point is not _UNBOUND and ep != entry_point:
        # entry_point 是**題目**的欄位。套件敢跟題目不一樣，就是它在替客戶決定
        # 「要驗的是哪一個函式」——那是 R452b 那條走私管道的第一步。
        #
        # ⚠ 順序有意義：**綁定先於黑名單**。走私用的 `exec` 兩條都撞得到，先報
        #   `entry_point_mismatch` 才說得出「擋住它的是結構（entry_point 屬於題目），
        #   不是那張名單」。名單只在題目**自己**宣告了危險名字時才是唯一的那道門。
        raise SuiteSpecError("entry_point_mismatch")
    if keyword.iskeyword(ep) or ep.startswith("__") or ep in ENTRY_POINT_BLACKLIST:
        # ⚠ 這一條是**防禦縱深**，不是修法。`exec` 之所以不再危險，是因為 `render`
        #   不用裸名字解析 entry point（見 `render` 的 docstring）；黑名單只是第二層。
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


def entry_binding(entry_point: str) -> str:
    """渲染出「怎麼拿到受測函式」的那一行：**明確的命名空間查找**。

    round452b 的修法就是這一行。在它之前，渲染器把 entry_point 當成一個**裸名字**
    寫進碼裡（`assert __aeq(f(*[1]), 2, None)`），而驗收碼是貼在 runner 的 module
    scope 執行的——裸名字解析是 module → builtins。候選沒有定義那個名字時，
    `exec`／`open`／`getattr` 這些**都在**，於是一個供應者宣告的 entry_point 加上
    一串字串字面值就是一次任意程式執行（實測：`ops/gain/replay/r452b_smuggle_gate.py`
    在 1cfec80 上假交付 31.52%，368/371 過 commit）。

    改成 `__vacant_ns['名字']` 之後，名字只以 **repr 過的字串鍵**出現：它不再是
    一個會被解析的識別字，所以無論那個字串是什麼，都只可能命中候選自己定義的
    函式，或 `KeyError`（fail-closed）。`__vacant_ns` 由 `vacant/checks.py` 的
    runner 模板提供（`CANDIDATE_NS_NAME`），它是這條修法**唯一**需要的鉤子。

    代價寫清楚：渲染出來的碼從此**依賴那個鉤子**。拿去別的 runner 跑會 NameError
    ——那是 fail-closed 的方向，但它確實讓 LCB 那條「轉換後與 loader 逐位元組相同」
    的性質不再成立（loader 自己還是用裸名字；那份碼不是供應者寫的，見模組 §紅線 5）。
    """
    return f"__entry = {CANDIDATE_NS_NAME}[{entry_point!r}]"


def render(spec: SuiteSpec) -> str:
    """spec → 驗收碼。**確定性**：同一份 spec 在任何機器、任何行程得到同一份碼。

    前置與 loader 逐位元組相同（`test_preludes_are_byte_identical_to_the_loaders`），
    差別只有兩處而且都是重點：
      1. loader 把**參考解**塞進套件裡當場算期望值（`exec(canonical); __canon(*args)`），
         這裡的期望值是**事先算好的字面值**。
      2. loader 用裸名字呼叫受測函式，這裡走 `entry_binding()` 的命名空間查找
         （round452b；理由見那支的 docstring）。
    於是渲染出來的碼裡**沒有任何一個位元組來自供應者的 Python**，而且供應者給的
    每一個 token 都落在**不可執行的位置**：repr 過的字面值，或一個字典鍵。
    """
    if not isinstance(spec, SuiteSpec):
        spec = validate(spec)
    if spec.dialect == "mbpp":
        lines = [mbpp_prelude(spec.regex_predicate, spec.set_equivalent).rstrip("\n"), "",
                 entry_binding(spec.entry_point)]
        for t in spec.tests:
            lines.append(
                f"assert __aeq(__entry(*{t.args}), {t.expected}, {spec.atol!r})")
        return "\n".join(lines)
    if spec.dialect == "lcb":
        tests_lit = "[" + ", ".join(
            "{'args': " + t.args + ", 'expected': " + t.expected + "}"
            for t in spec.tests) + "]"
        return "\n".join([
            lcb_prelude().rstrip("\n"),
            "",
            entry_binding(spec.entry_point),
            f"__tests = {tests_lit}",
            "for __t in __tests:",
            "    __got = __entry(*__t['args'])",
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
    # round452b：轉出來的 spec 也要**綁題目宣告的 entry_point**。這裡的 entry point
    # 是從 loader 的碼 parse 出來的，兩者本來就該相同；不同就是這一題的 visible_check
    # 與它的 `entry_point` 欄位對不上，那是資料問題，要在轉換階段吵出來而不是
    # 讓一份「驗別的函式」的 spec 帶著轉換成功的標記流下去。
    ep = task.get("entry_point")
    try:
        parsed = parse_check_code(code)
    except SuiteSpecError as exc:
        return Conversion(tid, None, f"unparsable:{exc}")
    if parsed["dialect"] == "lcb":
        try:
            spec = validate({"v": SPEC_VERSION, "dialect": "lcb",
                             "entry_point": parsed["entry_point"],
                             "tests": parsed["tests"], "cmp": {}}, entry_point=ep)
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
        }, entry_point=ep)
    except SuiteSpecError as exc:
        return Conversion(tid, None, f"invalid_spec:{exc}", parsed["reference"])
    return Conversion(tid, spec, "", parsed["reference"], spec.n_tests)
