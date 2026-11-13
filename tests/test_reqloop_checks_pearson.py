"""D3b（P20261113_0344-1）pearson 重算原語正負控制。

票面驗收：以 repo 凍結真實資料檔算出的已知相關係數正控制、錯值負控制
（必判 FAIL）、缺欄負控制（必判 UNKNOWN 而非 FAIL）。
資料＝dab_517 凍結 workspace 的 data/titanic.csv（g3_2，凍結進 repo）；
期望值以 pandas 獨立計算（Pclass vs Fare，r ≈ -0.5494996）。
防洩漏紅線：重算值永不進 detail/evidence（evidence.expected_in_evidence 必為 False）。
kv_recomputed 與 plain_recomputed 兩路徑各測。
"""
from __future__ import annotations

import math
import pathlib

import pandas as pd
import pytest

from vacant_network.reqloop.checks import run_requirement_checks
from vacant_network.reqloop.requirements import RequirementItem, RequirementSet

REPO = pathlib.Path(__file__).resolve().parents[1]
TASK_DIR = REPO / "ops" / "reqloop" / "g3_2" / "tasks" / "dab_517"
DATA_REL = "workspace/data/titanic.csv"

_DF = pd.read_csv(TASK_DIR / DATA_REL)
KNOWN_PEARSON = float(_DF[["Pclass", "Fare"]].corr().iloc[0, 1])
assert math.isfinite(KNOWN_PEARSON) and abs(KNOWN_PEARSON) > 0.1


def _req_set(verifier: str, params: dict) -> RequirementSet:
    return RequirementSet(
        task_id="t",
        items=[
            RequirementItem(
                id="req_pearson",
                quote="測試相關係數需求",
                deliverable="answer.txt",
                verifier=verifier,
                params=params,
            )
        ],
    )


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _judge(verifier: str, col_a: str, col_b: str, deliverable_dir: pathlib.Path):
    params = {
        "data_file": DATA_REL,
        "recompute": {"type": "pearson", "col_a": col_a, "col_b": col_b},
    }
    if verifier == "kv_recomputed":
        params["key"] = "corr"
    res = {
        r.claim_id: r
        for r in run_requirement_checks(TASK_DIR, _req_set(verifier, params), deliverable_dir)
    }
    return res["req_pearson"]


def _case(verifier: str, col_a: str, col_b: str, value: float, tmp_path: pathlib.Path):
    d = tmp_path / "d"
    if verifier == "kv_recomputed":
        _write(d / "answer.txt", f"@corr[{value!r}]\n")
    else:
        _write(d / "answer.txt", f"{value!r}\n")
    return _judge(verifier, col_a, col_b, d)


@pytest.mark.parametrize("verifier", ["kv_recomputed", "plain_recomputed"])
def test_pearson_positive_control(verifier: str, tmp_path: pathlib.Path) -> None:
    """正控制：已知相關係數（pandas 獨立實算）→ PASS。"""
    r = _case(verifier, "Pclass", "Fare", KNOWN_PEARSON, tmp_path)
    assert r.status == "PASS", (r.status, r.detail)


@pytest.mark.parametrize("verifier", ["kv_recomputed", "plain_recomputed"])
def test_pearson_wrong_value_is_fail(verifier: str, tmp_path: pathlib.Path) -> None:
    """負控制：錯值（+0.5，符號相反且數值不符）→ 必判 FAIL（不得假 PASS）。"""
    bad = 0.50
    assert abs(bad - KNOWN_PEARSON) > 1e-4
    r = _case(verifier, "Pclass", "Fare", bad, tmp_path)
    assert r.status == "FAIL", (r.status, r.detail)
    assert r.evidence.get("expected_in_evidence") is False, r.evidence  # 防洩漏紅線


@pytest.mark.parametrize("verifier", ["kv_recomputed", "plain_recomputed"])
def test_pearson_missing_column_is_unknown_not_fail(verifier: str, tmp_path: pathlib.Path) -> None:
    """負控制：缺欄 → 必判 UNKNOWN（不猜、非 FAIL）。"""
    r = _case(verifier, "no_such_col", "Fare", KNOWN_PEARSON, tmp_path)
    assert r.status == "UNKNOWN", (r.status, r.detail)
