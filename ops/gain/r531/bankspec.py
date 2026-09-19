#!/usr/bin/env python3
"""R531 題庫規格：**公開題庫 → R530 `TASK_FORMAT.md` 的決定性映射**。

這支在架構裡承重什麼（`DECISION_20260915_R531_…_PREREG.md` §二）：
R531 不新寫任何實驗邏輯——兩條臂就是 R530 的 `A-SOLO`／`A-GATE`，
一行都不改。**唯一新寫的東西就是這個轉換層**，而它是「資料轉換」不是
「實驗邏輯」（R452：題目是資料不是程式，同一條紀律）。

## 為什麼選擇與渲染要分成兩階段

`select` 算出「哪些題」並把 id 清單釘進 `manifest.json`；
`render` **只讀釘死的 id 清單**，不重算。
理由是決定性：選擇條件裡有 `sys.stdlib_module_names`，而那個集合
**在 Python 3.12 與 3.13 之間不一樣**（Mac 是 3.13、vacant-dev 是 3.12）。
兩台重算會選出不同的題 ⇒ 「同一個題庫」就不是同一個東西了。
⇒ **選擇只做一次並落盤，渲染在哪台跑都必須產生逐位元相同的樹。**

## 四族與它們的 V/GT 切法（Fable 2026-09-15 裁決第 4 點：用題庫自帶的測試）

| 族 | 來源 | 可見 | 隱藏 | 參考解（E-3 量具） |
|---|---|---|---|---|
| `pbf` | BigCodeBench v0.1.4（stdlib-only） | `TestCases` 前 2 個 `test_*` 方法 | 其餘方法 | `complete_prompt` ＋ `canonical_solution` |
| `pbc` | ClassEval | 前 ⌈k/3⌉ 個方法的 `test_code` | 其餘方法 ＋ 類別級測試類 | `solution_code` |
| `pba` | LiveCodeBench v3（已落盤、sha 已釘） | `visible_tests`（官方 public） | `hidden_tests`（官方 private） | `lcb_v3_probe_solutions.json`（**只有 12 題有**） |
| `pbd` | CodeContests test split | `public_tests` | `private_tests` ＋ `generated_tests`（取前 N） | `solutions` 裡 `language==3`（Python3） |

⚠ **`pbf`／`pbc` 的切法是我們切的，不是官方的** ⇒ 它們的通過率
**不可以拿去跟 BigCodeBench／ClassEval 的排行榜比**。
`pba`／`pbd` 的 public/private 是**官方就分好的**，那兩族的分母才是官方分母。
這句話要跟著任何一個數字一起被引用。

## 誠實邊界

- 產出的樹**不進版控**（ClassEval 資料是 CC BY-NC 4.0、LCB 授權只寫 `cc`
  未指明 BY/SA/NC）。repo 裡只有這支轉換器與 `manifest.json`。
- 「參考解全過 ＋ 每個壞樁被擋」是 `vacant_network/suitegauge.py` 的**單邊保證**：
  擋得住已知壞解 ≠ 涵蓋真需求。這裡的 `bad_*.py` 是**決定性突變**產生的，
  證明力比人工寫的壞樁**更弱**——這一條要寫進收官報告，不准省略。
"""
from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import re

# ── 四族的前綴。task_id 形如 `pbf_03_bcb0042`（小寫、底線）。 ─────────────
FAMILIES = ("pbf", "pbc", "pba", "pbd")

#: 每族要幾題（Fable 2026-09-15 裁決第 2 點）。`pba` 的 20 在 §六 被實測推翻。
TARGET_N = {"pbf": 25, "pbc": 20, "pba": 20, "pbd": 15}

#: `pbf` 的 hard／一般分層（裁決第 2 點逐字：hard 12 ＋ 一般 13）。
PBF_HARD_N, PBF_EASY_N = 12, 13

#: 可見測試條數上限。BCB 每題測試方法中位數 5 ⇒ 2 可見／3 隱藏。
PBF_VISIBLE_METHODS = 2
#: `pbd` 隱藏案例上限（generated_tests 有 200 筆，全放會讓隱藏樹爆掉）。
PBD_MAX_HIDDEN = 15
#: 單一測資的字元上限——巨無霸輸入撐爆樣板與沙箱（沿用 `build_lcb_bank.MAX_ARG_CHARS`）。
MAX_CASE_CHARS = 4000

#: 樣板大小硬上界（`tasks.TEMPLATE_MAX_BYTES`）。渲染時就要擋，不要等載入才炸。
TEMPLATE_MAX_BYTES = 30 * 1024
#: goal.md 的截斷長度：CodeContests 的 description 可以到 10 KB 以上。
GOAL_MAX_CHARS = 12000


def stable_pick(ids: list[str], n: int, seed: str) -> list[str]:
    """決定性抽樣：依 `sha256(seed:id)` 排序取前 n。**可重放、與輸入順序無關。**"""
    ordered = sorted(ids, key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())
    return sorted(ordered[:n])


def clip_text(s: str, n: int) -> str:
    s = (s or "").replace("\r\n", "\n").rstrip()
    if len(s) <= n:
        return s
    return s[:n] + "\n\n[... description truncated at %d characters ...]" % n


# ══ ast 工具：把一段測試原始碼**切開**而不是複製 ═══════════════════════════
#
# ⚠ 為什麼不能用「整段 class 都貼進可見檔、只是少呼叫幾個」的寫法：
#   那會讓**隱藏測試的原始碼出現在工作區裡** ⇒ V/GT 紅線（§五-3 第 1 條）破掉。
#   worker `cat` 一下就看到全部答案。所以一定要真的切。

