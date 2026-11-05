"""G1 must distinguish unknown, missing evidence and actual PASS."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from ops.reqloop.g1 import run_g1 as gate

@pytest.mark.parametrize("status", ["UNKNOWN", "CONFLICT", "FAIL"])
def test_nonpass_is_not_verified(status):
    assert not gate.required_verified([NS(id="r", required=True)], [NS(claim_id="r", status=status)])

@pytest.mark.parametrize("results", [[], [NS(claim_id="other", status="PASS")],
    [NS(claim_id="r", status="PASS"), NS(claim_id="r", status="PASS")]])
def test_missing_or_duplicate_result_is_not_verified(results):
    assert not gate.required_verified([NS(id="r", required=True)], results)

def test_empty_requirements_are_not_verified():
    assert not gate.required_verified([], [])

def test_explicit_pass_is_verified():
    assert gate.required_verified([NS(id="r", required=True)], [NS(claim_id="r", status="PASS")])

def test_unknown_good_cannot_pass_g1(monkeypatch, capsys):
    original = gate.run_requirement_checks
    def unknown_good(task, reqs, delivery):
        results = original(task, reqs, delivery)
        return [replace(c, status="UNKNOWN") for c in results] if delivery.name == "good" else results
    monkeypatch.setattr(gate, "run_requirement_checks", unknown_good)
    assert gate.main() == 20
    out = capsys.readouterr().out
    assert "UNKNOWN" in out
    assert "正確放行" not in out

def test_missing_good_cannot_pass_g1(monkeypatch):
    original = gate.evaluate_task
    def missing_good(task):
        result = original(task)
        result.update(good_evaluated=False, good_verified=False)
        return result
    monkeypatch.setattr(gate, "evaluate_task", missing_good)
    assert gate.main() == 20

def test_real_fixture_bank():
    assert gate.main() == 0
