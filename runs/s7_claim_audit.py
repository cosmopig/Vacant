#!/usr/bin/env python3
"""S7：把 S6 的結論當紅線，掃觀眾文案有沒有把「排除」歸因給「被抓到」。

S6（第 96 輪）量到的是：把作惡者擠出路由的主要動力是「評審看得見」，
不是「稽核抓到」——沒被抓的作惡者一樣只拿到守規矩者的 1%。
所以任何寫成「被稽核抓到才會被排除」的觀眾文案都是**對觀眾說錯話**
（HANDOFF §一：先行研究之所以重要，理由是不能對觀眾說錯話，不是新穎性）。

這支**只產生候選、不下判定**。關鍵字掃描判斷不了語意，它做的是高召回：
同一句內〈抓到類〉與〈排除類〉同時出現才進候選，之後逐條人工判定。
精準度預期很差，這是刻意的——漏掉比誤報貴。

用法：
    python3 runs/s7_claim_audit.py --self-test        # P1 探針 fixture
    python3 runs/s7_claim_audit.py --scan             # P3 原始碼掃描
    python3 runs/s7_claim_audit.py --scan --dom DIR   # 併入 rendered DOM（P4）
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path.home() / "vacant"

# ── 範圍：觀眾看得到的檔。probe/ styles/ *FINDINGS.md 是工作紀錄，不是文案。──
#
# ⚠ 第 102 輪加入 `vacant/dashboard.py`：第 101 輪量到**宣稱階梯那四階
# （`dashboard.py:394–436` 的 claim／evidence）是全站唯一沒被任何掃描路徑
# 涵蓋過的觀眾文案**——它由伺服器端組好、經 `/api/*` 送到面板上，
# `app.html`／`app.js` 的原始碼裡一個字都沒有。
# 加檔會改動所有既往輪次的分母，所以獨立登記一輪（S7f）。
SCOPE = [
    ("vacant-docs-web", ["index.html", "js/main.js"]),
    ("vacant_hm", ["index.html", "js/*.js", "world/*.html", "world/js/*.js",
                   "world/js/clay/*.js"]),
    ("Vacant", ["vacant/web/app.html", "vacant/web/app.js", "vacant/dashboard.py"]),
]
EXCLUDE_PARTS = ("probe", "styles", "vendor", "node_modules")

# ⚠ 事前登記的 CATCH 少了「抽到／抽中／被抽」這一族，會漏掉
# `vacant_hm/index.html:107` 的「抽到就扣分」——那句正是本輪要找的形狀。
# 是 --diag（也是事後加的）把它照出來的。**事後加詞是放寬召回、不是放寬判準**，
# 候選只會變多、被看的只會更多；照實記在 S7_CLAIM_AUDIT.md 第四節。
CATCH = ["稽核", "抽查", "查核", "抓到", "抓住", "查獲", "揭發", "識破",
         "發現作假", "被抓", "audit", "Audit", "caught", "Caught",
         "抽到", "抽中", "被抽", "抽樣", "查到", "逮"]
# ⚠ 第 101 輪事前登記加的兩個詞：`SLASH`（大寫）與「扣減」。
# 觀測台 `vacant/web/app.js:105` 的 SLASH 磚與其副標「信用已被扣減」是全站
# 最直接的「後果」文案，而原詞族有 `slash`／`Slash` 卻沒有 `SLASH`（比對是
# 區分大小寫的）、有「扣分」卻沒有「扣減」——兩個都抓不到。
# **加詞是放寬召回、不是放寬判準**（同 CATCH 那條先例）：候選只會變多。
EXCLUDE_CLAIM = ["排除", "踢出", "淘汰", "停權", "出局", "拿不到工作", "不再派工",
                 "再也", "永久", "slash", "Slash", "SLASH", "扣分", "扣減",
                 "降權", "封鎖", "剔除"]

SENT_SPLIT = re.compile(r"[。！？；!?;\n]+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]


def hits(sent: str) -> tuple[list[str], list[str]]:
    return ([w for w in CATCH if w in sent],
            [w for w in EXCLUDE_CLAIM if w in sent])


# ── 文案抽取：HTML 取文字節點＋文字型屬性；JS 取字串字面量 ──
_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TAG = re.compile(r"<[^>]+>")
_TEXT_ATTR = re.compile(
    r"""\b(alt|title|aria-label|placeholder|content)\s*=\s*["']([^"']*)["']""", re.I)

# ⚠ 這條正則是第 97 輪掃描漏掉四成文案的原因，留著只為了 `--cjk-audit --legacy`
# 能把「修之前」的數字重現出來。**不要拿它抽文案。**
#
# 第 98 輪把病因記成「分支順序」（`'…'`／`"…"` 排在反引號前面）——那個診斷是錯的：
# 單引號與反引號不可能在同一個起始位置競爭，調換順序不改變任何一個 match。
# 真正的病因是**配對錯位的連鎖**：反引號分支的內容類別是 `[^`\\]`，**不准含反斜線**，
# 所以第一條含 `\` 的模板字面量配不起來，掃描指標落進那條模板的內部，
# 之後每個反引號都跟錯的另一半配對——抽出來的是模板**之間**的程式碼
# （實測 `phone.js:250` 抽到 `";\n  }\n\n  $('ripple').innerHTML = head +\n    "`），
# 文案整段被跳過。單點錯配會連鎖到檔案結尾，所以越後面的文案越抽不到。
_JS_STR_LEGACY = re.compile(r"""'([^'\\\n]{2,})'|"([^"\\\n]{2,})"|`([^`\\]{2,})`""")

# 模板字面量的 `${...}` 洞：用一個非標點的佔位字元頂掉，句子才不會被切斷。
# （`牠${name}被抓到了` 若在洞的位置切開，同句掃描就永遠看不到這一句。）
HOLE = "▮"

_ESCAPES = {"n": "\n", "t": "\t", "r": "\n", "b": "", "f": "", "v": "",
            "0": "", "\n": ""}
# `/` 前面是這些字元 ⇒ 那個 `/` 是除法不是正則開頭（標準啟發式）。
_DIV_PREV = set(")]}") | set("abcdefghijklmnopqrstuvwxyz"
                             "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$")


def _unescape(raw: str) -> str:
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if c != "\\" or i + 1 >= len(raw):
            out.append(c)
            i += 1
            continue
        nxt = raw[i + 1]
        if nxt == "u":
            if i + 2 < len(raw) and raw[i + 2] == "{":
                end = raw.find("}", i + 3)
                if end > 0:
                    try:
                        out.append(chr(int(raw[i + 3:end], 16)))
                        i = end + 1
                        continue
                    except ValueError:
                        pass
            try:
                out.append(chr(int(raw[i + 2:i + 6], 16)))
                i += 6
                continue
            except ValueError:
                pass
        if nxt == "x":
            try:
                out.append(chr(int(raw[i + 2:i + 4], 16)))
                i += 4
                continue
            except ValueError:
                pass
        out.append(_ESCAPES.get(nxt, nxt))
        i += 2
    return "".join(out)


def js_strings(src: str) -> list[tuple[int, str]]:
    """逐字元走訪 JS，回傳 (行號, 字串內容)。

    正則配對抽不了 JS 字串——一個配不起來的引號會讓後面整個檔錯位（見
    `_JS_STR_LEGACY` 的註解）。這支改成走狀態機：認跳脫字元、`//` 與 `/* */`
    註解、正則字面量、以及模板裡的 `${}` 巢狀（洞內的字串本身也是文案，
    `${bad ? '被抓到' : '通過'}` 兩個分支都要抽出來）。
    """
    out: list[tuple[int, str]] = []
    n = len(src)
    line = 1
    i = 0
    prev_sig = ""          # 前一個有意義的字元，用來分辨除法與正則
    tmpl: list[list] = []  # 模板堆疊：[起始行, 已收集的 cooked 片段]

    def emit(ln: int, s: str) -> None:
        if s.strip():
            out.append((ln, s))

    while i < n:
        c = src[i]
        # ── 註解 ──
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += src.count("\n", i, j)
            i = j
            continue
        # ── 正則字面量：內容不是文案，但要正確跳過，否則裡面的引號會錯位 ──
        if c == "/" and prev_sig not in _DIV_PREV:
            j, cls = i + 1, False
            while j < n:
                d = src[j]
                if d == "\\":
                    j += 2
                    continue
                if d == "\n":
                    break
                if d == "[":
                    cls = True
                elif d == "]":
                    cls = False
                elif d == "/" and not cls:
                    j += 1
                    break
                j += 1
            if j <= n and j > i + 1:
                line += src.count("\n", i, j)
                i = j
                prev_sig = "/"
                continue
        # ── 單／雙引號字串 ──
        if c in "'\"":
            start_line, j, buf = line, i + 1, []
            while j < n:
                d = src[j]
                if d == "\\":
                    buf.append(src[j:j + 2])
                    j += 2
                    continue
                if d == c or d == "\n":
                    break
                buf.append(d)
                j += 1
            emit(start_line, _unescape("".join(buf)))
            line += src.count("\n", i, j)
            i = j + 1
            prev_sig = c
            continue
        # ── 模板字面量 ──
        if c == "`":
            tmpl.append([line, []])
            i += 1
            start = i
            buf: list[str] = []
            while i < n:
                d = src[i]
                if d == "\\":
                    buf.append(src[i:i + 2])
                    i += 2
                    continue
                if d == "`":
                    break
                if d == "$" and i + 1 < n and src[i + 1] == "{":
                    # 洞：交還給主迴圈處理（洞裡可以有字串、也可以有巢狀模板）
                    buf.append(HOLE)
                    depth, j = 1, i + 2
                    inner = src[i + 2:]
                    # 找到對應的 `}`，把洞內的原始碼遞迴丟回這支自己掃
                    k, dep = 0, 1
                    while k < len(inner) and dep > 0:
                        ch = inner[k]
                        if ch in "'\"`":
                            q = ch
                            k += 1
                            while k < len(inner):
                                if inner[k] == "\\":
                                    k += 2
                                    continue
                                if inner[k] == q:
                                    break
                                k += 1
                        elif ch == "{":
                            dep += 1
                        elif ch == "}":
                            dep -= 1
                            if dep == 0:
                                break
                        k += 1
                    hole_src = inner[:k]
                    base = line + src.count("\n", start, i)
                    for hl, hs in js_strings(hole_src):
                        emit(base + hl - 1, hs)
                    i = i + 2 + k + 1
                    continue
                buf.append(d)
                i += 1
            start_line = tmpl.pop()[0]
            emit(start_line, _unescape("".join(buf)))
            line += src.count("\n", start - 1, min(i, n))
            i += 1
            prev_sig = "`"
            continue
        if c == "\n":
            line += 1
        elif not c.isspace():
            prev_sig = c
        i += 1
    return out


