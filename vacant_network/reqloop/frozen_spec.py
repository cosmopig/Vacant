"""
vacant_network.reqloop.frozen_spec
D4 凍結規格的「可檢查性」關卡與寫入器（argon 審查 20261113_1042）。

問題（親自重現）：ops/reqloop/g4/specs/ 4 份 G4 凍結規格共 25 條，全部 ``params: {}``
（來源 g26 重播報告 params 0/76 未存）→ 每條都過不了擷取時同一把尺
``extract._param_problem``；拿明顯錯的答案去跑 ``checks.run_requirement_checks``
→ 25/25 UNKNOWN、0 FAIL。G4 full_rloop 用這批規格永遠拿不到 FAIL，R-loop
不會觸發修復——正是 11-13 定案要修的阻塞。原 g4gate dry-run 只核 hash，仍印
「12 cells ready」。

本模組：
- ``item_problem(item, user_text, input_files)``：單一條目能否被確定性檢查。
  順序與 ``extract.build_requirement_set`` 逐條相同（verifier 白名單 → params →
  輸入檔不得當交付物 → 交付物須為原文點名 → tag_format 的 tag 須在原文 →
  unverified 旗標）；None＝可檢查。只讀、0 model calls。
- ``spec_checkability(req_set, task_dir)``：整份規格的可檢查條數與逐條原因。
- ``freeze_requirement_set(req_set, task_dir, out_path, source=...)``：
  把**擷取當下完整的** RequirementSet（含 params）只留可檢查條目、綁 goal/contract
  sha256＋spec_sha256（與 ``RequirementSet.compute_spec_sha256`` 同口徑）落盤；
  0 條可檢查→ValueError（fail-closed，不寫空殼）。

不改 extract.py／checks.py（只 import 其既有函式；凍結/受控解凍界線不動）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
from typing import Any, Iterable

from . import checks as _checks
from . import extract as _extract
from .requirements import RequirementItem, RequirementSet

SPEC_SCHEMA = "vacant.reqloop.frozen_spec/2"


def _canon(d: dict[str, Any]) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def task_context(task_dir: str | pathlib.Path) -> tuple[str, list[str], str, str]:
    """task_dir＝含 workspace/ 的任務目錄。回 (user_text, input_files, goal_sha256, contract_sha256)。

    user_text 與 G3 發射路徑同口徑（goal.md＋公開 contract.md）；input_files＝workspace/data/ 檔名。
    """
    from .g3 import compose_extract_user_text  # 延遲 import：g3 依賴本套件多個模組

    ws = pathlib.Path(task_dir) / "workspace"
    goal_p, contract_p = ws / "goal.md", ws / "contract.md"
    goal = goal_p.read_text(encoding="utf-8")
    contract = contract_p.read_text(encoding="utf-8") if contract_p.is_file() else None
    data = ws / "data"
    inputs = sorted(p.name for p in data.iterdir() if p.is_file()) if data.is_dir() else []
    return (compose_extract_user_text(goal, contract), inputs,
            hashlib.sha256(goal_p.read_bytes()).hexdigest(),
            hashlib.sha256(contract_p.read_bytes()).hexdigest() if contract_p.is_file() else "")


def _is_input_file(deliverable: str, input_files: Iterable[str]) -> bool:
    names = {str(x).strip() for x in input_files if str(x).strip()}
    names |= {n.rsplit("/", 1)[-1] for n in names}
    d = str(_extract._strip_workspace_prefix(str(deliverable))).strip()
    return d in names or d.rsplit("/", 1)[-1] in names


def item_problem(item: RequirementItem, user_text: str, input_files: Iterable[str]) -> str | None:
    """None＝此條目可被確定性檢查（PASS/FAIL 可重算）；否則回機器可讀原因。"""
    v = str(item.verifier or "").strip()
    if v not in _checks.SUPPORTED_VERIFIERS:
        return f"unknown_verifier:{v or 'missing'}"
    p = _extract._param_problem(v, item.params)
    if p is not None:
        return p
    if _is_input_file(item.deliverable, input_files):
        return "deliverable_is_input_file"
    p = _extract._deliverable_problem(item.deliverable, user_text)
    if p is not None:
        return p
    if v == "tag_format":
        tag = str(item.params.get("tag", "")).strip()
        if tag and not re.search(r"@\s*" + re.escape(tag) + r"\b", user_text):
            return f"tag_not_in_request:{tag[:40]}"
    if item.unverified:
        return "item_marked_unverified"
    return None


def spec_checkability(req_set: RequirementSet, task_dir: str | pathlib.Path) -> dict[str, Any]:
    """{"n_items", "n_checkable", "problems": {item_id: reason}}；0 model calls。"""
    user_text, inputs, _, _ = task_context(task_dir)
    problems: dict[str, str] = {}
    for it in req_set.items:
        why = item_problem(it, user_text, inputs)
        if why is not None:
            problems[it.id] = why
    return {"n_items": len(req_set.items), "n_checkable": len(req_set.items) - len(problems),
            "problems": problems}


def freeze_requirement_set(req_set: RequirementSet, task_dir: str | pathlib.Path,
                           out_path: str | pathlib.Path | None = None, *,
                           source: str = "") -> dict[str, Any]:
    """擷取當下的完整需求組→只留可檢查條目的凍結規格（含 params）；out_path 給定才落盤。

    0 條可檢查→ValueError（fail-closed：不寫一份跑起來全是 UNKNOWN 的空殼）。
    被剔除的條目與原因留在 ``dropped``（紀錄用，不參與檢查）。
    """
    user_text, inputs, goal_sha, contract_sha = task_context(task_dir)
    kept, dropped = [], []
    for it in req_set.items:
        why = item_problem(it, user_text, inputs)
        if why is None:
            kept.append(it.to_dict())
        else:
            dropped.append({"id": it.id, "verifier": it.verifier, "reason": why})
    if not kept:
        raise ValueError(f"{req_set.task_id}: 0/{len(req_set.items)} 條可確定性檢查，拒絕凍結"
                         f"（{sorted({d['reason'] for d in dropped})}）")
    spec: dict[str, Any] = {"schema": SPEC_SCHEMA, "task_id": req_set.task_id, "source": source,
                            "goal_sha256": goal_sha, "contract_sha256": contract_sha,
                            "items": kept, "dropped": dropped}
    spec["spec_sha256"] = hashlib.sha256(_canon(spec).encode("utf-8")).hexdigest()
    if out_path is not None:
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return spec
