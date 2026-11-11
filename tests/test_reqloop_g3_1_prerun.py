# -*- coding: utf-8 -*-
"""G3.1 H2.0 extract 預跑門（P20261111_1315-2）：正/負控制＋--selftest（0 模型呼叫）。
正控制＝1/4 題有 1 條確定性 claim → H2_0_MET；負控制＝全 unverified → H2_0_REFUTED（fail-closed）。"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops" / "audits" / "g3_1_extract_prerun.py"

def _load():
    spec = importlib.util.spec_from_file_location("g3_1_extract_prerun", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"缺少 {SCRIPT}（P20261111_1315-2 未落地）"


def _classify(mod, unverified: bool, reason: str = "") -> dict:
    from vacant_network.reqloop.extract import (
        ExtractReport, RequirementItem, RequirementSet, UnverifiedItem,
    )
    item = RequirementItem(
        id="R1", quote="q", deliverable="answer.txt",
        verifier="answer_kv" if not unverified else "made_up",
        params={}, unverified=unverified,
    )
    rep = ExtractReport(
        kept=("R1",),
        unverified=(UnverifiedItem("R1", reason),) if unverified else (),
    )
    return mod.classify(RequirementSet(task_id="t", items=[item]), rep)


def test_positive_control_met() -> None:
    mod = _load()
    pos = _classify(mod, unverified=False)
    neg = _classify(mod, unverified=True, reason="unknown_verifier:made_up")
    rows = [pos, neg, neg, neg]
    assert pos["n_deterministic_claims"] == 1 and pos["n_requirements"] == 1
    assert mod.h20_verdict(rows) == "H2_0_MET"
    doc = mod.build_report(rows, model="mock", cost={"model_calls": 4, "total_tokens": "UNKNOWN"})
    assert doc["h20_verdict"] == "H2_0_MET"
    assert doc["n_tasks_with_deterministic_claim"] == 1
    assert {"schema", "cost", "tasks"} <= set(doc)
    json.dumps(doc, ensure_ascii=False)


def test_negative_control_refuted() -> None:
    mod = _load()
    rows = []
    for i in range(4):
        r = _classify(mod, unverified=True, reason=f"unknown_verifier:x{i}")
        assert r["n_deterministic_claims"] == 0 and r["n_unverified_claims"] == 1
        assert r["reason_distribution"] == {f"unknown_verifier:x{i}": 1}
        rows.append(r)
    assert mod.h20_verdict(rows) == "H2_0_REFUTED"
    doc = mod.build_report(rows, model="mock", cost={"model_calls": 4, "total_tokens": "UNKNOWN"})
    assert doc["n_tasks_with_deterministic_claim"] == 0
    json.dumps(doc, ensure_ascii=False)


def test_selftest_cli() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--selftest"],
        cwd=REPO, capture_output=True, text=True, timeout=300,
    )
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    assert "Traceback" not in r.stderr, r.stderr
    assert "VERDICT: G3_1_PRERUN_SELFTEST_OK" in r.stdout, r.stdout


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