def extract_html(src: str) -> list[tuple[int, str]]:
    """回傳 (行號, 文案片段)。行號用片段在原文的位置回推。"""
    out: list[tuple[int, str]] = []
    # 屬性先抽（去標籤之後就沒了）
    for m in _TEXT_ATTR.finditer(src):
        out.append((src[:m.start()].count("\n") + 1, m.group(2)))
    # inline <script> 當 JS 處理
    for m in re.finditer(r"<script\b[^>]*>(.*?)</script>", src, re.S | re.I):
        base = src[:m.start(1)].count("\n") + 1
        for ln, frag in extract_js(m.group(1)):
            out.append((base + ln - 1, frag))
    # 挖掉 <script>/<style>/註解時要**保留換行數**，否則後面每一行的行號都會偏掉。
    # （第 97 輪實際踩到：hm index.html 真實行號 111，工具報 107，差 4 行 ——
    #  報告會把人送到錯的一行，而那一行看起來也像是「差不多的地方」。）
    def blank(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")

    stripped = _COMMENT.sub(blank, _SCRIPT_STYLE.sub(blank, src))
    # 逐行去標籤，行號才對得上
    for i, line in enumerate(stripped.split("\n"), 1):
        txt = _TAG.sub(" ", line).strip()
        if txt:
            out.append((i, txt))
    return out


def extract_js(src: str) -> list[tuple[int, str]]:
    return js_strings(src)


def extract_js_legacy(src: str) -> list[tuple[int, str]]:
    """第 97 輪那支（壞的）。只給 `--cjk-audit --legacy` 重現「修之前」用。"""
    out: list[tuple[int, str]] = []
    for m in _JS_STR_LEGACY.finditer(src):
        s = m.group(1) or m.group(2) or m.group(3) or ""
        if not s.strip():
            continue
        out.append((src[:m.start()].count("\n") + 1, s))
    return out


# ── Python 文案抽取（第 102 輪新增）──────────────────────────────────────
#
# **為什麼不能把 .py 丟進 `js_strings`**：舊的 `extract()` 對任何非 HTML 檔
# 一律走 JS tokenizer。Python 的 `#` 註解在 JS 裡不是註解（`# 被抓到就排除`
# 會被當成文案抽出來）、三引號在 JS 裡是三個空字串加一段錯位、中文識別字
# （`被抓到的次數 = 1`）在 JS 眼裡也不是文案。用錯的抽取器會**同時**多抽
# 註解、少抽真文案——兩個方向都錯，而候選數看起來還是「有在動」。
# `--py-test` 的 P7b 那一欄就是把這件事量出來（見該處輸出）。
#
# **docstring 不算觀眾文案**（事前登記，第 102 輪）：它跟 `probe/`、`styles/`、
# `*FINDINGS.md` 同性質，是寫給改碼的人看的工作紀錄，觀眾走到展場前面看不到它。
# 但**不准靜靜丟掉**：`scan_sources` 會把 docstring 另外掃一遍並印出段數，
# 若 docstring 裡出現候選句也照樣印。`--cjk-audit` 把它列成第三類。


def _py_docstring_nodes(tree: ast.AST) -> list[ast.Constant]:
    """模組／類別／函式的第一個字串陳述式 ＝ docstring。"""
    out: list[ast.Constant] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            out.append(body[0].value)
    return out


def extract_py(src: str) -> list[tuple[int, str]]:
    """回傳 (行號, 文案片段)。走 `ast`，所以註解天然不在裡面。

    f-string 比照 JS 模板字面量處理：`{...}` 用 `HOLE` 頂掉，句子才不會被切斷；
    洞裡的字串本身也是文案（`f"{'不合格' if bad else '通過'}"` 兩個分支都要抽）。
    相鄰字串隱式相接由 `ast` 在解析時就併好了——`dashboard.py` 的 evidence
    正是那個形狀，逐 token 抽取會把一句話切成三段、同句掃描就看不到它。
    """
    out: list[tuple[int, str]] = []
    tree = ast.parse(src)
    doc_ids = {id(n) for n in _py_docstring_nodes(tree)}

    def emit(ln: int, s: str) -> None:
        if s.strip():
            out.append((ln, s))

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.JoinedStr):
            buf: list[str] = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    buf.append(v.value)
                elif isinstance(v, ast.FormattedValue):
                    buf.append(HOLE)
                    visit(v.value)      # 洞內的字串也是文案
            emit(node.lineno, "".join(buf))
            return
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and id(node) not in doc_ids:
                emit(node.lineno, node.value)
            return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return out


def py_docstrings(src: str) -> list[tuple[int, str]]:
    """被刻意排除的那一類。分開回傳，才數得出來丟了多少。"""
    return [(n.lineno, n.value) for n in _py_docstring_nodes(ast.parse(src))]


def comment_spans_py(src: str) -> list[tuple[int, int]]:
    """`.py` 的註解字元區間——量尺用，走 `tokenize` 不走 `ast`。

    誠實邊界：這比 JS 那組量尺**不那麼獨立**。JS 那邊量尺（`comment_spans`）
    是另外手寫一份掃描器，跟 `js_strings` 沒有共用程式；這邊 `tokenize` 與
    `ast` 雖是兩支不同的實作（詞法器 vs C 解析器），但同屬 CPython 自己的
    剖析路徑。所以「兩邊一起錯」的機率不是零，只是比共用同一份函式低。
    照記，不假裝它跟 JS 那組同級。
    """
    lines = src.splitlines(keepends=True)
    starts, off = [], 0
    for ln in lines:
        starts.append(off)
        off += len(ln)

    def pos(row: int, col: int) -> int:
        return starts[row - 1] + col if 1 <= row <= len(starts) else len(src)

    spans: list[tuple[int, int]] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                spans.append((pos(*tok.start), pos(*tok.end)))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return spans


def docstring_spans_py(src: str) -> list[tuple[int, int]]:
    """docstring 的字元區間——量尺的第三類，不准併進「漏失」也不准消失。"""
    lines = src.splitlines(keepends=True)
    starts, off = [], 0
    for ln in lines:
        starts.append(off)
        off += len(ln)

    def pos(row: int, col: int) -> int:
        return starts[row - 1] + col if 1 <= row <= len(starts) else len(src)

    out: list[tuple[int, int]] = []
    for n in _py_docstring_nodes(ast.parse(src)):
        if n.end_lineno is None:
            continue
        out.append((pos(n.lineno, n.col_offset),
                    pos(n.end_lineno, n.end_col_offset)))
    return out


def extract(path: Path, src: str) -> list[tuple[int, str]]:
    if path.suffix.lower() in (".html", ".htm"):
        return extract_html(src)
    if path.suffix.lower() == ".py":
        return extract_py(src)
    return extract_js(src)


def in_scope(path: Path) -> bool:
    return not any(p in EXCLUDE_PARTS for p in path.parts)


SOLO: list[dict] = []  # 只中一邊的句子——用來分辨「沒踩到」與「根本沒提」


