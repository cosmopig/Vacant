"""G4 預註冊實驗包：manifest 完整性 / 12 格 / 發射門 fail-closed / dry-run 0 model calls。

工單: P20261113_0708-2-g4-preregistration（2026-11-13 人類定案第 4 條：G4 預註冊、發射前須人類點頭）。
不變量：本模組與測試不發起任何真模型呼叫（0 model calls）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = REPO / "ops" / "reqloop" / "g4" / "manifest.json"
EXPECTED_TASKS = ["dab_725", "dab_587", "dab_657", "dab_517"]
EXPECTED_ARMS = ["native_pi", "reqlist_only", "full_rloop"]


def _self_sha256(spec: dict) -> str:
    """規格自 hash：整份規格（除 spec_sha256 欄）canonical JSON 的 sha256（freeze_specs._canon 同口徑）。"""
    body = {k: v for k, v in spec.items() if k != "spec_sha256"}
    canon = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class LaunchRefused(RuntimeError):
    """拒絕真發射（fail-closed）：尚無人類點頭。"""


def decide_launch(manifest: dict) -> str:
    """參考發射門：純決策、0 model calls。approval_required 且 signoff 為 null→拒絕；否則 authorized（真發射不在本模組範圍）。"""
    if manifest.get("approval_required") is True and manifest.get("human_signoff") is None:
        raise LaunchRefused("human_signoff is null: real launch refused (fail-closed)")
    return "authorized"


def dry_run(manifest: dict) -> dict:
    """發射前 dry-run：確認環境（路徑）、凍結規格（12 格全可載入＋hash 與 manifest 吻合）、前置檢查；0 model calls。"""
    spec_dir = REPO / manifest["spec_dir"]
    cells = []
    for task in manifest["tasks"]:
        for arm in manifest["arms"]:
            p = spec_dir / f"{task}.json"
            spec = json.loads(p.read_text(encoding="utf-8"))
            expect = manifest["specs"][task]["spec_sha256"]
            if spec.get("spec_sha256") != expect or _self_sha256(spec) != expect:
                raise ValueError(f"{task}: frozen spec hash mismatch (fail-closed)")
            cells.append({"task_id": task, "arm": arm, "n_items": len(spec["items"])})
    return {"status": "ready", "n_cells": len(cells), "cells": cells, "model_calls": 0}


def test_manifest_complete_and_specs_match():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
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
        assert p.exists(), f"規格檔不存在 {p}"
        spec = json.loads(p.read_text(encoding="utf-8"))
        assert spec["task_id"] == task
        assert entry["spec_sha256"] == spec["spec_sha256"] == _self_sha256(spec), f"{task}: hash 不符（被改）"
        assert entry["n_items"] == len(spec["items"]) >= 1


def test_launch_fails_closed_without_human_signoff():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert m["human_signoff"] is None  # 前置：本票不產生簽核
    with pytest.raises(LaunchRefused):
        decide_launch(m)
    # 正控制：簽核後門翻轉（仍 0 model calls；decide_launch 是純決策、不發起任何發射）
    signed = {**m, "human_signoff": {"by": "human", "ts": "2026-11-13T00:00:00Z", "sha256": "0" * 64}}
    assert decide_launch(signed) == "authorized"


def test_dry_run_zero_model_calls():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = dry_run(m)
    assert out["status"] == "ready" and out["n_cells"] == 12
    assert {(c["task_id"], c["arm"]) for c in out["cells"]} == {(t, a) for t in m["tasks"] for a in m["arms"]}
    assert out["model_calls"] == 0
