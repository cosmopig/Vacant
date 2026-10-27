"""docs/REAL_SIGNAL_COLUMNS.md（真訊號列 vs 上限列）與落盤數據的一致性釘死。

本頁是 P1 成效口徑的單一引用點（ASSIGNMENT「任何成效數字：寫清楚用的是哪一欄、
有沒有用到評分器、n 是多少」）。本測試不重跑實驗，只做三件事：

1. §2 對照表每行（題型、n、pass@1、flag_restart、test_restart、oracle_any）必須等於
   鏡像 `ops/realrun/offline_real_signal_replay.json` 的落盤值；
   「上界／真訊號」標記必須與鏡像的 scorer_used 一致。
2. §3 live v4/v6 的 (b, c, p, n, state) 必須等於 `analyze_v4.json`／`analyze_v6.json`。
3. 紀律語必須在檔內：77.7（test_restart ALL）只能當上界報告、禁句清單、輸入檔 sha256。
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "REAL_SIGNAL_COLUMNS.md"
MIRROR = REPO / "ops" / "realrun" / "offline_real_signal_replay.json"


def _text() -> str:
    assert DOC.exists(), "docs/REAL_SIGNAL_COLUMNS.md 缺失（引用口徑的單一頁面）"
    return DOC.read_text(encoding="utf-8")


def _load(p: Path) -> dict:
    assert p.exists(), f"missing {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _row(text: str, first_cell: str) -> list[str]:
    """抓對照表裡第一格等於 first_cell 的那一行，回傳各格（去空白）。"""
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == first_cell:
            return cells
    raise AssertionError(f"table row not found: {first_cell}")


def _pct(cell: str, value: float) -> None:
    assert f"{value}%" in cell, (cell, value)


def test_section2_table_matches_mirror() -> None:
    t = _text()
    m = _load(MIRROR)
    vtg = tuple(m["definition"]["visible_tests_are_grader_suites"])
    assert vtg == ("polyglot_py",)  # 與鏡像測試同一守衛：清單被改動需重新審視

    def check_row(name: str, r: dict) -> None:
        cells = _row(t, name)
        assert len(cells) == 6, (name, cells)
        assert cells[1] == str(r["units"]), (name, cells[1], r["units"])
        _pct(cells[2], r["pass_at_1_pct"])
        # flag_restart：真訊號——不得標「上界」
        _pct(cells[3], r["flag_restart"]["pct"])
        assert "上界" not in cells[3], (name, cells[3])
        assert "scorer=否" in cells[3], (name, cells[3])
        # test_restart：只有 vtg 題型是真實訊號，其餘上界
        _pct(cells[4], r["test_restart"]["pct"])
        if name in vtg:
            assert "上界" not in cells[4], (name, cells[4])
        else:
            assert "上界" in cells[4], (name, cells[4])
            assert "scorer=是" in cells[4], (name, cells[4])
        # oracle_any：永遠上界
        _pct(cells[5], r["oracle_any"]["pct"])
        assert "上界" in cells[5], (name, cells[5])

    for suite, r in m["suites"].items():
        check_row(suite, r)
    check_row("ALL（每組等權）", m["all"])


def test_live_v4_v6_pinned() -> None:
    t = _text()
    # 逐行釘死（表格第一格含批次號）
    for name in ("v4", "v6"):
        d = _load(REPO / "ops" / "realrun" / f"analyze_{name}.json")
        pool = d["pooled"]
        b, c, p = pool["b"], pool["c"], pool["p"]
        line = next(
            (l for l in t.splitlines()
             if l.startswith("|") and f"| {name}（" in l),
            None)
        assert line, f"live row not found: {name}"
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        assert cells[2] == str(d["n_pairs"]), (name, cells)
        assert cells[3] == str(b) and cells[4] == str(c), (name, cells)
        assert cells[5] == f"{p:.4f}", (name, cells[5], p)
        assert d["state"] in cells, (name, cells)
        assert d["arm_a"] in line and d["arm_b"] in line, (name, line)
    # v6 的口徑句：同一列真實訊號、不得「證明變好」
    assert "n=170 pairs" in t
    assert "證明變好" in t and "不得" in t


def test_discipline_lines_present() -> None:
    t = _text()
    # 77.7（test_restart ALL 池）只能當上界，不得當成效
    for line in t.splitlines():
        if "77.7" in line and "15.4" in line:
            assert "上界" in line, line
            break
    else:
        raise AssertionError("77.7 的引用規則句缺失")
    # 禁句與紀律語
    for phrase in (
        "flag_restart", "test_restart", "oracle_any",
        "scorer", "不得引用", "上界",
        "replication failed", "effect disappeared",
        "信任層",                               # 口徑用「可究責／有根據」，不用「信任」
        "H-12",
    ):
        assert phrase in t, phrase
    # 輸入檔 sha256 在檔內（與鏡像一致）
    m = _load(MIRROR)
    assert m["input"]["sha256"] in t
    assert m["input"]["sha256"] == (
        "9c6e2b1383e478f88805ccac0f0db219f32316fb4692107d9d4e9e76804bbf5c")


def test_repo_copy_of_input_same_sha() -> None:
    """repo 內的副本（runs/_replay/c37_final.json）與鏡像輸入同 sha256，重現不依賴 ~/dev/ops。"""
    m = _load(MIRROR)
    import hashlib
    p = REPO / "runs" / "_replay" / "c37_final.json"
    assert p.exists(), f"missing repo copy {p}"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == m["input"]["sha256"]
