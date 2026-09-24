#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BigCodeBench-Hard 題庫渲染：把 `bigcode/bigcodebench-hard` v0.1.4 投影成
R534 同形狀的 `templates/`＋`hidden/` 兩棵樹。

這支在架構裡承重什麼
--------------------
R534 的題庫（LCB v2 選 20 題）有兩個已知的弱點：題目是純演算法（只准標準函式庫），
而且**沒有參考解**，正控制只有 1/20（`ops/gain/r534/BANK_README.md` §五）。
BigCodeBench-Hard 補的正是這兩格：題目要用真實函式庫（pandas／matplotlib／
sklearn／requests…）做事，而且**每一題都有 canonical_solution** ⇒
r530 的雙向量具（參考解全過／退化樁被擋）在這裡做得到，由 `gauge_bank.py` 量。

形狀逐字沿用 R534（`ops/gain/r534/build_bank.py`）：

    <out>/templates/<id>/                  ← 工作區樣板（agent 看得到全部）
        goal.md                    ＝ 題庫 `instruct_prompt` 逐位元組
        contract.md                介面釘死（檔名／函式名／imports／可用函式庫）
        tests_visible/test_visible.py   可見驗收（＝出貨閘門）
        run_tests.sh               ＝ R534 的 RUN_TESTS_SH 逐字

    <out>/hidden/<id>/                     ← **另一棵樹**，永遠不進工作區
        test_hidden.py             TestCases 的**全部**方法（可見 ∪ 隱藏）

可見／隱藏怎麼切（確定性，寫進 render_manifest.json）
----------------------------------------------------
上游只有一個 `TestCases`，沒有可見／隱藏之分——**切法是我們定的，不是官方的**。
規則：`TestCases` 裡名字以 `test` 開頭的方法（＝ unittest 預設 loader 會收的那些），
依方法名**字典序**排序，取前 ⌈n/3⌉ 個（至少 1 個）當可見；隱藏檔收全部 n 個。
148 題的 n 落在 3–12，沒有 n=1 的題（若有，可見＝隱藏，照實記）。

可見檔**只含可見的那幾個方法的原始碼**：其餘 test 方法（連同它們的 decorator 與
緊貼在上方的註解行）以**行區間**從原文刪掉，其餘位元組照抄——所以隱藏方法的內容
不會出現在工作區。`setUp`／`tearDown`／其他非 test 方法與模組層級程式碼整份保留
（它們是兩邊共用的基礎設施；若某個 helper 只被隱藏方法用到，它會連帶出現在可見檔，
這是已知的小洩漏，README 誠實邊界有寫）。

測試檔的形狀
------------
    from solution import *           ← BigCodeBench 的測試假設與解答同一個命名空間
    sys.modules.setdefault(__name__, solution)   ← 讓 patch(__name__ + '.x') 打到解答（見 NAMESPACE_SHIM）
    <上游 test 原文（可見檔：刪掉非可見方法；隱藏檔：整份）>
    <清掉命名空間裡所有 check_* 名字>  ← 見下
    def check_<method>(): _vacant_run("<method>")   ← 每個選中的方法一個

`_vacant_run` 用 `unittest.TestSuite([TestCases(m)]).run(unittest.TestResult())`
跑那一個方法（含 setUp／tearDown／setUpClass），`wasSuccessful() and testsRun == 1`
才算過，否則 `raise AssertionError(<精簡訊息>)`。跑法與 BigCodeBench 官方評測
（`TestResult` ＋ `suite.run`，skip 不算失敗）一致。

⚠ **為什麼要清 `check_*`**：`acceptance.py` 的 driver 收的是模組裡**所有**
`check_` 開頭的 callable。`from solution import *` 會把 agent 自己寫的 helper
（例如 `def check_input(x)`）一起帶進來，driver 會零引數呼叫它 ⇒ TypeError ⇒
一份正確的解被判失敗。清掉之後才定義我們自己的 `check_*`。上游 test 原文若自己
在模組層級定義 `check_*` 名字，這支會 fail-closed（148 題實測沒有）。

