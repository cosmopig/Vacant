#!/usr/bin/env python3
"""xmv_post — XMV 的確定性後處理器（決定檔「XMV」一節）。

對每題 `xmv_raw.py`：斷言單位＝每個 `assert` 敘述與每個 `with pytest.raises(...)` 區塊。單位正上方（連續的註解／空白行往上找，
遇到程式碼行即停）要有最近的一行 `# SRC: "<引文>"`；沒有 SRC、或引文（空白正規化後）不是 goal.md 子字串者，整個單位換成 `pass`，
其 SRC 註解行刪除。刪除寫進 `xmv_deletions.json`。raw 檔無法解析＝malformed：原樣當作 xmv_test.py，不處理。
不用手改。凍結檔 `xmv_test.py` 已存在就不覆寫。
"""
import ast
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import haiku_call as H  # noqa: E402

SRC_RE = re.compile(r'^\s*#\s*SRC:\s*"(.*)"\s*$')


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def is_raises(node: ast.AST) -> bool:
    if not isinstance(node, ast.With):
        return False
    for it in node.items:
        c = it.context_expr
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "raises":
            return True
    return False


def units(tree: ast.AST) -> list[ast.stmt]:
    out: list[ast.stmt] = []

    def walk(n: ast.AST) -> None:
        for ch in ast.iter_child_nodes(n):
            if isinstance(ch, ast.Assert) or is_raises(ch):
                out.append(ch)  # type: ignore[arg-type]
                continue  # 單位內部不再往下數
            walk(ch)

    walk(tree)
    return sorted(out, key=lambda u: u.lineno)


def find_src(lines: list[str], lineno: int) -> tuple[int | None, str | None]:
    """lineno 為 1-based 單位首行；往上走，回傳 (SRC 行的 0-based 索引, 引文)。"""
    i = lineno - 2
    while i >= 0:
        s = lines[i].strip()
        if s == "" or s.startswith("#"):
            m = SRC_RE.match(lines[i])
            if m:
                return i, m.group(1)
            i -= 1
            continue
        break
    return None, None


def process(raw: str, goal: str) -> tuple[str, list[dict], dict]:
    try:
        tree = ast.parse(raw)
    except SyntaxError as e:
        return raw, [], {"malformed": True, "error": str(e), "units": None, "kept": None, "deleted": None}
    lines = raw.split("\n")
    g = norm(goal)
    dels: list[dict] = []
    repl: dict[int, tuple[int, str]] = {}  # 0-based start line -> (end line exclusive, replacement text)
    drop_lines: set[int] = set()
    us = units(tree)
    for u in us:
        si, q = find_src(lines, u.lineno)
        reason = None
        if q is None:
            reason = "no_src"
        else:
            cands = {norm(q), norm(q.replace('\\"', '"'))}
            if not any(c and c in g for c in cands):
                reason = "quote_not_in_text"
        if reason:
            start, end = u.lineno - 1, u.end_lineno
            indent = re.match(r"\s*", lines[start]).group(0)
            dels.append({"line": u.lineno, "kind": "raises_block" if isinstance(u, ast.With) else "assert",
                         "reason": reason, "src": q, "code": "\n".join(lines[start:end])})
            repl[start] = (end, indent + "pass  # deleted by xmv_post: " + reason)
            if si is not None:
                drop_lines.add(si)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if i in repl:
            end, text = repl[i]
            out.append(text)
            i = end
            continue
        if i in drop_lines:
            i += 1
            continue
        out.append(lines[i])
        i += 1
    new = "\n".join(out)
    ast.parse(new)  # 後處理結果必須仍可解析
    return new, dels, {"malformed": False, "units": len(us), "kept": len(us) - len(dels), "deleted": len(dels)}


def main() -> int:
    log = {}
    for t in H.tasks():
        d = H.OUT / t
        raw_p, fin_p = d / "xmv_raw.py", d / "xmv_test.py"
        if not raw_p.exists() or fin_p.exists():
            continue
        goal = H.task_inputs(t)["goal"]
        new, dels, stat = process(raw_p.read_text(encoding="utf-8"), goal)
        fin_p.write_text(new, encoding="utf-8")
        log[t] = {"stats": stat, "deletions": dels}
    if log:
        (H.OUT / "xmv_deletions.json").write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({t: v["stats"] for t, v in log.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
