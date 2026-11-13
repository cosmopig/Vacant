"""P20261113_0746-1 — RequirementSet 任務雜湊錨點與完整性校驗（goal_sha256 / contract_sha256 / verify_task_hash）。

正控制 1 條＋負控制 3 條；0 model calls。
"""

import dataclasses
import hashlib
import pathlib

from vacant_network.reqloop.requirements import RequirementItem, RequirementSet


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


def test_verify_self_hash_controls():
    """P20261113_0846-2：spec_sha256 欄位＋自雜湊自校驗（正 1／負 2／真實資料 1；0 model calls）。

    口徑同 freeze_specs._canon：整份規格（除 spec_sha256 欄）canonical JSON 的 sha256。
    """
    # (c) 負控制：未綁定 spec_sha256 → unbound（不是 PASS、不是「沒有」）
    rs = RequirementSet(
        task_id="t1",
        items=[RequirementItem(id="r1",
                               quote="answer.txt 必須給出數字結果",
                               deliverable="answer.txt",
                               verifier="answer_kv")],
    )
    assert rs.verify_self_hash() == (False, "unbound")
    # (a) 正控制：設定正確 spec_sha256 → (True, "OK")
    rs.spec_sha256 = rs.compute_spec_sha256()
    assert rs.verify_self_hash() == (True, "OK")
    # (b) 負控制：改動 items 內任何一個字元 → False 且含 mismatch
    # （RequirementItem 為 frozen dataclass，以 replace 換入改字元後的新條目）
    rs.items[0] = dataclasses.replace(rs.items[0], quote="answer.txt 必須給出數字結果。")
    ok, msg = rs.verify_self_hash()
    assert ok is False
    assert "mismatch" in msg
    # (d) 實例驗證：G4 凍結規格 dab_517（檔案 spec_sha256 即整份規格 canonical JSON 之 sha256）
    repo = pathlib.Path(__file__).resolve().parent.parent
    spec = RequirementSet.load(repo / "ops" / "reqloop" / "g4" / "specs" / "dab_517.json")
    assert spec.verify_self_hash() == (True, "OK")