排除（渲染前，具名）
--------------------
`POLICY_EXCLUDE`：用到 tensorflow／keras 的題（~2GB，超出 vacant-dev 4G 磁碟預算）。
其餘的排除由 `gauge_bank.py` 依實測決定（參考解過不了／樁沒被擋）。

用法（在 vacant-dev，用 venv 的 python——讀 parquet 需要 pyarrow）
--------------------------------------------------------------
    venv/bin/python build_bank.py --parquet raw/bcb_hard_v0.1.4.parquet --out bank
    venv/bin/python build_bank.py --parquet ... --out bank --check   # 驗磁碟沒漂
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import shutil
import sys

DATASET = "bigcode/bigcodebench-hard"
SPLIT = "v0.1.4"
#: 原始檔：HF repo 裡的 `data/v0.1.4-00000-of-00001.parquet`（LFS oid＝sha256）。
SOURCE_URL = ("https://huggingface.co/datasets/bigcode/bigcodebench-hard/resolve/"
              "main/data/v0.1.4-00000-of-00001.parquet")
#: 2026-09-24 下載時 HF API 回的 repo commit（lastModified 2025-02-23T16:42:46Z）。
SOURCE_REPO_SHA = "298d2cc7b96612e15e47313c3603ee124cee0c1f"
#: 釘死。讀到的檔案不是這個雜湊 ⇒ 停（fail-closed，不是安靜地換一份題庫）。
PARQUET_SHA256 = "73a4270b43feb81abefad7bb1b592937c768ea45c3263bedc1cabd30a9a6ce79"
N_EXPECTED = 148

#: 渲染前就排除的題（具名＋理由）。**只放「環境政策」決定的**，
#: 實測決定的排除一律交給 gauge_bank.py，不在這裡預判。
POLICY_EXCLUDE = {
    "BigCodeBench/417": "用 keras（Sequential／SGD）訓練模型；keras 2.11 需要 tensorflow 後端，"
                        "tensorflow 未安裝（~2GB，超出 vacant-dev 4G 磁碟預算）",
    "BigCodeBench/418": "用 tensorflow.keras 訓練模型；tensorflow 未安裝"
                        "（~2GB，超出 vacant-dev 4G 磁碟預算）",
}

SPLIT_RULE = ("TestCases 中名字以 'test' 開頭的方法（unittest 預設 loader 收的那些），"
              "依方法名字典序（Python sorted，str 比較）排序，取前 ceil(n/3) 個"
              "（至少 1 個）為可見；隱藏檔收全部 n 個（可見 ∪ 隱藏）。"
              "n=1 時可見＝隱藏。")

# R534 的 run_tests.sh（`ops/gain/r534/build_bank.py::RUN_TESTS_SH`）逐字。
RUN_TESTS_SH = """#!/bin/sh
# Run the checks that ship with this task against the current directory.
# Each check_* function in tests_visible/ is run; failures are printed.
exec python3 - "$@" <<'PY'
import importlib.util, os, sys, traceback
sys.path.insert(0, os.getcwd())
failed = 0
d = os.path.join(os.getcwd(), "tests_visible")
for name in sorted(os.listdir(d)):
    if not (name.startswith("test_") and name.endswith(".py")):
        continue
    path = os.path.join(d, name)
    spec = importlib.util.spec_from_file_location("vis_" + name[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        failed += 1
        print("%s: could not be imported" % name)
        traceback.print_exc()
        continue
    checks = [(n, v) for n, v in vars(mod).items()
              if n.startswith("check_") and callable(v)]
    if not checks:
        main = getattr(mod, "main", None)
        checks = [("main", main)] if callable(main) else []
    for cname, fn in checks:
        try:
            fn()
        except Exception as e:
            failed += 1
            print("FAIL %s::%s  %s: %s" % (name, cname, type(e).__name__, e))
        else:
            print("pass %s::%s" % (name, cname))
print("%d check(s) failed" % failed)
sys.exit(1 if failed else 0)
PY
"""

