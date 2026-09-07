#!/usr/bin/env python3
"""H 臂：worker harness（HPI／HOC／HMIX）——把「執行結果回饋迴圈」當處理本身。

規格：`docs/HARNESS_STUDY_2026-09-07.md` §4（共同骨架 §4.0、三臂差異 §4.1–4.3）。
這支在架構裡承重什麼：既有六臂（OFF／OFF5／CONFORM／EQ5／ON／ONR）**沒有任何一條**
把「候選跑出來的失敗訊息」餵回同一個 worker——CONFORM 是換人重抽、ON 是開評審會。
pi／OpenCode 兩個真實 agent harness 唯一的共識是 F3（失敗是一則正常輸入）＋
F4（狀態明寫），而那條路徑在本 repo 從來沒被量過。這三條臂就是量它。

**三條臂的 prompt 本來就不同，而且必須不同**（§3.6）：KS-1（鐵律 1）要求 prompt
逐字相同的那條規則管的是**記憶臂**（X1 的 M0/M1/M2），那裡要量的是記憶的效果。
這裡要量的就是 harness，而 prompt 是 harness 的一部分。**但 KS-1 的實質禁令照樣
適用**：本模組任何 prompt／回饋訊息禁止出現「你有責任／會被懲罰／有人在看」類
措辭，只准說「做什麼」與「執行結果是什麼」——`vacant.memory.assert_ks1_clean`
在 import 時就對每一個常數跑過一遍（見本檔尾端），繞不過去。

**V/GT 分離（SPEC_GAIN §2、§5.8）**：本模組只轉發 `str(exc)`，永遠不自己計算期望值。
LCB 的 assert 訊息 `args=… got=… want=…` 三個欄位**全部來自 visible_tests**
（客戶自己的驗收測資），給模型看合法；MBPP+ 的期望值要**執行內嵌的官方參考解**才算得
出來，所以那裡的訊息天生是空的，**不准去補**。動態稽核見 `ops/gain/harness_vgt_audit.py`。

⚠ 可見測資的**內容**（args／got／want）進 worker prompt，這在本 repo 是第一次
  （HARNESS_STUDY D7）。合法性依據是「可見測資照設計就是給供應者看的」，
  只有 `hidden \\ visible` 那一段才是 GT；稽核腳本檢查的正是後者。

不改任何既有臂：`arm_off`／`arm_off5`／`arm_conform`／`arm_eq5`／`arm_on` 一個字不動，
`gain_run.extract_code`／`meets_demand`／`vacant/checks.py` 也一個字不動——
本模組只**呼叫**它們（§4.5 的「不動的東西」清單，`tests/test_gain_harness_arms.py`
用原始碼 sha256 釘死）。
"""
from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import secrets
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.brain_cline import InfraVoid  # noqa: E402
from vacant.memory import assert_ks1_clean  # noqa: E402

# ── 預算（三臂相同，寫死成模組常數，**不做成 CLI 旋鈕**；§4.0.6）────────────
#
# max_calls=5 等於 OFF5／EQ5：SPEC_GAIN §3「OFF-5x 是這個實驗誠實與否的分水嶺」。
# 用 6 會讓 H 臂比 OFF5 多花一通，那正是 SPEC 罵的「拿成本冒充機制」。
# ⇒ HPI ＝ 1 初稿 ＋ 最多 4 次修訂；HOC ＝ 1 計畫 ＋ 1 初稿 ＋ 最多 3 次修訂。
# max_tokens=32k ≈ OFF5 每題平均（14,102）的 2.3 倍，且高於單次 completion 的
# max（33,974 是 outlier，p99 為 13,242）——低於這個數會變成常常在「模型話太多」
# 而不是「迴圈跑太久」上收工。
# max_wall_s=900：單次延遲 p50 20.7 s、max 504.9 s（本 repo 自己的實測，
# 不引用 pi 那組沒有出處快照的 428/57/13.3%）。撞線單獨記成 stop_reason。
HARNESS_BUDGET = {
    "max_calls": 5,
    "max_tokens": 32_000,
    "max_wall_s": 900,
    "sandbox_timeout_s": 10,
    "truncation_retries": 1,
    "doom_threshold": 2,   # 只有 HMIX 用
}

VARIANTS = ("HPI", "HOC", "HMIX")

# 與 `gain_run._GAIN_ALLOWED_IMPORTS` 同一份白名單。這裡不 import gain_run
# （會循環 import），改由呼叫端傳入；這個預設值只在單獨呼叫 `static_precheck`
# 時當方便值，run 路徑一律用 `gain_run` 傳進來的那一份（不變量 5）。
DEFAULT_ALLOWED_IMPORTS = (
    "bisect", "cmath", "collections", "functools", "heapq", "itertools",
    "math", "operator", "re", "sys", "typing",
)

# `static_precheck` 的封閉理由集合（HARNESS_STUDY D4）。多一個就是規格變更，
# 不准在別處臨時造字串——`tests/test_gain_harness_arms.py` 釘死這個集合。
PRECHECK_REASONS = frozenset({
    "syntax_error", "forbidden_import", "forbidden_attr",
    "entry_point_missing", "empty",
})


