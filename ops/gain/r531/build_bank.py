#!/usr/bin/env python3
"""R531 題庫建置：**公開題庫 → R530 的三個目錄**。零模型呼叫。

兩階段，理由在 `bankspec.py` 的 docstring（選擇條件依賴
`sys.stdlib_module_names`，而那個集合在 3.12 與 3.13 之間不同）：

    select  ── 算出「哪些題」，寫進 `ops/gain/r531/manifest.json`
    render  ── **只讀釘死的 id 清單**，渲染成 templates/hidden/gauge

產出落在 R530 既有的三個目錄底下，前綴 `pb`：

    ops/gain/r530/templates/<task_id>/   ops/gain/r530/hidden/<task_id>/
    ops/gain/r530/gauge/<task_id>/

⚠ **為什麼放在 R530 的目錄裡而不是自己開一個**：`ops/gain/r530/tasks.py`
  的 `TEMPLATES_DIR`／`HIDDEN_DIR`／`GAUGE_DIR` 是模組常數，
  而 `run_r530.py` 不吐路徑旋鈕。Fable 2026-09-15 裁決第 1 點是
  「不准改 openwork_arms.py／sandbox.py／receipts.py 任何一行」，
  而改 `tasks.py` 一樣是改既有程式碼 ⇒ **選擇零改動，代價是共用目錄**。
  R530 正在跑的四塊用的是**逐題列出的 `--task-set`**（不是 `all`），
  所以多出來的 `pb*` 目錄動不到它們；`--bank-sha` 也是逐題比對。

⚠ **產出不進版控**：ClassEval 資料是 CC BY-NC 4.0、LCB 授權只寫 `cc`
  未指明 BY/SA/NC ⇒ 轉出來的樹是衍生物，不轉散布（裁決第 3 點）。
  `.gitignore` 有對應的三行。**repo 裡只有這支轉換器與 manifest.json。**
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from ops.gain.r531 import bankspec as BS  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
R530 = REPO / "ops" / "gain" / "r530"
TPL, HID, GAU = R530 / "templates", R530 / "hidden", R530 / "gauge"
PRIV = REPO / ".vacant-private" / "benchmarks"
MANIFEST = REPO / "ops" / "gain" / "r531" / "manifest.json"
TASKLIST = REPO / "ops" / "gain" / "r531" / "tasks_r531.json"
SELECT_SEED = "r531-bank-2026-09-15"

#: **先選 2 倍，再由量具裁掉**。理由是 `TASK_FORMAT.md` 對 `gauge/` 的判準
#: （參考解必須全過可見與隱藏、每個壞樁都必須被擋）**本來就是題目的合格條件**
#: 而不是事後補救：「不全過的意思不是參考解寫得不好，是驗收與契約對不起來」。
#: 公開題庫轉過來的題有多少會踩到這一條，事前**量不出來**（要跑才知道），
#: 所以流程是 select(2×) → render → gauge → finalize(取前 N 個合格的)。
#: ⚠ 這個規則在看到「哪幾題」之前就寫死了，而且它就是 E-3 既有的判準，
#:   不是為了救某幾題發明的新標準。淘汰名單逐題落盤在 manifest 的 `finalize`。
POOL_MULT = 2

NET_RE = re.compile(r"urlopen|requests\.|\bsocket\b|http\.client|urllib\.request|smtplib|ftplib")
IMPORT_RE = re.compile(r"(?m)^\s*(?:from|import)\s+([A-Za-z_]\w*)")


def _third_party(src: str, stdlib: frozenset[str]) -> set[str]:
    return {m.group(1) for m in IMPORT_RE.finditer(src or "")} - stdlib - {"solution"}


def _read_jsonl(p: pathlib.Path) -> list[dict]:
    """逐行 JSON。**用 `split("\n")` 不是 `splitlines()`**——後者也會在
    U+2028／U+2029／\x0b／\x0c 上斷行，而 `ensure_ascii=False` 寫出來的
    JSON 字串裡真的有這些字元（CodeContests 的題目敘述就有）⇒ 一列會被
    切成兩半，然後 `json.loads` 在半行上炸掉。我們寫檔時一列一個 `\n`。"""
    return [json.loads(l) for l in p.read_text(encoding="utf-8").split("\n") if l.strip()]


# ══════════════════════ 選擇（select） ═══════════════════════════════════
def select_pbf(stdlib: frozenset[str]) -> tuple[list[str], dict]:
    """BigCodeBench：stdlib-only ∧ 測試也不碰第三方 ∧ ≥5 個 test 方法 ∧ 不觸網。"""
    rows = {r["task_id"]: r for r in _read_jsonl(PRIV / "bigcodebench" / "v0.1.4.jsonl")}
    hard = {r["task_id"] for r in _read_jsonl(PRIV / "bigcodebench_hard" / "v0.1.4.jsonl")}
    elig, why = {}, {"libs_3rd": 0, "imports_3rd": 0, "network": 0, "few_tests": 0, "parse": 0, "entry": 0}
    for tid, r in rows.items():
        libs = r.get("libs") or []
        if isinstance(libs, str):
            libs = ast.literal_eval(libs)
        if [x for x in libs if x not in stdlib]:
            why["libs_3rd"] += 1; continue
        if r.get("entry_point") != "task_func":
            why["entry"] += 1; continue
        blob = (r.get("complete_prompt") or "") + (r.get("canonical_solution") or "") + (r.get("test") or "")
        if _third_party(blob, stdlib):
            why["imports_3rd"] += 1; continue
        if NET_RE.search(blob):
            why["network"] += 1; continue
        try:
            parts = BS.split_testcase_source(r.get("test") or "")
        except SyntaxError:
            why["parse"] += 1; continue
        n = sum(len(c["tests"]) for c in parts["classes"])
        if len(parts["classes"]) != 1 or n < BS.PBF_VISIBLE_METHODS + 3:
            why["few_tests"] += 1; continue
        elig[tid] = r
    hard_pool = [t for t in elig if t in hard]
    easy_pool = [t for t in elig if t not in hard]
    h = BS.stable_pick(hard_pool, min(len(hard_pool), BS.PBF_HARD_N * POOL_MULT), SELECT_SEED + ":hard")
    e = BS.stable_pick(easy_pool, min(len(easy_pool), BS.PBF_EASY_N * POOL_MULT), SELECT_SEED + ":easy")
    return h + e, {"eligible": len(elig), "eligible_hard": len([t for t in elig if t in hard]),
                   "rejected": why, "hard_picked": h, "easy_picked": e}


def select_pbc(stdlib: frozenset[str]) -> tuple[list[str], dict]:
    """ClassEval：整個類別（解 ＋ 測試）都不碰第三方 ∧ ≥3 個方法。"""
    data = json.loads((PRIV / "classeval" / "ClassEval_data.json").read_text(encoding="utf-8"))
    elig, why = {}, {"imports_3rd": 0, "few_methods": 0, "parse": 0, "network": 0}
    for c in data:
        blob = ("\n".join(c.get("import_statement") or []) + "\n"
                + (c.get("solution_code") or "") + "\n" + (c.get("test") or ""))
        tp = _third_party(blob, stdlib)
        if tp:
            why["imports_3rd"] += 1; continue
        if NET_RE.search(blob):
            why["network"] += 1; continue
        if len(c.get("methods_info") or []) < 3:
            why["few_methods"] += 1; continue
        try:
            for m in c["methods_info"]:
                BS.split_testcase_source(m["test_code"])
            ast.parse(c["solution_code"]); ast.parse(c["skeleton"])
        except SyntaxError:
            why["parse"] += 1; continue
        elig[c["task_id"]] = c
    return BS.stable_pick(list(elig), min(len(elig), BS.TARGET_N["pbc"] * POOL_MULT),
                          SELECT_SEED + ":pbc"), {"eligible": len(elig), "rejected": why}


def select_pba(stdlib: frozenset[str]) -> tuple[list[str], dict]:
    """LiveCodeBench v3：**硬上界是參考解的數量**（只有 12 題有）。

    E-3 的判準是「量不到不是通過」：沒有 `good.py` 的題不計入覆蓋，
    而 `coverage_n != n_tasks` ⇒ 發射閘門紅。
    ⇒ 這一族只能取「有參考解」的那 12 題，**取不到裁決寫的 20**。
    """
    rows = {r["task_id"]: r for r in _read_jsonl(REPO / "ops/gain/data/lcb_bank_v3.jsonl")}
    sols = json.loads((REPO / "ops/gain/data/lcb_v3_probe_solutions.json").read_text(encoding="utf-8"))
    known_bad = {"lcb_3613", "lcb_3763"}          # ops/gain/check_bank_precision.py::KNOWN_BAD
    elig = [t for t, s in sols.items()
            if t in rows and t not in known_bad and s.strip()
            and rows[t].get("visible_tests") and rows[t].get("hidden_tests")]
    want = min(BS.TARGET_N["pba"], len(elig))
    return BS.stable_pick(elig, want, SELECT_SEED + ":pba"), \
        {"eligible": len(elig), "with_reference_solution": len(sols),
         "bank_n": len(rows), "target_unreachable": BS.TARGET_N["pba"] > len(elig)}


def select_pbd(stdlib: frozenset[str]) -> tuple[list[str], dict]:
    """CodeContests test split：要有 Python3 參考解 ∧ 有 public ∧ 夠多 hidden。

    取**評分最低（最簡單）**的那幾題，不是隨機抽——12B 在 Codeforces 題上
    的地板效應是本族最大的風險（§六），評分是我們手上唯一的事前難度訊號。
    """
    rows = _read_jsonl(PRIV / "codecontests" / "test.jsonl")
    elig, why = [], {"no_py3": 0, "no_public": 0, "few_hidden": 0, "huge": 0}
    for r in rows:
        s = r.get("solutions") or {}
        py3 = [so for lg, so in zip(s.get("language", []), s.get("solution", []))
               if lg == 3 and len(so) < 8000]
        if not py3:
            why["no_py3"] += 1; continue
        pub = r.get("public_tests") or {}
        hid_in = list((r.get("private_tests") or {}).get("input", [])) + \
                 list((r.get("generated_tests") or {}).get("input", []))
        if not pub.get("input"):
            why["no_public"] += 1; continue
        if len(hid_in) < 5:
            why["few_hidden"] += 1; continue
        if len(r.get("description") or "") > BS.GOAL_MAX_CHARS * 2:
            why["huge"] += 1; continue
        elig.append((r.get("cf_rating") or 9999, r["name"]))
    elig.sort()
    picked = [n for _, n in elig[:BS.TARGET_N["pbd"] * POOL_MULT]]
    return sorted(picked), {"eligible": len(elig), "rejected": why,
                            "rating_range": [elig[0][0], elig[min(len(elig), BS.TARGET_N['pbd']) - 1][0]] if elig else None}


SELECTORS = {"pbf": select_pbf, "pbc": select_pbc, "pba": select_pba, "pbd": select_pbd}


def cmd_select(args) -> int:
    stdlib = frozenset(sys.stdlib_module_names)
    sources = json.loads((PRIV / "sources.json").read_text(encoding="utf-8"))
    man = {"built_by": "ops/gain/r531/build_bank.py", "select_seed": SELECT_SEED,
           "python": sys.version.split()[0], "sources": sources["sources"], "families": {}}
    for fam, fn in SELECTORS.items():
        ids, info = fn(stdlib)
        man["families"][fam] = {"source_ids": ids, "n": len(ids),
                                "target_n": BS.TARGET_N[fam], "selection": info}
        print(f"[{fam}] picked {len(ids)} / target {BS.TARGET_N[fam]}   eligible={info.get('eligible')}")
        if len(ids) < BS.TARGET_N[fam]:
            print(f"   ⚠ 取不到目標題數——這一族要回報給 Fable（裁決第 9 點）")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nmanifest → {MANIFEST}")
    return 0


# ══════════════════════ 突變體（E-3 的 bad_*.py） ═══════════════════════
#
# ⚠ **誠實邊界，不准省略**：這些壞樁是**決定性突變**產生的，
#   不是人手寫的「最接近正確的錯解」。`vacant_network/suitegauge.py` 的單邊保證
#   在這裡**更弱**：擋得住「回傳 None」不代表擋得住一個聰明的錯解。
#   收官報告要寫出「本 run 的 bad_* 是自動生成的」這一句。

class _NegateFirstIf(ast.NodeTransformer):
    """把函式體裡**第一個** `if` 的條件取反——一個語意上的近似錯解。"""

    def __init__(self) -> None:
        self.done = False

    def visit_If(self, node: ast.If):                      # noqa: N802
        self.generic_visit(node)
        if not self.done:
            self.done = True
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
        return node


def mutant_negate(src: str) -> str | None:
    """回傳「第一個 if 取反」的版本；沒有 `if` 就回 None（那一題少一個壞樁）。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    tr = _NegateFirstIf()
    tree = tr.visit(tree)
    if not tr.done:
        return None
    ast.fix_missing_locations(tree)
    try:
        return ast.unparse(tree) + "\n"
    except Exception:                                      # noqa: BLE001
        return None


