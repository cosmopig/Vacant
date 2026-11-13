"""G4 預註冊實驗包：manifest 完整性 / 12 格 / 發射門 fail-closed / dry-run 0 model calls。

工單: P20261113_0708-2-g4-preregistration（2026-11-13 人類定案第 4 條：G4 預註冊、發射前須人類點頭）。
P20261113_0948-2：LaunchRefused／decide_g4_launch／g4_dry_run 已封裝為產品模組
vacant_network.reqloop.g4gate；本測試改由產品模組引入（不再內嵌參考實現）。
不變量：本模組與測試不發起任何真模型呼叫（0 model calls）。
"""
from __future__ import annotations

import json
import pathlib

import pytest

from vacant_network.reqloop.g4gate import (
    LaunchRefused,
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
