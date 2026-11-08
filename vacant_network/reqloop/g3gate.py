"""
vacant_network.reqloop.g3gate
G3「未見任務完整對照」（epic vq-1zf）的**發射前置門**——離線、零模型呼叫、不發射。

本模組只做發射前置的**可重算驗證**（審查指示 #5「G3 準備工作」；11-06 指示 #5 六要素）：
1. 選題＝未見任務：bank 順序 − 已見集合，前 4 題；用代碼重算，與預註冊清單逐題核
   （vq-1zf 預註冊：dab_129/144/176/216；已見 9 dab_ 來源＝effects_20261105 50 格聯集）。
2. 任務輸入凍結副本在 repo 內（ops/reqloop/g3_gate/tasks/），verify_frozen 逐檔核 sha256
   ＋選題一致性——篡改/缺檔即 fail（同 G2Manifest.verify_frozen 的門）。
3. 預算門：≤12 格（3 臂×4 題）、300s/輪、日 ≤2,000,000 tok 撞額停不重試（fail-closed）、
   模型呼叫唯一入口＝glm CLI、無硬 token 上限→成本從 raw usage 讀、缺值＝UNKNOWN 絕不填 0。
4. 核准門 fail-closed：人類明確核准文件（approved=true、epic=vq-1zf、by=核准者）；
   無核准信號→RC 2、0 模型呼叫。核准前禁止任何發射。

紅線：不讀 /srv/eval hidden 與 scorer.py 內容、不按隱藏分數反推規則；hidden_after 一律
UNKNOWN；cost_usd=0 不報 0 成本。發射（三臂真跑）是核准後另一步授權，不在本模組範圍——
本輪只交付「前置門可跑」。

入口（單一）：
  python -m vacant_network.reqloop.g3gate --plan                      # 驗前置，RC 0，NOT FIRED
  python -m vacant_network.reqloop.g3gate --fire [--approval <file>]  # 無核准→RC 2（0 呼叫）
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
from typing import Any, Sequence

PLAN_SCHEMA = "vacant.reqloop.g3gate.plan/1"
APPROVAL_SCHEMA = "vacant.reqloop.g3gate.approval/1"
MAX_CELLS = 12
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "ops" / "reqloop" / "g3_gate" / "manifest.json"

# 發射前置的最低預算形（fail-closed 底線；manifest 可加嚴、不可放寬）
DEFAULT_BUDGET: dict[str, Any] = {
    "max_cells": MAX_CELLS,
    "timeout_s_per_round": 300,
    "daily_token_cap": 2_000_000,
    "quota_fail_closed": True,
    "model_entry": "glm",
    "hard_token_cap": False,
    "cost_missing": "UNKNOWN",
}

# 退出碼（如實區分）
RC_OK = 0
RC_NOT_APPROVED = 2          # 無核准信號/核准不合格：0 模型呼叫
RC_APPROVED_NOT_WIRED = 3    # 已核准、但發射管線尚未接線（核准後另一步）

ARM_ORDER = ("native_pi", "reqlist_only", "full_rloop")


def sha256_file(p: str | pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def unseen_selection(bank_order: Sequence[str], seen: set[str], n: int) -> list[str]:
    """bank 順序中未見的前 n 題。未見不足→raise（fail-closed，不補位不猜題）。"""
    if n < 1:
        raise ValueError("n 必須 ≥ 1")
    unseen = [t for t in bank_order if t not in seen]
    if len(unseen) < n:
        raise ValueError(
            f"bank 未見題不足：需要 {n}，只有 {len(unseen)}（seen={sorted(seen)}）")
    return list(unseen[:n])


@dataclasses.dataclass(frozen=True)
class G3Plan:
    """G3 發射前置凍結清單：3 臂 × 4 未見任務、輸入檔 sha256、預算、核准要求。"""
    schema: str
    frozen_at: str
    ticket: str
    purpose: str
    arms: tuple[str, ...]
    arm_defs: dict[str, str]
    tasks: tuple[dict[str, Any], ...]     # {"task_id", "files": {rel: sha256}}
    seen_set: tuple[str, ...]
    seen_set_source: str
    bank: dict[str, Any]
    budget: dict[str, Any]
    scoring: dict[str, Any]
    leak_guard: str
    approval: dict[str, Any]
    raw: dict[str, Any]
    manifest_path: str | None = None      # load() 設

    @classmethod
    def load(cls, path: str | pathlib.Path) -> G3Plan:
        p = pathlib.Path(path)
        raw = json.loads(p.read_text(encoding="utf-8"))
        if raw.get("schema") != PLAN_SCHEMA:
            raise ValueError(f"plan schema 不符：{raw.get('schema')!r} ≠ {PLAN_SCHEMA!r}")
        tasks = list(raw.get("tasks", []))
        if not tasks:
            raise ValueError("plan 沒有 tasks")
        for t in tasks:
            if not str(t.get("task_id", "")).strip():
                raise ValueError(f"task 缺 task_id：{t!r}")
            files = t.get("files") or {}
            if not files:
                raise ValueError(f"task {t.get('task_id')!r} 沒有凍結輸入檔")
            for rel, h in files.items():
                if not (isinstance(h, str) and len(h) == 64
                        and all(c in "0123456789abcdef" for c in h)):
                    raise ValueError(f"task {t['task_id']!r} 檔 {rel!r} sha256 非法")
        bank = raw.get("bank") or {}
        ordering = bank.get("ordering")
        if not (isinstance(ordering, list) and ordering):
            raise ValueError("bank.ordering 缺失（選題不可重算＝不可驗）")
        if raw.get("seen_set") is None:
            raise ValueError("seen_set 缺失（已見集合是選題前提）")
        if not raw.get("arms"):
            raise ValueError("arms 缺失")
        if not isinstance(raw.get("budget"), dict):
            raise ValueError("budget 缺失")
        if not isinstance(raw.get("approval"), dict):
            raise ValueError("approval 缺失（核准要求必須寫在案）")
        return cls(
            schema=raw["schema"],
            frozen_at=str(raw.get("frozen_at", "")),
            ticket=str(raw.get("ticket", "")),
            purpose=str(raw.get("purpose", "")),
            arms=tuple(raw["arms"]),
            arm_defs=dict(raw.get("arm_defs", {})),
            tasks=tuple(tasks),
            seen_set=tuple(raw["seen_set"]),
            seen_set_source=str(raw.get("seen_set_source", "")),
            bank=dict(bank),
            budget=dict(raw["budget"]),
            scoring=dict(raw.get("scoring", {})),
            leak_guard=str(raw.get("leak_guard", "")),
            approval=dict(raw["approval"]),
            raw=raw,
            manifest_path=str(p),
        )

    def verify_frozen(self, base: str | pathlib.Path) -> None:
        """凍結輸入副本必須真的在 base/tasks/ 下、逐檔 sha256 對得上、選題與規則一致。"""
        base = pathlib.Path(base)
        for t in self.tasks:
            for rel, h in t["files"].items():
                f = base / "tasks" / t["task_id"] / rel
                if not f.is_file():
                    raise FileNotFoundError(f"凍結任務輸入缺失：{f}")
                if sha256_file(f) != h:
                    raise ValueError(f"凍結任務輸入 hash 不符：{f}")
        expected = unseen_selection(
            self.bank["ordering"], set(self.seen_set), len(self.tasks))
        actual = [t["task_id"] for t in self.tasks]
        if expected != actual:
            raise ValueError(f"選題與預註冊規則不一致：{actual} ≠ {expected}")


def plan_cells(plan: G3Plan) -> list[tuple[str, str]]:
    """12 格＝4 任務 × 3 臂（順序固定：先任務、後臂，兩臂同輸入同預算）。"""
    return [(t["task_id"], arm) for t in plan.tasks for arm in plan.arms]


def check_budget(plan: G3Plan) -> None:
    """預算門（fail-closed）：任何一項缺失/放寬即拒。"""
    b = plan.budget
    cells = len(plan_cells(plan))
    try:
        max_cells = int(b.get("max_cells", MAX_CELLS))
    except (TypeError, ValueError):
        raise ValueError("budget.max_cells 非法")
    if max_cells < 1 or cells > max_cells:
        raise ValueError(f"格數 {cells} 超預算上限 {max_cells}")
    try:
        tpr = int(b.get("timeout_s_per_round"))
    except (TypeError, ValueError):
        raise ValueError("budget.timeout_s_per_round 缺失/非法（每輪必須有牆時上限）")
    if tpr <= 0:
        raise ValueError("budget.timeout_s_per_round 必須 > 0")
    cap = b.get("daily_token_cap")
    if cap is None:
        raise ValueError("budget.daily_token_cap 缺失（日額度上限必須寫在案）")
    try:
        if int(cap) <= 0:
            raise ValueError("budget.daily_token_cap 必須 > 0")
    except TypeError:
        raise ValueError("budget.daily_token_cap 非法")
    if b.get("quota_fail_closed") is not True:
        raise ValueError("撞額度必須停、不得重試（quota_fail_closed 必須為 true）")
    if b.get("model_entry") != "glm":
        raise ValueError("模型呼叫唯一入口＝glm CLI（model_entry 必須為 'glm'）")
    if b.get("hard_token_cap") is not False:
        raise ValueError("無硬 token 上限能力：hard_token_cap 必須如實為 false")
    if b.get("cost_missing") != "UNKNOWN":
        raise ValueError("成本缺值必須 UNKNOWN（絕不填 0）")


def approval_gate(doc: Any) -> tuple[bool, str]:
    """核准門（fail-closed）：任何異常＝未核准。核准者必須是人類可追溯的身份。"""
    if not isinstance(doc, dict):
        return False, f"核准文件不是 JSON 物件（got {type(doc).__name__}）"
    if doc.get("schema") != APPROVAL_SCHEMA:
        return False, f"核准 schema 不符（要 {APPROVAL_SCHEMA!r}）"
    if doc.get("approved") is not True:
        return False, "approved 不是 true"
    if doc.get("epic") != "vq-1zf":
        return False, f"epic 不符（要 vq-1zf，got {doc.get('epic')!r}）"
    by = str(doc.get("by", "")).strip()
    if not by:
        return False, "缺核准者（by 必須非空）"
    return True, f"approved（by={by}）"


def plan_report(plan: G3Plan) -> dict[str, Any]:
    return {
        "schema": PLAN_SCHEMA,
        "ticket": plan.ticket,
        "arms": list(plan.arms),
        "arm_defs": dict(plan.arm_defs),
        "tasks": [t["task_id"] for t in plan.tasks],
        "seen_set": list(plan.seen_set),
        "cells": [[t, a] for t, a in plan_cells(plan)],
        "budget": dict(plan.budget),
        "scoring": dict(plan.scoring),
        "approval": dict(plan.approval),
        "state": "NOT FIRED（核准前 0 模型呼叫）",
    }


# ── 凍結工具（建 manifest 用；建一次、之後只驗）───────────────────────

def build_manifest(bank_dir: str | pathlib.Path, seen_set: Sequence[str], *,
                   n_tasks: int, ticket: str, purpose: str,
                   arm_defs: dict[str, str], budget: dict[str, Any],
                   scoring: dict[str, Any], leak_guard: str,
                   approval: dict[str, Any], seen_set_source: str,
                   frozen_at: str, bank_name: str = "dabench") -> dict[str, Any]:
    """從 bank 實目錄算選題＋逐檔 sha256，產出 plan dict（未寫盤）。"""
    bank_dir = pathlib.Path(bank_dir)
    if not bank_dir.is_dir():
        raise FileNotFoundError(f"bank 目錄不存在：{bank_dir}")
    ordering = sorted(p.name for p in bank_dir.iterdir() if p.is_dir())
    tasks = []
    for tid in unseen_selection(ordering, set(seen_set), n_tasks):
        tdir = bank_dir / tid
        files: dict[str, str] = {}
        for f in sorted(tdir.rglob("*")):
            if f.is_file():
                files[str(f.relative_to(tdir))] = sha256_file(f)
        tasks.append({"task_id": tid, "files": files})
    return {
        "schema": PLAN_SCHEMA,
        "frozen_at": frozen_at,
        "ticket": ticket,
        "purpose": purpose,
        "arms": list(ARM_ORDER),
        "arm_defs": {a: arm_defs[a] for a in ARM_ORDER},
        "tasks": tasks,
        "seen_set": list(seen_set),
        "seen_set_source": seen_set_source,
        "bank": {"name": bank_name, "dir": str(bank_dir),
                 "n_total": len(ordering), "ordering": ordering},
        "budget": dict(budget),
        "scoring": dict(scoring),
        "leak_guard": leak_guard,
        "approval": dict(approval),
    }


# ── CLI ──────────────────────────────────────────────────────────────

def _print_plan_lines(plan: G3Plan, *, verified: bool) -> None:
    print(f"G3GATE plan: {plan.ticket}（{plan.schema}）")
    for t in plan.tasks:
        print(f"  task {t['task_id']}: {len(t['files'])} 個凍結輸入檔")
    print(f"  arms({len(plan.arms)}): {' '.join(plan.arms)}")
    print(f"  cells: {len(plan_cells(plan))}（{len(plan.tasks)} 題 × {len(plan.arms)} 臂；"
          f"上限 {plan.budget.get('max_cells')}）")
    print(f"  budget: {plan.budget.get('timeout_s_per_round')}s/輪；"
          f"日 ≤{int(plan.budget.get('daily_token_cap', 0)):,} tok 撞額停不重試；"
          f"入口={plan.budget.get('model_entry')}；"
          f"無硬 token 上限、缺值={plan.budget.get('cost_missing')}")
    if verified:
        print("  verify_frozen: OK（輸入檔 sha256 全核＋選題與規則一致）")
        print("  budget gate: OK")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vacant_network.reqloop.g3gate",
                                 description="G3 發射前置門（離線、零模型呼叫）")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true",
                      help="驗前置並印計劃（預設；RC 0；NOT FIRED）")
    mode.add_argument("--fire", action="store_true",
                      help="需 --approval 核准文件；無核准→RC 2、0 模型呼叫")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--approval", default=None,
                    help="核准 JSON（schema/epic/approved/by）")
    a = ap.parse_args(list(argv) if argv is not None else None)
    manifest = pathlib.Path(a.manifest)

    plan = G3Plan.load(manifest)
    base = manifest.parent
    try:
        plan.verify_frozen(base)
        check_budget(plan)
    except (ValueError, FileNotFoundError) as e:
        print(f"G3GATE PLAN FAIL: {e}")
        return 1
    _print_plan_lines(plan, verified=True)

    if not a.fire:
        print("NOT FIRED（無核准信號；0 model calls）")
        print("G3GATE PLAN OK")
        return RC_OK

    if a.approval is None:
        print("NOT FIRED（無核准信號 → fail-closed；0 model calls）")
        return RC_NOT_APPROVED
    try:
        doc = json.loads(pathlib.Path(a.approval).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"NOT FIRED（核准文件不可讀/不可解析：{e}；0 model calls）")
        return RC_NOT_APPROVED
    ok, why = approval_gate(doc)
    if not ok:
        print(f"NOT FIRED（核准門拒：{why}；0 model calls）")
        return RC_NOT_APPROVED
    print(f"APPROVED（{why}）")
    print("發射管線本輪未接線（核准後另一步授權：三臂逐格發射＋/srv/vlab scorer）")
    return RC_APPROVED_NOT_WIRED


if __name__ == "__main__":
    raise SystemExit(main())
