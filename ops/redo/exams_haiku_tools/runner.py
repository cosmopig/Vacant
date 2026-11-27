#!/usr/bin/env python3
"""runner — 在 bwrap 沙箱（無網路、唯讀系統、可寫的只有一次性工作目錄）裡用釘版 venv 的 pytest 跑一份考卷對一份解。

run_tests(test_src, solution_src, module) → {"collect_error": bool, "tests": {id: "pass"|"fail"|"skip"}, "timeout": bool, ...}
run_instrumented(exam_src, solution_src, module) → 逐斷言（行號）pass／fail／unreached
"""
from __future__ import annotations

import ast
import json
import os
import pathlib
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

VENV = "/opt/ctl-venv"
TIMEOUT = 30

HELPER = '''
import json, os
def rec(line, state, msg=""):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_rec.jsonl"), "a") as f:
        f.write(json.dumps({"line": line, "state": state, "msg": msg}) + "\\n")
'''


def _bwrap(w: pathlib.Path, argv: list[str]) -> list[str]:
    b = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
         "--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib", "/lib",
         "--ro-bind-try", "/lib64", "/lib64", "--ro-bind", VENV, VENV,
         "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--bind", str(w), "/w", "--chdir", "/w",
         "--setenv", "HOME", "/tmp", "--setenv", "PATH", f"{VENV}/bin:/usr/local/bin:/usr/bin:/bin",
         "--setenv", "PYTHONDONTWRITEBYTECODE", "1", "--setenv", "PYTHONNOUSERSITE", "1",
         "--setenv", "LC_ALL", "C.UTF-8", "--setenv", "PYTHONHASHSEED", "0"]
    return b + argv


def versions() -> dict:
    out = {}
    for name, cmd in [("python", [f"{VENV}/bin/python", "-V"]), ("pytest", [f"{VENV}/bin/python", "-m", "pytest", "--version"]),
                      ("bwrap", ["bwrap", "--version"])]:
        p = subprocess.run(cmd, capture_output=True, text=True)
        out[name] = (p.stdout + p.stderr).strip()
    return out


def _pytest(w: pathlib.Path, test_name: str) -> dict:
    argv = _bwrap(w, [f"{VENV}/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no",
                      "--junitxml=/w/_r.xml", "--no-header", test_name])
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        timeout, tail = False, (p.stdout + p.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        timeout, tail = True, "timeout"
    res = {"collect_error": False, "tests": {}, "timeout": timeout, "tail": tail}
    x = w / "_r.xml"
    try:
        root = ET.parse(x).getroot()
    except (OSError, ET.ParseError):
        res["collect_error"] = True
        return res
    for tc in root.iter("testcase"):
        tid = (tc.get("classname") or "") + "::" + (tc.get("name") or "")
        if tc.find("failure") is not None or tc.find("error") is not None:
            st = "fail"
        elif tc.find("skipped") is not None:
            st = "skip"
        else:
            st = "pass"
        res["tests"][tid] = st
    if not res["tests"]:
        res["collect_error"] = True
    return res


def run_tests(test_src: str, solution_src: str, module: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="ex_run_") as td:
        w = pathlib.Path(td)
        (w / f"{module}.py").write_text(solution_src, encoding="utf-8")
        (w / "exam_test.py").write_text(test_src, encoding="utf-8")
        return _pytest(w, "exam_test.py")


# ---- 逐斷言 -----------------------------------------------------------------
def _is_raises(n: ast.AST) -> bool:
    return isinstance(n, ast.With) and any(
        isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Attribute)
        and i.context_expr.func.attr == "raises" for i in n.items)


class _T(ast.NodeTransformer):
    def __init__(self) -> None:
        self.lines: list[int] = []

    def _wrap(self, node: ast.stmt) -> ast.stmt:
        self.lines.append(node.lineno)
        ln = node.lineno
        tpl = ast.parse(
            "try:\n    pass\nexcept Exception as _vrec_e:\n"
            f"    _vrec_rec({ln}, 'fail', repr(_vrec_e)[:200])\nelse:\n    _vrec_rec({ln}, 'pass')\n").body[0]
        tpl.body = [node]
        return ast.copy_location(tpl, node)

    def visit_Assert(self, node: ast.Assert):  # noqa: N802
        return self._wrap(node)

    def visit_With(self, node: ast.With):  # noqa: N802
        if _is_raises(node):
            return self._wrap(node)
        return self.generic_visit(node)


def instrument(src: str) -> tuple[str, list[int]]:
    tree = ast.parse(src)
    t = _T()
    tree = t.visit(tree)
    ast.fix_missing_locations(tree)
    # `from __future__` 要在最前面：helper import 插在其後
    body = tree.body
    idx = 0
    while idx < len(body) and isinstance(body[idx], ast.ImportFrom) and body[idx].module == "__future__":
        idx += 1
    body.insert(idx, ast.parse("from _vrec import rec as _vrec_rec").body[0])
    return ast.unparse(tree), sorted(set(t.lines))


def run_instrumented(exam_src: str, solution_src: str, module: str) -> dict:
    inst, lines = instrument(exam_src)
    with tempfile.TemporaryDirectory(prefix="ex_inst_") as td:
        w = pathlib.Path(td)
        (w / f"{module}.py").write_text(solution_src, encoding="utf-8")
        (w / "_vrec.py").write_text(HELPER, encoding="utf-8")
        (w / "exam_test.py").write_text(inst, encoding="utf-8")
        r = _pytest(w, "exam_test.py")
        recs = []
        rp = w / "_rec.jsonl"
        if rp.exists():
            recs = [json.loads(x) for x in rp.read_text().splitlines() if x.strip()]
    state, msgs = {}, {}
    for ln in lines:
        rs = [x for x in recs if x["line"] == ln]
        if any(x["state"] == "fail" for x in rs):
            state[ln] = "fail"
            msgs[ln] = next(x["msg"] for x in rs if x["state"] == "fail")
        elif rs:
            state[ln] = "pass"
        else:
            state[ln] = "unreached"
    return {"assertions": state, "messages": msgs, "collect_error": r["collect_error"], "timeout": r["timeout"],
            "n_units": len(lines)}


def count_units(src: str) -> int | None:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    n = 0

    def walk(x: ast.AST) -> None:
        nonlocal n
        for ch in ast.iter_child_nodes(x):
            if isinstance(ch, ast.Assert) or _is_raises(ch):
                n += 1
                continue
            walk(ch)

    walk(tree)
    return n
