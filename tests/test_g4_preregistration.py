"""G4 預註冊實驗包：manifest 完整性 / 12 格 / 發射門 fail-closed / dry-run 0 model calls。

工單: P20261113_0708-2-g4-preregistration（2026-11-13 人類定案第 4 條：G4 預註冊、發射前須人類點頭）。
P20261113_0948-2：LaunchRefused／decide_g4_launch／g4_dry_run 已封裝為產品模組
vacant_network.reqloop.g4gate；本測試改由產品模組引入（不再內嵌參考實現）。
不變量：本模組與測試不發起任何真模型呼叫（0 model calls）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib

import pytest

from vacant_network.reqloop.g4gate import (
    LaunchRefused,
    build_g4_execution_plan,
    decide_g4_launch,
    g4_dry_run,
    load_g4_manifest,
)
from vacant_network.reqloop.requirements import RequirementSet

REPO = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = REPO / "ops" / "reqloop" / "g4" / "manifest.json"
EXPECTED_TASKS = ["dab_725", "dab_587", "dab_657", "dab_517"]
EXPECTED_ARMS = ["native_pi", "reqlist_only", "full_rloop"]


def test_manifest_complete_and_specs_match():
    m = load_g4_manifest(MANIFEST)  # 產品模組驗證：schema／4 題／3 臂／12 格／規格檔路徑
    for key in ("v", "experiment", "status", "approval_required", "human_signoff",
                "tasks", "arms", "cells", "spec_dir", "specs"):
        assert key in m, f"manifest 缺欄 {key}"
    assert (m["v"], m["experiment"], m["status"]) == (1, "G4", "preregistered")
    assert m["approval_required"] is True and m["human_signoff"] is None
    assert m["tasks"] == EXPECTED_TASKS and m["arms"] == EXPECTED_ARMS
    assert m["cells"] == 12 == len(m["tasks"]) * len(m["arms"])
    assert m["spec_dir"] == "ops/reqloop/g4/specs"
    assert sorted(m["specs"]) == sorted(EXPECTED_TASKS)
    for task in EXPECTED_TASKS:
        entry = m["specs"][task]
        p = REPO / entry["file"]
        spec = json.loads(p.read_text(encoding="utf-8"))
        assert spec["task_id"] == task
        assert entry["spec_sha256"] == spec["spec_sha256"], f"{task}: manifest 與規格 hash 不符"
        assert RequirementSet.load(p).verify_self_hash()[0] is True, f"{task}: hash 不符（被改）"
        assert entry["n_items"] == len(spec["items"]) >= 1


def test_launch_fails_closed_without_human_signoff():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert m["human_signoff"] is None  # 前置：本票不產生簽核
    with pytest.raises(LaunchRefused):
        decide_g4_launch(m)
    # 正控制：簽核後門翻轉（仍 0 model calls；decide_g4_launch 是純決策、不發起任何發射）
    signed = {**m, "human_signoff": {"by": "human", "ts": "2026-11-13T00:00:00Z", "sha256": "0" * 64}}
    assert decide_g4_launch(signed) == "authorized"


def test_dry_run_zero_model_calls():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = g4_dry_run(m)
    assert out["status"] == "ready" and out["n_cells"] == 12
    assert {(c["task_id"], c["arm"]) for c in out["cells"]} == {(t, a) for t in m["tasks"] for a in m["arms"]}
    assert out["model_calls"] == 0
    # 票 P20261113_1100-2：cells 帶 n_checkable（每題 ≥1 條可確定性檢查）
    assert all(isinstance(c["n_checkable"], int) and c["n_checkable"] >= 1 for c in out["cells"])


def test_dry_run_fails_closed_on_shell_specs(tmp_path):
    """負控制（票 P20261113_1100-2）：凍結規格全空殼時 g4_dry_run 必須 fail-closed 拋 ValueError。

    三類缺陷各一個：全部條目清空 params／全部條目置未支援 verifier／全部條目交付物＝輸入檔。
    每類都重算 spec_sha256（同 RequirementSet 口徑），確保守衛在「可檢查性」而非「hash」上觸發。
    標準乾跑 RC0＋0 model calls 由 test_dry_run_zero_model_calls 與 CLI 驗收覆蓋。"""
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    spec_path = REPO / m["specs"]["dab_587"]["file"]
    base = json.loads(spec_path.read_text(encoding="utf-8"))

    def corrupt(mutate) -> dict:
        raw = copy.deepcopy(base)
        mutate(raw)
        body = {k: v for k, v in raw.items() if k != "spec_sha256"}
        raw["spec_sha256"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        p = tmp_path / "dab_587_shell.json"
        p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        m2 = copy.deepcopy(m)
        m2["specs"]["dab_587"] = {"file": str(p), "spec_sha256": raw["spec_sha256"],
                                 "n_items": len(raw["items"])}
        return m2

    with pytest.raises(ValueError, match="全空殼"):
        g4_dry_run(corrupt(lambda raw: [it.update({"params": {}}) for it in raw["items"]]))
    with pytest.raises(ValueError, match="unknown_verifier"):
        g4_dry_run(corrupt(lambda raw: [it.update({"verifier": "not_a_verifier"}) for it in raw["items"]]))
    with pytest.raises(ValueError, match="deliverable_is_input_file"):
        g4_dry_run(corrupt(lambda raw: [
            it.update({"deliverable": "20170413_000000_group_statistics.csv"}) for it in raw["items"]]))


def _copy_real_workspaces(tasks_dir: pathlib.Path) -> None:
    """把真實任務工作檔（規格已綁 goal／contract sha256）複製到 tasks_dir，作負控制基底。"""
    real = REPO / "ops" / "reqloop" / "g3_2" / "tasks"
    for t in EXPECTED_TASKS:
        dst = tasks_dir / t / "workspace"
        dst.mkdir(parents=True)
        for name in ("goal.md", "contract.md"):
            (dst / name).write_bytes((real / t / "workspace" / name).read_bytes())


def test_build_g4_execution_plan(tmp_path):
    """票 P20261113_1206-1：12 格執行排程矩陣（0 model calls）＋工作區缺檔 fail-closed。

    票 P20261113_1307-3：＋任務工作區檔案雜湊不符（goal.md 被改一個字元）fail-closed 負控制。"""
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    plan = build_g4_execution_plan(m)
    assert plan["status"] == "ready" and plan["n_cells"] == 12 == len(plan["cells"])
    assert plan["model_calls"] == 0
    assert {(c["task_id"], c["arm"]) for c in plan["cells"]} == \
        {(t, a) for t in EXPECTED_TASKS for a in EXPECTED_ARMS}
    for c in plan["cells"]:
        assert c["n_checkable"] >= 1
        ws = pathlib.Path(c["workspace"])
        assert ws.is_dir() and (ws / "goal.md").is_file() and (ws / "contract.md").is_file()
        assert (REPO / c["spec_file"]).is_file()

    # 負控制（缺檔）：任一題工作區缺 goal.md → ValueError（fail-closed，寧拒不空轉）。
    # 以真實工作檔為基底（規格已綁 hash），才能 isolating 到「缺檔」這一條路徑。
    tasks_dir = tmp_path / "tasks_missing"
    _copy_real_workspaces(tasks_dir)
    (tasks_dir / "dab_657" / "workspace" / "goal.md").unlink()
    with pytest.raises(ValueError, match="dab_657.*缺"):
        build_g4_execution_plan(m, tasks_dir=tasks_dir)

    # 負控制（票 P20261113_1307-3，雜湊不符）：工作區 goal.md 被改一個字元 →
    # ValueError 含「雜湊不符」（fail-closed：輸入檔漂移在離線組裝時即攔截，
    # 不必等到真發射 load_frozen_spec 才報錯）。
    tasks_dir2 = tmp_path / "tasks_tampered"
    _copy_real_workspaces(tasks_dir2)
    goal = tasks_dir2 / "dab_657" / "workspace" / "goal.md"
    orig = goal.read_text(encoding="utf-8")
    goal.write_text(("x" if orig[0] != "x" else "y") + orig[1:], encoding="utf-8")
    with pytest.raises(ValueError, match="dab_657.*雜湊不符"):
        build_g4_execution_plan(m, tasks_dir=tasks_dir2)