# 每個測試檔尾端的包裝。名字一律 `_vacant_` 開頭，避開上游 test 原文的名字。
WRAPPER = '''

# ── Vacant wrapper (generated by build_bank.py) ──────────────────────────
# Each check_* below runs exactly one TestCases method (with its setUp /
# tearDown) and raises AssertionError with a short message if it fails.
import unittest as _vacant_unittest

for _vacant_name in [_n for _n in list(globals()) if _n.startswith("check_")]:
    del globals()[_vacant_name]


def _vacant_short(tb_text, limit=700):
    lines = (tb_text or "").rstrip().splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.startswith("  File ")]
    tail = lines[idx[-1] + 2:] if idx and idx[-1] + 2 < len(lines) else lines[-3:]
    tail = [ln for ln in tail if ln.strip() and set(ln.strip()) - set("^~")]
    msg = "\\n".join(tail).strip()
    if len(msg) > limit:
        msg = msg[: limit // 2] + " ...[cut]... " + msg[-(limit // 2):]
    return msg


def _vacant_run(method_name):
    suite = _vacant_unittest.TestSuite([TestCases(method_name)])
    result = _vacant_unittest.TestResult()
    suite.run(result)
    if result.wasSuccessful() and result.testsRun == 1:
        return
    if result.failures:
        kind, tb = "FAIL", result.failures[0][1]
    elif result.errors:
        kind, tb = "ERROR", result.errors[0][1]
    elif result.unexpectedSuccesses:
        kind, tb = "UNEXPECTED SUCCESS", ""
    else:
        kind, tb = "NOT RUN", ""
    raise AssertionError("%s %s: %s" % (kind, method_name, _vacant_short(tb)))

'''


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def dir_name(task_id: str) -> str:
    """`BigCodeBench/13` → `bcb_13`（檔名安全、與 `lcb_3522` 同形）。"""
    prefix, num = task_id.split("/")
    assert prefix == "BigCodeBench" and num.isdigit(), task_id
    return f"bcb_{num}"


def load_rows(parquet: str) -> list[dict]:
    raw = open(parquet, "rb").read()
    got = sha256_bytes(raw)
    if got != PARQUET_SHA256:
        raise SystemExit(f"parquet sha256 不符：{got} ≠ 釘死的 {PARQUET_SHA256}。停。")
    import pyarrow.parquet as pq  # 只有 venv 裡有
    rows = pq.read_table(parquet).to_pylist()
    if len(rows) != N_EXPECTED:
        raise SystemExit(f"題數 {len(rows)} ≠ {N_EXPECTED}。停。")
    return rows


def parse_libs(s: str) -> list[str]:
    v = ast.literal_eval(s)
    assert isinstance(v, list) and all(isinstance(x, str) for x in v), s
    return v


