"""D3（P20261113_0300-3）mean_col／median_col／std_col 重算原語正負控制。

票面驗收：每型別一個以 repo 凍結真實資料檔算出的已知值正控制、一個錯值負控制
（必判 FAIL）、一個缺欄負控制（必判 UNKNOWN 而非 FAIL）。
資料＝dab_725 凍結 workspace 的 data/auto-mpg.csv（g3_2，凍結進 repo）；期望值
本檔以 pandas 獨立計算（與 checks.py 同 pandas 口徑、獨立代碼路徑，非轉抄實作）。
防洩漏紅線：重算值永不進 detail/evidence（evidence.expected_in_evidence 必為 False）。
kv_recomputed 與 plain_recomputed 兩路徑各測（兩型別集合皆含此三型別）。
"""
from __future__ import annotations

import math
import pathlib

import pandas as pd
import pytest

from vacant_network.reqloop.checks import run_requirement_checks
from vacant_network.reqloop.requirements import RequirementItem, RequirementSet

REPO = pathlib.Path(__file__).resolve().parents[1]
TASK_DIR = REPO / "ops" / "reqloop" / "g3_2" / "tasks" / "dab_725"
DATA_REL = "workspace/data/auto-mpg.csv"

_DF = pd.read_csv(TASK_DIR / DATA_REL)
KNOWN = {
    "mean_col": float(_DF["mpg"].mean()),
    "median_col": float(_DF["mpg"].median()),
    "std_col": float(_DF["mpg"].std()),  # pandas 口徑＝樣本標準差（ddof=1）
}
for _v in KNOWN.values():
    assert math.isfinite(_v) and _v > 0, KNOWN


def _req_set(verifier: str, params: dict) -> RequirementSet:
    return RequirementSet(
        task_id="t",
        items=[
            RequirementItem(
                id="req_main",
                quote="測試需求",
                deliverable="answer.txt",
                verifier=verifier,
                params=params,
            )
        ],
    )


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _judge(verifier: str, rtype: str, col: str, deliverable_dir: pathlib.Path):
    params = {"data_file": DATA_REL, "recompute": {"type": rtype, "col": col}}
    if verifier == "kv_recomputed":
        params["key"] = "stat"
    res = {
        r.claim_id: r
        for r in run_requirement_checks(TASK_DIR, _req_set(verifier, params), deliverable_dir)
    }
    return res["req_main"]


def _case(verifier: str, rtype: str, col: str, value: float, tmp_path: pathlib.Path):
    d = tmp_path / "d"
    if verifier == "kv_recomputed":
        _write(d / "answer.txt", f"@stat[{value!r}]\n")
    else:
        _write(d / "answer.txt", f"{value!r}\n")
    return _judge(verifier, rtype, col, d)


@pytest.mark.parametrize("verifier", ["kv_recomputed", "plain_recomputed"])
@pytest.mark.parametrize("rtype", ["mean_col", "median_col", "std_col"])
def test_stats_positive_control(verifier: str, rtype: str, tmp_path: pathlib.Path) -> None:
    """正控制：已知值（pandas 獨立實算）→ PASS。"""
    r = _case(verifier, rtype, "mpg", KNOWN[rtype], tmp_path)
    assert r.status == "PASS", (r.status, r.detail)


@pytest.mark.parametrize("verifier", ["kv_recomputed", "plain_recomputed"])
@pytest.mark.parametrize("rtype", ["mean_col", "median_col", "std_col"])
def test_stats_wrong_value_is_fail(verifier: str, rtype: str, tmp_path: pathlib.Path) -> None:
    """負控制：錯值（期望×1.02＋1，超出容差）→ 必判 FAIL（不得假 PASS）。"""
    bad = KNOWN[rtype] * 1.02 + 1.0
    assert abs(bad - KNOWN[rtype]) > 1e-6
    r = _case(verifier, rtype, "mpg", bad, tmp_path)
    assert r.status == "FAIL", (r.status, r.detail)
    assert r.evidence.get("expected_in_evidence") is False, r.evidence  # 防洩漏紅線


@pytest.mark.parametrize("verifier", ["kv_recomputed", "plain_recomputed"])
@pytest.mark.parametrize("rtype", ["mean_col", "median_col", "std_col"])
def test_stats_missing_column_is_unknown_not_fail(verifier: str, rtype: str, tmp_path: pathlib.Path) -> None:
    """負控制：缺欄 → 必判 UNKNOWN（不猜、非 FAIL）。"""
    r = _case(verifier, rtype, "no_such_col_9x7z", KNOWN[rtype], tmp_path)
    assert r.status == "UNKNOWN", (r.status, r.detail)
