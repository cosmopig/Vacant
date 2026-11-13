"""D3b（P20261113_0344-1）：pearson 重算原語回歸測試（零模型）。

驗收：python3 -m pytest tests/test_reqloop_checks_pearson.py -q → 3 passed

資料：repo 已凍結真實資料檔 ops/reqloop/g3_2/tasks/dab_517/workspace/data/titanic.csv
（Pclass/Fare；891 行全數成對、r = -0.5494996199439077 → round 2 = -0.55）。

覆蓋（票面要求）：
- 已知相關值正控制 → PASS（kv_recomputed 與 plain_recomputed 兩條分派）
- 錯值負控制 → FAIL（不得因 NaN/缺值假 PASS）
- 缺欄位負控制 → UNKNOWN（不是 FAIL、不是 PASS）
- 重算值不進 detail/evidence（防洩漏：修復模型不被直接給答案）
"""

import json
import pathlib

from vacant_network.reqloop.requirements import RequirementItem, RequirementSet
from vacant_network.reqloop.checks import run_requirement_checks

REPO = pathlib.Path(__file__).resolve().parents[1]
TITANIC = REPO / "ops" / "reqloop" / "g3_2" / "tasks" / "dab_517" / "workspace" / "data" / "titanic.csv"
# Pclass × Fare（891 對全數成對）：r 的已知值（口徑＝checks.py _pearson_pair，與 pearson2 同）
KNOWN_R = -0.5494996199439077
KNOWN_R_ROUND2 = "-0.55"


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _task_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """把凍結 titanic 資料檔放進任務目錄（data/titanic.csv）。"""
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "data").mkdir()
    (task_dir / "data" / "titanic.csv").write_bytes(TITANIC.read_bytes())
    return task_dir


def _req_set(verifier: str, params: dict, deliverable: str = "answer.txt") -> RequirementSet:
    return RequirementSet(
        task_id="t",
        items=[
            RequirementItem(
                id="req_main",
                quote="測試需求（D3b pearson）",
                deliverable=deliverable,
                verifier=verifier,
                params=params,
            )
        ],
    )


def _blob(results) -> str:
    return json.dumps(
        [{"detail": r.detail, "evidence": r.evidence} for r in results], ensure_ascii=False)


def test_kv_pearson_known_value_pass_and_wrong_value_fails(tmp_path: pathlib.Path):
    """kv_recomputed 分派：已知相關值正控制 PASS；錯值負控制 FAIL。"""
    task_dir = _task_dir(tmp_path)
    params = {
        "key": "corr",
        "data_file": "data/titanic.csv",
        "recompute": {"type": "pearson", "col_a": "Pclass", "col_b": "Fare", "round": 2},
    }
    rs = _req_set("kv_recomputed", params)

    good = tmp_path / "good"
    _write(good / "answer.txt", "@corr[-0.55]\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, rs, good)}
    assert res["req_main"].status == "PASS"

    bad = tmp_path / "bad"
    _write(bad / "answer.txt", "@corr[-0.54]\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, rs, bad)}
    assert res["req_main"].status == "FAIL"


def test_kv_pearson_missing_column_is_unknown_not_fail(tmp_path: pathlib.Path):
    """kv_recomputed 分派：缺欄位 → UNKNOWN（不是 FAIL、不是 PASS；不自評）。"""
    task_dir = _task_dir(tmp_path)
    params = {
        "key": "corr",
        "data_file": "data/titanic.csv",
        "recompute": {"type": "pearson", "col_a": "no_such_col_9x", "col_b": "Fare"},
    }
    rs = _req_set("kv_recomputed", params)
    d = tmp_path / "d"
    _write(d / "answer.txt", "@corr[0]\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, rs, d)}
    assert res["req_main"].status == "UNKNOWN"


def test_plain_pearson_dispatch_and_value_not_leaked(tmp_path: pathlib.Path):
    """plain_recomputed 分派：已知值 PASS／錯值 FAIL；重算值不進 detail/evidence（防洩漏）。"""
    task_dir = _task_dir(tmp_path)
    params = {
        "data_file": "data/titanic.csv",
        "recompute": {"type": "pearson", "col_a": "Pclass", "col_b": "Fare", "round": 2},
    }
    rs = _req_set("plain_recomputed", params)

    good = tmp_path / "good"
    _write(good / "answer.txt", "-0.55\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, rs, good)}
    assert res["req_main"].status == "PASS"
    # 正控制側：重算值也不得出現在 detail/evidence
    blob_pass = _blob(res.values())
    for needle in (repr(KNOWN_R), KNOWN_R_ROUND2):
        assert needle not in blob_pass, f"{needle!r} leaked in {blob_pass}"

    bad = tmp_path / "bad"
    _write(bad / "answer.txt", "0.55\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, rs, bad)}
    r0 = res["req_main"]
    assert r0.status == "FAIL"
    blob_fail = _blob(res.values())
    for needle in (repr(KNOWN_R), KNOWN_R_ROUND2, "-0.5494996"):
        assert needle not in blob_fail, f"{needle!r} leaked in {blob_fail}"