def test_methods(test_src: str) -> tuple[ast.ClassDef, list[ast.FunctionDef]]:
    tree = ast.parse(test_src)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TestCases"]
    if len(classes) != 1:
        raise SystemExit(f"找不到唯一的 TestCases（{len(classes)} 個）。停。")
    # 上游 test 原文不准在模組層級定義 check_*（會被我們的清除步驟誤刪）。
    for n in tree.body:
        names = []
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [n.name]
        elif isinstance(n, ast.Assign):
            names = [t.id for t in n.targets if isinstance(t, ast.Name)]
        if any(x.startswith("check_") for x in names):
            raise SystemExit(f"test 原文在模組層級定義了 check_*：{names}。停。")
    cls = classes[0]
    meths = [n for n in cls.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")]
    return cls, meths


def split_methods(names: list[str]) -> list[str]:
    s = sorted(names)
    k = max(1, math.ceil(len(s) / 3))
    return s[:k]


def strip_methods(test_src: str, cls: ast.ClassDef, drop: list[ast.FunctionDef]) -> str:
    """以行區間刪掉 `drop` 裡的方法（含 decorator 與緊貼上方的註解／空行）。其餘位元組照抄。"""
    lines = test_src.splitlines(keepends=True)
    kill = set()
    body_nodes = sorted(cls.body, key=lambda n: n.lineno)
    for node in drop:
        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
        end = node.end_lineno
        # 往上吃掉緊貼的註解行／空行，但不越過前一個 class-body 節點或 class 標頭。
        prev_end = cls.lineno
        for other in body_nodes:
            o_end = other.end_lineno or other.lineno
            if o_end < start and other is not node:
                prev_end = max(prev_end, o_end)
        j = start - 1  # 1-based 行號 → 往上看的那一行
        while j > prev_end:
            t = lines[j - 1].strip()
            if t == "" or t.startswith("#"):
                j -= 1
            else:
                break
        for ln in range(j + 1, end + 1):
            kill.add(ln)
    out = "".join(l for i, l in enumerate(lines, start=1) if i not in kill)
    return out


#: `from solution import *` 之後緊接的三行。BigCodeBench 官方把解答與測試 exec 在
#: **同一個**模組裡並註冊進 sys.modules，所以上游測試可以寫
#: `@patch(__name__ + '.randint')` 去改解答用到的名字（BigCodeBench/593）。
#: acceptance 的 driver 用 spec_from_file_location 載入測試檔、**不註冊** sys.modules
#: ⇒ `__name__` 那個模組 import 不到。這裡把 `solution` 模組登記在 `__name__` 底下：
#: patch 目標因此落在 task_func 真正查找的命名空間，與官方語意一致。
#: `setdefault`：若將來 driver 自己註冊了，就不蓋掉。其餘 145 題的測試不用 `__name__`，
#: 這三行對它們沒有作用。
NAMESPACE_SHIM = ("import sys as _vacant_sys\n"
                  "import solution as _vacant_solution\n"
                  "_vacant_sys.modules.setdefault(__name__, _vacant_solution)\n")


def render_test_file(header: str, test_src: str, methods: list[str]) -> str:
    body = test_src if test_src.endswith("\n") else test_src + "\n"
    checks = "".join(f"\ndef check_{m}():\n    _vacant_run({m!r})\n" for m in methods)
    return header + "from solution import *\n" + NAMESPACE_SHIM + "\n" + body + WRAPPER + checks


def render_task(r: dict) -> tuple[dict[str, str], dict]:
    tid = r["task_id"]
    d = dir_name(tid)
    libs = parse_libs(r["libs"])
    if r["entry_point"] != "task_func":
        raise SystemExit(f"{tid} entry_point={r['entry_point']!r}，不是 task_func。停。")
    cls, meths = test_methods(r["test"])
    # 重名方法：Python 以最後一個定義為準，unittest 也只跑那一個 ⇒ 名字去重即為
    # 實際會跑的方法集合。可見的名字保留它的所有定義（前面被遮蔽的是死碼，與上游
    # 一致）；非可見的名字連同所有定義一起刪。
    all_names = sorted(set(m.name for m in meths))
    dup = sorted(n for n in all_names if sum(1 for m in meths if m.name == n) > 1)
    visible = split_methods(all_names)
    drop = [m for m in meths if m.name not in visible]
    vis_src = strip_methods(r["test"], cls, drop)
    # 驗：刪完之後仍可 parse，且剩下的 test 方法恰好是可見那一組。
    _, left = test_methods(vis_src)
    if sorted(set(m.name for m in left)) != sorted(visible):
        raise SystemExit(f"{tid} 刪方法後剩下 {[m.name for m in left]} ≠ 可見 {visible}。停。")
    hidden_sorted = sorted(all_names)

    vis_header = (
        f'"""Visible checks for {d} -- these ship with the task and can be run.\n\n'
        f"Rendered from {DATASET} {SPLIT} ({tid}) by\n"
        "ops/vacantrun/bcb_hard_bank_20260924/build_bank.py. The code below is the\n"
        "dataset's unittest TestCases, restricted to the test methods that ship with\n"
        "this task; each check_* runs one of those methods.\n"
        '"""\n\n'
    )
    hid_header = (
        f'"""Scoring checks for {d} -- NOT part of any workspace.\n\n'
        "This file lives in a separate tree and is never copied into an agent's\n"
        "workspace. It runs every test method of the dataset's TestCases\n"
        f"({DATASET} {SPLIT}, {tid}): the visible ones plus the rest.\n"
        '"""\n\n'
    )
    third_party = [x for x in libs if x not in sys.stdlib_module_names]
    stdlib = [x for x in libs if x in sys.stdlib_module_names]
    lib_line = ", ".join(f"`{x}`" for x in third_party) if third_party else "(none beyond the standard library)"
    std_line = ", ".join(f"`{x}`" for x in stdlib) if stdlib else "-"
    code_prompt = r["code_prompt"] if r["code_prompt"].endswith("\n") else r["code_prompt"] + "\n"
    contract = (
        "# Contract\n\n"
        "Write your answer in `solution.py` at the root of this workspace.\n\n"
        "- Define a top-level function named `task_func`. Not a method, not a class.\n"
        "- Keep the imports and the signature exactly as the task gives them.\n"
        "  `solution.py` should start with:\n\n"
        + "".join("      " + ln if ln.strip() else ln for ln in code_prompt.splitlines(keepends=True))
        + "\n"
        f"- Installed third-party libraries this task uses: {lib_line}.\n"
        f"  Standard-library modules it uses: {std_line}. The rest of the standard\n"
        "  library is available too. Do not install packages.\n"
        "- Do not rely on network access.\n"
        "- The checks load your module with `from solution import *` and call\n"
        "  `task_func` the way the task statement describes. Names you define in\n"
        "  `solution.py` that start with `check_` are ignored by the checks.\n\n"
        "The checks that ship with this task are in `tests_visible/`. Run them with:\n\n"
        "    sh run_tests.sh\n\n"
        "Each failure prints `FAIL` or `ERROR`, the test name, and the end of the\n"
        "error message.\n"
    )
    files = {
        f"templates/{d}/goal.md": r["instruct_prompt"],
        f"templates/{d}/contract.md": contract,
        f"templates/{d}/tests_visible/test_visible.py": render_test_file(vis_header, vis_src, visible),
        f"templates/{d}/run_tests.sh": RUN_TESTS_SH,
        f"hidden/{d}/test_hidden.py": render_test_file(hid_header, r["test"], hidden_sorted),
    }
    reference = r["complete_prompt"] + "\n" + r["canonical_solution"]
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)  # 上游 regex 字串的無效跳脫，不影響執行
        compile(reference, f"{d}/reference.py", "exec")
    info = {
        "task_id": tid,
        "dir": d,
        "libs": libs,
        "third_party_libs": third_party,
        "n_methods_total": len(all_names),
        "n_visible": len(visible),
        "n_hidden_only": len(all_names) - len(visible),
        "visible_methods": visible,
        "hidden_file_methods": hidden_sorted,
        "duplicate_method_names": dup,
        "reference_solution_sha256": sha256_bytes(reference.encode("utf-8")),
        "test_upstream_sha256": sha256_bytes(r["test"].encode("utf-8")),
        "files_sha256": {k: sha256_bytes(v.encode("utf-8")) for k, v in files.items()},
    }
    return files, info


