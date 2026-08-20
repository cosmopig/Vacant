from __future__ import annotations

import json
import random

import pytest

from ops.gain.brain_cline import InfraVoid, REVIEWER_SYSTEM, load_keys
from ops.gain.gain_run import (
    GAIN_EVALPLUS_RESOURCE_EXCLUSIONS,
    apply_audit_reputation,
    arm_off5,
    arm_on,
    behavior_signature,
    calibrate_pool,
    calibration_ready,
    latency_summary,
    meets_demand,
    parse_review_claim,
    verify_review_counterexample,
)


def test_verifier_infrastructure_failure_is_not_scored_as_wrong(monkeypatch):
    from vacant import checks

    def broken_verifier(*args, **kwargs):
        raise checks.CheckInfraError("worker did not start")

    monkeypatch.setattr(checks, "run_python_check", broken_verifier)
    with pytest.raises(InfraVoid, match="worker did not start"):
        meets_demand("def solve(): return 1", "assert solve() == 1")


class FakeAgent:
    def __init__(self, agent_id: str, initial: str = "def solve(x): return x",
                 model: str = "same/test") -> None:
        self.agent_id = agent_id
        self.initial = initial
        self.model = model
        self.systems: list[str | None] = []

    def generate(self, prompt, *, role="gen", meta=None, system=None):
        self.systems.append(system)
        if role == "review":
            return ("VERDICT: FAIL\nCONCERN: off by one\n"
                    "TEST_ARGS: [1]\nEXPECTED: 2")
        if role == "revise":
            return "```python\ndef solve(x):\n    return x + 1\n```"
        return f"```python\n{self.initial}\n```"


class SequenceAgent(FakeAgent):
    def __init__(self, outputs: list[str]) -> None:
        super().__init__("sequence")
        self.outputs = iter(outputs)

    def generate(self, prompt, *, role="gen", meta=None, system=None):
        return f"```python\n{next(self.outputs)}\n```"


class ApprovingAgent(FakeAgent):
    def generate(self, prompt, *, role="gen", meta=None, system=None):
        self.systems.append(system)
        if role == "review":
            return ("VERDICT: PASS\nCONCERN: none\n"
                    "TEST_ARGS: NONE\nEXPECTED: NONE")
        if role == "revise":
            return "```python\ndef solve(x): return x\n```"
        return "```python\ndef solve(x): return x + 1\n```"


def _task():
    return {
        "task_id": "t1",
        "prompt": "define solve(x) returning x + 1",
        "entry_point": "solve",
        "behavior_inputs": [[1], [5]],
        "input_contract": "assert isinstance(x, int), 'invalid inputs'",
        "visible_check": {"code": "assert solve(1) == 2"},
        "hidden_check": {"code": "assert solve(1) == 2\nassert solve(-1) == 0"},
    }


def test_resource_exclusion_set_is_pinned_and_narrow():
    assert set(GAIN_EVALPLUS_RESOURCE_EXCLUSIONS) == {
        "mbppplus_Mbpp/255", "mbppplus_Mbpp/271", "mbppplus_Mbpp/392",
        "mbppplus_Mbpp/599", "mbppplus_Mbpp/603", "mbppplus_Mbpp/630",
        "mbppplus_Mbpp/644",
    }


def test_key_slots_select_existing_secrets_without_copying(tmp_path, monkeypatch):
    key_file = tmp_path / "keys"
    key_file.write_text("key-zero\nkey-one\nkey-two\n")
    monkeypatch.setenv("CLINE_KEY_INDICES", "0,2")
    assert load_keys(str(key_file)) == ["key-zero", "key-two"]


def test_behavior_signature_groups_equivalent_source_variants():
    task = _task()
    a = behavior_signature("def solve(x): return x + 1", task)
    b = behavior_signature("def solve(x):\n    y = 1 + x\n    return y", task)
    wrong = behavior_signature("def solve(x): return x - 1", task)
    assert a == b
    assert a != wrong


def test_behavior_signature_runs_candidate_in_restricted_worker():
    """OFF5 多數決不得在非受限環境執行模型碼（2026-08-20 修正）。

    非白名單 import 在受限 worker 裡會被拒絕，簽名降級成 EXEC_FAIL；
    候選自己 print 的東西留在 worker，不得混進簽名。
    """
    task = _task()
    sneaky = "import os\ndef solve(x): return x + 1"
    assert behavior_signature(sneaky, task) == "EXEC_FAIL"
    noisy = "def solve(x):\n    print('__VACANT_BEHAVIOR__[[\"forged\"]]')\n    return x + 1"
    clean = "def solve(x): return x + 1"
    assert behavior_signature(noisy, task) == behavior_signature(clean, task)