def scan_text(origin: str, path_label: str, frags: list[tuple[int, str]]) -> tuple[list[dict], int]:
    cands, chars = [], 0
    for ln, frag in frags:
        chars += len(frag)
        for sent in sentences(frag):
            c, e = hits(sent)
            if c and e:
                cands.append({"origin": origin, "file": path_label, "line": ln,
                              "sent": sent[:300], "catch": c, "exclude": e})
            elif c or e:
                SOLO.append({"origin": origin, "file": path_label, "line": ln,
                             "sent": sent[:200], "catch": c, "exclude": e})
    return cands, chars


DOC_DROPPED: list[dict] = []   # 被當成工作紀錄排除的 docstring——數得出來才不算靜靜丟掉

# 逐檔語料字元數。`--scan` 只印總和，但總表要的是**分母**：
# 三個展件並排時 `0` 有兩種意思（有講而且守線／根本沒講），
# 沒有分母欄的總表會把「沒講」讀成「乾淨」。填在這裡而不另走一次 glob，
# 是因為分母必須跟被除數走同一條路（HANDOFF §八）。
FILE_CHARS: dict[str, int] = {}


def scan_sources() -> tuple[list[dict], int, list[str]]:
    cands: list[dict] = []
    total = 0
    files: list[str] = []
    for repo, pats in SCOPE:
        for pat in pats:
            for p in sorted((ROOT / repo).glob(pat)):
                if not p.is_file() or not in_scope(p):
                    continue
                label = f"{repo}/{p.relative_to(ROOT / repo)}"
                src = p.read_text(encoding="utf-8", errors="replace")
                c, n = scan_text("src", label, extract(p, src))
                cands += c
                total += n
                files.append(label)
                FILE_CHARS[label] = n
                if p.suffix.lower() == ".py":
                    # 排除的那一類要能被數：段數、字元數，以及**排除掉的東西
                    # 裡面有沒有候選句**。有的話照樣印，由人判定該不該收回來。
                    docs = py_docstrings(src)
                    keep = len(SOLO)
                    dc, dn = scan_text("doc", label, docs)
                    del SOLO[keep:]     # docstring 的 SOLO 不進診斷分母
                    DOC_DROPPED.append({"file": label, "segs": len(docs),
                                        "chars": dn, "cands": dc})
    return cands, total, files


def scan_dom(dom_dir: Path) -> tuple[list[dict], int, list[str]]:
    """吃 chrome-headless-shell --dump-dom 的產物（*.html）。"""
    cands: list[dict] = []
    total = 0
    files: list[str] = []
    for p in sorted(dom_dir.glob("*.html")):
        src = p.read_text(encoding="utf-8", errors="replace")
        c, n = scan_text("dom", f"DOM:{p.name}", extract_html(src))
        cands += c
        total += n
        files.append(f"DOM:{p.name}")
    return cands, total, files


# ── P1：探針 fixture。已知答案，兩個方向都要答對。──
FIXTURE = [
    ("V1", "index.html", "<p>只有被稽核抓到的作惡者才會被排除。</p>", True),
    ("V2", "index.html", "<p>稽核抓到之後，它就再也拿不到工作。</p>", True),
    ("V3", "js/main.js", "const s = '查核發現造假就永久停權';", True),
    ("N1", "index.html", "<p>評審看得見就會被降權。</p>", False),
    ("N2", "index.html", "<p>稽核會在 20% 的交付上抽樣。</p>", False),
    ("N3", "probe/x.html", "<p>只有被稽核抓到的作惡者才會被排除。</p>", False),
    # V4 是事後補的：事前那五個詞族抓不到它，而它是本輪真正找到的東西。
    ("V4", "index.html", "<p>信譽路由　·　三層漏斗　·　抽到就扣分</p>", True),
]


def self_test() -> int:
    rows, ok = [], 0
    for key, rel, body, expect in FIXTURE:
        p = Path(rel)
        if not in_scope(p):
            got = False  # 範圍過濾擋掉（N3）
        else:
            c, _ = scan_text("fix", rel, extract(p, body))
            got = bool(c)
        good = got == expect
        ok += good
        rows.append((key, expect, got, good))
    print(f"{'格':<4}{'該不該抓':<10}{'實際':<8}{'':<4}")
    for key, expect, got, good in rows:
        print(f"{key:<5}{str(expect):<12}{str(got):<10}{'OK' if good else 'FAIL'}")
    print(f"\nP1 fixture: {ok}/{len(FIXTURE)}")
    return 0 if ok == len(FIXTURE) else 1


# ── P5：tokenizer 探針。兩個方向都要答對——會抽到什麼，以及**不准**抽到什麼。──
# 「不准抽到」那半才是本輪的待測物：第 97 輪的 bug 不是少抽，是**抽錯東西**
# （抽到模板之間的程式碼），而只驗「有沒有抽到文案」的探針對那個形狀是瞎的。
TOK_FIXTURE = [
    # (格號, 原始碼, 必須出現的子字串, 必須不出現的子字串)
    ("T1 含跳脫的模板",
     r"const a = `第一行\n第二行的中文`;", ["第一行", "第二行的中文"], []),
    ("T2 跳脫模板之後還要抽得到下一條",
     r"const a = `頭\n尾`; const b = '被抓到就排除';",
     ["被抓到就排除"], []),
    # T3 的「不准出現」原本寫 `cap`，那一格**是探針自己寫錯的**：模板被整條正確
    # 抽出來時，`class="cap"` 本來就是那條模板的原文，要求它不出現等於要求程式做錯事。
    # 第 99 輪實測 11/12，FAIL 的就是這一格，而程式的輸出是對的。
    # 保留意圖、改成驗後果 ⇒ 見 T13：屬性若真的搶走配對，**後面那條字串會不見**。
    ("T3 模板裡的雙引號屬性",
     'const h = `<p class="cap">牠被抽查到了</p>`;',
     ["牠被抽查到了"], []),
    ("T13 屬性搶走配對的話，後面那條會不見",
     'const h = `<p class="cap">前一條文案</p>`;\nconst k = `<b class="x">後一條文案</b>`;',
     ["前一條文案", "後一條文案"], []),
    ("T4 模板之間的程式碼不准被當成字串",
     "const a = `甲文案`;\n  $('x').innerHTML = a;\n  const b = `乙文案`;",
     ["甲文案", "乙文案"], ["innerHTML"]),
    ("T5 洞不切斷句子、洞內字串也要抽到",
     "const t = `牠${who}被抓到了`; const u = `${bad ? '不合格' : '通過'}`;",
     ["牠▮被抓到了", "不合格", "通過"], []),
    ("T6 行註解不算文案",
     "// 這句是註解不是文案\nconst a = '這句是文案';",
     ["這句是文案"], ["這句是註解不是文案"]),
    ("T7 區塊註解不算文案",
     "/* 區塊註解的中文 */\nconst a = '區塊之後的文案';",
     ["區塊之後的文案"], ["區塊註解的中文"]),
    ("T8 註解裡的引號不准讓後面錯位",
     "// 別碰 it's 這個撇號\nconst a = '撇號之後的文案';",
     ["撇號之後的文案"], []),
    ("T9 正則字面量裡的引號不准讓後面錯位",
     "const re = /['\"]/g;\nconst a = '正則之後的文案';",
     ["正則之後的文案"], []),
    ("T10 跨行模板",
     "const a = `上半段的中文\n下半段的中文`;",
     ["上半段的中文", "下半段的中文"], []),
    ("T11 字串裡的 // 不是註解",
     "const u = 'http://例子/路徑'; const a = '之後的文案';",
     ["之後的文案", "http://例子/路徑"], []),
    ("T12 除法的斜線不准被當成正則開頭",
     "const r = (a) / 2; const a = '除法之後的文案';",
     ["除法之後的文案"], []),
]


def tok_test() -> int:
    ok = 0
    for key, src, must, mustnot in TOK_FIXTURE:
        frags = [f for _, f in js_strings(src)]
        blob = "".join(frags)
        miss = [m for m in must if m not in blob]
        leak = [m for m in mustnot if m in blob]
        good = not miss and not leak
        ok += good
        print(f"{'OK  ' if good else 'FAIL'} {key}")
        if not good:
            print(f"       缺 {miss} · 不該有卻有 {leak}")
            print(f"       實際抽到 {frags}")
    print(f"\nP5 tokenizer fixture: {ok}/{len(TOK_FIXTURE)}")
    return 0 if ok == len(TOK_FIXTURE) else 1


# ── P6：獨立量尺。不解析字串，只問「這段中文有沒有被讀進去」。──
# 量尺跟被測物必須分開：用被修的那支程式去證明自己修好了，等於沒證。
_CJK = re.compile(r"[一-鿿぀-ヿ]{4,}")


def comment_spans(src: str) -> list[tuple[int, int]]:
    """註解的字元區間。**故意跟 `js_strings` 分開寫一份。**

    量尺跟待測物共用同一份程式的話，同一個判斷錯誤會同時把某段中文
    「排除在分母外」又「抽不到」——兩邊一起錯，結果是漂亮的 0 漏失。
    這支只做一件事：跳過引號區段、標出註解區段。不管字串內容是什麼。

    第 99 輪的第一版量尺是逐行看「這行開頭是不是 `//`／`*`」，
    對 `vacant_hm/js/app.js` 那種續行不加 `*` 的區塊註解**全部漏判**，
    1903 段裡塞了大量註解 ⇒ 分母是髒的。所以改成掃區間。
    """
    spans: list[tuple[int, int]] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"`":
            q, i = c, i + 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == q or (q != "`" and src[i] == "\n"):
                    break
                i += 1
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            spans.append((i, j))
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            spans.append((i, j))
            i = j
            continue
        i += 1
    return spans


