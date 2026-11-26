"""ops.e1.units — 單元抽取、任務範圍推導與範圍受限原子提交（程式碼 AST 與文件範本行）。

這支在架構裡承重什麼
====================
實作 E1′ 實驗中 `S`、`S+B2`、`O` 三臂的核心機制：宿主端（host-side）將 agent 在暫存工作區
留下的候選檔拆解為離散單元，**只提交屬於本回合允許範圍（allowed_scope）的單元變更**，其餘
單元與非單元基線結構一律保留上一回合的基線版本，最後以原子寫檔（暫存檔＋`os.replace`）落地。

單元定義：
- **程式碼（code）**：`solution.py` 的頂層函式定義（`ast.FunctionDef`／`ast.AsyncFunctionDef`），
  以函式名稱為鍵。基線的 imports 與其他頂層敘述一律保留；僅當 `allowed_scope` 非空時，才接受
  候選檔新增且不與任何基線頂層名稱碰撞的 `import`/`from ... import` 敘述（不允許刪除或修改基線
  import／常數，亦不接受非函式的新頂層敘述）。候選檔若語法錯誤則 fail-closed 保留基線。
- **文件（doc）**：`report.md` 的範本宣稱行，以最後一個 `": "` 之前的標籤前綴為鍵（與產品
  `vacant_network.trace.sources._label_key` 口徑一致）。標題與說明文字一律保留基線。

誠實邊界（改碼請保留）
----------------------
- 程式碼範圍提交只切頂層函式定義：若多個函式共用某個被修改的頂層全域變數，本模組刻意拒絕
  該全域變數變更（保護基線），但也因此不適用於必須修改頂層共用狀態的任務。
- `extract_code_scope_from_task` 只讀任務文字（不碰 oracle），依 `def <name>(` 與改名句型抽取
  函式名；若任務文字未依此慣例提及函式名，可能漏抽（進而造成 false reject，由分析器事後量測）。
- 文件單元比對仰賴標籤前綴（`": "` 之前）在檔案中唯一；若範本有重複標籤前綴，該行保守不覆蓋。
"""
from __future__ import annotations

import ast
import pathlib
import re
from typing import Iterable

from . import atomic_write_text

_DEF_RE = re.compile(r"(?m)^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_RENAME_RE = re.compile(
    r"\brename\s+(?:the\s+)?(?:existing\s+)?function\s+`?([A-Za-z_][A-Za-z0-9_]*)`?"
    r"(?:\s+in\s+`?[^\s`]+`?)?\s+to\s+`?([A-Za-z_][A-Za-z0-9_]*)`?",
    re.I,
)


def _node_span(node: ast.AST) -> tuple[int, int]:
    """回傳頂層 AST 節點的 1-based 行號區間（含裝飾器）。"""
    start = int(getattr(node, "lineno"))
    decs = getattr(node, "decorator_list", None) or []
    if decs:
        start = min(start, *(int(d.lineno) for d in decs))
    end = int(getattr(node, "end_lineno"))
    return start, end


