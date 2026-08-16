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
_JS_STR = re.compile(r"""'([^'\\\n]{2,})'|"([^"\\\n]{2,})"|`([^`\\]{2,})`""")


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
    out: list[tuple[int, str]] = []
    for m in _JS_STR.finditer(src):
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--dom", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--diag", action="store_true",
                    help="印只中一邊的句子：分辨『沒踩到』與『根本沒提這件事』")
    a = ap.parse_args()

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
