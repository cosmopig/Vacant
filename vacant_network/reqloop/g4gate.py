"""
vacant_network.reqloop.g4gate
G4 預註冊離線檢驗與發射門控制（票 P20261113_0948-2；11-13 人類定案第 4 條：發射前須人類點頭）。
只做離線機械複核與簽核門控，**不發起任何真模型呼叫（0 model calls）、不發射**：
- `load_g4_manifest(path)`：讀取並驗證 manifest（schema、4 題、3 臂、12 格、規格檔路徑）；
- `g4_dry_run(manifest)`：4 份凍結規格存在、`spec_sha256` 自校驗吻合（複用 `RequirementSet.verify_self_hash`）、
  可檢查性守衛（票 P20261113_1100-2：每題規格 ≥1 條可確定性檢查條目，0 條＝空殼→ValueError fail-closed）；
- `decide_g4_launch(manifest)`：`approval_required == True` 且 `human_signoff is None` → 拋 `LaunchRefused`（fail-closed）；
- CLI：`--dry-run`（RC 0）／`--fire`（未簽核 RC 2；0 model calls）。

入口（單一）：
  python3 -m vacant_network.reqloop.g4gate --dry-run   # G4 DRY-RUN: 12 cells ready (0 model calls)
  python3 -m vacant_network.reqloop.g4gate --fire      # 未簽核 → G4 FIRE REFUSED，RC 2
  python3 -m vacant_network.reqloop.g4gate --plan      # 12 格執行排程矩陣 JSON（0 model calls）
"""
from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any, Sequence

from .checks import SUPPORTED_VERIFIERS
from .extract import _param_problem
from .requirements import RequirementItem, RequirementSet
from .specs import SpecIntegrityError, load_frozen_specs

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO / "ops" / "reqloop" / "g4" / "manifest.json"
G26_REPLAY = REPO / "ops" / "audits" / "g26_claim_replay.json"
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


