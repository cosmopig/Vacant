"""vq-7f1 缺陷 1 回歸與規格測試：`locate`／`sources` 的 `b24` 正規化比對與外層環境開關。

對齊實驗側參考實作（`ops/d2/expT_feedback.py`）與合成規格測試（`ops/d2/expT_b36_spec_test.py`）：
- 預設 `matching="literal"` 維持既有行為不變；
- `matching="b24"` 在既有行為之上，對頁面文字與值兩邊套用封閉三項正規化：
  1. 移除每一個 `*`；
  2. 移除每一個反引號 `` ` ``；
  3. 移除緊鄰 `(` 或 `)` 內外的連續空白（Python `str.isspace()`，含 U+00A0、U+2009）。
- 其餘字元（他處空白、`_`、千分位、Unicode 負號等）不新增任何規則；既有數值邊界原樣沿用。
- 環境變數 `VACANT_FLAG_MATCHING=b24` 只在最外層入口解析，內層比對函式不讀環境變數。
"""
from __future__ import annotations

import json
import random
import string

import pytest

from vacant_network.intake import keys
from vacant_network.trace import blame as B
from vacant_network.trace import cli as trace_cli
from vacant_network.trace import locate as L
from vacant_network.trace import recorder as R
from vacant_network.trace import sources as S


# 與 ops/d2/expT_b36_spec_test.py 逐條對應的 20 組合成規格測例
SPEC_CASES: list[tuple[str, str, str, str]] = [
    ("same", "US$2.9 billion (2016)", "<td>US$2.9 billion (2016)</td>", "eq_literal"),
    ("same", "Monolithic kernel", "<p>Kernel type Monolithic kernel here</p>", "eq_literal"),
    ("same", "absent value", "<p>nothing relevant here</p>", "eq_literal"),
    ("paren_ws", "32(1)", "<td>32</td> <td>(1)</td>", "match"),
    ("paren_ws", "32 (1)", "<td>32(1)</td>", "match"),
    ("paren_ws", "32(1)", "<p>32\u00a0(1)</p>", "match"),
    ("paren_ws", "32(1)", "<p>32\u2009(1)</p>", "match"),
    ("paren_ws", "Xfce (default)", "<p>Xfce ( default )</p>", "match"),
    ("md", "**32 (1)**", "<p>32 (1)</p>", "match"),
    ("md", "`US$2.9 billion`", "<p>US$2.9 billion</p>", "match"),
    ("md", "`32` `(1)`", "<p>32 (1)</p>", "match"),
    ("other_ws", "US$2.9billion", "<p>US$2.9 billion</p>", "no_match"),
    ("other_ws", "US$ 2.9 billion", "<p>US$2.9 billion</p>", "no_match"),
    ("underscore", "x86_64", "<p>x86-64</p>", "no_match"),
    ("underscore", "foo_bar", "<p>foo bar</p>", "no_match"),
    ("thousands", "1234567", "<p>1,234,567 employees</p>", "eq_literal"),
    ("minus", "-76.8 million", "<p>\u221276.8 million</p>", "no_match"),
    ("boundary", "12", "<p>value 123 here</p>", "eq_literal"),
    ("boundary", "12(3)", "<p>value 112 (3) here</p>", "known_deviation_b41"),
    ("boundary", "12 (3)", "<p>value 12 (34) here</p>", "eq_literal"),
]


def test_identical_strings_without_features_match_literal():
    cases = [
        ("US$2.9 billion (2016)", "<td>US$2.9 billion (2016)</td>", True),
        ("Monolithic kernel", "<p>Kernel type Monolithic kernel here</p>", True),
        ("absent value", "<p>nothing relevant here</p>", False),
        ("45 days", "duration is 45 days total", True),
        ("v3.14.2", "released v3.14.2 yesterday", True),
    ]
    for value, page, expected in cases:
        assert L.contains(page, value) is expected
        assert L.contains(page, value, matching="literal") is expected
        assert L.contains(page, value, matching="b24") is expected
        assert S.plain_contains(page, value) is expected
        assert S.plain_contains(page, value, matching="literal") is expected
        assert S.plain_contains(page, value, matching="b24") is expected