# ══ 靜態預檢（零沙箱、零呼叫；F9 在我們這邊的對應物）════════════════════
def static_precheck(code: str, allowed_imports=DEFAULT_ALLOWED_IMPORTS,
                    entry_point: str | None = None) -> tuple[bool, str | None]:
    """回傳 `(ok, reason)`；`reason` ∈ `PRECHECK_REASONS`，通過時為 None。

    為什麼要有它（§3.2）：`_run_sandboxed` 在 `_candidate_functions` 回 None 時
    直接回 `(None, "")` ⇒ `visible_report` 也回 None，而那個 None 有**兩個完全不同
    的成因**（語法錯／禁用 import 或屬性）。回饋必須說出是哪一個，否則模型收到的是
    「你的程式壞了」這種零資訊訊息。

    **判準必須與沙箱一致**：本函式的 ok 必須等於
    `checks._candidate_functions(code, ...) is not None`（`entry_point_missing`
    是唯一的例外方向，見下）。r447 的 925 份真候選上實測 0 分歧；
    `tests/test_gain_harness_arms.py::T5` 是防漂移的可執行防呆。

    ⚠ 為什麼不用 LSP／pyflakes：OpenCode 的 Python LSP 需要專案 marker，我們是
      暫存目錄裡的一份 .py，server 根本不會起來；pyflakes 會違反「runtime 依賴
      只有 cryptography」（CLAUDE.md 慣例）。`ast` ＋ 既有白名單務實得多。
    """
    from vacant.checks import (_BASE_IMPORTS, _FORBIDDEN_ATTRS, _FORBIDDEN_CALLS,
                               _FORBIDDEN_NAMES)
    if not (code or "").strip():
        return False, "empty"
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False, "syntax_error"
    import_roots = _BASE_IMPORTS | set(allowed_imports)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            # `eval`/`exec`/`open`/… 這些裸名字在沙箱裡與禁用屬性同一條 fail-closed
            # 規則（`_candidate_functions` 用的是同一組常數），理由集合封閉在
            # D4 的五個 token，所以歸到 forbidden_attr，具體符號放進 detail。
            return False, "forbidden_attr"
        if isinstance(node, ast.Attribute) and (
                node.attr.startswith("__") or node.attr in _FORBIDDEN_ATTRS):
            return False, "forbidden_attr"
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0] not in import_roots
                   for alias in node.names):
                return False, "forbidden_import"
        elif isinstance(node, ast.ImportFrom):
            if not node.module or node.module.split(".", 1)[0] not in import_roots:
                return False, "forbidden_import"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and (
                    node.func.id in _FORBIDDEN_CALLS or node.func.id == "__import__"):
                return False, "forbidden_attr"
    if not _top_level_functions(tree, entry_point):
        return False, "entry_point_missing"
    return True, None


def _top_level_functions(tree: ast.Module, entry_point: str | None) -> list[str]:
    """沙箱側 `_candidate_functions` 的同款頂層函式列（含 lambda 綁定）。

    `entry_point` 給定時要求它真的在裡面——那是「拿不到 proxy」的另一個成因，
    D4 要求**單獨計數**（`entry_point_missing`）。給 None 時退化成「有沒有函式」，
    與 `_candidate_functions` 的 `or None` 同義。
    """
    import builtins

    from vacant.checks import RUNNER_RESERVED_NAMES
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            if isinstance(node.value, ast.Lambda):
                names.extend(t.id for t in targets if isinstance(t, ast.Name))
    reserved = set(dir(builtins)) | RUNNER_RESERVED_NAMES
    allowed = {entry_point} if entry_point else set()
    usable = [n for n in dict.fromkeys(names)
              if n.isidentifier() and (n not in reserved or n in allowed)]
    if entry_point is not None:
        return [n for n in usable if n == entry_point]
    return usable


def precheck_detail(code: str, allowed_imports=DEFAULT_ALLOWED_IMPORTS,
                    entry_point: str | None = None) -> str | None:
    """被擋下來的**具體符號**（`os`／`getattr`／entry point 名）。

    純資訊：不改 `static_precheck` 的 `(ok, reason)`，只讓回饋那一行說得出
    是哪一個名字被擋。OpenCode 只報 severity-1、上限 20 條的節制在我們這邊
    天然滿足（一次只有一個 reason）。
    """
    from vacant.checks import (_BASE_IMPORTS, _FORBIDDEN_ATTRS, _FORBIDDEN_CALLS,
                               _FORBIDDEN_NAMES)
    if not (code or "").strip():
        return None
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"line {exc.lineno}: {exc.msg}" if exc.lineno else exc.msg
    import_roots = _BASE_IMPORTS | set(allowed_imports)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            return node.id
        if isinstance(node, ast.Attribute) and (
                node.attr.startswith("__") or node.attr in _FORBIDDEN_ATTRS):
            return f".{node.attr}"
        if isinstance(node, ast.Import):
            bad = [a.name.split(".", 1)[0] for a in node.names
                   if a.name.split(".", 1)[0] not in import_roots]
            if bad:
                return bad[0]
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root not in import_roots:
                return root or "relative import"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and (
                    node.func.id in _FORBIDDEN_CALLS or node.func.id == "__import__"):
                return node.func.id
    if entry_point and not _top_level_functions(tree, entry_point):
        return entry_point
    return None


# ══ 執行回饋（§3.1：不改 checks.py，用既有的 run_python_capture 包一層）════
def visible_report(code: str, task: dict,
                   timeout_s: int = HARNESS_BUDGET["sandbox_timeout_s"],
                   allowed_imports=DEFAULT_ALLOWED_IMPORTS,
                   ) -> list[str] | None:
    """跑客戶的可見驗收，回 `["pass"|"fail", exc_type, message]`；載不進去回 None。

    做法（§3.1 選項 B，選項 A「在 checks.py 加回傳 stderr 的函式」已被否決）：
    把 `visible_check['code']` **原封不動**縮排進一個 try/except，只多印一行帶
    nonce 的 JSON。候選碼仍然只活在 worker、仍走 literal-only proxy、仍受
    `python -I`／RLIMIT／import 白名單約束——**與 OFF5 的 `behavior_signature`
    是同一條路徑**（2026-08-20 修正後）。

    ⚠ 變數名帶 nonce：候選可以定義任意頂層函式名，而 `_test_runner_source` 先貼
      proxy 再貼 test_code；用固定名字有被候選的同名 proxy 佔走的理論風險。

    ⚠ 只轉發 `str(exc)`，永遠不自己算期望值、不呼叫內嵌的官方參考解（§3.3）。

    ⚠ 本模組全文刻意不出現驗收碼專屬的識別字（那幾個雙底線名字）與隱藏測資的欄位名，
      好讓 §5.8 的靜態斷言可以逐字 grep 而不必開例外——唯一的例外是下面 `_RULES`
      那句給模型的禁令，稽核腳本會先把那個**凍結常數**整段扣掉再掃。
    """
    from vacant.checks import CheckInfraError, run_python_capture
    nonce = "FB_" + secrets.token_hex(8)
    var = "__vacant_fb_" + secrets.token_hex(4)
    check_src = task["visible_check"]["code"]
    indented = "\n".join("    " + line for line in check_src.splitlines())
    probe = (
        f"{var} = ['pass', '', '']\n"
        "try:\n" + indented + "\n"
        "except BaseException as __vacant_e:\n"
        f"    {var} = ['fail', type(__vacant_e).__name__, str(__vacant_e)]\n"
        f"print({nonce!r} + __import__('json').dumps({var}))\n"
    )
    try:
        out = run_python_capture(
            code, probe, timeout=timeout_s, allowed_imports=tuple(allowed_imports),
            allowed_entry_points=((task["entry_point"],)
                                  if task.get("entry_point") else ()),
        )
    except CheckInfraError as exc:
        # 沙箱 harness 起不來是**沒有量到**，不是候選寫錯——與 `meets_demand`
        # 同一條規則（鐵律 3 的 infra_void）。
        raise InfraVoid(f"sandbox verifier unavailable: {exc}") from exc
    if out is None:
        return None
    for line in out.splitlines():
        if line.startswith(nonce):
            try:
                rep = json.loads(line[len(nonce):])
            except ValueError:
                return None
            if isinstance(rep, list) and len(rep) == 3:
                return [str(x) for x in rep]
            return None
    return None