def _stub_bodies(src: str, value: str) -> str | None:
    """把**所有**函式／方法的 body 換成 `return <value>`（保留簽名與類別結構）。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    ret = ast.parse(f"return {value}").body[0]
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "__init__":
                continue
            node.body = [ret]
            n += 1
    if not n:
        return None
    ast.fix_missing_locations(tree)
    try:
        return ast.unparse(tree) + "\n"
    except Exception:                                      # noqa: BLE001
        return None


# ══════════════════════ 渲染（render） ═══════════════════════════════════
def _tid(fam: str, i: int, src_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", src_id.lower())[-8:] or "x"
    return f"{fam}_{i:02d}_{slug}"


def render_pbf(row: dict) -> dict:
    parts = BS.split_testcase_source(row["test"])
    cls = parts["classes"][0]
    vis, hid = cls["tests"][:BS.PBF_VISIBLE_METHODS], cls["tests"][BS.PBF_VISIBLE_METHODS:]
    # ⚠ **`from solution import *` 是必要的，不是方便。**
    # BigCodeBench 官方 harness 把「解」與「測試」接成**同一個模組**跑，
    # 所以它的測試預設看得到解那一側的 `import os`／`import math`／
    # 模組層級常數（`OUTPUT_DIR`…）。只 `import solution` 的話那些名字
    # 不在測試模組的命名空間裡 ⇒ `NameError`，而那會被記成「參考解沒過」。
    # （2026-09-16 第一次量具實測：25 題裡 13 題因此紅。）
    imp = ("import solution\n"
           "from solution import *  # noqa: F403 —— 重現官方 harness 的單一模組語意\n"
           "task_func = solution.task_func\n")
    cp = (row["complete_prompt"] or "").rstrip("\n") + "\n"
    goal = (BS.clip_text(row.get("instruct_prompt") or "", BS.GOAL_MAX_CHARS)
            + "\n\nWrite the result as `solution.py` in this directory.\n")
    contract = ("The module `solution.py` must define this function, with exactly "
                "this name and signature:\n\n```python\n"
                + (row.get("code_prompt") or "").rstrip() + "\n```\n")
    good = cp + (row["canonical_solution"] or "")
    # ⚠ **三個型別錯的樁是保證存在的那三個**，`bad_negate` 是第四個（近似錯解）。
    #   第一版只有前兩個 ＋ negate，而 `mutant_negate` 在沒有 `if` 的參考解上回 None
    #   ⇒ 50 個候選裡 23 個因為「壞樁只有 2 個（要 ≥3）」被裁掉。
    #   那是**生成器的限制被記成題目的性質**，會讓「量具過的比例」說謊。
    bads = {"bad_none.py": cp + "    return None\n",
            "bad_empty.py": cp + "    return []\n",
            "bad_zero.py": cp + "    return 0\n"}
    nm = mutant_negate(good)
    if nm:
        bads["bad_negate.py"] = nm
    return {
        "template": {
            "goal.md": goal, "contract.md": contract,
            "run_tests.sh": BS.run_tests_sh_text(),
            "tests_visible/test_visible.py": BS.render_unittest_file(
                header=BS.HEADER_VISIBLE, preamble=parts["preamble"],
                classes=[{**cls, "tests": vis}], import_line=imp)},
        "hidden": {"test_hidden.py": BS.render_unittest_file(
            header=BS.HEADER_HIDDEN, preamble=parts["preamble"],
            classes=[{**cls, "tests": hid}], import_line=imp)},
        "gauge": {"good.py": good, **bads},
        "counts": {"visible": len(vis), "hidden": len(hid)},
    }


def render_pbc(c: dict) -> dict:
    methods = c["methods_info"]
    k = max(1, math.ceil(len(methods) / 3))
    per_method_classes = {m["test_class"] for m in methods}
    extra = [cl for cl in BS.split_testcase_source(c["test"])["classes"]
             if cl["name"] not in per_method_classes]
    vis_cls, hid_cls = [], list(extra)
    for i, m in enumerate(methods):
        got = BS.split_testcase_source(m["test_code"])["classes"]
        (vis_cls if i < k else hid_cls).extend(got)
    imp = (f"import unittest\nfrom solution import {c['class_name']}\n"
           + "\n".join(c.get("import_statement") or []) + "\n")
    desc = re.sub(r'^\s*"""|"""\s*$', "", (c.get("class_description") or "").strip()).strip()
    goal = (f"Build a class called `{c['class_name']}`.\n\n{desc}\n\n"
            "Write the result as `solution.py` in this directory.\n")
    contract = ("The module `solution.py` must define this class. Keep every name "
                "and signature exactly as written; replace each `pass` with a real "
                "implementation:\n\n```python\n" + c["skeleton"].rstrip() + "\n```\n")
    good = c["solution_code"]
    bads = {"bad_skeleton.py": c["skeleton"]}
    for nm, val in (("bad_none.py", "None"), ("bad_empty.py", "''")):
        s = _stub_bodies(good, val)
        if s:
            bads[nm] = s
    nm2 = mutant_negate(good)
    if nm2:
        bads["bad_negate.py"] = nm2
    return {
        "template": {"goal.md": goal, "contract.md": contract,
                     "run_tests.sh": BS.run_tests_sh_text(),
                     "tests_visible/test_visible.py": BS.render_unittest_file(
                         header=BS.HEADER_VISIBLE, preamble="", classes=vis_cls, import_line=imp)},
        "hidden": {"test_hidden.py": BS.render_unittest_file(
            header=BS.HEADER_HIDDEN, preamble="", classes=hid_cls, import_line=imp)},
        "gauge": {"good.py": good, **bads},
        "counts": {"visible": sum(len(x["tests"]) for x in vis_cls),
                   "hidden": sum(len(x["tests"]) for x in hid_cls)},
    }


_LCB_CASE = '''

def _case(args, expected):
    got = solution.{entry}(*args)
    assert got == expected, "args=%r got=%r want=%r" % (args, got, expected)
'''


def _lcb_file(header: str, entry: str, cases: list[dict], tag: str) -> str:
    out = [header, "import solution\n", _LCB_CASE.format(entry=entry)]
    for i, c in enumerate(cases, 1):
        out.append(f"\n\ndef check_{tag}{i:02d}():\n"
                   f"    _case({c['args']!r}, {c['expected']!r})\n")
    return "".join(out)


def render_pba(row: dict, sol: str) -> dict:
    entry = row["entry_point"]
    vis, hid = row["visible_tests"], row["hidden_tests"]
    arity = len(vis[0]["args"]) if vis else 1
    goal = (BS.clip_text(row.get("prompt") or "", BS.GOAL_MAX_CHARS)
            + "\n\nWrite the result as `solution.py` in this directory.\n")
    contract = (f"The module `solution.py` must define a module-level function "
                f"`{entry}` taking {arity} positional argument(s) and returning the "
                f"answer. It is called directly as `solution.{entry}(...)`; nothing "
                f"is read from stdin and nothing is printed.\n")
    bads = {"bad_none.py": f"def {entry}(*args, **kwargs):\n    return None\n",
            "bad_zero.py": f"def {entry}(*args, **kwargs):\n    return 0\n"}
    if vis:
        bads["bad_const.py"] = (f"def {entry}(*args, **kwargs):\n"
                                f"    return {vis[0]['expected']!r}\n")
    nm = mutant_negate(sol)
    if nm:
        bads["bad_negate.py"] = nm
    return {
        "template": {"goal.md": goal, "contract.md": contract,
                     "run_tests.sh": BS.run_tests_sh_text(),
                     "tests_visible/test_visible.py": _lcb_file(BS.HEADER_VISIBLE, entry, vis, "v")},
        "hidden": {"test_hidden.py": _lcb_file(BS.HEADER_HIDDEN, entry, hid, "h")},
        "gauge": {"good.py": sol, **bads},
        "counts": {"visible": len(vis), "hidden": len(hid)},
    }


#: `pbd` 走 stdin/stdout ⇒ 測試用 subprocess 跑 `solution.py`。
#: **不 import solution**：那會在 import 的瞬間執行它，而一支讀 stdin 的
#: 程式會就地卡住。`find_spec` 只定位不執行。
_CC_PRE = '''
import importlib.util as _ilu
import subprocess
import sys

_spec = _ilu.find_spec("solution")
assert _spec is not None and _spec.origin, "solution.py was not found"
_SCRIPT = _spec.origin


def _norm(s):
    return "\\n".join(ln.rstrip() for ln in (s or "").strip().splitlines())


def _case(stdin_text, expected):
    p = subprocess.run([sys.executable, _SCRIPT], input=stdin_text,
                       capture_output=True, text=True, timeout=8)
    assert p.returncode == 0, "stdin=%r got=exit %d (stderr %r) want=exit 0" % (
        stdin_text, p.returncode, (p.stderr or "")[-300:])
    got, want = _norm(p.stdout), _norm(expected)
    assert got == want, "stdin=%r got=%r want=%r" % (stdin_text, got, want)
'''


def _cc_file(header: str, cases: list[tuple[str, str]], tag: str) -> str:
    out = [header, _CC_PRE]
    for i, (inp, exp) in enumerate(cases, 1):
        out.append(f"\n\ndef check_{tag}{i:02d}():\n    _case({inp!r}, {exp!r})\n")
    return "".join(out)


def render_pbd(row: dict) -> dict:
    s = row["solutions"]
    py3 = sorted((so for lg, so in zip(s["language"], s["solution"]) if lg == 3 and len(so) < 8000),
                 key=lambda x: (len(x), x))
    pub = row["public_tests"]
    vis = [(i, o) for i, o in zip(pub["input"], pub["output"])
           if len(i) + len(o) <= BS.MAX_CASE_CHARS]
    pool = [(i, o) for src in ("private_tests", "generated_tests")
            for i, o in zip((row.get(src) or {}).get("input", []),
                            (row.get(src) or {}).get("output", []))
            if len(i) + len(o) <= BS.MAX_CASE_CHARS]
    hid = sorted(pool, key=lambda t: (len(t[0]), t[0]))[:BS.PBD_MAX_HIDDEN]
    goal = (f"# {row['name']}\n\n" + BS.clip_text(row.get("description") or "", BS.GOAL_MAX_CHARS)
            + "\n\nWrite the result as `solution.py` in this directory.\n")
    contract = ("`solution.py` is run as a script: `python3 solution.py`. It reads the "
                "whole problem input from standard input and writes the answer to "
                "standard output. It must exit with status 0. Trailing whitespace on a "
                "line and a trailing newline at the end are ignored when comparing.\n")
    return {
        "template": {"goal.md": goal, "contract.md": contract,
                     "run_tests.sh": BS.run_tests_sh_text(),
                     "tests_visible/test_visible.py": _cc_file(BS.HEADER_VISIBLE, vis, "v")},
        "hidden": {"test_hidden.py": _cc_file(BS.HEADER_HIDDEN, hid, "h")},
        "gauge": {"good.py": py3[0],
                  "bad_silent.py": "import sys\nsys.stdin.read()\n",
                  "bad_zero.py": "import sys\nsys.stdin.read()\nprint(0)\n",
                  "bad_echo.py": "import sys\nsys.stdout.write(sys.stdin.read())\n"},
        "counts": {"visible": len(vis), "hidden": len(hid)},
    }


# ══════════════════════ 落盤 ═══════════════════════════════════════════════
def _write_tree(root: pathlib.Path, files: dict[str, str]) -> int:
    if root.exists():
        shutil.rmtree(root)
    total = 0
    for rel, text in sorted(files.items()):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        blob = text if text.endswith("\n") else text + "\n"
        p.write_text(blob, encoding="utf-8")
        total += len(blob.encode("utf-8"))
    return total


def _load_family_rows(fam: str) -> dict:
    if fam == "pbf":
        return {r["task_id"]: r for r in _read_jsonl(PRIV / "bigcodebench" / "v0.1.4.jsonl")}
    if fam == "pbc":
        return {c["task_id"]: c for c in
                json.loads((PRIV / "classeval" / "ClassEval_data.json").read_text(encoding="utf-8"))}
    if fam == "pba":
        return {r["task_id"]: r for r in _read_jsonl(REPO / "ops/gain/data/lcb_bank_v3.jsonl")}
    return {r["name"]: r for r in _read_jsonl(PRIV / "codecontests" / "test.jsonl")}


def cmd_render(args) -> int:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    lcb_sols = json.loads((REPO / "ops/gain/data/lcb_v3_probe_solutions.json").read_text(encoding="utf-8"))
    all_ids: list[str] = []
    for fam in BS.FAMILIES:
        rows = _load_family_rows(fam)
        entry = man["families"][fam]
        tasks, dropped = [], []
        for i, sid in enumerate(entry["source_ids"], 1):
            row = rows.get(sid)
            if row is None:
                dropped.append({"source_id": sid, "why": "來源列不見了（題庫漂了）"}); continue
            try:
                if fam == "pbf":
                    r = render_pbf(row)
                elif fam == "pbc":
                    r = render_pbc(row)
                elif fam == "pba":
                    r = render_pba(row, lcb_sols[sid])
                else:
                    r = render_pbd(row)
            except Exception as e:                          # noqa: BLE001
                dropped.append({"source_id": sid, "why": f"{type(e).__name__}: {e}"}); continue
            if r["counts"]["visible"] < 1 or r["counts"]["hidden"] < 1:
                dropped.append({"source_id": sid, "why": f"切出來是 {r['counts']}"}); continue
            tid = _tid(fam, i, sid)
            nb = _write_tree(TPL / tid, r["template"])
            if not (200 <= nb <= BS.TEMPLATE_MAX_BYTES):
                shutil.rmtree(TPL / tid)
                dropped.append({"source_id": sid, "why": f"樣板 {nb} B 超出 200–30720"}); continue
            _write_tree(HID / tid, r["hidden"])
            _write_tree(GAU / tid, r["gauge"])
            tasks.append({"task_id": tid, "source_id": sid, "template_bytes": nb,
                          "visible_cases": r["counts"]["visible"],
                          "hidden_cases": r["counts"]["hidden"],
                          "gauge_bad_n": len([k for k in r["gauge"] if k.startswith("bad_")])})
            all_ids.append(tid)
        entry["tasks"] = tasks
        entry["dropped"] = dropped
        entry["rendered_n"] = len(tasks)
        #: **`rendered_ids` 是 finalize 的唯一輸入，而且 finalize 不准改它。**
        #: 理由是冪等：finalize 會把 `tasks` 砍成留下來的那些，
        #: 所以拿 `tasks` 當輸入的話**跑第二次會再砍一輪**（2026-09-17 實測踩到：
        #: 同一條 ssh 指令被執行兩次，pbf 從 50→25→25 看起來正常，
        #: 但 pba 的 12→9 之後第二輪就再也看不到那 3 題為什麼被裁）。
        entry["rendered_ids"] = [t["task_id"] for t in tasks]
        vc = [t["visible_cases"] for t in tasks]
        hc = [t["hidden_cases"] for t in tasks]
        entry["case_stats"] = {
            "visible_total": sum(vc), "hidden_total": sum(hc),
            "visible_median": sorted(vc)[len(vc) // 2] if vc else 0,
            "hidden_median": sorted(hc)[len(hc) // 2] if hc else 0,
            "visible_min": min(vc) if vc else 0, "hidden_min": min(hc) if hc else 0}
        print(f"[{fam}] rendered {len(tasks)}  dropped {len(dropped)}  "
              f"visible median {entry['case_stats']['visible_median']}  "
              f"hidden median {entry['case_stats']['hidden_median']}")
        for d in dropped:
            print(f"    drop {d['source_id']}: {d['why'][:110]}")
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TASKLIST.write_text(json.dumps(
        {"name": "r531_main", "tasks": sorted(all_ids)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"\n{len(all_ids)} tasks → {TASKLIST}")
    return 0


def cmd_clean(args) -> int:
    n = 0
    for base in (TPL, HID, GAU):
        for p in sorted(base.glob("pb[fcad]_*")):
            shutil.rmtree(p); n += 1
    print(f"removed {n} generated dirs")
    return 0


def cmd_check(args) -> int:
    """載入每一題（走 R530 自己的 `tasks.load_task`）＋ 印逐族統計。零模型呼叫。"""
    from ops.gain.r530 import tasks as taskmod
    ids = json.loads(TASKLIST.read_text(encoding="utf-8"))["tasks"]
    loaded = taskmod.load_tasks(",".join(ids))
    man = taskmod.bank_manifest(loaded)
    by: dict[str, list] = {}
    for t in loaded:
        by.setdefault(t["task_id"].split("_")[0], []).append(t)
    for fam, ts in sorted(by.items()):
        print(f"{fam}: {len(ts)} 題  樣板 {min(t['template_bytes'] for t in ts)}–"
              f"{max(t['template_bytes'] for t in ts)} B")
    print(f"\nbank _root_sha256 = {man['_root_sha256']}")
    out = REPO / "ops" / "gain" / "r531" / "bank_sha256.json"
    out.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"bank sha 表 → {out}")
    return 0


def cmd_finalize(args) -> int:
    """讀量具結果，**只留合格的題**，每族取前 `TARGET_N` 個。零模型呼叫。

    合格 ＝ `TASK_FORMAT.md` §七 既有的三條，一條都沒有放寬：
      1. `good.py` **全過**可見與隱藏（不全過＝驗收與契約對不起來，那是題目壞了）；
      2. **每一個** `bad_*.py` 都被隱藏驗收擋下來（有一個沒擋＝隱藏套件有洞）；
      3. 壞樁數 ≥ 3。

    ⚠ 淘汰名單**逐題落盤**在 `manifest.families[fam].finalize.dropped`，
      連同它是哪一條不過。**不准只報留下來的那些**——被裁掉的比例本身
      就是「公開題庫轉進本格式有多順」的量測值。
    """
    g = json.loads(pathlib.Path(args.gauge).read_text(encoding="utf-8"))
    verdict: dict[str, dict] = {}
    for r in g["tasks"]:
        good = r.get("good") or {}
        vis, hid = good.get("visible") or {}, good.get("hidden") or {}
        bads = r.get("bad") or []
        unblocked = [b.get("stub") for b in bads if not b.get("blocked")]
        why = []
        if not (vis.get("all_pass") and hid.get("all_pass")):
            why.append(f"good 沒全過 visible={vis.get('passed')}/{vis.get('total')} "
                       f"hidden={hid.get('passed')}/{hid.get('total')}")
        if unblocked:
            why.append(f"壞樁沒被擋：{','.join(str(x) for x in unblocked)}")
        if len(bads) < 3:
            why.append(f"壞樁只有 {len(bads)} 個（要 ≥3）")
        verdict[r["task_id"]] = {"ok": not why, "why": "；".join(why)}

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    keep_all: list[str] = []
    for fam in BS.FAMILIES:
        entry = man["families"][fam]
        rendered = entry.get("rendered_ids") or [t["task_id"] for t in entry.get("tasks", [])]
        ok = [t for t in rendered if verdict.get(t, {}).get("ok")]
        keep = ok[:BS.TARGET_N[fam]]
        drop = [t for t in rendered if t not in keep]
        entry["finalize"] = {
            "gauge_pass_n": len(ok), "rendered_n": len(rendered),
            "kept_n": len(keep), "target_n": BS.TARGET_N[fam],
            "short_of_target": max(0, BS.TARGET_N[fam] - len(keep)),
            "kept": keep,
            "dropped": [{"task_id": t,
                         "why": verdict.get(t, {}).get("why") or "超出目標題數（量具過了但用不到）"}
                        for t in drop]}
        for t in drop:
            for base in (TPL, HID, GAU):
                if (base / t).exists():
                    shutil.rmtree(base / t)
        entry["tasks"] = [x for x in entry.get("tasks", []) if x["task_id"] in set(keep)]
        keep_all += keep
        flag = "  ⚠ 不足目標" if len(keep) < BS.TARGET_N[fam] else ""
        print(f"[{fam}] 量具過 {len(ok)}/{len(rendered)} → 留 {len(keep)}/{BS.TARGET_N[fam]}{flag}")
        for d in entry["finalize"]["dropped"]:
            if "超出目標題數" not in d["why"]:
                print(f"    drop {d['task_id']}: {d['why'][:120]}")
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TASKLIST.write_text(json.dumps({"name": "r531_main", "tasks": sorted(keep_all)},
                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n最終 {len(keep_all)} 題 → {TASKLIST}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="R531 題庫建置（零模型呼叫）")
    sub = ap.add_subparsers(dest="stage", required=True)
    sub.add_parser("select")
    sub.add_parser("render")
    sub.add_parser("clean")
    sub.add_parser("check")
    fz = sub.add_parser("finalize")
    fz.add_argument("--gauge", required=True, help="`gauge.py --json` 的輸出")
    args = ap.parse_args()
    return {"select": cmd_select, "render": cmd_render, "clean": cmd_clean,
            "check": cmd_check, "finalize": cmd_finalize}[args.stage](args)


if __name__ == "__main__":
    raise SystemExit(main())