def reference_solution(r: dict) -> str:
    """BigCodeBench 官方組法：complete_prompt ＋ "\\n" ＋ canonical_solution。"""
    return r["complete_prompt"] + "\n" + r["canonical_solution"]


def build(parquet: str, out: str, check_only: bool) -> int:
    rows = load_rows(parquet)
    rows.sort(key=lambda r: int(r["task_id"].split("/")[1]))
    all_files: dict[str, str] = {}
    tasks, excluded = [], []
    for r in rows:
        if r["task_id"] in POLICY_EXCLUDE:
            excluded.append({"task_id": r["task_id"], "dir": dir_name(r["task_id"]),
                             "stage": "policy", "reason": POLICY_EXCLUDE[r["task_id"]],
                             "libs": parse_libs(r["libs"])})
            continue
        files, info = render_task(r)
        leak = [k for k in files if k.startswith("templates/") and "hidden" in k.lower()]
        if leak:
            raise SystemExit(f"{r['task_id']} 的樣板路徑出現 hidden 字樣：{leak}。停。")
        all_files.update(files)
        tasks.append(info)
    manifest = {
        "bank": "bcb_hard_20260924",
        "dataset": DATASET, "split": SPLIT, "source_url": SOURCE_URL,
        "source_repo_sha": SOURCE_REPO_SHA, "parquet_sha256": PARQUET_SHA256,
        "n_upstream": len(rows), "n_rendered": len(tasks),
        "split_rule": SPLIT_RULE,
        "split_rule_sha256": sha256_bytes(SPLIT_RULE.encode("utf-8")),
        "reference_solution_rule": "complete_prompt + '\\n' + canonical_solution（BigCodeBench 官方組法）",
        "stub_solution": "def task_func(*a, **k): return None",
        "policy_excluded": excluded,
        "tasks": tasks,
    }
    if check_only:
        # 量具 --prune 之後，題庫只留可用題：以 bank_manifest.json 的 usable_dirs 為準，
        # 並驗磁碟上的題目目錄恰好是那一組（多一題、少一題都算漂）。
        bm = os.path.join(out, "bank_manifest.json")
        if os.path.isfile(bm):
            usable = set(json.load(open(bm, encoding="utf-8"))["usable_dirs"])
            for sub in ("templates", "hidden"):
                on_disk = set(os.listdir(os.path.join(out, sub)))
                if on_disk != usable:
                    print(f"{sub}/ 的題目目錄 ≠ usable_dirs：多 {sorted(on_disk - usable)[:5]} "
                          f"少 {sorted(usable - on_disk)[:5]}")
                    return 1
            all_files = {k: v for k, v in all_files.items() if k.split("/")[1] in usable}
        bad = []
        for rel, content in all_files.items():
            p = os.path.join(out, rel)
            if not os.path.isfile(p) or open(p, encoding="utf-8").read() != content:
                bad.append(rel)
        if bad:
            print(f"漂了 {len(bad)} 個檔：{bad[:10]}")
            return 1
        print(f"OK：{len(all_files)} 個檔與渲染結果逐位元組相同")
        return 0
    for sub in ("templates", "hidden"):
        shutil.rmtree(os.path.join(out, sub), ignore_errors=True)
    for rel, content in sorted(all_files.items()):
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        if rel.endswith(".sh"):
            os.chmod(p, 0o755)
    # 參考解另外放一棵樹（只給量具用；不是題庫的一部分，也不進工作區）。
    refdir = os.path.join(out, "..", "reference")
    shutil.rmtree(refdir, ignore_errors=True)
    for r in rows:
        if r["task_id"] in POLICY_EXCLUDE:
            continue
        p = os.path.join(refdir, dir_name(r["task_id"]), "solution.py")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(reference_solution(r))
    with open(os.path.join(out, "render_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"渲染 {len(tasks)} 題（政策排除 {len(excluded)}）→ {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    return build(a.parquet, a.out, a.check)


if __name__ == "__main__":
    raise SystemExit(main())