# ══ 模型自寫測資（H-OC；**只吃 literal，絕不執行模型寫的測試碼**）═════════
def parse_selftests(text: str, limit: int = 3) -> tuple[list[tuple[list, object]], int]:
    """從計畫輪的回應裡抓 `SELFTEST: [args] -> expected`。回傳 `(cases, n_bad)`。

    ⚠ 為什麼不讓模型交 test code（§3.4）：`_test_runner_source` 把 test_code
      **原樣貼進 runner 的 module scope**，而 runner 裡有 `os`、`subprocess`、
      `sys`、`_worker.stdin`。runner 是**受信任側**，只有 worker 裡的候選碼是
      不受信任的。把模型產生的碼貼進 runner ＝ 自己開一個逃逸通道。
      改成收 literal 對、由 harness 用**自己的**模板渲染——這在本 repo 有先例
      （`brain_cline.REVIEWER_SYSTEM` 的 `TEST_ARGS:`／`EXPECTED:` 就是同一形狀）。

    解析不了就丟掉並計數，**不回問模型**（省呼叫）。
    """
    cases: list[tuple[list, object]] = []
    n_bad = 0
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line.upper().startswith("SELFTEST:"):
            continue
        body = line[len("SELFTEST:"):].strip()
        if not body or body.upper() == "NONE":
            continue
        parsed = _parse_selftest_line(body)
        if parsed is None:
            n_bad += 1
            continue
        if len(cases) < limit:
            cases.append(parsed)
    return cases, n_bad


def _parse_selftest_line(body: str) -> tuple[list, object] | None:
    """`[<args list literal>] -> <expected literal>`；兩邊都 `ast.literal_eval`。

    先用括號／引號感知的掃描找出 args list 的結尾，再要求剩下的以 `->` 開頭——
    直接 `split("->")` 會被字串裡的箭頭騙走。
    """
    if not body.startswith("["):
        return None
    depth, i, quote, esc = 0, 0, "", False
    while i < len(body):
        ch = body[i]
        if quote:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    else:
        return None
    args_src, rest = body[:i + 1], body[i + 1:].strip()
    if not rest.startswith("->"):
        return None
    try:
        args = ast.literal_eval(args_src)
        expected = ast.literal_eval(rest[2:].strip())
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    if not isinstance(args, list):
        return None
    return args, expected


def render_selftest_check(entry_point: str, cases: list[tuple[list, object]],
                          nonce: str) -> str:
    """把 literal 對渲染成**harness 自己的**檢查碼（模型的碼一行都不進來）。

    判等沿用 `codebench._lcb_check_code` 的寬容遞迴語義（float 容忍 1e-6、
    list/tuple 逐元素），名字全部帶 nonce，避免與候選的同名頂層函式互踩。
    """
    aeq = f"__vst_aeq_{nonce}"
    cases_name = f"__vst_cases_{nonce}"
    res = f"__vst_res_{nonce}"
    lines = [
        f"def {aeq}(a, b):",
        "    try:",
        "        if a == b:",
        "            return True",
        "    except (TypeError, ValueError):",
        "        pass",
        "    if isinstance(a, bool) != isinstance(b, bool):",
        "        return False",
        "    if isinstance(a, (int, float)) and isinstance(b, (int, float)):",
        "        return abs(a - b) <= 1e-6",
        "    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):",
        f"        return len(a) == len(b) and all({aeq}(x, y) for x, y in zip(a, b))",
        "    return a == b",
        "",
        f"{cases_name} = {[(list(a), e) for a, e in cases]!r}",
        f"{res} = []",
        f"for __vst_a_{nonce}, __vst_e_{nonce} in {cases_name}:",
        "    try:",
        f"        __vst_g_{nonce} = {entry_point}(*__vst_a_{nonce})",
        f"        {res}.append([{aeq}(__vst_g_{nonce}, __vst_e_{nonce}),"
        f" repr(__vst_g_{nonce}), ''])",
        "    except BaseException as __vst_exc:",
        f"        {res}.append([False, None, type(__vst_exc).__name__])",
    ]
    return "\n".join(lines)


def run_selftests(code: str, task: dict, cases: list[tuple[list, object]],
                  timeout_s: int = HARNESS_BUDGET["sandbox_timeout_s"],
                  allowed_imports=DEFAULT_ALLOWED_IMPORTS) -> list[list] | None:
    """跑 harness 渲染出來的自測。回 `[[ok, got_repr, exc_type], ...]`；載不進去回 None。

    ⚠ 自測**永遠不是出貨閘門**（§3.4）：R518 量到反例精確度上界 <0.80、
      R438/R516 量到評審票近乎常數函數 ⇒ 模型自己寫的期望值有相當比例是錯的。
      只有 `visible_check` 決定出貨；自測只在可見測資也失敗時才顯示，
      而且訊息裡必須標明是它自己的測試、可能是錯的。
    """
    if not cases or not task.get("entry_point"):
        return None
    from vacant.checks import CheckInfraError, run_python_capture
    nonce = secrets.token_hex(4)
    marker = "ST_" + secrets.token_hex(8)
    body = render_selftest_check(task["entry_point"], cases, nonce)
    probe = body + (f"\nprint({marker!r} + __import__('json')"
                    f".dumps(__vst_res_{nonce}))\n")
    try:
        out = run_python_capture(
            code, probe, timeout=timeout_s, allowed_imports=tuple(allowed_imports),
            allowed_entry_points=(task["entry_point"],),
        )
    except CheckInfraError as exc:
        raise InfraVoid(f"sandbox verifier unavailable: {exc}") from exc
    if out is None:
        return None
    for line in out.splitlines():
        if line.startswith(marker):
            try:
                res = json.loads(line[len(marker):])
            except ValueError:
                return None
            return res if isinstance(res, list) else None
    return None


