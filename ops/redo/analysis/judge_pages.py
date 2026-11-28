#!/usr/bin/env python3
"""判定問法離線測（2026-11-28，事後探索性）的共用件：讀該格 agent 抓過的凍結頁、解析表格列與內文句、值的比對與第二正規化器。
規則見 ops/redo/audit/judge_v2v3_20261128/PLAN.md（呼叫前已提交）。"""
from __future__ import annotations
import functools, hashlib, html as _html, json, pathlib, re, sys
from html.parser import HTMLParser
REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "d2"))
from ops.d2 import expT_metrics as M  # noqa: E402
from vacant_network.trace import sources as SRC  # noqa: E402
SRC._plain = functools.lru_cache(maxsize=256)(SRC._plain)

AGE_RE = re.compile(r";?\s*\d+\s+years?\s+ago", re.I)
TICK_RES = [re.compile(r"\b([A-Za-z]{2,10})\s*:\s*([A-Z0-9][A-Z0-9.\-]{0,9})\b"),
            re.compile(r"\b([A-Z0-9][A-Z0-9.\-]{0,9})\s*\(\s*([A-Za-z]{2,10})\s*\)")]
SCALE = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}


def norm(s: str) -> str:
    return re.sub(r"[\s`*,]", "", _html.unescape(s or "")).lower()


def ticker_pairs(s: str) -> set:
    out = set()
    for m in TICK_RES[0].finditer(s or ""):
        out.add((m.group(1).lower(), m.group(2).upper()))
    for m in TICK_RES[1].finditer(s or ""):
        out.add((m.group(2).lower(), m.group(1).upper()))
    return {p for p in out if p[0] in {"nyse", "nasdaq", "lse", "sehk", "bsx", "tsx", "asx", "euronext", "otc", "fwb", "six", "tyo", "nse", "bse", "amex", "otcqx", "krx"}}


def key_equiv(val: str, ans: str, label: str) -> str | None:
    """第二正規化器：回 'age'／'ticker'／None。"""
    cv = M.canon_strict(val)
    if cv is not None and cv == M.canon_strict(AGE_RE.sub("", ans or "")) and AGE_RE.search(ans or ""):
        return "age"
    if label.strip().lower() == "traded as":
        vp, ap = ticker_pairs(val), ticker_pairs(ans)
        if vp and vp <= ap:
            return "ticker"
    return None


def num_with_scale(s: str):
    m = re.search(r"(-?\d[\d,]*\.?\d*)\s*(thousand|million|billion|trillion)?", s or "", re.I)
    if not m:
        return None
    x = float(m.group(1).replace(",", ""))
    return x * SCALE.get((m.group(2) or "").lower(), 1.0), m.group(1)


def unit_or_round(val: str, ans: str) -> bool:
    a, b = num_with_scale(val), num_with_scale(ans)
    if not a or not b or a[0] == 0 or b[0] == 0:
        return False
    va, vb = a[0], b[0]
    for k in (-4, -3, -2, -1, 1, 2, 3, 4):
        if abs(va * (1000 ** k) - vb) <= 1e-9 * abs(vb):
            return True
    sig = min(len(re.sub(r"[^\d]", "", a[1]).lstrip("0")), len(re.sub(r"[^\d]", "", b[1]).lstrip("0")))
    if sig <= 0:
        return False
    fmt = lambda x: float(f"{x:.{sig}g}")
    return va != vb and fmt(va) == fmt(vb)


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.tables = []; self.stack = []; self.cell = None; self.row = None; self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "table":
            self.stack.append([]); self.tables.append(self.stack[-1])
        elif tag == "tr" and self.stack:
            self.row = []; self.stack[-1].append(self.row)
        elif tag in ("td", "th") and self.row is not None:
            self.cell = [tag, []]; self.row.append(self.cell)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag == "table" and self.stack:
            self.stack.pop(); self.row = None
        elif tag in ("td", "th"):
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None and not self.skip:
            self.cell[1].append(data)


@functools.lru_cache(maxsize=256)
def parse_tables(html: str):
    p = _Tables(); p.feed(html or "")
    return [[[(t, " ".join("".join(parts).split())) for t, parts in r] for r in tb if r] for tb in p.tables]


def fetched_pages(c0: pathlib.Path) -> list[tuple[str, str]]:
    shas = set()
    for ej in (c0 / "snapshot" / "vh").glob("trace/projects/*/egress.jsonl"):
        for l in ej.read_text(errors="replace").splitlines():
            try:
                e = json.loads(l)
            except ValueError:
                continue
            if e.get("method") == "GET" and e.get("status") == 200 and e.get("sha256"):
                shas.add(e["sha256"])
    out = []
    for f in sorted((c0 / "site_frozen").glob("*")):
        if f.is_file() and f.name != "index.html":
            b = f.read_bytes()
            if hashlib.sha256(b).hexdigest() in shas:
                out.append((f.name, b.decode("utf-8", "replace")))
    return out


def cell_match(cell: str, val: str) -> bool:
    if not cell:
        return False
    if norm(cell) == norm(val):
        return True
    cc, cv = M.canon_strict(cell), M.canon_strict(val)
    return cc is not None and cc == cv and len(norm(cell)) <= 3 * len(norm(val)) + 20


def row_locs(tables, val: str):
    """(表 i, 列 j, 欄 k)：單一儲存格相符；或相鄰儲存格接起來相符（k＝起點）。"""
    out = []
    nv = norm(val)
    for i, tb in enumerate(tables):
        for j, r in enumerate(tb):
            texts = [c[1] for c in r]
            for k, t in enumerate(texts):
                if cell_match(t, val):
                    out.append((i, j, k)); continue
                acc = norm(t)
                for k2 in range(k + 1, min(len(texts), k + 4)):
                    acc += norm(texts[k2])
                    if acc == nv:
                        out.append((i, j, k)); break
    return out


@functools.lru_cache(maxsize=256)
def sentences(plain: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", plain) if s.strip()]


def in_sentence(plain: str, val: str) -> str | None:
    nums = re.findall(r"\d+(?:\.\d+)?", (val or "").replace(",", ""))
    for s in sentences(plain):
        if SRC.plain_contains(s, val):
            return s
        if nums and len(nums) >= 1 and all(re.search(rf"(?<![\d.]){re.escape(n)}(?![\d])", s.replace(",", "")) for n in nums) and len("".join(nums)) >= 3:
            return s
    return None


def on_pages(pages, val: str) -> bool:
    for _, h in pages:
        if SRC.plain_contains(h, val):
            return True
        if row_locs(parse_tables(h), val):
            return True
        if in_sentence(SRC._plain(h), val):
            return True
    return False