def _slice_lines(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def _bound_names_of_stmt(node: ast.stmt) -> set[str]:
    """估算頂層敘述綁定的模組層級名稱（用於防止新增 import 覆蓋基線名稱）。"""
    names: set[str] = set()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names.add(node.name)
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        for alias in node.names:
            if alias.name == "*":
                names.add("*")
            else:
                names.add(alias.asname or alias.name.split(".")[0])
    elif isinstance(node, ast.Assign):
        for tgt in node.targets:
            for sub in ast.walk(tgt):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        names.add(node.target.id)
    return names


def extract_code_units(source: str) -> dict[str, dict]:
    """抽取 Python 原始碼的所有頂層函式定義，回傳 `{函式名: {source, ast_dump, start, end}}`。"""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    out: dict[str, dict] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            st, en = _node_span(node)
            seg = _slice_lines(lines, st, en)
            if seg and not seg.endswith("\n"):
                seg += "\n"
            out[node.name] = {
                "name": node.name,
                "source": seg,
                "ast_dump": ast.dump(node, include_attributes=False),
                "start": st,
                "end": en,
            }
    return out


def extract_code_scope_from_task(task_text: str) -> list[str]:
    """僅從任務文字（不看 oracle）抽出被點名的函式名：新增的 `def name(` 與改名的 `old -> new`。"""
    out: list[str] = []
    for m in _RENAME_RE.finditer(task_text or ""):
        for g in (m.group(1), m.group(2)):
            if g not in out:
                out.append(g)
    for m in _DEF_RE.finditer(task_text or ""):
        fn = m.group(1)
        if fn not in out:
            out.append(fn)
    return out


def _top_level_non_func_dumps(tree: ast.Module) -> list[str]:
    return [
        ast.dump(n, include_attributes=False)
        for n in tree.body
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _import_key(node: ast.stmt) -> str:
    return ast.dump(node, include_attributes=False)


def commit_code_scoped(
    baseline_src: str,
    candidate_src: str,
    allowed_units: Iterable[str],
) -> dict:
    """程式碼的範圍受限提交：僅套用 `allowed_units` 內的頂層函式變更，其餘與非函式基線保留原狀。

    回傳 dict：
      committed_src:              合併後的最終原始碼
      committed_units:            實際套用變更的範圍內函式名清單（含新增、修改、允許的刪除）
      rejected_units:             候選檔企圖修改／新增／刪除但不在範圍內的函式名清單
      rejected_non_unit_changes:  候選檔是否修改／刪除基線非函式頂層碼或新增非 import 頂層碼
      syntax_error:               候選檔是否無法通過 ast.parse（fail-closed 保留基線）
    """
    allowed = set(allowed_units)
    base_tree = ast.parse(baseline_src)
    base_lines = baseline_src.splitlines(keepends=True)
    base_funcs = extract_code_units(baseline_src)

    try:
        cand_tree = ast.parse(candidate_src)
        cand_lines = candidate_src.splitlines(keepends=True)
        cand_funcs = extract_code_units(candidate_src)
    except SyntaxError as exc:
        return {
            "committed_src": baseline_src,
            "committed_units": [],
            "rejected_units": [],
            "rejected_non_unit_changes": True,
            "syntax_error": True,
            "error": f"SyntaxError: {exc}",
        }

    # 基線頂層已綁定名稱（用來防止新增 import 覆蓋既有名稱）
    base_bound: set[str] = set()
    base_import_keys: set[str] = set()
    for node in base_tree.body:
        base_bound |= _bound_names_of_stmt(node)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            base_import_keys.add(_import_key(node))

    # 偵測候選檔對非函式頂層敘述的異動
    base_non_func = _top_level_non_func_dumps(base_tree)
    cand_non_func = _top_level_non_func_dumps(cand_tree)
    extra_imports: list[str] = []
    extra_import_dumps: set[str] = set()
    rejected_non_unit = False

    for node in cand_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        dmp = ast.dump(node, include_attributes=False)
        if dmp in base_non_func:
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # 僅當本回合允許修改某些函式時，才允許「純新增、不覆蓋基線名稱、非星號」的 import
            bnames = _bound_names_of_stmt(node)
            if allowed and "*" not in bnames and not (bnames & base_bound):
                st, en = _node_span(node)
                seg = _slice_lines(cand_lines, st, en)
                if seg and not seg.endswith("\n"):
                    seg += "\n"
                if dmp not in base_import_keys and dmp not in extra_import_dumps:
                    extra_imports.append(seg)
                    extra_import_dumps.add(dmp)
                    base_bound |= bnames
            else:
                rejected_non_unit = True
        else:
            rejected_non_unit = True

    # 檢查基線的非函式頂層敘述是否被候選檔刪除或修改
    cand_non_func_set = set(cand_non_func)
    if any(d not in cand_non_func_set for d in base_non_func):
        rejected_non_unit = True

    committed_units: list[str] = []
    rejected_units: list[str] = []
    pieces: list[str] = []

    # 按基線原本順序重建頂層區塊；在最後一個基線 import（或檔頭）之後插入允許的新增 import
    last_import_idx = -1
    for idx, node in enumerate(base_tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last_import_idx = idx
        elif idx == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            # 模組 docstring 之後也可放 import
            if last_import_idx == -1:
                last_import_idx = 0

    inserted_imports = False
    if extra_imports and last_import_idx == -1:
        pieces.extend(extra_imports)
        pieces.append("\n")
        inserted_imports = True

    for idx, node in enumerate(base_tree.body):
        st, en = _node_span(node)
        orig_seg = _slice_lines(base_lines, st, en)
        if orig_seg and not orig_seg.endswith("\n"):
            orig_seg += "\n"

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn = node.name
            if fn in cand_funcs:
                changed = cand_funcs[fn]["ast_dump"] != base_funcs[fn]["ast_dump"]
                if changed:
                    if fn in allowed:
                        pieces.append("\n" + cand_funcs[fn]["source"])
                        committed_units.append(fn)
                    else:
                        pieces.append("\n" + orig_seg)
                        rejected_units.append(fn)
                else:
                    pieces.append("\n" + orig_seg)
            else:
                # 候選檔刪除了這個函式
                if fn in allowed:
                    committed_units.append(fn)
                else:
                    pieces.append("\n" + orig_seg)
                    rejected_units.append(fn)
        else:
            pieces.append(orig_seg)

        if extra_imports and not inserted_imports and idx == last_import_idx:
            pieces.extend(extra_imports)
            inserted_imports = True

    # 候選檔新增的頂層函式（原本不在基線裡）
    for fn, info in cand_funcs.items():
        if fn in base_funcs:
            continue
        if fn in allowed:
            pieces.append("\n\n" + info["source"])
            committed_units.append(fn)
        else:
            rejected_units.append(fn)

    committed_src = "".join(pieces).lstrip("\n")
    if committed_src and not committed_src.endswith("\n"):
        committed_src += "\n"

    # Fail-closed 驗證：合併結果必須可通過 ast.parse
    try:
        ast.parse(committed_src)
    except SyntaxError as exc:
        return {
            "committed_src": baseline_src,
            "committed_units": [],
            "rejected_units": rejected_units,
            "rejected_non_unit_changes": True,
            "syntax_error": True,
            "error": f"PostMergeSyntaxError: {exc}",
        }

    return {
        "committed_src": committed_src,
        "committed_units": committed_units,
        "rejected_units": rejected_units,
        "rejected_non_unit_changes": rejected_non_unit,
        "syntax_error": False,
        "error": None,
    }


# ── 文件（report.md 範本行）單元抽取與範圍提交 ──────────────────────────────

def doc_line_prefix(line: str) -> str | None:
    """回傳範本行的標籤前綴（最後一個 `": "` 之前）；標題行或不含 `": "` 者回 None。"""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if ": " not in line:
        # 亦容許尾端空值行（例如 `- Label:`）
        if s.endswith(":") and len(s) > 1:
            return s[:-1].strip()
        return None
    return line.rsplit(": ", 1)[0].strip()


def doc_line_value(line: str) -> str:
    """回傳範本行 `": "` 之後的值（去頭尾空白）。"""
    if ": " in line:
        return line.rsplit(": ", 1)[1].strip()
    if ":" in line:
        return line.rsplit(":", 1)[1].strip()
    return ""


def extract_doc_units(text: str) -> dict[str, str]:
    """抽取文件所有範本宣稱行，回傳 `{標籤前綴: 值}`（依出現順序）。"""
    out: dict[str, str] = {}
    for line in text.splitlines():
        pref = doc_line_prefix(line)
        if pref is not None:
            out[pref] = doc_line_value(line)
    return out


def commit_doc_scoped(
    baseline_text: str,
    candidate_text: str,
    allowed_prefixes: Iterable[str],
) -> dict:
    """文件的範圍受限提交：僅套用 `allowed_prefixes` 內的範本行變更，其餘行與標題保留基線。"""
    allowed = set(allowed_prefixes)
    base_lines = baseline_text.splitlines()
    cand_lines = candidate_text.splitlines()

    base_counts: dict[str, int] = {}
    for ln in base_lines:
        p = doc_line_prefix(ln)
        if p is not None:
            base_counts[p] = base_counts.get(p, 0) + 1

    cand_by_pref: dict[str, list[str]] = {}
    cand_non_unit: list[str] = []
    for ln in cand_lines:
        p = doc_line_prefix(ln)
        if p is not None:
            cand_by_pref.setdefault(p, []).append(ln)
        else:
            cand_non_unit.append(ln)

    base_non_unit = [ln for ln in base_lines if doc_line_prefix(ln) is None]
    rejected_non_unit = cand_non_unit != base_non_unit

    committed_units: list[str] = []
    rejected_units: list[str] = []
    out_lines: list[str] = []

    for ln in base_lines:
        pref = doc_line_prefix(ln)
        if pref is None:
            out_lines.append(ln)
            continue
        cands = cand_by_pref.get(pref) or []
        if base_counts.get(pref, 0) != 1:
            # 重複標籤前綴：保守維持原樣
            out_lines.append(ln)
            continue
        if len(cands) == 1:
            cand_ln = cands[0]
            if cand_ln.strip() != ln.strip():
                if pref in allowed:
                    out_lines.append(cand_ln)
                    committed_units.append(pref)
                else:
                    out_lines.append(ln)
                    rejected_units.append(pref)
            else:
                out_lines.append(ln)
        elif len(cands) == 0:
            # 候選檔刪除了這一行
            if pref in allowed:
                committed_units.append(pref)
            else:
                out_lines.append(ln)
                rejected_units.append(pref)
        else:
            # 候選檔產生了重複的同前綴行：視為異常變更
            if pref in allowed:
                out_lines.append(cands[0])
                committed_units.append(pref)
            else:
                out_lines.append(ln)
                rejected_units.append(pref)

    # 候選檔新增了基線不存在的標籤行
    for pref, cands in cand_by_pref.items():
        if pref in base_counts:
            continue
        if pref in allowed:
            out_lines.append(cands[0])
            committed_units.append(pref)
        else:
            rejected_units.append(pref)

    trailing = "\n" if baseline_text.endswith("\n") or not baseline_text else ""
    committed_text = "\n".join(out_lines) + trailing
    return {
        "committed_text": committed_text,
        "committed_units": committed_units,
        "rejected_units": rejected_units,
        "rejected_non_unit_changes": rejected_non_unit,
    }


def atomic_commit_file(target: pathlib.Path, content: str) -> str:
    """以暫存檔＋os.replace 原子提交檔案內容，回傳 sha256。"""
    return atomic_write_text(target, content)