# 量尺自己的已知答案格。量尺沒過就不准拿它去量待測物。
YARDSTICK_FIXTURE = [
    ("Y1 區塊註解續行沒有 `*` 也算註解",
     "/* 開頭\n   續行的中文\n*/\nconst a = '真文案';", ["續行的中文"], ["真文案"]),
    ("Y2 字串裡的 /* 不是註解開頭",
     "const a = '含有/*的文案'; const b = '後面的文案';", [], ["後面的文案"]),
    ("Y3 行註解",
     "const a = '文案甲'; // 註解甲\nconst b = '文案乙';",
     ["註解甲"], ["文案甲", "文案乙"]),
    ("Y4 模板裡的 // 不是註解",
     "const a = `網址 http://例子 後面還有中文`;", [], ["後面還有中文"]),
]


def yardstick_test() -> int:
    ok = 0
    for key, src, in_cmt, out_cmt in YARDSTICK_FIXTURE:
        spans = comment_spans(src)

        def covered(sub: str) -> bool:
            k = src.find(sub)
            return k >= 0 and any(a <= k < b for a, b in spans)

        bad = [s for s in in_cmt if not covered(s)] + \
              [s for s in out_cmt if covered(s)]
        ok += not bad
        print(f"{'OK  ' if not bad else 'FAIL'} {key}")
        if bad:
            print(f"       判錯的：{bad} · spans={spans}")
    print(f"\nP6 量尺 fixture: {ok}/{len(YARDSTICK_FIXTURE)}")
    return 0 if ok == len(YARDSTICK_FIXTURE) else 1


# ── P7：Python 抽取器探針。兩個方向都要答對，而且要跟現行 JS 路徑對照。──
# 「不准抽到」那半是重點：`#` 註解、docstring、中文識別字。
# 這三樣在 JS tokenizer 眼裡分別是「文案」「錯位的三段」「不存在」。
PY_FIXTURE = [
    ("PY1 一般字串",
     'x = "被稽核抓到就排除"', ["被稽核抓到就排除"], []),
    ("PY2 `#` 註解不算文案",
     '# 註解：被稽核抓到就排除\nx = "真文案甲"',
     ["真文案甲"], ["被稽核抓到就排除"]),
    ("PY3 模組 docstring 不算文案",
     '"""模組說明：被抓到就排除"""\nx = "真文案乙"',
     ["真文案乙"], ["模組說明：被抓到就排除"]),
    ("PY4 f-string 的洞不切斷句子",
     'x = f"牠{who}被抓到了"', ["牠▮被抓到了"], []),
    ("PY5 洞內兩個分支都要抽到",
     "x = f\"{'不合格' if bad else '通過'}\"", ["不合格", "通過"], []),
    ("PY6 註解裡的撇號不准讓後面錯位",
     '# don\'t 這行是註解\ny = "撇號之後的文案"',
     ["撇號之後的文案"], ["這行是註解"]),
    ("PY7 非 docstring 的三引號是文案",
     'x = """多行文案甲\n多行文案乙"""', ["多行文案甲", "多行文案乙"], []),
    ("PY8 中文識別字不是文案",
     '被抓到的次數 = 1\nz = "識別字之後的文案"',
     ["識別字之後的文案"], ["被抓到的次數"]),
    ("PY9 函式 docstring 排除、函式內字串保留",
     'def f():\n    """這是 docstring 不算文案"""\n    return "這是回傳的文案"',
     ["這是回傳的文案"], ["這是 docstring 不算文案"]),
    ("PY10 相鄰字串隱式相接要併成一句",
     'x = ("需要：預註冊凍結簽入 ledger ＋ "\n     "事前寫死的判準")',
     ["需要：預註冊凍結簽入 ledger ＋ 事前寫死的判準"], []),
    ("PY11 f-string 與一般字串混排相接（dashboard.py evidence 的形狀）",
     'x = (f"目前 on {n} 筆，"\n     "且本面板不承載此階宣稱")',
     ["目前 on ▮ 筆，且本面板不承載此階宣稱"], []),
]

PY_YARDSTICK_FIXTURE = [
    ("YP1 行註解",
     'x = "文案甲"  # 註解甲\ny = "文案乙"', ["註解甲"], ["文案甲", "文案乙"]),
    ("YP2 字串裡的 # 不是註解",
     'x = "含有#的文案"\ny = "後面的文案"', [], ["後面的文案", "含有#的文案"]),
    ("YP3 docstring 裡的 # 不是註解",
     '"""說明 # 井字號"""\nx = "之後的文案"', [], ["之後的文案", "說明 # 井字號"]),
    ("YP4 docstring 區間認得出來（第三類，另計）",
     '"""這是 docstring"""\nx = "這是文案"', [], []),
]


def py_test() -> int:
    """P7a：新抽取器全對。P7b：同一組 fixture 交給現行 `js_strings` 會錯幾格。"""
    ok = js_ok = 0
    for key, src, must, mustnot in PY_FIXTURE:
        blob = "".join(f for _, f in extract_py(src))
        miss = [m for m in must if m not in blob]
        leak = [m for m in mustnot if m in blob]
        good = not miss and not leak
        ok += good
        jblob = "".join(f for _, f in js_strings(src))
        jgood = (not [m for m in must if m not in jblob]
                 and not [m for m in mustnot if m in jblob])
        js_ok += jgood
        print(f"{'OK  ' if good else 'FAIL'} {key}   [現行 js_strings: "
              f"{'也對' if jgood else '答錯'}]")
        if not good:
            print(f"       缺 {miss} · 不該有卻有 {leak}")
            print(f"       實際抽到 {[f for _, f in extract_py(src)]}")
    n = len(PY_FIXTURE)
    print(f"\nP7a Python 抽取器 fixture: {ok}/{n}")
    print(f"P7b 同一組交給現行 js_strings: {js_ok}/{n} 對 · "
          f"答錯 {n - js_ok} 格（判準：答錯 ≥3，否則不該多寫這支）")
    return 0 if (ok == n and n - js_ok >= 3) else 1


def py_yardstick_test() -> int:
    """P7c：`.py` 量尺。沒過就不准拿它去量 `--cjk-audit`。"""
    ok = 0
    for key, src, in_cmt, out_cmt in PY_YARDSTICK_FIXTURE:
        spans = comment_spans_py(src)
        docs = docstring_spans_py(src)

        def covered(sub: str, rs: list[tuple[int, int]]) -> bool:
            k = src.find(sub)
            return k >= 0 and any(a <= k < b for a, b in rs)

        bad = [s for s in in_cmt if not covered(s, spans)] + \
              [s for s in out_cmt if covered(s, spans)]
        if key.startswith("YP4"):
            if not covered("這是 docstring", docs):
                bad.append("docstring 區間沒認出來")
            if covered("這是文案", docs):
                bad.append("把真文案算成 docstring")
        ok += not bad
        print(f"{'OK  ' if not bad else 'FAIL'} {key}")
        if bad:
            print(f"       判錯的：{bad} · 註解 spans={spans} · doc spans={docs}")
    print(f"\nP7c .py 量尺 fixture: {ok}/{len(PY_YARDSTICK_FIXTURE)}")
    return 0 if ok == len(PY_YARDSTICK_FIXTURE) else 1


