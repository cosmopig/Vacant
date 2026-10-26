"""方向 B 收口決定檔（v4 EFFECTIVE + v5 UNRESOLVED）與落盤數據的一致性釘死。

`decisions/DECISION_20261026_LIVE_REAL_SIGNAL_CLOSE.md` 是方向 B live 證據線的
正式收口（v4 乾淨重抽、v5 短失敗提示）。本檔不重跑實驗，只做兩件事：

1. 決定檔引用的 pooled (b, c, p, n, state) 必須與 `ops/realrun/analyze_v4.json`／
   `analyze_v5.json` 的落盤值一致（p 以 4 位小數呈現，與 `mcnemar_exact(b, c)` 相容）。
2. 引用口徑與紀律語必須在檔內（兩種讀法都記、不 pool、scorer=false、H-12、
   UNRESOLVED 合法、第一次 model call 前凍結、第二模型可用性實查結果）。
"""
from __future__ import annotations

import json
from pathlib import Path

from vacant_network.research import mcnemar_exact

REPO = Path(__file__).resolve().parent.parent
DECISION = REPO / "decisions" / "DECISION_20261026_LIVE_REAL_SIGNAL_CLOSE.md"
HERE = REPO / "ops" / "realrun"


def _text() -> str:
    assert DECISION.exists(), "方向 B 收口決定檔缺失"
    return DECISION.read_text(encoding="utf-8")


def _load(name: str) -> dict:
    p = HERE / name
    assert p.exists(), f"missing {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _pinned_pool(text: str, analyze: str) -> None:
    """決定檔引用的 pooled 數字必須等於落盤 analyze 檔的 pooled 數字。"""
    d = _load(analyze)
    pool = d["pooled"]
    b, c, p = pool["b"], pool["c"], pool["p"]
    # p 的呈現必須是 4 位小數、且與 (b, c) 的 exact McNemar 相容
    assert f"{p:.4f}" == f"{mcnemar_exact(b, c):.4f}"
    assert f"b={b}" in text and f"c={c}" in text
    assert f"p={p:.4f}" in text
    assert f"n={d['n_pairs']} pairs" in text
    assert d["state"] in text
    # 臂必須在檔內（對照方向不可抄錯）
    assert d["arm_a"] in text and d["arm_b"] in text


def test_v4_numbers_pinned() -> None:
    _pinned_pool(_text(), "analyze_v4.json")
    d = _load("analyze_v4.json")
    assert d["state"] == "EFFECTIVE"  # per prereg（本檔引用它，口徑另釘）


def test_v5_numbers_pinned() -> None:
    _pinned_pool(_text(), "analyze_v5.json")
    d = _load("analyze_v5.json")
    assert d["state"] == "UNRESOLVED"  # null 不是 negative、也不是 positive


def test_v4_must_carry_both_readings() -> None:
    """更嚴的 per-rep 讀法（Holm 無一通過 ⇒ UNRESOLVED）必須與 EFFECTIVE 並記。"""
    t = _text()
    assert "EFFECTIVE per prereg" in t
    assert "不是「證明變好」" in t
    assert "Holm" in t and "無一通過" in t
    assert "兩種讀法都記" in t


def test_v5_must_not_be_read_as_harmful() -> None:
    t = _text()
    assert "UNRESOLVED 是**合法結果" in t or "UNRESOLVED 是合法結果" in t
    assert "不是「hint 無用」" in t
    # 方向守衛：決定檔不得寫出「有害／無用」結論
    assert "hint 有害" not in t and "迴路無用" not in t and "the loop is useless" not in t


def test_no_pooling_and_scorer_disclosure() -> None:
    t = _text()
    assert "不 pool" in t
    assert "scorer" in t and "scorer_used=false" in t or "scorer 未使用" in t
    assert "scorer=false" in t
    assert "H-12" in t


def test_prereg_freeze_and_model_scope() -> None:
    t = _text()
    assert "第一次 model call 前凍結" in t
    assert "7938f654" in t  # v4 prereg commit
    assert "fc4ac6a6" in t  # v5 prereg commit
    assert "單一模型" in t or "單一槽位" in t
    # 第二模型可用性是本輪實查結果，不是假設
    assert "/v1/models" in t and "qwen/qwen3.8-27b" in t


def test_evidence_and_pin_tests_named() -> None:
    t = _text()
    for name in ("prereg_v4.json", "prereg_v5.json", "analyze_v4.json", "analyze_v5.json",
                 "tests/test_realrun_v4_prereg.py", "tests/test_realrun_v5_prereg.py"):
        assert name in t, f"決定檔未引用 {name}"