def test_paren_adjacent_whitespace_including_unicode_spaces():
    # 純文字（直接測 locate.contains，不經 _plain 壓縮，直接驗 U+00A0／U+2009）
    direct_cases = [
        ("12(3)", "12 (3)"),
        ("12 (3)", "12(3)"),
        ("32(1)", "32\u00a0(1)"),        # U+00A0 NO-BREAK SPACE
        ("32(1)", "32\u2009(1)"),        # U+2009 THIN SPACE
        ("32\u00a0(1)", "32(1)"),
        ("32(1)", "32(\u00a01\u2009)"),  # 括號內側的 Unicode 空白
        ("Xfce (default)", "Xfce ( default )"),
        ("12(3) extra", "12 ( 3 ) extra"),
    ]
    for value, text in direct_cases:
        assert not L.contains(text, value, matching="literal"), f"literal should not match {value!r} in {text!r}"
        assert L.contains(text, value, matching="b24"), f"b24 should match {value!r} in {text!r}"
        assert not S.plain_contains(text, value, matching="literal")
        assert S.plain_contains(text, value, matching="b24")

    # HTML 跨儲存格（經 plain_contains 的 _plain 拼出 "32 (1)" 後再套 b24）
    html_cells = "<td>32</td> <td>(1)</td>"
    assert not S.plain_contains(html_cells, "32(1)", matching="literal")
    assert S.plain_contains(html_cells, "32(1)", matching="b24")


def test_markdown_asterisk_and_backtick_only():
    cases = [
        ("**12(3)**", "12 (3)"),
        ("`12` `(3)`", "12 (3)"),
        ("**32 (1)**", "<p>32 (1)</p>"),
        ("`US$2.9 billion`", "<p>US$2.9 billion</p>"),
        ("`32` `(1)`", "<p>32 (1)</p>"),
        ("*Monolithic* kernel", "Monolithic kernel"),
        ("12(3)", "**12** `(3)`"),
    ]
    for value, page in cases:
        assert not S.plain_contains(page, value, matching="literal")
        assert S.plain_contains(page, value, matching="b24")


def test_disallowed_normalisations_do_not_match_under_b24():
    # 其他位置的空白、底線 `_`、Unicode 負號 U+2212 都不得被正規化掉
    negative_cases = [
        ("US$2.9billion", "<p>US$2.9 billion</p>"),
        ("US$ 2.9 billion", "<p>US$2.9 billion</p>"),
        ("foo bar", "foo\u00a0bar"),          # 非括號旁之 U+00A0（直接測 L.contains）
        ("x86_64", "<p>x86-64</p>"),
        ("foo_bar", "<p>foo bar</p>"),
        ("foo_bar", "foobar"),
        ("-76.8 million", "<p>\u221276.8 million</p>"),
        ("\u221276.8 million", "<p>-76.8 million</p>"),
    ]
    for value, page in negative_cases:
        assert not L.contains(page, value, matching="b24"), f"L.contains b24 must reject {value!r} vs {page!r}"
        if "foo\u00a0bar" not in page:
            # 註：plain_contains 的 _plain() 原就會把 HTML/純文字空白折成單一 ASCII 空白，
            # 該筆只在 L.contains 層級驗「非括號旁空白不動」。
            assert not S.plain_contains(page, value, matching="b24"), (
                f"plain_contains b24 must reject {value!r} vs {page!r}"
            )


def test_thousands_separator_matches_literal_behaviour():
    # 純數字：既有 literal 已容忍千分位，b24 結果與 literal 相同
    assert S.plain_contains("<p>1,234,567 employees</p>", "1234567", matching="literal") is True
    assert S.plain_contains("<p>1,234,567 employees</p>", "1234567", matching="b24") is True
    assert L.contains("1,234,567 employees", "1234567", matching="literal") is True
    assert L.contains("1,234,567 employees", "1234567", matching="b24") is True

    # 非純數字（帶單位）：既有 literal 不移除千分位，b24 也不得新增千分位處理
    assert L.contains("1,234,567 employees", "1234567 employees", matching="literal") is False
    assert L.contains("1,234,567 employees", "1234567 employees", matching="b24") is False
    assert S.plain_contains("<p>1,234,567 employees</p>", "1234567 employees", matching="literal") is False
    assert S.plain_contains("<p>1,234,567 employees</p>", "1234567 employees", matching="b24") is False


