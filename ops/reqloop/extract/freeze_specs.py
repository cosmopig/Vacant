#!/usr/bin/env python3
"""G4-SPEC（P20261113_0708-1）：dab_725/587/657/517 四題可檢查需求規格凍結落盤（0 model calls）。

資料來源（皆為既有產物之重編譯，不重新擷取）：
- ops/audits/g26_claim_replay.json（D1 重播）：選 replay_status=="deterministic" 且
  saved_verifier 非空者（驗證原語僅 g3_2_fire 批存了 26/26；其餘來源 verifier 0/50 未存）。
- ops/reqloop/g3_2/tasks/<tid>/workspace/{goal.md,contract.md}：hash 落盤進規格（goal_sha256／
  contract_sha256），使 D4 重用時可先核 workspace 未被改。

quote 口徑：來源報告未存逐條 quote（g26 raw_fields_saved.quote=0/76）→ 每條以 goal.md 全文
（使用者原文、已以 goal_sha256 凍結）為 quote，不偽造需求句。

防篡改：spec_sha256＝整份規格（除本欄位）canonical JSON 的 sha256 → 改任何一個字（含
goal_sha256 本身）都使 validate_spec 失敗。

跑法：python3 ops/reqloop/extract/freeze_specs.py          # 落盤 4 份
      python3 ops/reqloop/extract/freeze_specs.py --check   # 機械複核
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from vacant_network.reqloop.requirements import RequirementSet  # noqa: E402

TASKS = ("dab_725", "dab_587", "dab_657", "dab_517")
G26 = REPO / "ops/audits/g26_claim_replay.json"
TASKS_DIR = REPO / "ops/reqloop/g3_2/tasks"
SPEC_DIR = REPO / "ops/reqloop/g4/specs"
TICKET = "P20261113_0708-1-freeze-g4-specs"


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _canon(d: dict) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _claims_of(tid: str) -> list[dict]:
    return [c for c in json.loads(G26.read_text(encoding="utf-8"))["claims"] if c["task_id"] == tid]


def input_files(tid: str) -> list[str]:
    for c in _claims_of(tid):
        if c.get("input_files"):
            return list(c["input_files"])
    return []


def trusted_deliverable(tid: str) -> str:
    for c in _claims_of(tid):
        if c.get("trusted_deliverable"):
            return str(c["trusted_deliverable"])
    raise ValueError(f"{tid}: g26 replay 無 trusted_deliverable")


def build_spec(tid: str) -> dict:
    ws = TASKS_DIR / tid / "workspace"
    goal = (ws / "goal.md").read_text(encoding="utf-8")
    seen: set[str] = set()
    items = []
    for c in _claims_of(tid):
        vd, dlv = c.get("saved_verifier"), c.get("trusted_deliverable") or ""
        if c.get("replay_status") != "deterministic" or not vd or c["claim_id"] in seen:
            continue  # 無驗證原語＝無可確定性檢查條件，不凍結
        if not dlv or dlv in c.get("input_files", []):
            raise ValueError(f"{tid}/{c['claim_id']}: 交付物非「非輸入檔之可信交付物」: {dlv!r}")
        seen.add(c["claim_id"])
        items.append({"id": c["claim_id"], "quote": goal, "deliverable": dlv, "verifier": vd,
                      "kind": "explicit", "params": {},
                      "description": f"G4 frozen spec: g26 replay {c['source']}/{c['claim_id']} deterministic"})
    if not items:
        raise ValueError(f"{tid}: 無任何帶驗證原語的 deterministic 條件")
    spec = {"task_id": tid, "spec_version": 1, "ticket": TICKET,
            "frozen_from": "ops/audits/g26_claim_replay.json",
            "goal_sha256": _sha(ws / "goal.md"), "contract_sha256": _sha(ws / "contract.md"),
            "items": items}
    spec["spec_sha256"] = hashlib.sha256(_canon(spec).encode("utf-8")).hexdigest()
    return spec


def validate_spec(path: str | pathlib.Path) -> tuple[bool, str]:
    """機械複核：可載入＋自 hash＋workspace hash＋交付物全為非輸入檔可信交付物。回 (ok, reason)。"""
    try:
        raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        rs = RequirementSet.from_dict(raw)
        tid = raw["task_id"]
    except Exception as e:
        return False, f"load_failed:{type(e).__name__}:{e}"
    if tid not in TASKS:
        return False, "task_id"
    body = {k: v for k, v in raw.items() if k != "spec_sha256"}
    if raw.get("spec_sha256") != hashlib.sha256(_canon(body).encode("utf-8")).hexdigest():
        return False, "spec_sha256"
    ws = TASKS_DIR / tid / "workspace"
    if raw.get("goal_sha256") != _sha(ws / "goal.md") or raw.get("contract_sha256") != _sha(ws / "contract.md"):
        return False, "workspace_sha256"
    tr, ins = trusted_deliverable(tid), input_files(tid)
    if not rs.items or any(it.deliverable != tr or it.deliverable in ins for it in rs.items):
        return False, "deliverable"
    return True, "ok"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        ok = True
        for tid in TASKS:
            good, why = validate_spec(SPEC_DIR / f"{tid}.json")
            print(tid, "OK" if good else "FAIL", why)
            ok = ok and good
        return 0 if ok else 1
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    for tid in TASKS:
        sp = SPEC_DIR / f"{tid}.json"
        sp.write_text(json.dumps(build_spec(tid), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", sp.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