def cjk_audit(legacy: bool, verbose: bool) -> int:
    fn = extract_js_legacy if legacy else js_strings
    tot = miss = skipped = docskip = 0
    misses: list[str] = []
    skips: list[str] = []
    for repo, pats in SCOPE:
        for pat in pats:
            for p in sorted((ROOT / repo).glob(pat)):
                if not p.is_file() or not in_scope(p):
                    continue
                src = p.read_text(encoding="utf-8", errors="replace")
                is_py = p.suffix.lower() == ".py"
                if p.suffix.lower() in (".html", ".htm"):
                    blocks = [(m.start(1), m.group(1)) for m in re.finditer(
                        r"<script\b[^>]*>(.*?)</script>", src, re.S | re.I)]
                else:
                    blocks = [(0, src)]
                label = f"{repo}/{p.relative_to(ROOT / repo)}"
                for off, body in blocks:
                    base = src[:off].count("\n") + 1
                    # `.py` 一律走 `extract_py`；`--legacy` 是拿第 97 輪那支
                    # 壞掉的 JS 抽取器重現「修之前」數字用的，套到 Python 沒有意義。
                    got = "".join(f for _, f in (
                        extract_py(body) if is_py else fn(body)))
                    cmts = comment_spans_py(body) if is_py else comment_spans(body)
                    docs = docstring_spans_py(body) if is_py else []
                    for m in _CJK.finditer(body):
                        ln = body.count("\n", 0, m.start())
                        if any(a <= m.start() < b for a, b in cmts):
                            skipped += 1
                            skips.append(f"{label}:{base + ln} {m.group(0)[:30]}")
                            continue
                        if any(a <= m.start() < b for a, b in docs):
                            docskip += 1
                            skips.append(f"{label}:{base + ln} [doc] {m.group(0)[:30]}")
                            continue
                        tot += 1
                        if m.group(0) not in got:
                            miss += 1
                            misses.append(f"{label}:{base + ln} {m.group(0)[:40]}")
    rate = 100.0 * miss / tot if tot else 0.0
    print(f"量尺＝去註解後長度≥4 的中日韓字元段（{'legacy 壞版' if legacy else '修後'}）")
    print(f"待測中文段 {tot} 段 · 抽不到 {miss} 段 · 漏失率 {rate:.1f}%")
    print(f"（判為註解而排除在分母外：{skipped} 段 · "
          f"判為 docstring 而排除在分母外：{docskip} 段）")
    for s in misses[:40]:
        print(f"  [漏] {s}")
    if len(misses) > 40:
        print(f"  … 另外 {len(misses) - 40} 段")
    if verbose:
        for s in skips:
            print(f"  [註解·排除] {s}")
    return 0 if miss == 0 else 1


# ── 紅線 B（口徑）：觀眾文案不准出現「信任」。────────────────────────────
#
# S7 全系列到第 102 輪為止掃的都是**紅線 A**（把「排除」歸因給「被抓到」）。
# 誠實邊界的另一條——「不准用『信任』，用『可究責』『讓依賴有根據』」——
# 從來沒有任何自動檢查。理由見 CLAUDE.md §5：經典定義（Gambetta 1988、
# Mayer 1995）把「不依賴監督」寫進信任的必要條件，而監督正是本系統的全部。
#
# **這支跟紅線 A 共用 SCOPE 與 `extract()`，不另開腳本**（HANDOFF §八：
# 快速版與完整版必須呼叫同一個決策函式，否則兩份程式各自被正確地修改了
# 不同次數就會漂移）。
#
# 一樣**只產生候選、不下判定**：「面板不是信任來源」是在否定信任，
# 跟 `<title>Vacant — 信任觀測台` 當招牌用不是同一件事。機器只給
# 〈否定脈絡〉提示，判定與改文案留給人類。
DICTION_FAMILIES = [
    ("F1 信任", re.compile("信任")),
    ("F2 信賴", re.compile("信賴")),
    ("F3 可信", re.compile("可信")),
    ("F4 互信", re.compile("互信")),
    ("F5 trust", re.compile("trust", re.I)),   # trusted／trustworthy／distrust 都收
]
# 刻意**不**收進詞族的鄰近詞：`信譽` 是本專案自己的機制名（五維 Beta 的那個），
# `信用`／`自信`／`相信` 不是紅線 B 講的那件事。另外印出來，
# 是為了證明「考慮過而排除」不等於「沒想到」。
DICTION_NEIGHBORS = [
    ("信譽", re.compile("信譽")),
    ("信用", re.compile("信用")),
    ("自信", re.compile("自信")),
    ("相信", re.compile("相信")),
]
# 否定脈絡只是**提示**不是判準：命中前後 12 字內有沒有否定詞。
_NEG_MARKERS = ("不", "非", "未", "別", "沒", "無", "not", "n't", "never")
_NEG_WINDOW = 12


def _neg_context(text: str, at: int, length: int) -> bool:
    seg = text[max(0, at - _NEG_WINDOW):at + length + _NEG_WINDOW].lower()
    return any(m in seg for m in _NEG_MARKERS)


def diction_scan(origin: str, label: str, frags: list[tuple[int, str]]
                 ) -> tuple[list[dict], dict[str, int]]:
    """紅線 B 的詞族掃描。實作在 `family_scan()`，B 與 C 共用同一個決策函式。"""
    return family_scan(origin, label, frags, DICTION_FAMILIES)


def _fam_counts(text: str, fams) -> dict[str, int]:
    return {name: len(rx.findall(text)) for name, rx in fams}


def family_scan(origin: str, label: str, frags: list[tuple[int, str]], fams
                ) -> tuple[list[dict], dict[str, int]]:
    """回傳（逐條命中, 獨立計數）。紅線 B 與 C 共用這一條路。

    兩條路徑刻意不同：逐條命中**走 `sentences()` 切句**（跟紅線 A 同一條路），
    獨立計數**不切句**，直接對片段 `findall`。兩邊對不上就代表切句把命中吃掉了
    ——那正是「量尺跟待測物要分開」在這裡的形狀。
    """
    rows: list[dict] = []
    counts = {name: 0 for name, _ in fams}
    for ln, frag in frags:
        for name, rx in fams:
            counts[name] += len(rx.findall(frag))
        for sent in sentences(frag):
            for name, rx in fams:
                for m in rx.finditer(sent):
                    rows.append({
                        "origin": origin, "file": label, "line": ln,
                        "family": name, "word": m.group(0),
                        "neg": _neg_context(sent, m.start(), len(m.group(0))),
                        "sent": sent[:200],
                    })
    return rows, counts


def family_collect(fams, neighbors) -> dict:
    """跑一遍 SCOPE，把紅線 B／C 要的數字**收集起來但不印**。

    抽出來是因為 `--summary` 需要同一份數字的另一種排法。總表若自己再掃一次，
    兩份實作會各自被正確地修改不同次數然後漂移（HANDOFF §八）——
    所以總表跟 `--diction`／`--strength` 必須是同一次掃描的兩個出口。
    """
    rows: list[dict] = []
    corpus: dict[str, int] = {n: 0 for n, _ in fams}
    raw: dict[str, int] = {n: 0 for n, _ in fams}
    neigh: dict[str, int] = {n: 0 for n, _ in neighbors}
    per_file: list[tuple[str, dict[str, int], dict[str, int]]] = []
    per_file_neigh: dict[str, dict[str, int]] = {}
    doc_rows: list[dict] = []
    for repo, pats in SCOPE:
        for pat in pats:
            for p in sorted((ROOT / repo).glob(pat)):
                if not p.is_file() or not in_scope(p):
                    continue
                label = f"{repo}/{p.relative_to(ROOT / repo)}"
                src = p.read_text(encoding="utf-8", errors="replace")
                r, c = family_scan("src", label, extract(p, src), fams)
                rows += r
                rc = _fam_counts(src, fams)        # 原始檔（含註解與識別字）
                for k in corpus:
                    corpus[k] += c[k]
                    raw[k] += rc[k]
                blob = "".join(f for _, f in extract(p, src))
                fn = _fam_counts(blob, neighbors)
                per_file_neigh[label] = fn
                for k, v in fn.items():
                    neigh[k] += v
                if any(c.values()) or any(rc.values()):
                    per_file.append((label, c, rc))
                if p.suffix.lower() == ".py":
                    dr, _ = family_scan("doc", label, py_docstrings(src), fams)
                    doc_rows += dr
    return {"rows": rows, "corpus": corpus, "raw": raw, "neigh": neigh,
            "per_file": per_file, "per_file_neigh": per_file_neigh,
            "doc_rows": doc_rows}


def family_audit(fams, neighbors, title: str, note: str) -> int:
    """紅線 B／C 共用的掃描主體。差別只有詞族表與抬頭。"""
    got = family_collect(fams, neighbors)
    rows, corpus, raw = got["rows"], got["corpus"], got["raw"]
    neigh, per_file, doc_rows = got["neigh"], got["per_file"], got["doc_rows"]

    print(title)
    print(note + "\n")
    print(f"{'詞族':<12}{'語料':>6}{'原始檔':>8}   （原始檔＝含註解與識別字，語料＝抽取後的文案）")
    for name, _ in fams:
        print(f"{name:<14}{corpus[name]:>5}{raw[name]:>8}")
    print(f"\n逐條列出 {len(rows)} 條（含 docstring 外的全部 src 命中）")

    # 切句路徑與不切句路徑必須逐字相同。
    listed = {n: 0 for n, _ in fams}
    for r in rows:
        listed[r["family"]] += 1
    bad = [n for n in listed if listed[n] != corpus[n]]
    print(f"獨立計數器對帳（切句 vs 不切句）："
          f"{'一致' if not bad else '不一致 ' + str([(n, listed[n], corpus[n]) for n in bad])}")

    print("\n── 逐檔分佈（語料／原始檔）──")
    for label, c, rc in per_file:
        cells = " · ".join(f"{n.split()[1]} {c[n]}/{rc[n]}"
                           for n, _ in fams if c[n] or rc[n])
        print(f"  {label}: {cells}")

    print("\n── 逐條命中 ──")
    for i, r in enumerate(rows, 1):
        tag = "否定脈絡" if r["neg"] else "肯定用法"
        print(f"[{i:02d}] {r['file']}:{r['line']}  {r['family']}「{r['word']}」 [{tag}]")
        print(f"     {r['sent']}")
    neg_n = sum(1 for r in rows if r["neg"])
    print(f"\n〈否定脈絡〉{neg_n} 條 · 〈肯定用法〉{len(rows) - neg_n} 條"
          f"（機器提示，人類逐條判定）")

    print(f"\n── 刻意排除的鄰近詞（考慮過而排除，不是沒想到）──")
    print("   " + " · ".join(f"{n} {neigh[n]}" for n, _ in neighbors))
    if doc_rows:
        print(f"\n── 刻意排除：.py 的 docstring（工作紀錄，不是觀眾文案）{len(doc_rows)} 條 ──")
        for r in doc_rows:
            print(f"   {r['file']}:{r['line']} {r['family']}「{r['word']}」 "
                  f"| {r['sent'][:90]}")
    return 0 if not bad else 1


