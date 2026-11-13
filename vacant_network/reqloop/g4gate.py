"""
vacant_network.reqloop.g4gate
G4 預註冊離線檢驗與發射門控制（票 P20261113_0948-2；11-13 人類定案第 4 條：發射前須人類點頭）。
只做離線機械複核與簽核門控，**不發起任何真模型呼叫（0 model calls）、不發射**：
- `load_g4_manifest(path)`：讀取並驗證 manifest（schema、4 題、3 臂、12 格、規格檔路徑）；
- `g4_dry_run(manifest)`：4 份凍結規格存在、`spec_sha256` 自校驗吻合（複用 `RequirementSet.verify_self_hash`）；
- `decide_g4_launch(manifest)`：`approval_required == True` 且 `human_signoff is None` → 拋 `LaunchRefused`（fail-closed）；
- CLI：`--dry-run`（RC 0）／`--fire`（未簽核 RC 2；0 model calls）。

入口（單一）：
  python3 -m vacant_network.reqloop.g4gate --dry-run   # G4 DRY-RUN: 12 cells ready (0 model calls)
  python3 -m vacant_network.reqloop.g4gate --fire      # 未簽核 → G4 FIRE REFUSED，RC 2
"""
from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any, Sequence

from .frozen_spec import spec_checkability
from .requirements import RequirementSet

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO / "ops" / "reqloop" / "g4" / "manifest.json"
DEFAULT_TASK_ROOT = "ops/reqloop/g3_2/tasks"  # G4 4 題的凍結 workspace（manifest 可用 task_root 覆寫）
EXPECTED_TASKS = ("dab_725", "dab_587", "dab_657", "dab_517")
EXPECTED_ARMS = ("native_pi", "reqlist_only", "full_rloop")
_EXPECTED_KEYS = ("v", "experiment", "status", "approval_required", "human_signoff",
                  "tasks", "arms", "cells", "spec_dir", "specs")


class LaunchRefused(RuntimeError):
    """拒絕真發射（fail-closed）：尚無人類簽核。"""


def load_g4_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    """讀取並驗證 G4 manifest：schema、4 題、3 臂、12 格、每題規格檔路徑存在。"""
    m = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    for key in _EXPECTED_KEYS:
        if key not in m:
            raise ValueError(f"manifest 缺欄 {key}")
    if (m["v"], m["experiment"], m["status"]) != (1, "G4", "preregistered"):
        raise ValueError("manifest (v, experiment, status) != (1, 'G4', 'preregistered')")
    if list(m["tasks"]) != list(EXPECTED_TASKS) or list(m["arms"]) != list(EXPECTED_ARMS):
        raise ValueError("manifest tasks/arms 非預註冊 4 題 × 3 臂")
    if m["cells"] != 12 or m["cells"] != len(m["tasks"]) * len(m["arms"]):
        raise ValueError("manifest cells != 12（4 題 × 3 臂）")
    for task in m["tasks"]:
        entry = m["specs"].get(task) or {}
        if not entry.get("file") or not entry.get("spec_sha256"):
            raise ValueError(f"specs[{task}] 缺 file/spec_sha256")
        if not (REPO / entry["file"]).is_file():
            raise ValueError(f"規格檔不存在 {entry['file']}")
    return m


def g4_dry_run(manifest: dict[str, Any]) -> dict[str, Any]:
    """發射前 dry-run：4 份凍結規格存在＋`spec_sha256` 自校驗吻合（fail-closed）；0 model calls。"""
    cells = []
    for task in manifest["tasks"]:
        entry = manifest["specs"][task]
        spec_set = RequirementSet.load(REPO / entry["file"])
        ok, why = spec_set.verify_self_hash()
        if not ok:
            raise ValueError(f"{task}: frozen spec 自校驗失敗（{why}；fail-closed）")
        if spec_set.spec_sha256 != entry["spec_sha256"]:
            raise ValueError(f"{task}: manifest 與規格 spec_sha256 不符（fail-closed）")
        # argon 審查 20261113_1042：hash 對不代表能檢查。凍結規格每條都必須過擷取時
        # 同一把尺（frozen_spec.item_problem）；任一條不可檢查＝規格是空殼或被降級，
        # full_rloop 拿不到 FAIL、R-loop 不會觸發修復 → 拒發（fail-closed）。
        task_dir = REPO / str(manifest.get("task_root", DEFAULT_TASK_ROOT)) / task
        chk = spec_checkability(spec_set, task_dir)
        if chk["n_items"] == 0 or chk["n_checkable"] != chk["n_items"]:
            reasons = sorted(set(chk["problems"].values()))
            raise ValueError(
                f"{task}: 凍結規格只有 {chk['n_checkable']}/{chk['n_items']} 條可確定性檢查"
                f"（{reasons[:4]}）——不可檢查的規格不得發射（fail-closed）")
        for arm in manifest["arms"]:
            cells.append({"task_id": task, "arm": arm, "n_items": len(spec_set.items),
                          "n_checkable": chk["n_checkable"]})
    return {"status": "ready", "n_cells": len(cells), "cells": cells, "model_calls": 0}


def decide_g4_launch(manifest: dict[str, Any]) -> str:
    """發射門：純決策、0 model calls。`approval_required` 且 `human_signoff is None`→拒絕。"""
    if manifest.get("approval_required") is True and manifest.get("human_signoff") is None:
        raise LaunchRefused("human_signoff is null: real launch refused (fail-closed)")
    return "authorized"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vacant_network.reqloop.g4gate",
                                 description="G4 預註冊離線檢驗與發射門（0 model calls）")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="驗 12 格＋4 規格自 hash（預設）；RC 0")
    mode.add_argument("--fire", action="store_true",
                      help="真發射門；未簽核→RC 2（fail-closed、0 model calls）")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    a = ap.parse_args(list(argv) if argv is not None else None)

    try:
        manifest = load_g4_manifest(a.manifest)
        out = g4_dry_run(manifest)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"G4 DRY-RUN FAIL: {e}")
        return 1

    if a.fire:
        try:
            decide_g4_launch(manifest)
        except LaunchRefused:
            print("G4 FIRE REFUSED: human_signoff is null")
            return 2
        print("G4 FIRE AUTHORIZED（已簽核；發射管線另一步授權、不在本模組）")
        return 0
    print(f"G4 DRY-RUN: {out['n_cells']} cells ready (0 model calls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
