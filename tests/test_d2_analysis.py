"""Tests for ops/d2/analyze_d2.py (cluster bootstrap analysis for D2')."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO / "ops" / "d2") not in sys.path:
    sys.path.insert(0, str(REPO / "ops" / "d2"))

import analyze_d2 as A  # noqa: E402


def _make_synthetic(
    n_sets: int = 12,
    *,
    arms: tuple[str, ...] = ("a", "b", "c", "d"),
    cycles: tuple[int, ...] = (1, 2, 3),
    miss_fn=None,
    false_mod_fn=None,
    stale_fn=None,
    cost_fn=None,
):
    """Build synthetic score_data + costs matching score_d2.py schema.

    Each set × cycle has 2 changed claims (p1.price, p1.version) and 2 unchanged claims
    (p2.price, p2.version), matching the D2' structure at a small scale.
    """
    rows = []
    costs = {}
    for si in range(1, n_sets + 1):
        sid = f"s{si:02d}"
        for cid in ("p1.price", "p1.version", "p2.price", "p2.version"):
            rows.append({
                "set": sid, "arm": "c0", "cycle": 0, "claim": cid,
                "value": "$10", "status": "correct", "changed": False, "pre": None,
            })
        for arm in arms:
            for k in cycles:
                for cid, ch in (("p1.price", True), ("p1.version", True),
                                ("p2.price", False), ("p2.version", False)):
                    if ch:
                        missed = miss_fn(si, arm, k, cid) if miss_fn else (arm == "a")
                        st = "stale" if missed else "correct"
                    else:
                        fm = false_mod_fn(si, arm, k, cid) if false_mod_fn else False
                        st = "wrong" if fm else "correct"
                    if stale_fn and stale_fn(si, arm, k, cid):
                        st = "stale"
                    rows.append({
                        "set": sid, "arm": arm, "cycle": k, "claim": cid,
                        "value": "$10", "status": st, "changed": ch,
                        "pre": "correct", "edited": False,
                    })
                if cost_fn:
                    c = cost_fn(si, arm, k)
                else:
                    if arm == "a":
                        c = {"ran": False, "calls": 0, "tokens_in": 0, "tokens_out": 0, "wall_s": 0.0}
                    elif arm == "b":
                        c = {"ran": True, "calls": 10, "tokens_in": 4000, "tokens_out": 1000, "wall_s": 30.0}
                    elif arm == "c":
                        c = {"ran": True, "calls": 2, "tokens_in": 800, "tokens_out": 200, "wall_s": 6.0}
                    else:  # d
                        c = {"ran": True, "calls": 5, "tokens_in": 2000, "tokens_out": 500, "wall_s": 15.0}
                costs[(sid, arm, k)] = c
    return {"rows": rows, "summary": {}}, costs


def test_determinism_with_fixed_seed():
    """Same seed produces identical bootstrap bounds; different seeds remain deterministic."""
    def miss_fn(si, arm, k, cid):
        if arm == "a":
            return True
        if arm == "c":
            return (si % 4 == 0) and (k == 1) and (cid == "p1.price")
        if arm == "b":
            return (si % 5 == 0) and (k == 2) and (cid == "p1.price")
        return False

    def cost_fn(si, arm, k):
        base = {"a": 0, "b": 4000 + si * 100, "c": 900 + (si % 3) * 100, "d": 2000 + si * 50}[arm]
        return {"ran": arm != "a", "calls": 10 if arm == "b" else (2 if arm == "c" else 4),
                "tokens_in": base, "tokens_out": base // 4, "wall_s": float(base) / 200.0}

    score_data, costs = _make_synthetic(n_sets=15, miss_fn=miss_fn, cost_fn=cost_fn)
    audit = {"coverage": {"claims": 300, "with_source": 290, "correct_page": 270}}

    r1 = A.analyze(score_data, costs, audit, n_boot=1000, seed=20261125)
    r2 = A.analyze(score_data, costs, audit, n_boot=1000, seed=20261125)
    assert r1 == r2
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


def test_effective_verdict():
    """Coverage >= 0.80, miss diff upper < 0.10, and token ratio lower >= 3 => EFFECTIVE."""
    score_data, costs = _make_synthetic(
        n_sets=12,
        # arm b and arm c both catch all changes; arm d misses some; arm a misses all
        miss_fn=lambda si, arm, k, cid: (arm == "a") or (arm == "d" and k == 1 and cid == "p1.price"),
        false_mod_fn=lambda si, arm, k, cid: (arm == "b" and si == 1 and k == 1 and cid == "p2.price"),
    )
    # b=5000 tok/cycle, c=1000 tok/cycle => exact 5.0x ratio across all sets
    audit = {"coverage": {"claims": 240, "with_source": 230, "correct_page": 220}}

    res = A.analyze(score_data, costs, audit, n_boot=1000, seed=20261125)
    assert res["verdict"] == "EFFECTIVE"
    assert res["verdict_parts"] == {
        "complete": True,
        "coverage": "PASS",
        "miss_diff_c_b": "NONINFERIOR",
        "token_ratio_b_c": "EFFECTIVE",
    }
    assert res["coverage"]["rate"] == pytest.approx(220 / 240)
    assert res["primary"]["miss_diff_c_b"]["point"] == pytest.approx(0.0)
    assert res["primary"]["miss_diff_c_b"]["upper_95"] < 0.10
    assert res["primary"]["token_ratio_b_c"]["point"] == pytest.approx(5.0)
    assert res["primary"]["token_ratio_b_c"]["ci_95"][0] >= 3.0
    assert res["primary"]["calls_ratio_b_c"]["point"] == pytest.approx(5.0)
    assert res["primary"]["wall_ratio_b_c"]["point"] == pytest.approx(5.0)
    # Secondary checks (no verdict keys)
    assert "verdict" not in res["secondary"]["c_vs_d"]["miss_diff"]
    assert "verdict" not in res["secondary"]["c_vs_d"]["token_ratio"]
    assert res["secondary"]["c_vs_d"]["token_ratio"]["point"] == pytest.approx(2.5)
    assert res["secondary"]["d_vs_b"]["token_ratio"]["point"] == pytest.approx(2.0)
    assert res["secondary"]["false_mod"]["b"]["false_mod"] == 1
    assert res["secondary"]["false_mod"]["c"]["false_mod"] == 0
    assert res["secondary"]["residual_stale"]["a"]["1"]["stale"] == 24
    # Human-readable text contains key verdict
    txt = A.format_text(res)
    assert "EFFECTIVE" in txt
    assert "Coverage" in txt


def test_fail_on_coverage():
    """Coverage < 0.80 produces coverage FAIL and overall FAIL even if miss & ratio pass."""
    score_data, costs = _make_synthetic(n_sets=10)
    audit = {"coverage": {"claims": 200, "with_source": 170, "correct_page": 159}}  # 0.795 < 0.80

    res = A.analyze(score_data, costs, audit, n_boot=500, seed=20261125)
    assert res["coverage"]["verdict"] == "FAIL"
    assert res["primary"]["miss_diff_c_b"]["verdict"] == "NONINFERIOR"
    assert res["primary"]["token_ratio_b_c"]["verdict"] == "EFFECTIVE"
    assert res["verdict"] == "FAIL"


def test_fail_on_ratio():
    """Token ratio b/c point < 3 produces ratio FAIL and overall FAIL."""
    def cost_fn(si, arm, k):
        tok = {"a": 0, "b": 2500, "c": 1000, "d": 1500}[arm]  # b/c = 2.5 < 3
        return {"ran": arm != "a", "calls": 5 if arm == "b" else 2,
                "tokens_in": tok, "tokens_out": 0, "wall_s": 10.0 if arm == "b" else 4.0}

    score_data, costs = _make_synthetic(n_sets=10, cost_fn=cost_fn)
    audit = {"coverage": {"claims": 200, "with_source": 200, "correct_page": 195}}

    res = A.analyze(score_data, costs, audit, n_boot=500, seed=20261125)
    assert res["primary"]["token_ratio_b_c"]["point"] == pytest.approx(2.5)
    assert res["primary"]["token_ratio_b_c"]["verdict"] == "FAIL"
    assert res["verdict"] == "FAIL"


def test_unresolved_on_wide_ratio_ci_and_missing_audit():
    """Ratio point >= 3 with CI lower < 3 => UNRESOLVED; missing audit => UNRESOLVED (never EFFECTIVE)."""
    # 10 sets: 8 sets have b/c = 4.0, 2 sets have b/c = 1.5 => pooled point ~3.18 >= 3, but bootstrap lower < 3
    def cost_fn(si, arm, k):
        if arm == "a":
            return {"ran": False, "calls": 0, "tokens_in": 0, "tokens_out": 0, "wall_s": 0.0}
        if arm == "b":
            return {"ran": True, "calls": 6, "tokens_in": 4000 if si <= 8 else 3000, "tokens_out": 0, "wall_s": 10.0}
        if arm == "c":
            return {"ran": True, "calls": 2, "tokens_in": 1000 if si <= 8 else 2000, "tokens_out": 0, "wall_s": 3.0}
        return {"ran": True, "calls": 4, "tokens_in": 2000, "tokens_out": 0, "wall_s": 6.0}

    score_data, costs = _make_synthetic(n_sets=10, cost_fn=cost_fn)
    audit = {"coverage": {"claims": 200, "with_source": 200, "correct_page": 200}}
    res = A.analyze(score_data, costs, audit, n_boot=2000, seed=20261125)
    r = res["primary"]["token_ratio_b_c"]
    assert r["point"] >= 3.0
    assert r["ci_95"][0] < 3.0
    assert r["verdict"] == "UNRESOLVED"
    assert res["verdict"] == "UNRESOLVED"

    # Without --audit on an otherwise-EFFECTIVE dataset => UNRESOLVED (coverage not verified)
    sd_eff, costs_eff = _make_synthetic(n_sets=10)
    res_no_audit = A.analyze(sd_eff, costs_eff, audit_data=None, n_boot=500, seed=20261125)
    assert res_no_audit["coverage"]["verdict"] == "UNRESOLVED"
    assert res_no_audit["verdict"] == "UNRESOLVED"


def test_miss_upper_bound_logic():
    """Check all three miss difference verdicts: NONINFERIOR, UNRESOLVED (point<0.10<=upper), FAIL (point>=0.10)."""
    audit = {"coverage": {"claims": 200, "with_source": 200, "correct_page": 200}}

    # Case 1: point >= 0.10 => FAIL (c misses 2/6 per set = 0.333, b misses 0)
    sd_fail, costs_fail = _make_synthetic(
        n_sets=10,
        miss_fn=lambda si, arm, k, cid: (arm == "a") or (arm == "c" and k == 1),
    )
    res_fail = A.analyze(sd_fail, costs_fail, audit, n_boot=1000, seed=20261125)
    m_fail = res_fail["primary"]["miss_diff_c_b"]
    assert m_fail["point"] == pytest.approx(2 / 6)
    assert m_fail["verdict"] == "FAIL"
    assert res_fail["verdict"] == "FAIL"

    # Case 2: point < 0.10, but concentrated in a couple sets so 95th-percentile upper >= 0.10 => UNRESOLVED
    # 10 sets, 6 changed claims/set = 60 pairs. Set 1 misses all 4 of cycles 1-2 in arm c => 4/60 = 0.0667 < 0.10,
    # but resampling set 1 twice gives 8/60 = 0.1333 >= 0.10 (prob ~26% > 5%, so 95th percentile >= 0.1333).
    sd_unres, costs_unres = _make_synthetic(
        n_sets=10,
        miss_fn=lambda si, arm, k, cid: (arm == "a") or (arm == "c" and si == 1 and k in (1, 2)),
    )
    res_unres = A.analyze(sd_unres, costs_unres, audit, n_boot=2000, seed=20261125)
    m_unres = res_unres["primary"]["miss_diff_c_b"]
    assert m_unres["point"] == pytest.approx(4 / 60)
    assert m_unres["point"] < 0.10
    assert m_unres["upper_95"] >= 0.10
    assert m_unres["verdict"] == "UNRESOLVED"
    assert res_unres["verdict"] == "UNRESOLVED"

    # Case 3: small miss spread uniformly so upper_95 < 0.10 => NONINFERIOR
    # 20 sets, 120 pairs; only set 1 cycle 1 p1.price missed => 1/120 = 0.0083, upper_95 <= 3/120 = 0.025 < 0.10
    sd_ni, costs_ni = _make_synthetic(
        n_sets=20,
        miss_fn=lambda si, arm, k, cid: (arm == "a") or (arm == "c" and si == 1 and k == 1 and cid == "p1.price"),
    )
    res_ni = A.analyze(sd_ni, costs_ni, audit, n_boot=2000, seed=20261125)
    m_ni = res_ni["primary"]["miss_diff_c_b"]
    assert m_ni["point"] == pytest.approx(1 / 120)
    assert m_ni["upper_95"] < 0.10
    assert m_ni["verdict"] == "NONINFERIOR"
    assert res_ni["verdict"] == "EFFECTIVE"


def test_unknown_usage_exclusion_paired():
    """Set-cycles with tokens=None in either arm are counted and excluded from BOTH arms' sums."""
    def cost_fn(si, arm, k):
        if arm == "a":
            return {"ran": False, "calls": 0, "tokens_in": 0, "tokens_out": 0, "wall_s": 0.0}
        # In s01 cycle 1: arm b has huge known tokens (100000), arm c has None -> MUST exclude BOTH!
        if si == 1 and k == 1 and arm == "b":
            return {"ran": True, "calls": 10, "tokens_in": 100000, "tokens_out": 0, "wall_s": 30.0}
        if si == 1 and k == 1 and arm == "c":
            return {"ran": True, "calls": None, "tokens_in": None, "tokens_out": None, "wall_s": 5.0}
        # In s02 cycle 2: arm b has None, arm c has huge known tokens (100000) -> MUST exclude BOTH!
        if si == 2 and k == 2 and arm == "b":
            return {"ran": True, "calls": None, "tokens_in": None, "tokens_out": None, "wall_s": 30.0}
        if si == 2 and k == 2 and arm == "c":
            return {"ran": True, "calls": 2, "tokens_in": 100000, "tokens_out": 0, "wall_s": 5.0}
        # All other set-cycles: b=4000, c=1000 => exact 4.0x ratio
        tok = {"b": 4000, "c": 1000, "d": 2000}[arm]
        return {"ran": True, "calls": 8 if arm == "b" else 2,
                "tokens_in": tok, "tokens_out": 0, "wall_s": 20.0 if arm == "b" else 5.0}

    score_data, costs = _make_synthetic(n_sets=6, cost_fn=cost_fn)
    audit = {"coverage": {"claims": 120, "with_source": 120, "correct_page": 115}}

    res = A.analyze(score_data, costs, audit, n_boot=500, seed=20261125)
    tok = res["primary"]["token_ratio_b_c"]
    # 6 sets × 3 cycles = 18 pairs; 2 excluded => 16 used
    assert tok["n_paired_total"] == 18
    assert tok["n_paired_used"] == 16
    assert tok["excluded_unknown_count"] == 2
    assert tok["excluded_unknown"] == [["s01", 1], ["s02", 2]]
    assert tok["unknown_in_numerator"] == 1
    assert tok["unknown_in_denominator"] == 1
    # Sums reflect ONLY the 16 valid pairs (not the 100000 poisoned pairs!)
    assert tok["sum_numerator"] == pytest.approx(16 * 4000)
    assert tok["sum_denominator"] == pytest.approx(16 * 1000)
    assert tok["point"] == pytest.approx(4.0)
    assert tok["verdict"] == "EFFECTIVE"
    assert res["usage_unknown"]["total_tokens_unknown"] == 2
    assert res["verdict"] == "EFFECTIVE"