def _node_lines(src_lines: list[str], node: ast.AST) -> str:
    """取一個節點的完整原始行（含 decorator，含原本的縮排）。

    不用 `ast.get_source_segment`：它對「有 decorator 的方法」回的是
    `def` 那一行開始的片段，decorator 會掉；而 BCB 的測試大量使用
    `@patch(...)`。掉了 decorator 的測試會變成另一個測試。
    """
    start = node.lineno
    for d in getattr(node, "decorator_list", []) or []:
        start = min(start, d.lineno)
    return "".join(src_lines[start - 1: node.end_lineno])


def split_testcase_source(src: str) -> dict:
    """把一段 `unittest` 測試原始碼拆成可重組的零件。

    回傳：
      `preamble`   —— 模組層級**非測試類**的東西（import、helper、常數）
      `classes`    —— [{name, bases_src, fixture: [str], tests: [(name, src)]}]

    `fixture` ＝ 類別裡不是 `test_*` 的東西（`setUp`／`tearDown`／helper／類別屬性）。
    它進**兩邊**：沒有 `setUp` 的話隱藏測試根本跑不起來。
    ⚠ 代價要照實講：如果作者把「期望值」寫成類別屬性，那個值會同時出現在
      可見與隱藏兩份裡 ⇒ 可見那份洩漏了一點隱藏的資訊。這是**已知殘餘**，
      `--audit-leak` 會把兩份的交集印出來讓人看得見，不會自己消音。
    """
    src = src.replace("\r\n", "\n")
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    preamble_nodes, classes = [], []
    for node in tree.body:
        is_tc = isinstance(node, ast.ClassDef) and any(
            (isinstance(b, ast.Attribute) and b.attr == "TestCase")
            or (isinstance(b, ast.Name) and b.id.endswith("TestCase"))
            for b in node.bases)
        if not is_tc:
            # `unittest.main()` 之類的收尾呼叫不要帶進來——它會讓 import 就開始跑測試
            if isinstance(node, ast.Expr) and "unittest.main" in (_node_lines(lines, node)):
                continue
            preamble_nodes.append(node)
            continue
        fixture, tests = [], []
        for item in node.body:
            seg = _node_lines(lines, item)
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                tests.append((item.name, seg))
            elif isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                continue                      # class docstring：不需要
            else:
                fixture.append(seg)
        classes.append({
            "name": node.name,
            "bases_src": ", ".join(ast.unparse(b) for b in node.bases) or "unittest.TestCase",
            "fixture": fixture,
            "tests": tests,
        })
    preamble = "".join(_node_lines(lines, n) for n in preamble_nodes)
    return {"preamble": preamble, "classes": classes}


# ══ 生成的測試檔骨架 ═══════════════════════════════════════════════════════
#
# `check_*()` 一個函式一條 case（`acceptance.py` 的執行語意）。
# `_run` 走 `unittest` 的機制，所以 `setUp`／`tearDown` 照常生效，
# 而失敗訊息拿的是 unittest 自己的 got/want 文字（`CASE_LINE` 會逐字貼給 `A-GATE`）。
RUNNER_SRC = '''

def _run(_cls, _name):
    """Run one unittest method and turn its result into pass/raise."""
    import unittest as _u
    _t = _cls(_name)
    _r = _u.TestResult()
    _t.run(_r)
    if _r.errors:
        raise RuntimeError(_r.errors[0][1].strip().splitlines()[-1])
    if _r.failures:
        raise AssertionError(_r.failures[0][1].strip())
    if _r.skipped:
        return
'''

HEADER_VISIBLE = '''"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns normally.
These are the same checks the client runs before accepting the work.
"""
'''

HEADER_HIDDEN = '''"""Acceptance checks held by the client. Never copied into a working directory.

Each `check_*` function is one check, run in definition order.
"""
'''


def render_unittest_file(*, header: str, preamble: str, classes: list[dict],
                         import_line: str) -> str:
    """把切好的零件組回一個可執行的測試檔。

    `classes` 裡每個 dict 的 `tests` 已經是**這一份**要的那幾個方法。
    完全沒有測試方法的類別會被丟掉——留著只會產生一個永遠 0 條 case 的檔案。
    """
    out = [header, import_line, "\n"]
    if "import unittest" not in preamble:
        out.append("import unittest\n")
    if preamble.strip():
        out.append("\n" + preamble.rstrip() + "\n")
    checks: list[tuple[str, str]] = []
    for c in classes:
        if not c["tests"]:
            continue
        out.append(f"\n\nclass {c['name']}({c['bases_src']}):\n")
        body = "".join(c["fixture"]) + "".join(s for _, s in c["tests"])
        out.append(body if body.strip() else "    pass\n")
        for name, _ in c["tests"]:
            checks.append((c["name"], name))
    out.append(RUNNER_SRC)
    seen: set[str] = set()
    for cls, name in checks:
        fn = re.sub(r"[^a-z0-9_]", "_", f"check_{cls}_{name}".lower())
        while fn in seen:
            fn += "_x"
        seen.add(fn)
        out.append(f'\n\ndef {fn}():\n    _run({cls}, "{name}")\n')
    return "".join(out)


RUN_TESTS_SH = pathlib.Path(__file__).resolve().parents[1] / "r530" / "templates"


def run_tests_sh_text() -> str:
    """`run_tests.sh` **逐字沿用 R530 既有的那一份**（不重寫，避免兩套語意）。"""
    p = RUN_TESTS_SH / "ow_01_csvjson" / "run_tests.sh"
    return p.read_text(encoding="utf-8")