def test_numeric_boundary_and_known_deviation_b41():
    # 純數字邊界：值 "12" 對 "123" 必須維持不匹配（與 literal 相同）
    assert L.contains("<p>value 123 here</p>", "12", matching="literal") is False
    assert L.contains("<p>value 123 here</p>", "12", matching="b24") is False
    assert S.plain_contains("<p>value 123 here</p>", "12", matching="literal") is False
    assert S.plain_contains("<p>value 123 here</p>", "12", matching="b24") is False
    # 帶 markdown 的純數字在正規化後變純數字 "12"，仍受原有數字邊界約束
    assert L.contains("value 123 here", "**12**", matching="b24") is False
    assert L.contains("value 12 here", "**12**", matching="b24") is True

    # 尾端數字不同：值 "12 (3)" 對 "12 (34)" 不匹配
    assert S.plain_contains("<p>value 12 (34) here</p>", "12 (3)", matching="literal") is False
    assert S.plain_contains("<p>value 12 (34) here</p>", "12 (3)", matching="b24") is False

    # known_deviation_b41（規格明確保留、不可「修掉」）：
    # 既有數字邊界只套用於純數字值；"12(3)" 不是純數字，經 b24 正規化後
    # 頁面 "value 112 (3) here" 變成 "value 112(3)here"，子字串 "12(3)" 會命中。
    assert S.plain_contains("<p>value 112 (3) here</p>", "12(3)", matching="literal") is False
    assert S.plain_contains("<p>value 112 (3) here</p>", "12(3)", matching="b24") is True
    assert L.contains("value 112 (3) here", "12(3)", matching="b24") is True


def test_spec_cases_and_experiment_reference_agreement():
    """每一條合成規格測例都滿足預期，且在 ops/d2 存在時與 expT_feedback.compute_line_flags 逐條一致。"""
    for cls, val, page, expect in SPEC_CASES:
        lit = S.plain_contains(page, val, matching="literal")
        b24 = S.plain_contains(page, val, matching="b24")
        if expect == "eq_literal":
            assert b24 == lit, f"{cls}: {val!r} vs {page!r}: b24={b24} != literal={lit}"
        elif expect in ("match", "known_deviation_b41"):
            assert b24 is True, f"{cls}: expected b24=True for {val!r} vs {page!r}"
        elif expect == "no_match":
            assert b24 is False, f"{cls}: expected b24=False for {val!r} vs {page!r}"
        else:
            raise AssertionError(f"unexpected expect={expect!r}")

    # 若在 repo 檢出環境中存在實驗側參考實作，直接逐條比對一致
    try:
        from ops.d2 import expT_b36_spec_test as spec_mod
        from ops.d2 import expT_feedback as fb_mod
    except ImportError:
        return

    try:
        for cls, val, page, _expect in spec_mod.CASES:
            exp_lit = spec_mod.matched("literal", val, page)
            exp_b24 = spec_mod.matched("b24", val, page)
            prod_lit = S.plain_contains(page, val, matching="literal")
            prod_b24 = S.plain_contains(page, val, matching="b24")
            assert prod_lit == exp_lit, f"literal mismatch vs expT on {cls}: {val!r} | {page!r}"
            assert prod_b24 == exp_b24, f"b24 mismatch vs expT on {cls}: {val!r} | {page!r}"
    finally:
        fb_mod.set_flag_matching("literal")


