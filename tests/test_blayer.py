"""B 層六情境 harness 驗收（13 §3；17 §P4；vacant/blayer.py）。

鎖定每個情境的判準（事前寫死於 `_verdict`）——含 meta 判準：「拆掉機制，
數字必須變」（on/off 雙組是每個情境的內建反事實）。正式掃描是每格 ≥1000
seeds（`examples/b_layer.py`）；這裡用 8 seeds 的 smoke 格鎖行為不回退。
"""

from __future__ import annotations

import json

from vacant.blayer import RATIOS, SCENARIOS, run_all


def _run(tmp_path, only=None):
    return run_all(n_seeds=8, base_seed="test-blayer", out_dir=tmp_path, only=only)


def test_all_six_scenarios_pass(tmp_path):
    reports = _run(tmp_path)
    assert set(reports) == set(SCENARIOS)
    for name, rep in reports.items():
        assert rep.verdict, f"{name} 未過判準：{rep.detail}"


def test_eight_ratios_and_both_arms(tmp_path):
    reports = _run(tmp_path, only=("decay_slash",))
    rep = reports["decay_slash"]
    assert len(rep.on_cells) == len(RATIOS) == 8
    assert len(rep.off_cells) == 8
    assert [c.ratio for c in rep.on_cells] == list(RATIOS)
    # 每格帶 bootstrap CI 且種子數正確
    for c in rep.on_cells:
        assert c.n_seeds == 8 and c.ci_lo <= c.value <= c.ci_hi


def test_mechanism_removed_numbers_must_change(tmp_path):
    """meta 判準（13 §3 核心）：每個情境拆掉機制，指標必須可觀測地變化——
    否則該機制是裝飾，要從一切主張移除。"""
    reports = _run(tmp_path)
    for name, rep in reports.items():
        on07 = next(c for c in rep.on_cells if abs(c.ratio - 0.7) < 1e-9).value
        off07 = next(c for c in rep.off_cells if abs(c.ratio - 0.7) < 1e-9).value
        assert on07 != off07, f"{name} 拆掉機制數字沒變（on={on07} off={off07}）→ 裝飾"


def test_output_artifacts_written(tmp_path):
    reports = _run(tmp_path)
    cells = (tmp_path / "cells.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(cells) == 6 * 8 * 2  # 六情境 × 8 格 × on/off
    first = json.loads(cells[0])
    for k in ("scenario", "ratio", "n_seeds", "value", "ci_lo", "ci_hi", "arm"):
        assert k in first
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "B 層機制驗收六情境" in summary
    for name in reports:
        assert name in summary


def test_deterministic_same_seed_same_result(tmp_path):
    a = run_all(n_seeds=4, base_seed="det", only=("same_source",))
    b = run_all(n_seeds=4, base_seed="det", only=("same_source",))
    va = [c.value for c in a["same_source"].on_cells]
    vb = [c.value for c in b["same_source"].on_cells]
    assert va == vb  # 同 seed 同結果（可重放／歸檔對帳前提）