# ══ 文字協定：prompt 常數（英文，§3.5）════════════════════════════════════
#
# 為什麼是英文：OFF／CONFORM／OFF5 現在送的就是「中文 system prompt ＋ 英文
# user turn」（`arm_off` 送 `task["prompt"]`，LCB 的題目是英文競賽題）。H 臂用
# 英文寫 user turn，**語言組成與既有臂完全相同**；改用中文反而是引入一個 OFF
# 沒有的變因。回饋內容本身也是英文／Python（`args=… got=… want=…`）。

# ⚠ 這一行是**唯一**帶著 `exec` 加左括號那個字樣的送出文字（給模型的禁令，
# 不是驗收碼）。抽成具名常數，好讓 §5.8 的稽核腳本逐字扣掉它再掃描——扣掉的只有
# 這一行，別處出現的同一個字樣照樣會被抓到。逐字內容取自規格 §4.1 的 Rules 區塊。
RULES_NO_CALL_LINE = (
    "- Do not call input(), open(), eval(), exec(), locals(), globals() or getattr()."
)

_RULES = """Rules:
- Define a top-level function named `{entry_point}`. Do not rename it.
- Only these modules can be imported: bisect, cmath, collections, functools,
  heapq, itertools, math, operator, re, sys, typing.
""" + RULES_NO_CALL_LINE + """
- Return the value. Do not print it."""

PROMPT_HPI_BUILD = """Write a complete Python solution.

Reply with exactly one Python code block and nothing else:

```python
def {entry_point}(...):
    ...
```

""" + _RULES + """

Task:
{task}"""

# meta.txt:17 的核心子句「Verify the correctness of your solution through
# execution whenever possible and reasonable」的**改寫版**——模型在這裡沒有
# execution 可用，只能 by hand，所以改寫過、不標「逐字引用」。
# KS-1 檢查：沒有責任／懲罰／監督語意，只說「做什麼」。
HMIX_VERIFY_LINE = ("Before you answer, check your function against the examples "
                    "in the task by\nhand and fix anything that does not match.")

PROMPT_HMIX_BUILD = """Write a complete Python solution.

Reply with exactly one Python code block and nothing else:

```python
def {entry_point}(...):
    ...
```

""" + _RULES + "\n\n" + HMIX_VERIFY_LINE + """

Task:
{task}"""

PROMPT_HOC_PLAN = """Before writing code, plan.

Reply in exactly this format and nothing else:

PLAN:
<2 to 4 short lines: the algorithm you will use>
EDGE CASES:
<2 to 4 short lines: inputs that could break it>
SELFTEST: [<positional arguments as a Python list literal>] -> <expected value as a Python literal>
SELFTEST: ...

At most 3 SELFTEST lines. Each one must be a case you worked out yourself from
the statement and the examples above. Write "SELFTEST: NONE" if you cannot work
one out. Do not write the solution yet.

Task:
{task}"""

PROMPT_HOC_BUILD = """Now write the solution.

Reply with exactly one Python code block and nothing else:

```python
def {entry_point}(...):
    ...
```

""" + _RULES

# 截斷保護（F6）：截斷的輸出可能語法上 parse 得過卻是靜默不完整的。
PROMPT_TRUNCATED_RETRY = (
    "The previous reply was cut off before it was complete. Reply again with\n"
    "exactly one Python code block containing the complete function.")

# doom-loop（F7 門檻 3 → 2、`ask` → 自動介入）：預算只有 5 通，等到第 3 次
# 重複就沒機會了；無人值守（CLAUDE.md「離線可跑、可無人值守循環」）不能問人類。
DOOM_NUDGE = (
    "The same failure happened twice with the same input. Do not adjust the same\n"
    "line again. State in one sentence what the function currently computes for\n"
    "that input and why that is not what the task asks for, then write a different\n"
    "approach.")

FEEDBACK_TEMPLATE = """The function was run against the acceptance tests. It did not pass.

{block}

Reply with exactly one Python code block containing the complete corrected
function. Do not explain."""

# `{BLOCK}` 六種之一（§4.0.4）。**三臂逐字相同**——差異只在 prompt、迴圈與
# context 政策，否則就分不清增益來自「有回饋」還是「回饋寫得比較好」。
BLOCK_TIMEOUT = ("TimeoutError: the function did not return within the "
                 "10 second limit.")
BLOCK_NOCODE = "No Python code block was found in the reply."
SELFTEST_SUFFIX = ("Your own test also failed (this test is yours and may itself "
                   "be wrong): args={args!r} got={got} you expected={expected!r}")

MAX_MESSAGE_CHARS = 2000
HEAD_CHARS = 1000
TAIL_CHARS = 1000
MAX_BLOCK_LINES = 30


def truncate_message(msg: str) -> str:
    """>2000 字元時保留**前 1000 ＋ 後 1000**，中間插省略計數（F5 的改寫）。

    不用 pi 的純 tail：我們的訊息形狀是 `args=…（前） got=… want=…（後）`，
    砍頭會丟掉 args、砍尾會丟掉 want。**完整原文照樣落盤**
    （`harness_turns[i].fail_message_full_sha256` ＋ `calls.jsonl` 的全文）。
    """
    msg = msg or ""
    if len(msg) <= MAX_MESSAGE_CHARS:
        return msg
    omitted = len(msg) - HEAD_CHARS - TAIL_CHARS
    return (msg[:HEAD_CHARS] + f"…[{omitted} characters omitted]…"
            + msg[len(msg) - TAIL_CHARS:])


def _cap_lines(block: str) -> str:
    lines = block.splitlines()
    if len(lines) <= MAX_BLOCK_LINES:
        return block
    return "\n".join(lines[:MAX_BLOCK_LINES]
                     + [f"…[{len(lines) - MAX_BLOCK_LINES} more lines omitted]…"])


def render_block(kind: str, payload: dict) -> str:
    """`fail_kind` → 模型看得到的那一段。第一個 token 就是狀態（F4，站 pi 不站 OpenCode）。"""
    if kind == "assert":
        return f"AssertionError: {truncate_message(payload.get('message', ''))}"
    if kind == "exception":
        exc = payload.get("exc_type") or "Exception"
        return f"{exc}: {truncate_message(payload.get('message', ''))}"
    if kind == "timeout":
        return BLOCK_TIMEOUT
    if kind == "loader":
        reason = payload.get("reason") or "unknown"
        detail = payload.get("detail")
        # reason 本身是 D4 的封閉集合 token（落盤／計數用）；括號裡的具體符號
        # 是純資訊，不改 reason，也不改分類。
        suffix = f" ({truncate_message(str(detail))})" if detail else ""
        return f"The code could not be loaded: {reason}{suffix}"
    if kind == "nocode":
        return BLOCK_NOCODE
    raise ValueError(f"unknown fail kind: {kind}")