def test_property_no_three_features_b24_equals_literal():
    """性質檢查：對數十組不含 `*`、反引號、括號旁空白的生成字串，b24 與 literal 結果逐一相同。"""
    rng = random.Random(20261128)
    # 字元集刻意不含 `*`、`` ` ``、`(`、`)`、`<`、`>`、`&`，再以安全形式穿插無相鄰空白的括號片段
    safe_chars = string.ascii_letters + string.digits + ".,-_%$:/"

    def gen_token() -> str:
        kind = rng.randrange(5)
        if kind == 0:
            return str(rng.randint(0, 99999))
        if kind == 1:
            return f"{rng.randint(1, 999)},{rng.randint(100, 999)}"
        if kind == 2:
            left = "".join(rng.choice(safe_chars) for _ in range(rng.randint(1, 4)))
            inner = "".join(rng.choice(safe_chars) for _ in range(rng.randint(1, 3)))
            right = "".join(rng.choice(safe_chars) for _ in range(rng.randint(1, 3)))
            return f"{left}({inner}){right}"
        return "".join(rng.choice(safe_chars) for _ in range(rng.randint(2, 8)))

    for _ in range(60):
        words = [gen_token() for _ in range(rng.randint(4, 12))]
        page = " ".join(words)
        # 確保生成的字串真的不含三項特徵
        assert L.normalize_b24(page) == page
        # 測三個值：取自頁面的片語、單一詞、以及新生成的獨立字串
        start = rng.randrange(len(words))
        span = " ".join(words[start:start + rng.randint(1, 3)])
        candidates = [span, words[start], gen_token(), f"{gen_token()} {gen_token()}"]
        for val in candidates:
            assert L.normalize_b24(val) == val
            assert L.contains(page, val, matching="b24") == L.contains(page, val, matching="literal")
            assert L.occurrences(page, val, matching="b24") == L.occurrences(page, val, matching="literal")
            assert S.plain_contains(page, val, matching="b24") == S.plain_contains(page, val, matching="literal")


def test_occurrences_b24_preserves_original_line_col_and_offset_parity():
    samples = [
        "",
        "plain text",
        "32 * (1)",
        "`32` `(1)`",
        "a ( ( b ) ) c",
        "\u00a0(\u2009x\u00a0)\t",
        "line1\n32\n(1)\nline4",
        "**bold** and `code` ( inside )",
    ]
    for s in samples:
        norm, offs = L._normalize_b24_with_offsets(s)
        assert norm == L.normalize_b24(s)
        assert len(offs) == len(norm)

    doc = "header line\nsecond line\nvalue is 32\u00a0(1) here\n"
    assert L.occurrences(doc, "32(1)", matching="literal") == []
    occ = L.occurrences(doc, "32(1)", matching="b24")
    assert len(occ) == 1
    ln, col, tok = occ[0]
    assert ln == 3
    assert col == len("value is ") + 1
    assert tok == "32(1)"


def test_invalid_matching_mode_rejected():
    with pytest.raises(ValueError):
        L.contains("abc", "abc", matching="n2db")
    with pytest.raises(ValueError):
        L.occurrences("abc", "abc", matching="invalid")
    with pytest.raises(ValueError):
        S.plain_contains("abc", "abc", matching="fuzzy")
    with pytest.raises(ValueError):
        L.resolve_matching(None, env={"VACANT_FLAG_MATCHING": "bogus"})


