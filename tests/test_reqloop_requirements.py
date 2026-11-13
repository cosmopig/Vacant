"""P20261113_0746-1 — RequirementSet 任務雜湊錨點與完整性校驗（goal_sha256 / contract_sha256 / verify_task_hash）。

正控制 1 條＋負控制 3 條；0 model calls。
"""

import hashlib
import pathlib

from vacant_network.reqloop.requirements import RequirementSet


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _make_bound_spec(tmp_path: pathlib.Path) -> RequirementSet:
    goal = tmp_path / "goal.md"
    contract = tmp_path / "contract.md"
    goal.write_text("Goal: produce answer.txt with the value.\n", encoding="utf-8")
    contract.write_text("Deliverable: answer.txt (input files are never deliverables).\n", encoding="utf-8")
    return RequirementSet(
        task_id="t1",
        goal_sha256=_sha(goal),
        contract_sha256=_sha(contract),
    )


def test_verify_task_hash_positive_control(tmp_path):
    spec = _make_bound_spec(tmp_path)
    ok, msg = spec.verify_task_hash(tmp_path)
    assert ok is True
    assert msg == "OK"


def test_verify_task_hash_goal_tampered_negative(tmp_path):
    spec = _make_bound_spec(tmp_path)
    # 篡改 goal.md 一個字元
    (tmp_path / "goal.md").write_text("Goal: produce answer.txt with the VALUE.\n", encoding="utf-8")
    ok, msg = spec.verify_task_hash(tmp_path)
    assert ok is False
    assert "mismatch" in msg


def test_verify_task_hash_contract_missing_negative(tmp_path):
    spec = _make_bound_spec(tmp_path)
    (tmp_path / "contract.md").unlink()
    ok, msg = spec.verify_task_hash(tmp_path)
    assert ok is False
    assert "mismatch" in msg


def test_verify_task_hash_unbound_old_spec_negative(tmp_path):
    (tmp_path / "goal.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "contract.md").write_text("y\n", encoding="utf-8")
    # 舊版規格：未綁定任何 hash
    spec = RequirementSet(task_id="old")
    ok, msg = spec.verify_task_hash(tmp_path)
    assert ok is False
    assert msg == "unbound"