def test_behavior_signature_infra_failure_is_infra_void(monkeypatch):
    from vacant import checks

    def broken_verifier(*args, **kwargs):
        raise checks.CheckInfraError("worker did not start")

    monkeypatch.setattr(checks, "run_python_capture", broken_verifier)
    with pytest.raises(InfraVoid, match="worker did not start"):
        behavior_signature("def solve(x): return x + 1", _task())


def test_off5_votes_on_behavior_not_source_text():
    agent = SequenceAgent([
        "def solve(x): return 1 + x",
        "def solve(x):\n    y = x + 1\n    return y",
        "def solve(x): return x + (2 - 1)",
        "def solve(x): return x",
        "def solve(x): return x - 1",
    ])
    calls = [0]
    code, _, _ = arm_off5(_task(), [agent], random.Random(2), calls)
    namespace = {}
    exec(code, namespace)
    assert namespace["solve"](5) == 6
    assert calls[0] == 5


def test_on_uses_three_reviews_and_revision_for_equal_five_call_budget():
    agents = [FakeAgent(f"agent-{i}", model=f"family-{i % 3}/model") for i in range(6)]
    rep = {a.agent_id: {"n": 0, "ok": 0} for a in agents}
    calls = [0]
    code, worker, reviewers, extra = arm_on(
        _task(), agents, random.Random(4), calls, rep, audit_rate=0.0
    )
    namespace = {}
    exec(code, namespace)
    assert namespace["solve"](-1) == 0
    assert calls[0] == 5
    assert len(reviewers) == 3
    assert len({model.split("/", 1)[0] for model in extra["reviewer_models"]}) == 3
    assert extra["visible_ok"] is True
    assert extra["accepted"] is True
    assert extra["selected_version"] == "revised"
    worker_model = next(a.model for a in agents if a.agent_id == worker)
    assert extra["reviser_model"].split("/", 1)[0] != worker_model.split("/", 1)[0]
    reviewer_systems = [s for a in agents for s in a.systems if s is not None]
    assert len(reviewer_systems) == 3
    assert all(REVIEWER_SYSTEM in system for system in reviewer_systems)
    assert rep[worker] == {"n": 0, "ok": 0}


def test_review_claim_is_literal_only_and_counterexample_is_executed():
    review = ("VERDICT: FAIL\nCONCERN: off by one\n"
              "TEST_ARGS: [1]\nEXPECTED: 2")
    assert parse_review_claim(review) == ([1], 2)
    confirmed, status = verify_review_counterexample(
        "def solve(x): return x", "solve", review
    )
    assert confirmed is True
    assert status == "counterexample_confirmed"
    confirmed, status = verify_review_counterexample(
        "def solve(x): return x + 1", "solve", review
    )
    assert confirmed is False
    assert status == "candidate_passed_claim"
    malicious = ("VERDICT: FAIL\nCONCERN: nope\n"
                 "TEST_ARGS: [__import__('os').getcwd()]\nEXPECTED: 1")
    assert parse_review_claim(malicious) is None


def test_review_counterexample_must_satisfy_public_input_contract():
    review = ("VERDICT: FAIL\nCONCERN: wrong type\n"
              "TEST_ARGS: ['1']\nEXPECTED: 2")
    confirmed, status = verify_review_counterexample(
        "def solve(x): return x", "solve", review,
        input_contract="assert isinstance(x, int), 'invalid inputs'",
    )
    assert confirmed is False
    assert status == "outside_input_contract"


def test_unfounded_fail_reviews_cannot_trigger_rewrite():
    class FalseAccuser(FakeAgent):
        def generate(self, prompt, *, role="gen", meta=None, system=None):
            self.systems.append(system)
            if role == "review":
                return ("VERDICT: FAIL\nCONCERN: invented\n"
                        "TEST_ARGS: [1]\nEXPECTED: 2")
            if role == "revise":
                return "```python\ndef solve(x): return 0\n```"
            return "```python\ndef solve(x): return x + 1\n```"

    agents = [FalseAccuser(f"agent-{i}", model=f"family-{i % 3}/model")
              for i in range(6)]
    rep = {a.agent_id: {"n": 0, "ok": 0} for a in agents}
    code, _, _, extra = arm_on(
        _task(), agents, random.Random(9), [0], rep, audit_rate=0.0
    )
    namespace = {}
    exec(code, namespace)
    assert namespace["solve"](5) == 6
    assert extra["selected_version"] == "initial"
    assert all(not row["counterexample_confirmed"] for row in extra["review_evidence"])