def _task_input_files(task_id: str, items: Sequence[RequirementItem]) -> set[str]:
    """該任務的輸入檔（檔名正規化）：g26 replay（D2 可信交付物同源）∪ 規格 params 引用的資料來源。"""
    names: set[str] = set()
    try:
        claims = json.loads(G26_REPLAY.read_text(encoding="utf-8"))["claims"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(f"{task_id}: g26 replay 不可讀、無法判定輸入檔（fail-closed）") from e
    for c in claims:
        if c.get("task_id") == task_id:
            names.update(pathlib.Path(str(f)).name for f in c.get("input_files", ()))
    for it in items:
        p = it.params if isinstance(it.params, dict) else {}
        names.update(
            pathlib.Path(str(p[k])).name for k in ("data_file", "input_csv", "input_json")
            if isinstance(p.get(k), str) and p.get(k))
    return names


def _item_checkable(item: RequirementItem, input_files: set[str]) -> str | None:
    """單條需求非「確定性可檢查」的機器可讀原因；None＝可檢查（checks.run_requirement_checks 非永久 UNKNOWN）。"""
    if item.unverified:
        return "unverified_flag"
    if item.verifier not in SUPPORTED_VERIFIERS:
        return f"unknown_verifier:{item.verifier or 'missing'}"
    problem = _param_problem(item.verifier, item.params)
    if problem is not None:
        return problem
    if pathlib.Path(item.deliverable).name in input_files:
        return f"deliverable_is_input_file:{item.deliverable}"
    return None


def g4_dry_run(manifest: dict[str, Any]) -> dict[str, Any]:
    """發射前 dry-run：4 份凍結規格存在＋`spec_sha256` 自校驗吻合＋可檢查性守衛（fail-closed）；0 model calls。

    守衛（P20261113_1100-2）：每題規格須 ≥1 條可確定性檢查條目（verifier 在白名單＋無參數缺陷＋
    交付物非輸入檔）；0 條＝空殼規格→ValueError，拒絕宣稱 ready。個別條目缺參照 UNKNOWN 計數、
    不單獨拒發（凍結規格含永久 UNKNOWN 條目仍可满足——r1565/r1566 正負控制已證）。"""
    cells = []
    for task in manifest["tasks"]:
        entry = manifest["specs"][task]
        spec_set = RequirementSet.load(REPO / entry["file"])
        ok, why = spec_set.verify_self_hash()
        if not ok:
            raise ValueError(f"{task}: frozen spec 自校驗失敗（{why}；fail-closed）")
        if spec_set.spec_sha256 != entry["spec_sha256"]:
            raise ValueError(f"{task}: manifest 與規格 spec_sha256 不符（fail-closed）")
        input_files = _task_input_files(task, spec_set.items)
        reasons = {it.id: _item_checkable(it, input_files) for it in spec_set.items}
        n_checkable = sum(1 for r in reasons.values() if r is None)
        if n_checkable == 0:
            detail = "; ".join(f"{i}:{r}" for i, r in sorted(reasons.items()))
            raise ValueError(f"{task}: 凍結規格全空殼（0/{len(spec_set.items)} 可檢查；fail-closed）：{detail}")
        for arm in manifest["arms"]:
            cells.append({"task_id": task, "arm": arm, "n_items": len(spec_set.items),
                          "n_checkable": n_checkable})
    return {"status": "ready", "n_cells": len(cells), "cells": cells, "model_calls": 0}


def build_g4_execution_plan(manifest: dict[str, Any] | None = None,
                            tasks_dir: pathlib.Path | None = None) -> dict[str, Any]:
    """G4 執行排程矩陣（4 題 × 3 臂＝12 格）：離線機械組裝與前置資源驗證（0 model calls）。

    在 `g4_dry_run` 通過（4 規格存在＋hash 自校驗＋可檢查性守衛）的基礎上，逐題驗證任務工作區
    （`tasks_dir/<task>/workspace/goal.md`＋`contract.md`，預設 `ops/reqloop/g3_2/tasks`）齊備，
    並核對其 sha256 與凍結規格綁定的 `goal_sha256`／`contract_sha256` 吻合
    （票 P20261113_1307-3：輸入檔漂移在離線組裝時即攔截），
    組裝每格 task_id/arm/workspace/spec_file/n_checkable；任一題缺工作區檔案或雜湊不符→ValueError fail-closed。"""
    if manifest is None:
        manifest = load_g4_manifest(DEFAULT_MANIFEST)
    # D4（11-13 定案 §2）：統一 spec_sha256 核驗口——逐檔對 manifest 綁定值密碼學校驗；
    # 任何不符／缺檔即 SpecIntegrityError fail-closed（不返回部分結果），先於 g4_dry_run。
    # 傳入 dict 可用 `_manifest_path` 點名其來源檔（負控制用）；無則以 DEFAULT_MANIFEST 為準。
    load_frozen_specs(manifest.get("_manifest_path") or DEFAULT_MANIFEST)
    if tasks_dir is None:
        tasks_dir = REPO / "ops" / "reqloop" / "g3_2" / "tasks"
    dry = g4_dry_run(manifest)
    n_checkable = {c["task_id"]: c["n_checkable"] for c in dry["cells"]}
    cells = []
    for task in manifest["tasks"]:
        ws = pathlib.Path(tasks_dir) / task / "workspace"
        missing = [n for n in ("goal.md", "contract.md") if not (ws / n).is_file()]
        if missing:
            raise ValueError(f"{task}: 任務工作區缺 {', '.join(missing)}（{ws}；fail-closed）")
        spec_file = manifest["specs"][task]["file"]
        spec_set = RequirementSet.load(REPO / spec_file)
        ok_hash, why_hash = spec_set.verify_task_hash(ws)
        if not ok_hash:
            raise ValueError(f"{task}: 任務工作區檔案雜湊不符（{why_hash}；fail-closed）")
        for arm in manifest["arms"]:
            cells.append({"task_id": task, "arm": arm, "workspace": str(ws),
                          "spec_file": spec_file, "n_checkable": n_checkable[task]})
    return {"status": "ready", "cells": cells, "n_cells": len(cells), "model_calls": 0}


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
    mode.add_argument("--plan", action="store_true",
                      help="組裝 12 格執行排程矩陣並 JSON 印出（0 model calls）；RC 0")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    a = ap.parse_args(list(argv) if argv is not None else None)

    try:
        manifest = load_g4_manifest(a.manifest)
        out = g4_dry_run(manifest)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"G4 DRY-RUN FAIL: {e}")
        return 1

    if a.plan:
        try:
            plan = build_g4_execution_plan(manifest)
        except (SpecIntegrityError, OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"G4 PLAN FAIL: {e}")
            return 1
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

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