def render_feedback(kind: str, payload: dict, variant: str | None = None) -> str:
    """完整的回饋 user 訊息。**三臂逐字相同**（selftest 附加段只有 HOC 會有值）。"""
    block = render_block(kind, payload)
    selftest = payload.get("selftest_failure")
    if selftest and variant == "HOC":
        block = block + "\n\n" + SELFTEST_SUFFIX.format(
            args=selftest["args"], got=selftest["got"],
            expected=selftest["expected"])
    return FEEDBACK_TEMPLATE.format(block=_cap_lines(block))


# ══ 線路模式：多輪 vs 單則攤平（§4.0.2）════════════════════════════════════
#
# ⚠ **未驗證的假設**：規格寫作當時零呼叫，沒有驗證中轉接不接受 3 則以上的
#   messages。所以 run 一開始先發一次**四則訊息**的探針（system／user／
#   assistant／user）。通過 ⇒ 多輪模式；400／格式錯 ⇒ 退回單則攤平模式。
#   **兩種模式的結果不得混算**（SPEC_GAIN §7 的 timeout／retry 同理）——
#   模式逐格落盤在 `extra["harness_wire_mode"]`。
WIRE_PROBE_MESSAGES = [
    {"role": "user", "content": "Reply with exactly: OK"},
    {"role": "assistant", "content": "OK"},
    {"role": "user", "content": "Reply with exactly: OK"},
]

# 攤平格式**刻意不像對話**——抄 pi `docs/compaction.md` 的理由
# 「This prevents the model from treating it as a conversation to continue.」
FLATTEN_HEADER = ("Record of the work so far. This is a record, not a "
                  "conversation to continue.")

_WIRE_MODE: str | None = None


def reset_wire_mode() -> None:
    """測試／重跑用：清掉行程內的探針快取。"""
    global _WIRE_MODE
    _WIRE_MODE = None


def current_wire_mode() -> str | None:
    return _WIRE_MODE


# round460c：探針的輸出上限。原本寫死 16，而 16 不夠**會先輸出 reasoning 的模型**
# 講完話——gemma-4-12b-it-qat 把 16 個 completion token 全花在 reasoning 上、
# content 交空白 ⇒ `chat()` 丟 `EmptyResponse` ⇒ `InfraVoid` ⇒ **每一格 H 臂
# 都變 infra_void**。R460 smoke 實測（2026-09-07，直連 1003）：HPI／HOC／HMIX
# 三條臂在第一題就全 void，零 row；同一顆後端對同一個四則 body 在
# max_tokens=16／64 回 finish_reason=length ＋ 空 content，256 才回 "OK"
# （usage.reasoning_tokens 75）。512 ＝ 實測門檻再留一倍餘裕。
# 一個 run 只發一次，成本可忽略——「開小」省的那點 token 不值得拿整條臂去換。
WIRE_PROBE_MAX_TOKENS = 512


def _looks_like_format_rejection(err: str) -> bool:
    """400／422 ＝ 端點不吃這個 body 形狀；其餘（連不上、逾時、5xx）不是格式問題。"""
    return any(tag in err for tag in ("HTTP Error 400", "HTTP Error 422",
                                      "Error 400:", "Error 422:"))


def _looks_like_empty_content(err: str) -> bool:
    """端點回 HTTP 200、body 解得出 `choices`，只是 `content` 是空的。

    round460c：這**證明線路形狀被接受了**（不接受會是 400／422），所以它屬於
    multiturn，不屬於「連不上」。原本只有兩分法，這一格掉進 re-raise，
    結果是端點好好的、整條 H 臂卻全記 infra_void（見 `WIRE_PROBE_MAX_TOKENS`）。
    留著這一條而不是只調大 max_tokens：任何 reasoning 講得比上限久的模型都會
    重現同一個死法，而那個上限永遠只是猜的。
    """
    return "EmptyResponse" in err


def probe_wire_mode(agent, *, meta: dict | None = None) -> str:
    """一個 run 只發一次的四則訊息探針。回 `"multiturn"` 或 `"flattened"`。

    ⚠ 這是本階段**唯一**允許的活呼叫。連不上／逾時**不**退回攤平模式：那會把
      一次瞬斷變成整個 run 的實驗條件改變。那種情況照 `InfraVoid` 往外拋，
      該格記 infra_void，下一題再探一次（自癒）。

    三分法（round460c 修正；原本只有兩分法）：
      400／422        ⇒ 端點不吃這個 body 形狀 ⇒ `flattened`
      200 但 content 空 ⇒ 形狀**被接受了**，只是模型沒交字 ⇒ `multiturn`
      其餘（連不上、逾時、5xx）⇒ 沒量到 ⇒ 往外拋
    """
    global _WIRE_MODE
    if _WIRE_MODE is not None:
        return _WIRE_MODE
    try:
        agent.chat(list(WIRE_PROBE_MESSAGES), role="wire_probe",
                   meta={"probe": "harness_wire_mode", **(meta or {})},
                   retries=2, max_tokens=WIRE_PROBE_MAX_TOKENS)
        _WIRE_MODE = "multiturn"
    except InfraVoid as exc:
        err = str(exc)
        if _looks_like_format_rejection(err):
            _WIRE_MODE = "flattened"
        elif _looks_like_empty_content(err):
            _WIRE_MODE = "multiturn"
        else:
            raise
    return _WIRE_MODE


def flatten_messages(messages: list[dict]) -> list[dict]:
    """把整串對話序列化成**一則** user 訊息。單則對話原樣送（不加包裝）。"""
    if len(messages) <= 1:
        return [dict(m) for m in messages]
    parts = [FLATTEN_HEADER, ""]
    n_req = 0
    for i, m in enumerate(messages):
        is_last = i == len(messages) - 1
        if m["role"] == "user":
            n_req += 1
            label = "CURRENT REQUEST" if is_last else f"REQUEST {n_req}"
        else:
            label = f"REPLY {n_req}"
        parts += [f"--- {label} ---", m["content"], ""]
    return [{"role": "user", "content": "\n".join(parts).rstrip() + "\n"}]


# ══ 取碼器（D4）══════════════════════════════════════════════════════════
def _fenced_blocks(text: str) -> list[str]:
    """回應裡的圍欄區塊（去掉 `python`／`py` 標籤後的內文，空塊不算）。"""
    if "```" not in (text or ""):
        return []
    parts = text.split("```")
    blocks = []
    for i in range(1, len(parts), 2):
        blk = parts[i]
        if blk.startswith("python"):
            blk = blk[6:]
        elif blk.startswith("py"):
            blk = blk[2:]
        if blk.strip():
            blocks.append(blk.strip())
    return blocks


