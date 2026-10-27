"""離線重播「真實訊號驅動重抽」的釘死（`ops/realrun/offline_real_signal_replay.py`）。

背景：round 98（P1 主線）。過去引用的「重抽 +15.4pp（62.3→77.7%）」是 test-restart
欄——用**評分器的對錯**決定要不要重抽；在可見測試≠評分器的題型上那是上界（≈oracle），
不是 Vacant 自己訊號能做到的。本測試把「哪一欄用了評分器」釘死在機器輸出裡：

- flag_restart 永遠 scorer_used=false（Vacant 自己的紀錄訊號：findings 為空＝放行）。
- test_restart 只在 polyglot_py（可見測試＝評分器）上 scorer_used=false；其餘題型
  scorer_used=true＝上界，不得引用為 Vacant 自己能做到的。
- oracle_any 永遠 scorer_used=true。
- ALL 池的 test_restart 因為池裡含用評分器的題型，必須 scorer_used=true。

鏡像 `offline_real_signal_replay.json` 記錄 ref/c37_final.json（1187 格）的重播結果；
落盤輸入在本機存在時重跑 replay 並與鏡像逐欄位比對（round 93 同模式），不在則 skip
（鏡像本身的釘死不受影響）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HERE = REPO / "ops" / "realrun"
REPLAY = HERE / "offline_real_signal_replay.py"
MIRROR = HERE / "offline_real_signal_replay.json"
V5_AUDIT = HERE / "audit_v5_hint_delivery.json"


def _load(p: Path) -> dict:
    assert p.exists(), f"missing {p}（引用前必須在 repo 裡）"
    return json.loads(p.read_text(encoding="utf-8"))


def test_files_present() -> None:
    for p in (REPLAY, MIRROR):
        assert p.exists(), f"missing {p}"


def test_selftest_proves_arithmetic() -> None:
    r = subprocess.run(
        [sys.executable, str(REPLAY), "--selftest"],
        capture_output=True, text=True, cwd=REPO, timeout=120)
    assert r.returncode == 0, f"selftest failed:\n{r.stdout}\n{r.stderr}"
    assert "selftest OK" in r.stdout


def test_mirror_schema_and_columns_labeled() -> None:
    m = _load(MIRROR)
    assert m["schema"] == "vacant.realrun.offline_real_signal_replay/1"
    assert m["cap"] == 3
    for key in ("flag_restart", "test_restart", "oracle_any"):
        assert key in m["definition"]["columns"]
    # 每題型、每欄都有 scorer_used 標記（機器輸出，不是靠人記口徑）
    for suite, r in m["suites"].items():
        for col in ("flag_restart", "test_restart", "oracle_any"):
            assert isinstance(r[col]["scorer_used"], bool), (suite, col)
    for col in ("flag_restart", "test_restart", "oracle_any"):
        assert isinstance(m["all"][col]["scorer_used"], bool)


def test_scorer_labeling_guard() -> None:
    """口徑守衛：真實訊號欄與上界欄不得混用（round 93 方向守衛同型）。"""
    m = _load(MIRROR)
    vtg = tuple(m["definition"]["visible_tests_are_grader_suites"])
    assert vtg == ("polyglot_py",), "可見測試＝評分器的題型清單被改動，需重新審視所有引用"
    for suite, r in m["suites"].items():
        assert r["flag_restart"]["scorer_used"] is False
        assert r["oracle_any"]["scorer_used"] is True
        expect_test = suite not in vtg
        assert r["test_restart"]["scorer_used"] is expect_test, suite
    assert m["all"]["flag_restart"]["scorer_used"] is False
    assert m["all"]["test_restart"]["scorer_used"] is True  # 池含用評分器的題型
    assert m["all"]["oracle_any"]["scorer_used"] is True


def test_pinned_numbers() -> None:
    """已知數字釘死（與 ref/offline_restart_sim.py 的歷史輸出一致，容差 0.05pp）。"""
    m = _load(MIRROR)
    a = m["all"]
    assert a["units"] == 331
    assert abs(a["pass_at_1_pct"] - 62.3) < 0.05
    assert abs(a["flag_restart"]["pct"] - 66.4) < 0.05
    assert abs(a["test_restart"]["pct"] - 77.7) < 0.05
    assert abs(a["oracle_any"]["pct"] - 78.2) < 0.05
    pg = m["suites"]["polyglot_py"]
    assert abs(pg["pass_at_1_pct"] - 37.3) < 0.05
    assert abs(pg["flag_restart"]["pct"] - 47.0) < 0.05
    assert abs(pg["test_restart"]["pct"] - 55.9) < 0.05
    assert pg["test_restart"]["scorer_used"] is False  # 該題型上這欄才是真的拿得到


def test_rerun_matches_mirror_when_input_present() -> None:
    m = _load(MIRROR)
    src = Path(m["input"]["path"]).expanduser()
    if not src.exists():
        pytest.skip(f"落盤輸入不在本機：{src}")
    import hashlib
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    assert sha == m["input"]["sha256"], "輸入檔被改動，鏡像數字不可信"
    sys.path.insert(0, str(HERE))
    try:
        import offline_real_signal_replay as mod
    except ImportError:
        pytest.skip("module not importable")
    rows = json.loads(src.read_text(encoding="utf-8"))
    out = mod.replay(rows, m["cap"])
    for key in ("schema", "cap", "definition", "suites", "all"):
        assert out[key] == m[key], f"rerun diverges on {key}"
    assert out["suites"].keys() == m["suites"].keys()


def test_quoting_rule_text_present() -> None:
    m = _load(MIRROR)
    q = m["definition"]["quoting_rule"]
    assert "flag_restart" in q and "upper bound" in q.lower()
    # 禁句不得出現：不得把 77.7 說成可引用成效
    assert "77.7" not in q


def test_v5_delivery_premise_pinned() -> None:
    """v5 兩臂「重抽觸發＝可見驗收、治療照 prereg 投遞」是落盤事實，不是假設。

    `ops/realrun/audit_v5_hint_delivery.json`（round 93 的審計鏡像）記錄
    `all_checks_passed=true`；本測試把該前提讀出來釘死：治療 fresh_hint 照
    prereg 投遞、控制臂無 hint 檔、兩臂 prompt 逐字相同、兩臂 stop_reason 只有
    visible_pass／attempts_exhausted（隱藏評分器不參與重抽觸發）。這是本輪
    STATE「v5 兩臂本已此形」一行的依賴證據。
    """
    if not V5_AUDIT.exists():
        pytest.skip(f"v5 審計鏡像不在本 repo：{V5_AUDIT}")
    a = _load(V5_AUDIT)
    assert a["schema"] == "vacant.audit/v5_hint_delivery/1"
    assert a["prereg_id"] == "v5_live_fresh_hint_vs_resample_34tasks_20261026"
    assert a["all_checks_passed"] is True
    assert a["control_nonempty_hint_files"] == 0
    assert a["D5_prompt_identical_across_arms"]["pass"] is True
    n = 0
    for root, arms in a["per_root"].items():
        for arm, body in arms.items():
            for cell, c in body["cells"].items():
                assert c["stop_reason"] in ("visible_pass", "attempts_exhausted"), \
                    (root, arm, cell)
                assert not c.get("anomalies"), (root, arm, cell)
                n += 1
    assert n == a["n_cells"] == 204, (n, a["n_cells"])
