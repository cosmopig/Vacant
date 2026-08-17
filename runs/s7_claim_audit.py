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
import json
import re
import sys
from pathlib import Path

ROOT = Path.home() / "vacant"

# ── 範圍：觀眾看得到的檔。probe/ styles/ *FINDINGS.md 是工作紀錄，不是文案。──
SCOPE = [
    ("vacant-docs-web", ["index.html", "js/main.js"]),
    ("vacant_hm", ["index.html", "js/*.js", "world/*.html", "world/js/*.js",
                   "world/js/clay/*.js"]),
    ("Vacant", ["vacant/web/app.html", "vacant/web/app.js"]),
]
EXCLUDE_PARTS = ("probe", "styles", "vendor", "node_modules")

# ⚠ 事前登記的 CATCH 少了「抽到／抽中／被抽」這一族，會漏掉
# `vacant_hm/index.html:107` 的「抽到就扣分」——那句正是本輪要找的形狀。
# 是 --diag（也是事後加的）把它照出來的。**事後加詞是放寬召回、不是放寬判準**，
# 候選只會變多、被看的只會更多；照實記在 S7_CLAIM_AUDIT.md 第四節。
CATCH = ["稽核", "抽查", "查核", "抓到", "抓住", "查獲", "揭發", "識破",
         "發現作假", "被抓", "audit", "Audit", "caught", "Caught",
         "抽到", "抽中", "被抽", "抽樣", "查到", "逮"]
EXCLUDE_CLAIM = ["排除", "踢出", "淘汰", "停權", "出局", "拿不到工作", "不再派工",
                 "再也", "永久", "slash", "Slash", "扣分", "降權", "封鎖", "剔除"]

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


def extract(path: Path, src: str) -> list[tuple[int, str]]:
    if path.suffix.lower() in (".html", ".htm"):
        return extract_html(src)
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


def cjk_audit(legacy: bool, verbose: bool) -> int:
    fn = extract_js_legacy if legacy else js_strings
    tot = miss = skipped = 0
    misses: list[str] = []
    skips: list[str] = []
    for repo, pats in SCOPE:
        for pat in pats:
            for p in sorted((ROOT / repo).glob(pat)):
                if not p.is_file() or not in_scope(p):
                    continue
                src = p.read_text(encoding="utf-8", errors="replace")
                if p.suffix.lower() in (".html", ".htm"):
                    blocks = [(m.start(1), m.group(1)) for m in re.finditer(
                        r"<script\b[^>]*>(.*?)</script>", src, re.S | re.I)]
                else:
                    blocks = [(0, src)]
                label = f"{repo}/{p.relative_to(ROOT / repo)}"
                for off, body in blocks:
                    base = src[:off].count("\n") + 1
                    got = "".join(f for _, f in fn(body))
                    cmts = comment_spans(body)
                    for m in _CJK.finditer(body):
                        ln = body.count("\n", 0, m.start())
                        if any(a <= m.start() < b for a, b in cmts):
                            skipped += 1
                            skips.append(f"{label}:{base + ln} {m.group(0)[:30]}")
                            continue
                        tot += 1
                        if m.group(0) not in got:
                            miss += 1
                            misses.append(f"{label}:{base + ln} {m.group(0)[:40]}")
    rate = 100.0 * miss / tot if tot else 0.0
    print(f"量尺＝去註解後長度≥4 的中日韓字元段（{'legacy 壞版' if legacy else '修後'}）")
    print(f"待測中文段 {tot} 段 · 抽不到 {miss} 段 · 漏失率 {rate:.1f}%")
    print(f"（判為註解而排除在分母外：{skipped} 段）")
    for s in misses[:40]:
        print(f"  [漏] {s}")
    if len(misses) > 40:
        print(f"  … 另外 {len(misses) - 40} 段")
    if verbose:
        for s in skips:
            print(f"  [註解·排除] {s}")
    return 0 if miss == 0 else 1


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
