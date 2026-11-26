#!/usr/bin/env python3
"""ops.e1.fake_agent — E1′ 端對端 selftest 專用的確定性假 agent（跑在真實 bwrap 沙箱內）。

這支在架構裡承重什麼
====================
在不呼叫任何語言模型的情況下，模擬真實 agent 在多回合任務裡常見的「重寫整檔並意外弄壞既有正確單元」
行為，用來驗證 E1′ 整個執行器、隔離沙箱、來源伺服器、範圍提交、B2 檢查／回滾與分析管線：
- **程式碼模式（`/work/solution.py`）**：
  - 讀任務提示，依約定實作被要求新增的函式或完成改名（針對 selftest 合成題庫與改名回合），
  - 同時在預設 `regress_other` 模式下**重寫整個檔案並弄壞第一支原本已正確的非目標函式**
    （使 B0 回歸、B2 透過可見測試擋下並回滾、而 S／S+B2／O 僅提交範圍內單元而保護舊函式）。
- **文件模式（`/work/report.md`）**：
  - 從提示抓出索引網址，經由 `http_proxy`（真的打到 `ops/d2/source_server.py`）讀取索引頁與所有連結頁面，
  - 從維基百科 HTML 資訊框表格解析最新 `apps (goals)` 值更新有變動的行，
  - 同時在 `regress_other` 模式下**竄改第一條原本未變動的非目標行**（使 B0 與只看結構的 B2 均回歸，
    而 S／S+B2／O 憑 `value_status` 保護未變動行）。
- 結束前印出一筆與 `pi --mode json` 相容的 `message_end` 事件，連同 token 解析一併實測。

誠實邊界（改碼請保留）
----------------------
- 本腳本只供管線與機制自測，**不是**模型能力或實測成效的證據。
"""
from __future__ import annotations

import argparse
import ast
import html as _html
import json
import os
import pathlib
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser


def _emit_pi_usage(tin: int = 120, tout: int = 45) -> None:
    evt = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "stopReason": "stop",
            "usage": {"input": tin, "output": tout},
        },
    }
    print(json.dumps(evt), flush=True)


# ── 程式碼模式 ──────────────────────────────────────────────────────────────

_DEF_RE = re.compile(r"(?m)^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)")
_RENAME_RE = re.compile(
    r"Rename\s+the\s+existing\s+function\s+`?([A-Za-z_][A-Za-z0-9_]*)`?"
    r"(?:\s+in\s+`?[^\s`]+`?)?\s+to\s+`?([A-Za-z_][A-Za-z0-9_]*)`?",
    re.I,
)
_FORMULA_RE = re.compile(r"return\s+x\s*\+\s*(\d+)")
_MULT_RE = re.compile(r"return\s+x\s*\*\s*(\d+)")


def _synth_body_from_prompt(prompt: str, fn_name: str, args_str: str) -> str:
    """從 selftest 合成題的 docstring 推出正確實作（不碰任何外部答案）。"""
    m = _FORMULA_RE.search(prompt)
    if m:
        k = int(m.group(1))
        return f"def {fn_name}({args_str}):\n    return x + {k}\n"
    m2 = _MULT_RE.search(prompt)
    if m2:
        k = int(m2.group(1))
        return f"def {fn_name}({args_str}):\n    return x * {k}\n"
    return f"def {fn_name}({args_str}):\n    return x\n"


def _handle_code(sol_path: pathlib.Path, prompt: str, mode: str) -> None:
    src = sol_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)

    # 拆解既有頂層區塊
    imports: list[str] = []
    funcs: list[tuple[str, str]] = []
    for node in tree.body:
        seg = "".join(lines[node.lineno - 1 : node.end_lineno])
        if not seg.endswith("\n"):
            seg += "\n"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append((node.name, seg))
        else:
            imports.append(seg)

    rm = _RENAME_RE.search(prompt)
    dm = _DEF_RE.search(prompt)
    protected_target: set[str] = set()

    if rm:
        old_fn, new_fn = rm.group(1), rm.group(2)
        protected_target |= {old_fn, new_fn}
        new_funcs: list[tuple[str, str]] = []
        for name, seg in funcs:
            if name == old_fn:
                renamed = re.sub(rf"\bdef\s+{re.escape(old_fn)}\b", f"def {new_fn}", seg, count=1)
                new_funcs.append((new_fn, renamed))
            else:
                new_funcs.append((name, seg))
        funcs = new_funcs
    elif dm:
        new_fn, args_str = dm.group(1), dm.group(2)
        protected_target.add(new_fn)
        body = _synth_body_from_prompt(prompt, new_fn, args_str)
        replaced = False
        for i, (name, _) in enumerate(funcs):
            if name == new_fn:
                funcs[i] = (new_fn, body)
                replaced = True
                break
        if not replaced:
            funcs.append((new_fn, body))

    # 預設 regress_other：故意破壞第一支「不在本回合點名範圍內」的既有函式
    if mode == "regress_other":
        for i, (name, seg) in enumerate(funcs):
            if name not in protected_target:
                first_line = seg.splitlines()[0]
                funcs[i] = (name, f"{first_line}\n    return -999999\n")
                break

    out = "".join(imports)
    if out and not out.endswith("\n\n"):
        out += "\n"
    out += "\n\n".join(seg.rstrip() for _, seg in funcs) + "\n"
    sol_path.write_text(out, encoding="utf-8")