def test_incomplete_reports_missing_arm_cycle_and_cli(tmp_path):
    """Missing an arm/cycle yields INCOMPLETE with exact missing entries; CLI --out works."""
    score_data, costs = _make_synthetic(n_sets=4)
    # Drop s02 / arm d / cycle 3 from both rows and costs
    score_data["rows"] = [
        r for r in score_data["rows"]
        if not (r["set"] == "s02" and r["arm"] == "d" and r["cycle"] == 3)
    ]
    costs.pop(("s02", "d", 3))
    audit = {"coverage": {"claims": 80, "with_source": 80, "correct_page": 80}}

    res = A.analyze(score_data, costs, audit, n_boot=300, seed=20261125)
    assert res["verdict"] == "INCOMPLETE"
    assert res["completeness"]["complete"] is False
    assert res["completeness"]["missing"] == [
        {"set": "s02", "arm": "d", "cycle": 3, "missing_in": "both"}
    ]

    # Also test CLI end-to-end with a minimal fake run root readable by score_d2.load_harness
    root = tmp_path / "run"
    for si in (1, 2):
        sid = f"s{si:02d}"
        c0 = root / "cells" / sid / "c0"
        c0.mkdir(parents=True)
        (c0 / "report.md").write_text("- P — price: $10\n")
        for arm in ("a", "b", "c", "d"):
            adir = root / "cells" / sid / arm
            for k in (1, 2, 3):
                cd = adir / f"cycle_{k}"
                cd.mkdir(parents=True)
                (cd / "report.md").write_text("- P — price: $10\n")
                agent = None if arm == "a" else {
                    "rc": 0, "wall_s": 20.0 if arm == "b" else 4.0,
                    "usage": {"calls": 8 if arm == "b" else 2,
                              "input": 4000 if arm == "b" else 800,
                              "output": 1000 if arm == "b" else 200},
                }
                (cd / "cycle.json").write_text(json.dumps({"arm": arm, "cycle": k, "agent": agent}))
            (adir / "done.json").write_text(json.dumps({"ts": "2026-11-25T00:00:00Z"}))

    sd2, _ = _make_synthetic(n_sets=2)
    score_p = tmp_path / "score.json"
    audit_p = tmp_path / "audit.json"
    out_p = tmp_path / "analysis.json"
    score_p.write_text(json.dumps(sd2))
    audit_p.write_text(json.dumps({"coverage": {"claims": 40, "with_source": 40, "correct_page": 38}}))

    rc = A.main(["--score", str(score_p), "--root", str(root), "--audit", str(audit_p),
                 "--bootstrap", "300", "--seed", "20261125", "--out", str(out_p)])
    assert rc == 0
    loaded = json.loads(out_p.read_text())
    assert loaded["verdict"] == "EFFECTIVE"
    assert loaded["primary"]["token_ratio_b_c"]["point"] == pytest.approx(5.0)
