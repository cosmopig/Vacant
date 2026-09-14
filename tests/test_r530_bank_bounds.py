"""R530 題庫量具：條數的**界**（取代 AMEND1 的具名例外）。

Fable 2026-09-14 裁決：可見 2–4、tight 隱藏 10–16、loose 隱藏 5–7，
**上下界都判**。換掉具名例外的代價是「多寫兩條不再會在 diff 裡跳出來」，
換來的是「條數太少也擋得住」——而具名例外那個寫法擋不住太少。
所以這一批負控要同時測兩個方向，否則等於只換了個寫法。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GAUGE = ROOT / "ops" / "gain" / "r530" / "gauge_r530.py"


def _load():
    spec = importlib.util.spec_from_file_location("gauge_r530", GAUGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def g():
    return _load()


def test_named_exceptions_are_gone(g):
    assert not hasattr(g, "COUNT_EXCEPTIONS"), (
        "具名例外已被界取代（Fable 2026-09-14）——留著會讓「用哪一個」"
        "變成一個可以事後選的東西")
    assert g.VISIBLE_COUNT_RANGE == (2, 4)
    assert g.HIDDEN_COUNT_RANGE == {"tight": (10, 16), "loose": (5, 7)}


def test_source_no_longer_mentions_the_waiver(g):
    src = GAUGE.read_text(encoding="utf-8")
    # 註解裡可以留著「原本是具名例外」的來龍去脈，但**程式碼**不准再讀它。
    code_lines = [ln for ln in src.splitlines()
                  if "COUNT_EXCEPTIONS" in ln and not ln.lstrip().startswith("#")]
    assert code_lines == [], code_lines
    assert "waiver" not in src, "豁免這個概念要整個拿掉，不是改個名字"


def _check_counts(g, stratum, visible_n, hidden_n):
    """複製 `check_task` 裡那一段條數判定，逐字對同一組常數。"""
    errs = []
    lo, hi = g.HIDDEN_COUNT_RANGE[stratum]
    if hidden_n < lo:
        errs.append("hidden_low")
    elif hidden_n > hi:
        errs.append("hidden_high")
    vlo, vhi = g.VISIBLE_COUNT_RANGE
    if visible_n < vlo:
        errs.append("visible_low")
    elif visible_n > vhi:
        errs.append("visible_high")
    return errs


@pytest.mark.parametrize("stratum,vis,hid,want", [
    ("tight", 3, 14, []),                       # 正常
    ("tight", 2, 10, []),                       # 下界剛好
    ("tight", 4, 16, []),                       # 上界剛好
    ("tight", 1, 14, ["visible_low"]),          # 可見太少
    ("tight", 5, 14, ["visible_high"]),         # 可見太多
    ("tight", 3, 9, ["hidden_low"]),            # tight 隱藏太少
    ("tight", 3, 17, ["hidden_high"]),          # tight 隱藏太多
    ("loose", 2, 5, []),                        # loose 下界剛好
    ("loose", 2, 7, []),                        # loose 上界剛好
    ("loose", 2, 4, ["hidden_low"]),            # loose 隱藏太少
    ("loose", 2, 8, ["hidden_high"]),           # loose 隱藏太多
])
def test_both_bounds_have_teeth(g, stratum, vis, hid, want):
    assert _check_counts(g, stratum, vis, hid) == want


def test_unknown_stratum_is_not_a_pass(g):
    """認不出層別不是通過，是停（`suitegauge` 的同一條紀律）。"""
    assert "maybe" not in g.HIDDEN_COUNT_RANGE
    src = GAUGE.read_text(encoding="utf-8")
    assert "認不得" in src and "認不出來不是通過" in src