def _family_test(fixture, fams, label: str) -> int:
    ok = 0
    for key, rel, src, want, want_neg in fixture:
        p = Path(rel)
        rows, counts = family_scan("fix", rel, extract(p, src), fams)
        got = {n: v for n, v in counts.items() if v}
        bad = []
        if got != want:
            bad.append(f"詞族數 want={want} got={got}")
        listed = {n: sum(1 for r in rows if r['family'] == n) for n in got}
        if listed != got:
            bad.append(f"切句後 {listed} ≠ 不切句 {got}")
        if want_neg is not None:
            negs = [r["neg"] for r in rows]
            if negs != [want_neg] * len(negs) or not negs:
                bad.append(f"否定脈絡 want={want_neg} got={negs}")
        ok += not bad
        print(f"{'OK  ' if not bad else 'FAIL'} {key}")
        for b in bad:
            print(f"       {b}")
    print(f"\n{label} fixture: {ok}/{len(fixture)}")
    return 0 if ok == len(fixture) else 1


# ── 紅線 C（宣稱強度）：不准宣稱「保證正確」或「防止」作惡，─────────────
# 只能說提高作惡成本、留下改不掉的紀錄。
#
# 形狀跟紅線 B 一樣是單詞族掃描，所以**共用同一份 SCOPE、`extract()`、
# `sentences()` 與 `_neg_context()`**——不另開腳本（HANDOFF §八：快速版與完整版
# 必須呼叫同一個決策函式，否則只要各自被正確地修改了不同次數就會漂移）。
#
# 但它跟 B 有一個方向相反的地方，這決定了〈否定脈絡〉在這裡怎麼讀：
# 紅線 B 命中「信任」多半是**踩線**（把詞當招牌）；紅線 C 命中「防止」
# 有可能是**守線**（「提高成本，不是防止作惡」正是誠實邊界句本身）。
# 同一個提示欄位，兩條紅線要反過來讀——所以機器一樣只給提示，不下判定。
STRENGTH_FAMILIES = [
    ("C1 保證", re.compile("保證")),
    ("C2 確保", re.compile("確保")),
    ("C3 防止", re.compile("防止|防範|阻止|擋住|擋下")),
    ("C4 杜絕", re.compile("杜絕|根除|萬無一失")),
    ("C5 絕對", re.compile("絕對|絕不|必定|百分之百")),
    ("C6 EN", re.compile("guarantee|ensure|prevent|absolutely|foolproof", re.I)),
]
# 刻意**不**收進詞族的鄰近詞。`確定性` 是本專案自己的機制名（`auditor.py` 的
# 確定性稽核），誤收會讓紅線 C 對整個稽核系列文案誤報——形狀跟紅線 B 的
# `信譽` 一模一樣。其餘四個是通用副詞，不是強宣稱本身。
STRENGTH_NEIGHBORS = [
    ("確定性", re.compile("確定性")),
    ("一定", re.compile("一定")),
    ("一律", re.compile("一律")),
    ("完全", re.compile("完全")),
    ("永遠", re.compile("永遠")),
]


def strength_audit() -> int:
    return family_audit(
        STRENGTH_FAMILIES, STRENGTH_NEIGHBORS,
        "紅線 C（宣稱強度）：不准宣稱「保證正確」或「防止」作惡"
        "——只能說提高作惡成本、留下改不掉的紀錄",
        "這支只產生候選、不下判定。注意方向跟紅線 B 相反："
        "〈否定脈絡〉在這裡多半代表**守線**（誠實邊界句本身），不是踩線。")


# 宣稱強度探針的已知答案格。負向半（`確定性` 等五個鄰近詞不得進詞族）比正向半
# 更擋事：`確定性` 在 SCOPE 裡出現 27 次，誤收會讓紅線 C 對整個稽核系列文案誤報。
STRENGTH_FIXTURE = [
    ("S1 肯定強宣稱", "index.html",
     "<p>本系統保證每一件工作都正確</p>", {"C1 保證": 1}, False),
    ("S2 誠實邊界句是否定脈絡", "index.html",
     "<p>這提高作惡成本，不保證正確</p>", {"C1 保證": 1}, True),
    ("S3 防止族五個寫法都收", "js/main.js",
     'const s = "防止、防範、阻止、擋住、擋下";', {"C3 防止": 5}, None),
    ("S4 確定性不得進詞族", "vacant/dashboard.py",
     's = "確定性稽核抽樣"', {}, None),
    ("S5 一定／一律／完全／永遠不得進詞族", "js/main.js",
     'const s = "一定要一律完全永遠";', {}, None),
    ("S6 英文不分大小寫", "js/main.js",
     'const s = "Prevent and ENSURE";', {"C6 EN": 2}, None),
    ("S7 preventDefault 是識別字不是文案", "js/main.js",
     "e.preventDefault();", {}, None),
    ("S8 `#` 註解裡的保證不算文案", "vacant/dashboard.py",
     '# 這一段講保證\nx = "提高成本"', {}, None),
    ("S9 切句不准吃掉命中", "js/main.js",
     'const s = "保證。保證；保證";', {"C1 保證": 3}, None),
    ("S10 杜絕族與絕對族各自成族", "js/main.js",
     'const s = "杜絕、根除、萬無一失、絕對、絕不、必定、百分之百";',
     {"C4 杜絕": 3, "C5 絕對": 4}, None),
]


def strength_test() -> int:
    """C1：宣稱強度探針。沒過就不准拿去量未知的。"""
    return _family_test(STRENGTH_FIXTURE, STRENGTH_FAMILIES, "C1 宣稱強度探針")


def diction_audit() -> int:
    return family_audit(
        DICTION_FAMILIES, DICTION_NEIGHBORS,
        "紅線 B（口徑）：觀眾文案不准出現「信任」——用「可究責」「讓依賴有根據」",
        "這支只產生候選、不下判定；〈否定脈絡〉是提示不是判準。")


# 口徑探針的已知答案格。兩個方向都要答對——尤其「不准抽到」那半：
# `信譽` 是本專案的機制名，誤收進來會讓紅線 B 變成永遠在鬼叫的警報器。
DICTION_FIXTURE = [
    # D1 的 want_neg 我第一次寫成 True，探針當場打回來（8/9）。
    # 「這是信任觀測台」裡一個否定詞都沒有 ⇒ 已知答案本來就是 False。
    # **改的是 fixture 不是程式碼**——這格的答案是客觀可判的，記在 S7G 報告第二節。
    ("D1 一般文案", "index.html", "<p>這是信任觀測台</p>", {"F1 信任": 1}, False),
    ("D2 信譽不得進詞族", "js/main.js", 'const s = "信譽路由三層漏斗";', {}, None),
    ("D3 信用／自信／相信不得進詞族", "js/main.js",
     'const s = "信用已被扣減，我相信自己有自信";', {}, None),
    ("D4 英文 trust 不分大小寫", "js/main.js",
     'const s = "Trust is not a claim";', {"F5 trust": 1}, None),
    ("D5 否定脈絡認得出來", "index.html",
     "<p>本面板不是信任來源</p>", {"F1 信任": 1}, True),
    ("D6 招牌用法不是否定脈絡", "index.html",
     "<title>Vacant — 信任觀測台</title>", {"F1 信任": 1}, False),
    ("D7 `#` 註解裡的信任不算文案", "vacant/dashboard.py",
     '# 這一段在講信任\nx = "可究責"', {}, None),
    ("D8 三個小詞族各自成族", "js/main.js",
     'const s = "可信、信賴、互信";',
     {"F2 信賴": 1, "F3 可信": 1, "F4 互信": 1}, None),
    ("D9 切句不准吃掉命中", "js/main.js",
     'const s = "信任。信任；信任";', {"F1 信任": 3}, None),
]


def diction_test() -> int:
    """B1：口徑探針。沒過就不准拿去量未知的。"""
    return _family_test(DICTION_FIXTURE, DICTION_FAMILIES, "B1 口徑探針")


