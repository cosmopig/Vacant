#!/usr/bin/env python3
"""B36(2)(a) 合成規格測試：b24 模式在各類 (值, 頁面) 對上必須給出 B24／B32 規定的結果。不看答案鍵。2026-11-28。

每一對都走同一條實作路徑（`expT_feedback.compute_line_flags`，universe＝一頁），比較 literal 與 b24 的「這行是否配上（沒被標 F1）」。
預期（B36(2)(a)）：
  same          完全相同、沒有特徵            ⇒ b24 == literal
  paren_ws      只差括號內外空白（含 U+00A0、U+2009）⇒ b24 配上
  md            只差 `*` 或反引號               ⇒ b24 配上
  other_ws／underscore／minus  只差其他位置的空白、`_`、Unicode 負號 ⇒ b24 配不上
  thousands     只差千分位 ⇒ 和 literal 相同（B41(1)：舊 literal 對數字本來就忽略千分位，b24 沿用）
  boundary      數字邊界（值 12／頁面 123）⇒ b24 == literal；
                值 12(3)／頁面 112 (3) ⇒ **已知偏離（B41(2)）**：B32(3) 原樣執行的結果是配上，記為 known_deviation，不算失敗
用法：expT_b36_spec_test.py --out RESULT.json
"""
import argparse, json, pathlib, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_feedback as FB  # noqa: E402

CASES = [
    ("same", "US$2.9 billion (2016)", "<td>US$2.9 billion (2016)</td>", "eq_literal"),
    ("same", "Monolithic kernel", "<p>Kernel type Monolithic kernel here</p>", "eq_literal"),
    ("same", "absent value", "<p>nothing relevant here</p>", "eq_literal"),
    ("paren_ws", "32(1)", "<td>32</td> <td>(1)</td>", "match"),
    ("paren_ws", "32 (1)", "<td>32(1)</td>", "match"),
    ("paren_ws", "32(1)", "<p>32 (1)</p>", "match"),
    ("paren_ws", "32(1)", "<p>32 (1)</p>", "match"),
    ("paren_ws", "Xfce (default)", "<p>Xfce ( default )</p>", "match"),
    ("md", "**32 (1)**", "<p>32 (1)</p>", "match"),
    ("md", "`US$2.9 billion`", "<p>US$2.9 billion</p>", "match"),
    ("md", "`32` `(1)`", "<p>32 (1)</p>", "match"),
    ("other_ws", "US$2.9billion", "<p>US$2.9 billion</p>", "no_match"),
    ("other_ws", "US$ 2.9 billion", "<p>US$2.9 billion</p>", "no_match"),
    ("underscore", "x86_64", "<p>x86-64</p>", "no_match"),
    ("underscore", "foo_bar", "<p>foo bar</p>", "no_match"),
    ("thousands", "1234567", "<p>1,234,567 employees</p>", "eq_literal"),
    ("minus", "-76.8 million", "<p>−76.8 million</p>", "no_match"),
    ("boundary", "12", "<p>value 123 here</p>", "eq_literal"),
    ("boundary", "12(3)", "<p>value 112 (3) here</p>", "known_deviation_b41"),
    ("boundary", "12 (3)", "<p>value 12 (34) here</p>", "eq_literal"),
]


def matched(mode: str, value: str, page: str) -> bool:
    FB.set_flag_matching(mode)
    claims = [{"id": "c01", "entity": "E", "label": "L", "template_line": "- E — L: "}]
    report = f"- E — L: {value}\n"
    uni = [{"seq": 1, "url": "http://t.d2-sources.example/p.html", "text": page, "source": "egress"}]
    f = FB.compute_line_flags(report, claims, uni, round_idx=0, cur_bound_seq=1)
    return not f["flags_by_claim"]["c01"]["flagged"]


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
    rows = []; ok_all = True
    for cls, v, p, exp in CASES:
        lit, b24 = matched("literal", v, p), matched("b24", v, p)
        ok = (b24 == lit) if exp == "eq_literal" else (b24 is True) if exp in ("match", "known_deviation_b41") else (b24 is False)
        ok_all &= ok
        rows.append({"class": cls, "value": v, "page": p, "expect": exp, "literal": lit, "b24": b24, "pass": ok})
        print(("PASS " if ok else "FAIL ") + f"{cls:10s} expect={exp:10s} literal={lit!s:5s} b24={b24!s:5s}  {v!r} | {p!r}")
    FB.set_flag_matching("literal")
    pathlib.Path(a.out).write_text(json.dumps({"all_pass": ok_all, "cases": rows}, ensure_ascii=False, indent=1))
    print("ALL PASS" if ok_all else "NOT ALL PASS")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
