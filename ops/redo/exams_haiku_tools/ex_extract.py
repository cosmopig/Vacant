#!/usr/bin/env python3
"""ex_extract — EX 考卷的確定性抽取器（決定檔「EX」一節；無模型、不改寫，只逐字搬）。

認的形式（逐行掃 goal.md）：
  (a) doctest：`>>> <expr>` 下一行（非空、非 `>>>`）是期望值；
  (b) 同一行 `<expr> == <值>`、`<expr> => <值>`、`<expr> -> <值>`、`<expr> # => <值>`、`<expr> # returns <值>`。
`<expr>` 必須能 ast.parse 成單一運算式、是 Call，且呼叫鏈的根名稱（`Garden(...)`／`f(...)`／`obj.m(...)` 的 obj／f）
是存根定義的頂層名字（函式或類別）；`<值>` 必須能 ast.literal_eval。兩者的原文逐字進測試（斷言＝`assert <expr> == <值>`）。
行內反引號只剝掉最外層一對。抽不到任何一條＝該題標 none（寫 ex_NONE.txt），不手寫。
"""
import ast
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import haiku_call as H  # noqa: E402

ARROWS = re.compile(r"^(?P<e>.+?)\s*(?:#\s*)?(?:==|=>|->|returns?)\s+(?P<v>.+?)\s*$")


def stub_names(stub: str) -> set[str]:
    t = ast.parse(stub)
    return {n.name for n in t.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


def root_name(call: ast.Call) -> str | None:
    f = call.func
    while True:
        if isinstance(f, ast.Name):
            return f.id
        if isinstance(f, ast.Attribute):
            f = f.value
        elif isinstance(f, ast.Call):
            f = f.func
        else:
            return None


def ok_pair(e: str, v: str, names: set[str]) -> bool:
    try:
        te = ast.parse(e.strip(), mode="eval").body
        ast.literal_eval(v.strip())
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return False
    return isinstance(te, ast.Call) and root_name(te) in names


def unbt(s: str) -> str:
    s = s.strip()
    if s.startswith("`") and s.endswith("`") and s.count("`") == 2:
        return s[1:-1]
    return s


def extract(goal: str, stub: str) -> list[dict]:
    names = stub_names(stub)
    lines = goal.split("\n")
    out = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith(">>>"):
            e = s[3:].strip()
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt and not nxt.startswith(">>>") and ok_pair(e, nxt, names):
                out.append({"line": i + 1, "expr": e, "value": nxt, "form": "doctest"})
            continue
        m = ARROWS.match(unbt(s).lstrip("-* ").strip())
        if m and ok_pair(m["e"], m["v"], names):
            out.append({"line": i + 1, "expr": m["e"].strip(), "value": m["v"].strip(), "form": "arrow"})
    return out


def main() -> int:
    summary = {}
    for t in H.tasks():
        d = H.OUT / t
        d.mkdir(parents=True, exist_ok=True)
        inp = H.task_inputs(t)
        if (d / "ex_test.py").exists() or (d / "ex_NONE.txt").exists():
            continue
        ex = extract(inp["goal"], inp["stub"])
        if not ex:
            (d / "ex_NONE.txt").write_text("extractor found no verbatim example pair in goal.md; no hand-written fallback\n")
            summary[t] = 0
            continue
        names = sorted(stub_names(inp["stub"]))
        body = [f"from {inp['module']} import {', '.join(names)}", ""]
        for k, e in enumerate(ex, 1):
            body += [f"def test_example_{k}():", f"    # goal.md line {e['line']} ({e['form']})",
                     f"    assert {e['expr']} == {e['value']}", ""]
        (d / "ex_test.py").write_text("\n".join(body), encoding="utf-8")
        summary[t] = len(ex)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