def extract_code_revision(text: str, entry_point: str | None) -> tuple[str, bool]:
    """修訂輪的取碼器：第一個**能 ast.parse 且定義了 entry point** 的圍欄區塊。

    回傳 `(code, used_fallback)`；找不到就 fallback 到 `gain_run.extract_code`
    （逐字不改，不變量 4 只要求「六條臂用同一個取碼器」在**初稿輪**成立，
    因為那一輪才是與 OFF 直接可比的那一格）。

    為什麼修訂輪需要另一個規則（D4）：修訂輪的回應常常先貼一段「原本的錯」再貼
    修好的版本，第一塊規則會咬到錯的那一份。**兩個選擇都落盤**
    （`code_sha256` vs `baseline_code_sha256`）並計數分歧，事後可以離線重算
    「如果一律用 extract_code 會怎樣」——差異不會變成看不見的手腳。
    """
    from ops.gain.gain_run import extract_code
    baseline = extract_code(text)
    for blk in _fenced_blocks(text):
        try:
            tree = ast.parse(blk)
        except SyntaxError:
            continue
        if entry_point is None:
            return blk, False
        names = {n.name for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        names |= {t.id for n in tree.body if isinstance(n, ast.Assign)
                  and isinstance(n.value, ast.Lambda)
                  for t in n.targets if isinstance(t, ast.Name)}
        if entry_point in names:
            return blk, False
    return baseline, True


# ══ 主迴圈 ═══════════════════════════════════════════════════════════════
def _usage_tokens(usage: dict) -> int:
    if not isinstance(usage, dict):
        return 0
    total = usage.get("total_tokens")
    if isinstance(total, (int, float)):
        return int(total)
    return int((usage.get("prompt_tokens") or 0)
               + (usage.get("completion_tokens") or 0))


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _n_visible_tests(task: dict) -> int | None:
    """零成本：`_visible_test_slicer` 只做 ast 解析，不跑沙箱。"""
    from ops.gain.gain_run import _visible_test_slicer
    sl = _visible_test_slicer(task["visible_check"]["code"])
    return sl[0] if sl else None


def run_harness_arm(task, agents, rng, calls, book, ident, *, variant,
                    wire_mode: str | None = None,
                    budget: dict | None = None,
                    allowed_imports=None):
    """一題一個 worker、看著執行結果改，最多 5 通呼叫。回傳與其他 `arm_*` 同簽章。

    `variant` ∈ {"HPI", "HOC", "HMIX"}；三者的差異只有 §4.4 那張表列的五件事
    （計畫輪／自寫測資／靜態診斷先行／verify 指示／doom 偵測／context 政策），
    其餘（system prompt 池、取碼器、沙箱、白名單、10 s timeout、接受語意、
    計分路徑）一律相同。

    **一題一個 worker**（§4.0.5）：`rng.choice(agents)` 只抽一次，整題所有輪次
    都用同一個 persona。CONFORM 的增益來自「換人重抽」，H 臂的增益（若有）必須
    來自「同一個人看著執行結果改」——中途換 persona 會把兩件事混在一起。
    ⇒ H 臂**不繼承** CONFORM 的換人紅利，這是設計要的，不是遺漏。

    **拒交語意與 `arm_conform` 逐字相同**（§4.0.8）：拒交時仍然回傳最後一份草稿，
    dispatch 端無條件用隱藏測資離線計分（那是評分不是出貨），
    `accepted=False` 才是「沒有交出去」——目的就是讓
    `leaked = accepted and not truth` 在六條臂之間同義。

    `InfraVoid` 一律往外拋（不新增 void 語意），dispatch 端記成 `infra_void`。
    """
    if variant not in VARIANTS:
        raise ValueError(f"unknown harness variant: {variant}")
    if allowed_imports is None:
        # 不變量 5：白名單必須是**呼叫端那一份**，不是這裡的同名副本。
        # 這裡 lazy import 而不是模組層 import，是因為 gain_run 在模組層 import 本檔。
        from ops.gain.gain_run import _GAIN_ALLOWED_IMPORTS
        allowed_imports = _GAIN_ALLOWED_IMPORTS
    bud = dict(HARNESS_BUDGET)
    if budget:
        bud.update(budget)
    worker = rng.choice(agents)
    entry_point = task.get("entry_point")
    n_vis = _n_visible_tests(task)
    mode = wire_mode or probe_wire_mode(
        worker, meta={"arm": variant, "task_id": task["task_id"]})

    conversation: list[dict] = []          # 完整對話（全留政策的來源）
    turns: list[dict] = []
    t0 = time.time()
    calls_used = 0
    tokens_total = 0
    truncation_left = int(bud["truncation_retries"])
    chosen: str | None = None
    last_draft: str | None = None
    first_pass_turn: int | None = None
    stop_reason: str | None = None
    doom_hits = 0
    doom_nudges = 0
    prev_signature: tuple | None = None
    loader_refusals = nocode_turns = truncated_retries = 0
    extractor_divergences = 0
    entry_point_missing = 0
    first_block_non_python = 0
    selftests: list[tuple[list, object]] = []
    selftests_bad = 0
    pending_kind = "plan" if variant == "HOC" else "build"
    next_user = (
        PROMPT_HOC_PLAN.format(task=task["prompt"]) if variant == "HOC" else
        (PROMPT_HMIX_BUILD if variant == "HMIX" else PROMPT_HPI_BUILD).format(
            entry_point=entry_point, task=task["prompt"]))
    build_turn_done = False

    while True:
        turn_no = len(turns) + 1
        conversation.append({"role": "user", "content": next_user})
        sent = _context_for(variant, conversation)
        wire = flatten_messages(sent) if mode == "flattened" else sent
        text, info = worker.chat(
            wire, role="gen", turn=turn_no,
            meta={"arm": variant, "task_id": task["task_id"], "turn": turn_no,
                  "kind": pending_kind, "wire_mode": mode})
        calls[0] += 1
        calls_used += 1
        tokens_total += _usage_tokens(info.get("usage") or {})
        conversation.append({"role": "assistant", "content": text})
        rec: dict = {
            "turn": turn_no, "kind": pending_kind, "agent_id": worker.agent_id,
            "model": info.get("model"), "server_model": info.get("server_model"),
            "finish_reason": info.get("finish_reason"),
            "latency_ms": info.get("latency_ms"),
            "prompt_tokens": (info.get("usage") or {}).get("prompt_tokens"),
            "completion_tokens": (info.get("usage") or {}).get("completion_tokens"),
            "n_code_blocks": len(_fenced_blocks(text)),
            "n_visible_tests": n_vis,
            "context_messages": len(wire),
            "context_prompt_tokens": (info.get("usage") or {}).get("prompt_tokens"),
            "response_sha256": _sha(text),
        }

        # ── 2. 截斷保護（F6）───────────────────────────────────────────
        if info.get("finish_reason") == "length" and truncation_left > 0:
            truncation_left -= 1
            truncated_retries += 1
            rec.update({"kind": "truncated_retry", "requested_kind": pending_kind,
                        "used_output": False,
                        "fail_kind": None, "code_sha256": None,
                        "precheck_ok": None, "precheck_reason": None})
            _append_turn(book, ident, task, variant, rec, turns)
            stop_reason = _budget_stop(bud, calls_used, tokens_total, t0)
            if stop_reason:
                break
            next_user = PROMPT_TRUNCATED_RETRY
            # 被截斷的如果是初稿輪，重發之後**還是**初稿輪（`build_turn_done`
            # 也還沒翻）——不能記成 revise，否則 D5 的「turn1 效果 vs 迴圈效果」
            # 歸因會把重發算進迴圈那一邊。
            pending_kind = "revise" if build_turn_done else pending_kind
            continue
        rec["used_output"] = True

        # ── H-OC 的計畫輪：不出碼，只收 literal 自測 ────────────────────
        if pending_kind == "plan":
            selftests, selftests_bad = parse_selftests(text)
            rec.update({"selftests_parsed": len(selftests),
                        "selftests_bad": selftests_bad,
                        "fail_kind": None, "code_sha256": None,
                        "precheck_ok": None, "precheck_reason": None})
            _append_turn(book, ident, task, variant, rec, turns)
            stop_reason = _budget_stop(bud, calls_used, tokens_total, t0)
            if stop_reason:
                break
            next_user = PROMPT_HOC_BUILD.format(entry_point=entry_point)
            pending_kind = "build"
            continue

        # ── 3. 取碼（D4：初稿輪用 gain_run.extract_code，修訂輪用 harness 取碼器）
        from ops.gain.gain_run import extract_code
        blocks = _fenced_blocks(text)
        baseline_code = extract_code(text)
        if not build_turn_done:
            code, used_fallback = baseline_code, True
            rec["extractor"] = "gain_run.extract_code"
            build_turn_done = True
        else:
            code, used_fallback = extract_code_revision(text, entry_point)
            rec["extractor"] = ("gain_run.extract_code" if used_fallback
                                else "harness_first_valid")
        rec["baseline_code_sha256"] = _sha(baseline_code)
        rec["code_sha256"] = _sha(code)
        rec["extractor_divergent"] = bool(code != baseline_code)
        extractor_divergences += int(code != baseline_code)
        rec["code_chars"] = len(code)
        if blocks and not _compiles(blocks[0]):
            first_block_non_python += 1
            rec["first_block_non_python"] = True
        last_draft = code

        fail_kind = fail_exc = None
        fail_message = ""
        payload: dict = {}
        if not blocks:
            # 圍欄一個都沒有 ⇒ 協定失敗。**計入呼叫預算**並計數。
            nocode_turns += 1
            fail_kind = "nocode"
            rec.update({"precheck_ok": None, "precheck_reason": None})
        else:
            # ── 4. 靜態診斷（HOC／HMIX 明列先行；HPI 也要有 reason 才講得出
            #      `The code could not be loaded: …` 是哪一種——差異在 prompt
            #      與迴圈，不在回饋文字，§4.0.4）
            ok, reason = static_precheck(code, allowed_imports, entry_point)
            rec.update({"precheck_ok": ok, "precheck_reason": reason})
            if not ok:
                loader_refusals += 1
                entry_point_missing += int(reason == "entry_point_missing")
                fail_kind = "loader"
                payload = {"reason": reason,
                           "detail": precheck_detail(code, allowed_imports,
                                                     entry_point)}
            else:
                # ── 5. 跑客戶的可見驗收 ────────────────────────────────
                report = visible_report(code, task, bud["sandbox_timeout_s"],
                                        allowed_imports)
                if report is None:
                    # 理論上不該到這裡（步驟 4 已經放行）；到了就照實落盤。
                    loader_refusals += 1
                    fail_kind = "loader"
                    rec["detail_reason"] = "precheck_disagrees"
                    payload = {"reason": reason or "unknown", "detail": None}
                elif report[0] == "pass":
                    rec.update({"fail_kind": None, "visible_pass": True})
                    _append_turn(book, ident, task, variant, rec, turns)
                    chosen = code
                    first_pass_turn = turn_no
                    stop_reason = "visible_pass"
                    break
                else:
                    fail_exc, fail_message = report[1], report[2]
                    if fail_exc == "TimeoutError":
                        fail_kind = "timeout"
                    elif fail_exc == "AssertionError":
                        fail_kind = "assert"
                    else:
                        fail_kind = "exception"
                    payload = {"exc_type": fail_exc, "message": fail_message}

        rec.update({"fail_kind": fail_kind, "fail_exc_type": fail_exc,
                    "fail_message": (fail_message or "")[:MAX_MESSAGE_CHARS],
                    "fail_message_full_sha256": _sha(fail_message or ""),
                    "visible_pass": False})

        # ── H-OC 的自測回報（可見測資失敗時才跑；自測不是出貨閘門）─────
        if variant == "HOC" and selftests and fail_kind in ("assert", "exception",
                                                            "timeout"):
            st_res = run_selftests(code, task, selftests, bud["sandbox_timeout_s"],
                                   allowed_imports)
            rec["selftests_run"] = None if st_res is None else len(st_res)
            n_failed = 0 if not st_res else sum(1 for r in st_res if not r[0])
            rec["selftests_failed"] = n_failed
            if st_res:
                for (args, expected), res in zip(selftests, st_res):
                    if not res[0]:
                        payload["selftest_failure"] = {
                            "args": args, "expected": expected,
                            "got": res[1] if res[1] is not None
                            else f"<{res[2]}>"}
                        break

        # ── 6. doom 判定（只有 H-MIX）──────────────────────────────────
        signature = (fail_kind, fail_exc, _sha(fail_message or ""))
        nudge = False
        if variant == "HMIX":
            if prev_signature is not None and signature == prev_signature:
                doom_hits += 1
                if doom_hits >= int(bud["doom_threshold"]):
                    rec["doom_hits"] = doom_hits
                    _append_turn(book, ident, task, variant, rec, turns)
                    stop_reason = "doom"
                    break
                nudge = True
                doom_nudges += 1
            else:
                doom_hits = 0
            rec["doom_hits"] = doom_hits
        prev_signature = signature

        # ── 7. 預算檢查 ────────────────────────────────────────────────
        feedback = render_feedback(fail_kind, payload, variant)
        if nudge:
            feedback = feedback + "\n\n" + DOOM_NUDGE
        rec["feedback_chars"] = len(feedback)
        rec["feedback_sha256"] = _sha(feedback)
        _append_turn(book, ident, task, variant, rec, turns)
        stop_reason = _budget_stop(bud, calls_used, tokens_total, t0)
        if stop_reason:
            break

        # ── 8. 組回饋訊息 → 回到 1 ─────────────────────────────────────
        next_user = feedback
        pending_kind = "doom_nudge" if nudge else "revise"

    accepted = chosen is not None
    code_out = chosen if accepted else (last_draft if last_draft is not None else "")
    book.append(
        "harness_verdict",
        {"task_id": task["task_id"], "variant": variant, "accepted": accepted,
         "turns": len(turns), "worker": worker.agent_id,
         "stop_reason": stop_reason, "wire_mode": mode,
         "first_pass_turn": first_pass_turn},
        ident, ts_ms=int(time.time() * 1000),
    )
    extra = {
        "accepted": accepted,
        "visible_ok": accepted,
        "harness_variant": variant,
        "harness_wire_mode": mode,
        "harness_calls": calls_used,
        "harness_tokens_total": tokens_total,
        "harness_wall_s": round(time.time() - t0, 2),
        "stop_reason": stop_reason,
        "first_pass_turn": first_pass_turn,
        "n_turns": len(turns),
        "loader_refusals": loader_refusals,
        "entry_point_missing": entry_point_missing,
        "nocode_turns": nocode_turns,
        "first_block_non_python": first_block_non_python,
        "truncated_retries": truncated_retries,
        "extractor_divergences": extractor_divergences,
        "doom_triggered": stop_reason == "doom",
        "doom_nudges": doom_nudges,
        "selftests_parsed": len(selftests),
        "selftests_unparsable": selftests_bad,
        "receipt_head": book.head(),
        "harness_turns": turns,
    }
    return code_out, worker.agent_id, [worker.agent_id], extra


def _parses(src: str) -> bool:
    """`ast.parse` 過不過——**與沙箱 `_candidate_functions` 同一個判準**（T5 靠這個）。"""
    try:
        ast.parse(src)
        return True
    except SyntaxError:
        return False


def _compiles(src: str) -> bool:
    """更嚴的「這塊是不是 Python」：`ast.parse` 收得下 module 層的 `return`
    （那是編譯期錯不是語法錯），所以第一塊到底像不像程式碼要用 `compile` 判。

    純診斷用（`first_block_non_python` 計數）：`compile` 只編譯不執行，
    而且判準不進出貨閘門，所以不會與沙箱漂移。
    """
    try:
        compile(src, "<harness_block>", "exec")
        return True
    except (SyntaxError, ValueError):
        return False


def _context_for(variant: str, conversation: list[dict]) -> list[dict]:
    """context 政策。HPI／HOC 全留；HMIX 只留 `[u1, a_{n-1}, u_n]`。

    HMIX 抄的是 OpenCode `session/compaction.ts` 的 **prune**（把舊 tool output
    換掉而不刪訊息），不是它的 compaction——prune 零模型呼叫，compaction 要多花
    一次呼叫（我們只有 5 通，不划算）。⚠ 這是**有代價**的設計：模型看不到前兩輪
    試過什麼，可能繞回去；doom 偵測就是這個代價的對沖。
    """
    if variant != "HMIX" or len(conversation) <= 1:
        return [dict(m) for m in conversation]
    first_user = conversation[0]
    last_user = conversation[-1]
    prev_assistant = next((m for m in reversed(conversation[1:-1])
                           if m["role"] == "assistant"), None)
    out = [dict(first_user)]
    if prev_assistant is not None:
        out.append(dict(prev_assistant))
    out.append(dict(last_user))
    return out


def _budget_stop(bud: dict, calls_used: int, tokens_total: int,
                 t0: float) -> str | None:
    """呼叫數／tokens／牆鐘任一超過就停。撞線是一個**獨立的 outcome**，
    不可以混進失敗率——三個 stop_reason 分開記。"""
    if calls_used >= int(bud["max_calls"]):
        return "budget_calls"
    if tokens_total >= int(bud["max_tokens"]):
        return "budget_tokens"
    if (time.time() - t0) >= float(bud["max_wall_s"]):
        return "budget_wall"
    return None


def _append_turn(book, ident, task, variant, rec, turns) -> None:
    """每一輪都簽進與 CONFORM／EQ5 **同一條** hash-chain（`save_receipts` 不用改）。

    成本：簽章＋上鏈 1.0 ms／筆（R449 §三-3 實測），可忽略。
    """
    entry = book.append(
        "harness_attempt",
        {"task_id": task["task_id"], "variant": variant,
         **{k: v for k, v in rec.items() if k != "fail_message"}},
        ident, ts_ms=int(time.time() * 1000),
    )
    rec["entry_hash"] = entry.hash()
    turns.append(rec)


# ── KS-1 可執行防呆（鐵律 1 的實質禁令；§3.6）────────────────────────────
#
# import 時就跑，繞不過去：任何 prompt／回饋模板出現「你有責任／會被懲罰／
# 有人在看／這關係到你的評價」類措辭 ⇒ KS1Violation ⇒ 這支 import 不進來 ⇒
# run 起不來。允許的只有「做什麼」與「執行結果是什麼」。
for _txt in (_RULES, PROMPT_HPI_BUILD, PROMPT_HMIX_BUILD, PROMPT_HOC_PLAN,
             PROMPT_HOC_BUILD, PROMPT_TRUNCATED_RETRY, DOOM_NUDGE,
             HMIX_VERIFY_LINE, FEEDBACK_TEMPLATE, BLOCK_TIMEOUT, BLOCK_NOCODE,
             SELFTEST_SUFFIX, FLATTEN_HEADER):
    assert_ks1_clean(_txt)
del _txt
