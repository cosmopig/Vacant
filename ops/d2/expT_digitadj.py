#!/usr/bin/env python3
"""B41(3)「數字相鄰命中」的計數（機械、不看答案鍵）。2026-11-28。

定義：b24 比「只補回、不正規化」多解除的行裡，命中段在正規化後的頁面文字中，前一個字元是數字且值以數字開頭，
或後一個字元是數字且值以數字結尾。回傳 (多解除的行數, 其中數字相鄰的行數)。
"""
from __future__ import annotations
import pathlib, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_feedback as FB  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402


def _norm_map(s: str):
    out, idx, i, n = [], [], 0, len(s)
    while i < n:
        ch = s[i]
        if ch in "*`":
            i += 1; continue
        if ch.isspace():
            j = i
            while j < n and s[j].isspace():
                j += 1
            nxt = s[j] if j < n else ""; prv = out[-1] if out else ""
            if nxt in "()" or prv in "()":
                i = j; continue
            for k in range(i, j):
                out.append(s[k]); idx.append(k)
            i = j; continue
        out.append(ch); idx.append(i); i += 1
    return "".join(out), idx


def count(vh: pathlib.Path, report_text: str, claims, bound: int | None) -> tuple[int, int]:
    def flags(ident: bool):
        FB.set_flag_matching("b24"); orig = FB.b24_norm
        if ident:
            FB.b24_norm = lambda s: s or ""
        try:
            return FB.compute_flags_from_recorder(FB.open_recorder(vh), report_text, claims, round_idx=0, cur_bound_seq=bound,
                                                  ingest_egress=False)["flags_by_claim"]
        finally:
            FB.b24_norm = orig
    rst, b24 = flags(True), flags(False)
    rec = FB.open_recorder(vh)
    univ = [S._plain(str(u.get("text") or "")) for u in FB.fetch_universe(rec) if bound is None or int(u["seq"]) <= bound]
    extra = adj = 0
    for cid, n in b24.items():
        if not (rst[cid].get("flagged") and not n.get("flagged")):
            continue
        extra += 1; nv = FB.b24_norm(n.get("value") or "")
        for p in univ:
            np_, idx = _norm_map(p); j = np_.find(nv)
            if j >= 0 and nv:
                a, z = idx[j], idx[j + len(nv) - 1] + 1
                if (nv[0].isdigit() and a > 0 and p[a - 1].isdigit()) or (nv[-1].isdigit() and z < len(p) and p[z].isdigit()):
                    adj += 1
                break
    return extra, adj