# ── S7 系列總表：三個展件 × 三條紅線 ──────────────────────────────
#
# 這一節**不做任何新掃描**。它是 `scan_sources()`／`family_collect()` 同一份結果
# 的另一種排法。總表若自己再掃一次，兩份實作會各自被正確地修改不同次數然後漂移。
#
# ⚠ 總表最容易造成的傷害不是算錯，是**把「沒講」讀成「乾淨」**。
# 三個展件並排之後 `0` 有兩種意思。第 100 輪已經踩過一次：官網沒踩到紅線 A，
# 不是因為歸因寫對，是因為它沒講「後果」。所以每一條紅線都配一個**分母**——
# 「你本來該說的那句話」出現幾次。三條紅線的分母各自是：
#   A（歸因）  → SOLO 單邊命中（只講抓到、或只講後果，沒把兩者連起來）
#   B（口徑）  → 可究責族（B 要求的替代詞）
#   C（宣稱）  → 被允許的強度講法（提高成本／留下紀錄／改不掉）
# 分母 0 ＋ 命中 0 ＝ 沒講；分母 >0 ＋ 命中 0 ＝ 有講而且守線。這兩件事必須分得開。
EXHIBITS = [
    ("vacant-docs-web", "官網"),
    ("vacant_hm", "人類動物園"),
    ("Vacant", "觀測台"),
]

# 紅線 B 的分母：B 說「不准講信任，要講可究責／讓依賴有根據」——所以分母就是替代詞。
EVID_B = [
    ("R1 可究責", re.compile(r"可究責|究責|問責|accountab", re.I)),
    ("R2 有根據", re.compile(r"有根據|有憑據|有依據|站得住")),
]
# 紅線 C 的分母：C 說「不准講保證／防止，只能講提高成本、留下改不掉的紀錄」。
EVID_C = [
    ("R3 提高成本", re.compile(r"(提高|抬高|拉高|增加)[^。！？；\n]{0,6}成本"
                              r"|成本[^。！？；\n]{0,4}(提高|變高|上升)|raise[sd]?[- ]cost", re.I)),
    ("R4 留下紀錄", re.compile(r"留下[^。！？；\n]{0,6}(紀錄|記錄|痕跡)|會留下|留得下|上鏈|寫進帳")),
    # ⚠ `竄改` 原本只收「不可竄改｜竄改不了」，漏掉 `app.html:37`
    # 「任一行被**竄改**／重排／刪除都會改變它」——那是全站最正宗的「改不掉」宣稱。
    # 是拿本輪結果去對第 104 輪紀錄（觀測台 C 分母該是 8，機器給 0）才照出來的。
    ("R5 改不掉", re.compile(r"改不掉|刪不掉|抹不掉|賴不掉|竄改|事後改")),
]

# 分母詞族的已知答案格。**分母本身也是量尺，一樣要先驗兩個方向。**
# 「不准抽到」那半直接取自觀測台的面板欄位名：第 104 輪的事後診斷用裸關鍵字
# 數出「app.js 提高成本 2 · 留下紀錄 3」，但那 5 個全是「尚無成本資料」
# 「交付紀錄」這類欄位標籤，**不是在講「提高作惡成本」**。
# 裸關鍵字計數會把 UI 標籤算成「有在講」，於是分母虛高、`0` 被讀成「守線」。
EVID_FIXTURE = [
    ("E1 提高作惡成本", "index.html", "<p>它只提高作惡的成本</p>", {"R3 提高成本": 1}, None),
    ("E2 留下紀錄", "index.html", "<p>做過什麼會留下紀錄</p>", {"R4 留下紀錄": 1}, None),
    ("E3 竄改會被看出來", "index.html",
     "<p>任一行被竄改／重排／刪除都會改變它</p>", {"R5 改不掉": 1}, None),
    ("E4 欄位標籤不算有在講（成本）", "js/main.js",
     'const s = "尚無成本資料";', {}, None),
    ("E5 欄位標籤不算有在講（紀錄）", "js/main.js",
     'const s = "交付紀錄。尚無稽核紀錄";', {}, None),
    ("E6 單位成本代理量不是強度宣稱", "js/main.js",
     'const s = "是單位成本品質的可觀測代理量";', {}, None),
]
EVID_B_FIXTURE = [
    ("E7 可究責", "index.html", "<p>這是可究責層</p>", {"R1 可究責": 1}, None),
    ("E8 讓依賴有根據", "index.html", "<p>讓依賴有根據</p>", {"R2 有根據": 1}, None),
    ("E9 信譽不算可究責族", "js/main.js", 'const s = "信譽路由";', {}, None),
]


def evid_test() -> int:
    """G2：分母探針。分母沒驗過，`0` 就不准被讀成「守線」。"""
    rc = _family_test(EVID_FIXTURE, EVID_C, "G2a C 分母探針")
    print()
    return _family_test(EVID_B_FIXTURE, EVID_B, "G2b B 分母探針") or rc


def exhibit_of(label: str) -> str:
    """`vacant_hm/world/js/main.js` → `vacant_hm`。"""
    return label.split("/", 1)[0]


def by_exhibit(rows: list[dict], field: str = "file") -> dict[str, int]:
    """把逐條命中按展件分組。**純函式**——吃 rows 出計數，才能餵已知答案給它。

    落在 EXHIBITS 之外的 label 不會被靜靜丟掉，而是自己成一格印出來
    （總表最不能有的就是無聲截斷）。
    """
    out: dict[str, int] = {repo: 0 for repo, _ in EXHIBITS}
    for r in rows:
        k = exhibit_of(r[field])
        out[k] = out.get(k, 0) + 1
    return out


def _denominator_a() -> dict[str, int]:
    """紅線 A 的分母：只中一邊的句子（有在講這件事，只是沒把兩頭連起來）。"""
    return by_exhibit(SOLO)


def summary_audit() -> int:
    cands, chars, files = scan_sources()
    b = family_collect(DICTION_FAMILIES, DICTION_NEIGHBORS)
    c = family_collect(STRENGTH_FAMILIES, STRENGTH_NEIGHBORS)
    eb = family_collect(EVID_B, [])
    ec = family_collect(EVID_C, [])

    a_hit, b_hit, c_hit = by_exhibit(cands), by_exhibit(b["rows"]), by_exhibit(c["rows"])
    a_den, b_den, c_den = _denominator_a(), by_exhibit(eb["rows"]), by_exhibit(ec["rows"])
    nfile: dict[str, int] = {r: 0 for r, _ in EXHIBITS}
    nchar: dict[str, int] = {r: 0 for r, _ in EXHIBITS}
    for label, n in FILE_CHARS.items():
        nfile[exhibit_of(label)] = nfile.get(exhibit_of(label), 0) + 1
        nchar[exhibit_of(label)] = nchar.get(exhibit_of(label), 0) + n

    print("S7 系列總表：三個展件 × 三條誠實邊界")
    print("**不是新掃描**——是 --scan／--diction／--strength 同一份結果的重新分組。")
    print("這支只產生候選、不下判定。\n")
    print("紅線 A＝歸因（把「抓到」與「後果」連成因果）· "
          "B＝口徑（不准出現「信任」）· C＝宣稱強度（不准說「保證」「防止」）\n")

    head = f"{'展件':<12}{'檔':>4}{'語料字元':>9}  │{'紅線A':>7}{'紅線B':>7}{'紅線C':>7}"
    print(head)
    print("─" * 55)
    for repo, name in EXHIBITS:
        print(f"{name:<13}{nfile[repo]:>3}{nchar[repo]:>9}  │"
              f"{a_hit[repo]:>6}{b_hit[repo]:>6}{c_hit[repo]:>6}")
    print("─" * 55)
    print(f"{'小計':<13}{sum(nfile.values()):>3}{sum(nchar.values()):>9}  │"
          f"{sum(a_hit.values()):>6}{sum(b_hit.values()):>6}{sum(c_hit.values()):>6}")

    print("\n── 分母：「本來該說的那句話」出現幾次 ──")
    print("   命中 0 ＋ 分母 0 ＝ **根本沒講**；命中 0 ＋ 分母 >0 ＝ **有講而且守線**。")
    print(f"\n{'展件':<12}{'A 單邊句':>9}{'B 可究責':>9}{'C 允許講法':>11}   讀法")
    # ⚠ A 欄跟 B／C 欄的三態**不一樣**，不能共用同一句讀法。
    # B／C 的分母是「該說的替代詞」⇒ 分母 >0 ＋ 命中 0 真的是守線。
    # A 的分母是 SOLO **單邊句**（只講「抓到」或只講「後果」，沒把兩頭連起來）
    # ⇒ 分母 >0 ＋ 命中 0 只代表**講了一半**，那既不是踩線也不是守線。
    # 第一版我把它一起寫成「守線」——為了防「沒講被讀成乾淨」而加的分母，
    # 自己又把「講了一半」讀成了乾淨。同一個病往上爬了一層。
    for repo, name in EXHIBITS:
        reads = [f"A=" + ("命中" if a_hit[repo] else
                          ("單邊" if a_den[repo] else "沒講"))]
        for tag, h, d in (("B", b_hit[repo], b_den[repo]),
                          ("C", c_hit[repo], c_den[repo])):
            reads.append(f"{tag}=" + ("命中" if h else ("守線" if d else "沒講")))
        print(f"{name:<13}{a_den[repo]:>7}{b_den[repo]:>9}{c_den[repo]:>10}   "
              + " · ".join(reads))
    print("\n   A 的「單邊」＝只講「抓到」或只講「後果」，沒把兩頭連成因果"
          "——不是守線，是講了一半。")

    print("\n── 對帳：總表列小計必須等於各單掃描的既往總數 ──")
    checks = [
        ("A 候選數", sum(a_hit.values()), len(cands)),
        ("A 檔數", sum(nfile.values()), len(files)),
        ("A 語料字元", sum(nchar.values()), chars),
        ("B 逐條命中", sum(b_hit.values()), len(b["rows"])),
        ("C 逐條命中", sum(c_hit.values()), len(c["rows"])),
    ]
    bad = [n for n, x, y in checks if x != y]
    for n, x, y in checks:
        print(f"   {n:<12} 總表 {x:>6} vs 單掃描 {y:>6}   {'一致' if x == y else '不一致'}")

    print("\n── 逐檔（只印有命中的）──")
    per_b = {label: cc for label, cc, _ in b["per_file"]}
    per_c = {label: cc for label, cc, _ in c["per_file"]}
    for label in sorted(set(per_b) | set(per_c)):
        cells = []
        for tag, d in (("B", per_b.get(label, {})), ("C", per_c.get(label, {}))):
            for k, v in d.items():
                if v:
                    cells.append(f"{tag}:{k.split()[1]} {v}")
        if cells:
            print(f"   {label}: " + " · ".join(cells))
    return 0 if not bad else 1