def test_env_var_only_applies_at_outermost_entry_points(tmp_path, monkeypatch, capsys):
    """VACANT_FLAG_MATCHING=b24 只在最外層入口生效；內層原語維持預設 literal；顯式參數蓋過環境變數。"""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    keys.init_local()

    ws = tmp_path / "proj"
    ws.mkdir()
    (ws / "report.md").write_text("# Report\n- Tool — version: ____\n- Tool — score: ____\n", encoding="utf-8")
    rec = R.Recorder(ws)
    actor = R.Actor("pi", "s-b24")

    url = "http://docs.fictional.example/spec.html"
    page_html = "<html><body><p>Release v1.2.*3</p><p>Score: 12 (3)</p></body></html>\n"
    rec.pre("t1", actor, "Bash", {"command": f"curl -s {url}"})
    rec.post("t1", actor, "Bash", {"command": f"curl -s {url}"}, page_html)

    report_text = "# Report\n- Tool — version: v1.2.3\n- Tool — score: 12(3)\n"
    rec.pre("t2", actor, "Write", {"file_path": str(ws / "report.md"), "content": report_text})
    (ws / "report.md").write_text(report_text, encoding="utf-8")
    rec.post("t2", actor, "Write", {"file_path": str(ws / "report.md"), "content": report_text}, "ok")

    # 預設（未設環境變數）= literal：頁面裡的 "v1.2.*3" 與報告的 "v1.2.3" 配不上 ⇒ no_source
    monkeypatch.delenv("VACANT_FLAG_MATCHING", raising=False)
    res_default = S.check_candidates(ws, "report.md", fetch=lambda _u: page_html, record=False)
    by_val = {c["value"]: c for c in res_default["claims"]}
    assert by_val["v1.2.3"]["status"] == "no_source"

    # 顯式傳入 matching="b24"：配得上 ⇒ unchanged
    res_b24 = S.check_candidates(ws, "report.md", fetch=lambda _u: page_html, record=False, matching="b24")
    by_val_b24 = {c["value"]: c for c in res_b24["claims"]}
    assert by_val_b24["v1.2.3"]["status"] == "unchanged"

    # 設環境變數 VACANT_FLAG_MATCHING=b24：
    monkeypatch.setenv("VACANT_FLAG_MATCHING", "b24")

    # (1) 內層原語 MUST 忽略環境變數、維持預設 literal
    assert L.contains(page_html, "v1.2.3") is False
    assert L.contains(page_html, "12(3)") is False
    assert L.occurrences(page_html, "12(3)") == []
    assert S.plain_contains(page_html, "12(3)") is False
    tbl = "<html><body><table><tr><th>Team</th><th>Apps</th><th>Gls</th></tr><tr><td>Exampletown</td><td>12</td><td>(3)</td></tr></table></body></html>"
    assert S.value_status(tbl, tbl, "12(3)", by_field=True) is None
    assert S.value_status(tbl, tbl, "12(3)", by_field=True, matching="b24") == "unchanged"
    # blame_location 是中層 API，也不讀環境變數
    b_inner = B.blame_location(B.Trace(rec), L.Location("report.md", 3, value="12(3)"))
    assert b_inner["fault_class"] == "agent" and b_inner["source"] is None
    b_inner_b24 = B.blame_location(B.Trace(rec), L.Location("report.md", 3, value="12(3)"), matching="b24")
    assert b_inner_b24["fault_class"] == "input" and b_inner_b24["source"]["ref"] == url

    # (2) 最外層入口（sources.check_candidates / sources.candidates / trace CLI）吃 VACANT_FLAG_MATCHING=b24
    res_env = S.check_candidates(ws, "report.md", fetch=lambda _u: page_html, record=False)
    assert {c["value"]: c for c in res_env["claims"]}["v1.2.3"]["status"] == "unchanged"

    # (3) 顯式傳入 matching="literal" 優先於環境變數
    res_override = S.check_candidates(ws, "report.md", fetch=lambda _u: page_html, record=False, matching="literal")
    assert {c["value"]: c for c in res_override["claims"]}["v1.2.3"]["status"] == "no_source"

    # (4) 最外層 CLI：`vacant trace blame` 預設讀 VACANT_FLAG_MATCHING，顯式 `--matching literal` 覆蓋
    monkeypatch.chdir(ws)
    assert trace_cli.main(["trace", "blame", "report.md:3", "--value", "12(3)", "--json"]) == 0
    cli_env = json.loads(capsys.readouterr().out)
    assert cli_env["fault_class"] == "input" and cli_env["source"]["ref"] == url

    assert trace_cli.main(["trace", "blame", "report.md:3", "--value", "12(3)", "--matching", "literal", "--json"]) == 0
    cli_lit = json.loads(capsys.readouterr().out)
    assert cli_lit["fault_class"] == "agent" and cli_lit["source"] is None
