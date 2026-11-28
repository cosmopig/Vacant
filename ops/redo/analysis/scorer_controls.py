#!/usr/bin/env python3
"""評分器效度 1(a)：合成控制組（不涉及任何實驗資料）。『必須視為不同』與『應視為相同』兩組，跑現行 canon_strict（相等＝判同）
與第二正規化器（canon_strict 相等，或合 K 規則）。報各自誤放（該不同卻判同）與誤擋（該相同卻判不同）。"""
import json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from regrade_sensitivity import key_equiv_nolabel, M  # noqa: E402
DIFF = [  # (類別, 值, 答案) —— 必須判不同
    ("scale", "US$3 million", "US$3 billion"), ("scale", "3 thousand", "3 million"), ("scale", "€1.2 billion", "€1.2 trillion"), ("scale", "US$5 bn", "US$5 m"),
    ("sign", "−3", "3"), ("sign", "-3 million", "3 million"), ("sign", "US$(120) million", "US$120 million"), ("sign", "loss of US$5 million", "US$5 million"),
    ("percent", "10%", "10"), ("percent", "15%", "15 million"), ("percent", "2.5%", "2.5"),
    ("currency", "USD 10", "JPY 10"), ("currency", "€10 billion", "US$10 billion"), ("currency", "£3 million", "US$3 million"), ("currency", "CN¥8 billion", "US$8 billion"),
    ("period", "US$5 billion (2023)", "US$5 billion (2024)"), ("period", "US$5 billion (FY2023)", "US$5 billion (Q3 2023)"), ("period", "US$2 billion (2022)", "US$2 billion"),
    ("unit", "10 km", "10 mi"), ("unit", "5 kg", "5 lb"), ("unit", "300 employees", "300 stores"),
    ("date", "March 1990", "April 1990"), ("date", "5 March 1990", "3 May 1990"),
    ("football_order", "12 (3)", "3 (12)"), ("football_partial", "12", "12 (0)"), ("football_partial", "(3)", "12 (3)"),
    ("decimal", "1.5", "15"), ("ticker", "NYSE: ABC", "NYSE: ABD"), ("ticker_exchange", "Nasdaq: ABC", "NYSE: ABC"),
]
SAME = [  # 應判相同
    ("currency_form", "US$3 million", "$3 million"), ("currency_form", "USD 3 million", "US$3 million"), ("thousands_sep", "1,234", "1234"),
    ("scale_word_vs_digits", "US$3 million", "US$3,000,000"), ("scale_abbrev", "US$3.2 bn", "US$3.2 billion"),
    ("minus_glyph", "−3", "-3"), ("percent_space", "10 %", "10%"), ("date_order", "March 5, 1990", "5 March 1990"),
    ("football_space", "12(3)", "12 (3)"), ("markdown", "**12 (3)**", "12 (3)"), ("year_paren", "US$1.2 billion (2023)", "$1.2 billion (2023)"),
    ("age_suffix", "1990", "1990; 36 years ago"), ("ticker_index", "NYSE: ABC", "NYSE: ABC S&P 500 component"), ("trailing_dot", "1990.", "1990"),
]


def same_strict(v, a):
    cv, ca = M.canon_strict(v), M.canon_strict(a)
    return cv is not None and cv == ca


def same_second(v, a):
    return same_strict(v, a) or key_equiv_nolabel(v, a) is not None


res = {"note": "合成控制組；判同＝評分器會把值當成答案（判對）。", "must_differ": [], "should_match": []}
for grp, rows, want_same in (("must_differ", DIFF, False), ("should_match", SAME, True)):
    for cat, v, a in rows:
        res[grp].append({"cat": cat, "value": v, "answer": a, "canon_strict_same": same_strict(v, a), "second_same": same_second(v, a),
                         "canon_v": M.canon_strict(v), "canon_a": M.canon_strict(a)})
s = lambda grp, k, want: sum(r[k] == want for r in res[grp])
res["summary"] = {"must_differ_n": len(DIFF), "should_match_n": len(SAME),
                  "canon_strict": {"false_pass(判同但該不同)": s("must_differ", "canon_strict_same", True), "false_block(判不同但該相同)": s("should_match", "canon_strict_same", False)},
                  "second": {"false_pass": s("must_differ", "second_same", True), "false_block": s("should_match", "second_same", False)}}
res["false_pass_by_cat_canon_strict"] = sorted({r["cat"] for r in res["must_differ"] if r["canon_strict_same"]})
res["false_block_by_cat_canon_strict"] = sorted({r["cat"] for r in res["should_match"] if not r["canon_strict_same"]})
res["false_block_by_cat_second"] = sorted({r["cat"] for r in res["should_match"] if not r["second_same"]})
out = HERE.parent / "audit/scorer_validity_20261128/synthetic_controls.json"
out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps({k: res[k] for k in ("summary", "false_pass_by_cat_canon_strict", "false_block_by_cat_canon_strict", "false_block_by_cat_second")}, ensure_ascii=False, indent=1))
for r in res["must_differ"]:
    if r["canon_strict_same"]: print("PASS-WRONG", r["cat"], r["value"], "|", r["answer"], "|", r["canon_v"])