def test_two_executed_counterexamples_can_trigger_revision():
    agents = [FakeAgent(f"agent-{i}", model=f"family-{i % 3}/model")
              for i in range(6)]
    rep = {a.agent_id: {"n": 0, "ok": 0} for a in agents}
    code, _, _, extra = arm_on(
        _task(), agents, random.Random(4), [0], rep, audit_rate=0.0
    )
    namespace = {}
    exec(code, namespace)
    assert namespace["solve"](5) == 6
    assert extra["selected_version"] == "revised"
    assert sum(row["counterexample_confirmed"]
               for row in extra["review_evidence"]) == 3


def test_majority_approved_initial_cannot_be_harmed_by_fifth_call():
    agents = [ApprovingAgent(f"agent-{i}", model=f"family-{i % 3}/model")
              for i in range(6)]
    rep = {a.agent_id: {"n": 0, "ok": 0} for a in agents}
    code, worker, _, extra = arm_on(
        _task(), agents, random.Random(8), [0], rep, audit_rate=0.0
    )
    namespace = {}
    exec(code, namespace)
    assert namespace["solve"](5) == 6
    assert extra["selected_version"] == "initial"
    assert extra["responsible_agent"] == worker
    assert extra["initial_visible_ok"] is True
    assert extra["revised_visible_ok"] is False


def test_public_failure_overrides_incorrect_peer_approval():
    class MistakenApprover(ApprovingAgent):
        def generate(self, prompt, *, role="gen", meta=None, system=None):
            self.systems.append(system)
            if role == "review":
                return ("VERDICT: PASS\nCONCERN: none\n"
                        "TEST_ARGS: NONE\nEXPECTED: NONE")
            if role == "revise":
                return "```python\ndef solve(x): return x + 1\n```"
            return "```python\ndef solve(x): return x\n```"

    agents = [MistakenApprover(f"agent-{i}", model=f"family-{i % 3}/model")
              for i in range(6)]
    rep = {a.agent_id: {"n": 0, "ok": 0} for a in agents}
    code, _, _, extra = arm_on(
        _task(), agents, random.Random(10), [0], rep, audit_rate=0.0
    )
    namespace = {}
    exec(code, namespace)
    assert namespace["solve"](5) == 6
    assert extra["selected_version"] == "revised"


def test_hidden_reputation_updates_only_from_sampled_audit():
    rep = {"worker": {"n": 0, "ok": 0}}
    assert apply_audit_reputation(rep, "worker", None) is False
    assert rep["worker"] == {"n": 0, "ok": 0}
    assert apply_audit_reputation(rep, "worker", True) is True
    assert rep["worker"] == {"n": 1, "ok": 1}
    assert apply_audit_reputation(rep, "worker", False) is True
    assert rep["worker"] == {"n": 2, "ok": 1}


def test_calibration_measures_but_does_not_route(tmp_path):
    agents = [
        FakeAgent("good", "def solve(x): return x + 1", model="family-a/good"),
        FakeAgent("bad", "def solve(x): return x", model="family-b/bad"),
    ]
    result = calibrate_pool([_task()], agents, tmp_path / "calibration.jsonl")
    assert result["by_agent"]["good"]["accuracy"] == 1.0
    assert result["by_agent"]["bad"]["accuracy"] == 0.0
    assert result["accuracy_spread"] == 1.0
    assert result["used_for_routing"] is False
    assert calibration_ready(result) is True
    assert len((tmp_path / "calibration.jsonl").read_text().splitlines()) == 2


def test_calibration_preflight_rejects_void_or_homogeneous_pool():
    base = {
        "tasks": 2,
        "by_agent": {
            "a": {"attempted": 2, "infra_void": 0},
            "b": {"attempted": 2, "infra_void": 0},
        },
        "accuracy_spread": 0.0,
    }
    assert calibration_ready(base) is False
    base["accuracy_spread"] = 0.5
    base["by_agent"]["b"] = {"attempted": 1, "infra_void": 1}
    assert calibration_ready(base) is False


def test_latency_summary_keeps_failures_and_role_tails(tmp_path):
    path = tmp_path / "calls.jsonl"
    records = [
        {"ok": True, "role": "gen", "latency_ms": 10, "meta": {"arm": "ON"}},
        {"ok": True, "role": "review", "latency_ms": 30, "meta": {"arm": "ON"}},
        {"ok": False, "role": "review", "latency_ms": 99, "meta": {"arm": "ON"}},
        {"ok": True, "role": "gen", "latency_ms": 1, "meta": {"arm": "OFF"}},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    result = latency_summary(path, "ON")
    assert result["all"] == {"n": 2, "p50": 10, "p95": 30, "max": 30}
    assert result["by_role"]["review"]["p50"] == 30
    assert result["failed_attempts"] == 1