# 分組探針的已知答案格。總表本身是一個量測工具 ⇒ 先餵它一定知道答案的輸入。
SUMMARY_FIXTURE = [
    ("G1 三展件各自分對",
     [{"file": "vacant_hm/index.html"}, {"file": "vacant_hm/js/a.js"},
      {"file": "vacant_hm/world/js/clay/b.js"}, {"file": "vacant-docs-web/index.html"}],
     {"vacant-docs-web": 1, "vacant_hm": 3, "Vacant": 0}),
    ("G2 空輸入三格全 0",
     [], {"vacant-docs-web": 0, "vacant_hm": 0, "Vacant": 0}),
    ("G3 只落在觀測台",
     [{"file": "Vacant/vacant/dashboard.py"}, {"file": "Vacant/vacant/web/app.js"}],
     {"vacant-docs-web": 0, "vacant_hm": 0, "Vacant": 2}),
    # 這一格是「不准靜靜丟掉」那半：SCOPE 之外的 label 必須自己冒出來，
    # 不能被吞進三格裡任何一格，也不能消失（消失了小計就會對不上總數）。
    ("G4 未知展件不得被靜靜丟掉",
     [{"file": "some-other-repo/x.html"}, {"file": "vacant_hm/index.html"}],
     {"vacant-docs-web": 0, "vacant_hm": 1, "Vacant": 0, "some-other-repo": 1}),
]


def summary_test() -> int:
    """G1：分組探針。沒過就不准拿去排總表。"""
    ok = 0
    for key, rows, want in SUMMARY_FIXTURE:
        got = by_exhibit(rows)
        bad = []
        if got != want:
            bad.append(f"分組 want={want} got={got}")
        if sum(got.values()) != len(rows):
            bad.append(f"小計 {sum(got.values())} ≠ 總數 {len(rows)}（有條目被丟掉）")
        ok += not bad
        print(f"{'OK  ' if not bad else 'FAIL'} {key}")
        for x in bad:
            print(f"       {x}")
    print(f"\nG1 分組探針 fixture: {ok}/{len(SUMMARY_FIXTURE)}")
    return 0 if ok == len(SUMMARY_FIXTURE) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--tok-test", action="store_true",
                    help="P5：tokenizer 已知答案探針（含『不准抽到』那半）")
    ap.add_argument("--cjk-audit", action="store_true",
                    help="P6：獨立量尺——中文段有沒有被讀進去")
    ap.add_argument("--legacy", action="store_true",
                    help="--cjk-audit 用第 97 輪那支壞的抽取器（重現修前數字）")
    ap.add_argument("--show-skipped", action="store_true",
                    help="--cjk-audit 印出被判為註解而排除的每一段")
    ap.add_argument("--py-test", action="store_true",
                    help="P7：Python 抽取器已知答案探針（含量尺與 js 對照）")
    ap.add_argument("--diction", action="store_true",
                    help="紅線 B：口徑掃描——觀眾文案有沒有出現「信任」")
    ap.add_argument("--diction-test", action="store_true",
                    help="B1：口徑探針已知答案格（含『不准抽到』那半）")
    ap.add_argument("--strength", action="store_true",
                    help="紅線 C：宣稱強度掃描——有沒有說「保證」「防止」")
    ap.add_argument("--strength-test", action="store_true",
                    help="C1：宣稱強度探針已知答案格（含『不准抽到』那半）")
    ap.add_argument("--summary", action="store_true",
                    help="S7 總表：三個展件 × 紅線 A／B／C（重新分組，不新掃描）")
    ap.add_argument("--summary-test", action="store_true",
                    help="G1：分組探針已知答案格（含『不准靜靜丟掉』那半）")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--dom", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--diag", action="store_true",
                    help="印只中一邊的句子：分辨『沒踩到』與『根本沒提這件事』")
    a = ap.parse_args()

    if a.tok_test:
        rc = yardstick_test()          # 量尺沒過就不准往下量
        print()
        return tok_test() or rc
    if a.py_test:
        rc = py_yardstick_test()       # 量尺沒過就不准往下量
        print()
        return py_test() or rc
    if a.summary_test:
        rc = evid_test()               # 分母沒驗過就不准拿去讀「守線」
        print()
        return summary_test() or rc
    if a.summary:
        rc = evid_test()
        print()
        rc = summary_test() or rc      # 探針沒過就不准往下排表
        print()
        if rc:
            print("G1 探針沒過 ⇒ 不往下排總表。先修探針。")
            return rc
        return summary_audit()
    if a.strength_test:
        return strength_test()
    if a.strength:
        rc = strength_test()           # 探針沒過就不准往下量
        print()
        if rc:
            print("C1 探針沒過 ⇒ 不往下掃。先修探針。")
            return rc
        return strength_audit()
    if a.diction_test:
        return diction_test()
    if a.diction:
        rc = diction_test()            # 探針沒過就不准往下量
        print()
        if rc:
            print("B1 探針沒過 ⇒ 不往下掃。先修探針。")
            return rc
        return diction_audit()
    if a.cjk_audit:
        return cjk_audit(a.legacy, a.show_skipped)
    if a.self_test:
        return self_test()
    if not a.scan:
        ap.print_help()
        return 2

    cands, chars, files = scan_sources()
    origin_note = f"原始碼 {len(files)} 檔 · {chars} 字元"
    if a.dom:
        dc, dn, df = scan_dom(a.dom)
        cands += dc
        chars += dn
        files += df
        origin_note += f" ＋ DOM {len(df)} 檔 · {dn} 字元"

    print(f"掃描範圍：{origin_note}")
    print(f"P3 覆蓋量閘門（>20000）：{chars} → {'PASS' if chars > 20000 else 'FAIL'}")
    print(f"候選數：{len(cands)}\n")
    for i, c in enumerate(cands, 1):
        print(f"[{i:02d}] ({c['origin']}) {c['file']}:{c['line']}")
        print(f"     抓到類={c['catch']} 排除類={c['exclude']}")
        print(f"     {c['sent']}")
    if DOC_DROPPED:
        tot_seg = sum(d["segs"] for d in DOC_DROPPED)
        tot_chr = sum(d["chars"] for d in DOC_DROPPED)
        tot_cand = sum(len(d["cands"]) for d in DOC_DROPPED)
        print(f"\n── 刻意排除：.py 的 docstring（工作紀錄，不是觀眾文案）──")
        print(f"   {tot_seg} 段 · {tot_chr} 字元 · 其中候選句 {tot_cand} 條"
              f"（>0 就要逐條看該不該收回來）")
        for d in DOC_DROPPED:
            print(f"   {d['file']}: {d['segs']} 段 / {d['chars']} 字元")
            for c in d["cands"]:
                print(f"     [docstring 候選] :{c['line']} {c['sent'][:120]}")
    if a.diag:
        conly = [s for s in SOLO if s["catch"]]
        eonly = [s for s in SOLO if s["exclude"]]
        print(f"\n── 診斷：只中〈抓到類〉{len(conly)} 句 · 只中〈排除類〉{len(eonly)} 句 ──")
        for tag, rows in (("抓到", conly), ("排除", eonly)):
            for s in rows:
                w = s["catch"] or s["exclude"]
                print(f"  [{tag}] {s['file']}:{s['line']} {w} | {s['sent'][:90]}")
    if a.json:
        a.json.write_text(json.dumps(
            {"chars": chars, "files": files, "candidates": cands},
            ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