# ── 文件模式 ──────────────────────────────────────────────────────────────

class _SimpleTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._in_tr = False
        self._cell: list[str] | None = None
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.links.append(v)
        elif tag == "tr":
            self._in_tr = True
            self.rows.append([])
        elif tag in ("td", "th") and self._in_tr:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._in_tr:
            self.rows[-1].append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr":
            self._in_tr = False

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "e1-fake-agent"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", "replace")


def _norm_txt(s: str) -> str:
    return " ".join(_html.unescape(s).replace("\u2013", "-").replace("\u2014", "-").split()).lower()


def _handle_doc(report_path: pathlib.Path, prompt: str, mode: str) -> None:
    m = re.search(r"https?://[^\s'\"<>]+", prompt)
    if not m:
        return
    index_url = m.group(0).rstrip(".,;)")
    idx_html = _fetch_url(index_url)
    ip = _SimpleTableParser()
    ip.feed(idx_html)

    # 讀取索引頁連結的所有分頁並抽取表格列（支援 Wikipedia 足球員資料表與一般簡易表）
    page_rows: list[tuple[str, list[list[str]]]] = []
    for href in ip.links:
        if href.startswith("#") or href.startswith("http"):
            continue
        full_u = urllib.parse.urljoin(index_url, href)
        html_txt = _fetch_url(full_u)
        tp = _SimpleTableParser()
        tp.feed(html_txt)
        page_rows.append((html_txt, tp.rows))

    lines = report_path.read_text(encoding="utf-8").splitlines()
    changed_indices: set[int] = set()
    new_lines = list(lines)

    for idx, ln in enumerate(lines):
        if ": " not in ln or ln.lstrip().startswith("#"):
            continue
        pref, old_val = ln.rsplit(": ", 1)
        # 解析 `- Entity — <years> <team> apps (goals)`
        m_lbl = re.match(r"^-\s*(.+?)\s+[—-]\s+(.+?)\s+apps\s*\(goals\)\s*$", pref.strip())
        if not m_lbl:
            continue
        entity, stint = m_lbl.group(1).strip(), m_lbl.group(2).strip()
        ent_norm = _norm_txt(entity)
        # 拆出年份前綴與隊名
        parts = stint.split(" ", 1)
        years_norm = _norm_txt(parts[0])
        team_norm = _norm_txt(parts[1]) if len(parts) > 1 else ""

        found_val: str | None = None
        for raw_html, rows in page_rows:
            if ent_norm not in _norm_txt(raw_html):
                continue
            for row in rows:
                if len(row) >= 4:
                    r0 = _norm_txt(row[0])
                    r1 = _norm_txt(row[1])
                    if r0 == years_norm and (team_norm in r1 or r1 in team_norm):
                        apps = re.sub(r"\[\d+\]", "", row[2]).strip()
                        goals = re.sub(r"\[\d+\]", "", row[3]).strip()
                        if apps and goals:
                            found_val = f"{apps} {goals}" if goals.startswith("(") else f"{apps} ({goals})"
                            break
            if found_val is not None:
                break

        if found_val is not None and found_val != old_val.strip():
            new_lines[idx] = f"{pref}: {found_val}"
            changed_indices.add(idx)

    # 預設 regress_other：故意破壞第一條「其實沒變動」的範本行
    if mode == "regress_other":
        for idx, ln in enumerate(lines):
            if ": " in ln and not ln.lstrip().startswith("#") and idx not in changed_indices:
                pref, _ = ln.rsplit(": ", 1)
                new_lines[idx] = f"{pref}: 999 (99)"
                break

    report_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="E1′ 確定性假 agent（僅供 selftest）")
    ap.add_argument("--prompt", required=True)
    args = ap.parse_args()

    mode = os.environ.get("E1_FAKE_MODE", "regress_other")
    ws = pathlib.Path.cwd()
    sol = ws / "solution.py"
    rep = ws / "report.md"

    if sol.is_file():
        _handle_code(sol, args.prompt, mode)
    elif rep.is_file():
        _handle_doc(rep, args.prompt, mode)

    _emit_pi_usage()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
