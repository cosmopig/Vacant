"""D4（11-13 定案第 2 條）：預跑通過的需求規格凍結落盤，正式發射直接重用。

票 P20261113_0545-1 驗收（3 passed）：
- 正控制：提供合法凍結規格 → 0 次 client 擷取呼叫，且 prompt 中的需求清單
  以凍結規格逐條渲染（RequirementSet 逐條吻合）。
- 負控制 1：goal 篡改一個字（goal_sha256 不符）→ fail-closed ValueError 拒發，
  絕不默默降級為重新擷取。
- 負控制 2：規格檔案損壞（非 JSON）→ fail-closed ValueError 拒發。
全程假通道、0 真模型呼叫；plan 切片為 1 task（verify_frozen 選題規則自洽）。
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import re

import pytest

import vacant_network.reqloop.g3 as g3
import vacant_network.reqloop.g3gate as g3gate
from vacant_network.reqloop.requirements import RequirementSet

REPO = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = REPO / "ops" / "reqloop" / "g3_gate" / "manifest.json"
BASE = REPO / "ops" / "reqloop" / "g3_gate"
CONFORMING_ARMS = ("reqlist_only", "full_rloop")
# G4 原生扁平規格（P20261113_0846-1）：spec_dir＋對應 workspace（g3_2 任務集）。
G4_SPEC_DIR = REPO / "ops" / "reqloop" / "g4" / "specs"
G4_MANIFEST = REPO / "ops" / "reqloop" / "g4" / "manifest.json"
G4_TASKS = REPO / "ops" / "reqloop" / "g3_2" / "tasks"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _approval() -> dict:
    return {
        "schema": g3gate.APPROVAL_SCHEMA,
        "approved": True,
        "epic": "vq-1zf",
        "by": "測試核准者（假通道；非真發射）",
    }


def _plan_1task():
    """接線臂（reqlist_only＋full_rloop）× 第 1 題：verify_frozen 選題規則自洽。"""
    full = g3gate.G3Plan.load(MANIFEST)
    return dataclasses.replace(full, arms=CONFORMING_ARMS, tasks=[full.tasks[0]])


def _task_io(tid: str) -> tuple[str, str]:
    ws = BASE / "tasks" / tid / "workspace"
    return (ws / "goal.md").read_text(encoding="utf-8"), \
           (ws / "contract.md").read_text(encoding="utf-8")


def _frozen_reqset(tid: str) -> RequirementSet:
    """凍結規格的需求清單：2 條（1 必需／1 任意；皆無程式重算檢查器→UNKNOWN 口徑）。"""
    return RequirementSet.from_dict({
        "task_id": tid,
        "items": [
            {"id": "f1", "quote": "凍結規格條目一（必需）", "deliverable": "answer.txt",
             "verifier": "unverified", "kind": "explicit", "required": True,
             "unverified": True},
            {"id": "f2", "quote": "凍結規格條目二（任意）", "deliverable": "answer.txt",
             "verifier": "unverified", "kind": "explicit", "required": False,
             "unverified": True},
        ],
    })


def _write_spec(spec_dir: pathlib.Path, tid: str, goal: str, contract: str,
                reqset: RequirementSet) -> pathlib.Path:
    spec_dir.mkdir(parents=True, exist_ok=True)
    p = spec_dir / f"{tid}.json"
    p.write_text(json.dumps({
        "schema": "vacant.g3.frozen_spec/1",
        "task_id": tid,
        "goal_sha256": _sha(goal),
        "contract_sha256": _sha(contract),
        "reqset": reqset.to_dict(),
    }, ensure_ascii=False), encoding="utf-8")
    return p


class CountingChannel(g3.Channel):
    """假通道：記錄呼叫；作答回必要答案項齊全的答案。

    若出現擷取呼叫（purpose 含「擷取需求」）＝D4 失效，regex 斷言直接炸。
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def call(self, *, prompt: str, model: str, purpose: str,
             timeout_s: float) -> tuple[str, g3.RoundUsage]:
        self.calls.append({"purpose": purpose, "prompt": prompt})
        m = re.match(r"G3 (\S+)/(\S+) r(\d+)$", purpose)
        assert m, f"出現非作答呼叫（D4 凍結規格應 0 次擷取呼叫）：{purpose!r}"
        tid = m.group(1)
        names = g3.required_answer_names(
            (BASE / "tasks" / tid / "workspace" / "contract.md").read_text(encoding="utf-8"))
        return "\n".join(f"@{n}[1.00]" for n in names) + "\n", g3.RoundUsage(1, 1000, 5)


def test_frozen_spec_reused_zero_extract_calls(tmp_path):
    """正控制：合法凍結規格 → 0 次 client 擷取呼叫、RequirementSet 逐條吻合。"""
    plan = _plan_1task()
    tid = plan.tasks[0]["task_id"]
    goal, contract = _task_io(tid)
    expected = _frozen_reqset(tid)
    spec_dir = tmp_path / "specs"
    _write_spec(spec_dir, tid, goal, contract, expected)

    fake = CountingChannel()
    result = g3.run_g3(plan, BASE, tmp_path / "o", channel=fake,
                       approval=_approval(), spec_dir=spec_dir)

    # 0 次 client 擷取呼叫（假通道 regex 已擋非作答呼叫；此處明數一遍）
    assert [c for c in fake.calls if "擷取需求" in c["purpose"]] == []
    # 發射真的跑了（兩臂各 1 輪作答）
    assert {c["purpose"] for c in fake.calls} == {
        f"G3 {tid}/reqlist_only r1", f"G3 {tid}/full_rloop r1"}
    # RequirementSet 逐條吻合：需求清單以凍結規格逐條渲染、逐字進 prompt
    rendered = g3.render_requirement_list(expected)
    for arm in CONFORMING_ARMS:
        prompt = next(c["prompt"] for c in fake.calls
                      if c["purpose"] == f"G3 {tid}/{arm} r1")
        assert rendered in prompt
    # task 記錄：2 條需求、無擷取錯誤、無 unverified 原因（凍結重用＝無擷取報告）
    t = result["tasks"][0]
    assert t["n_requirements"] == 2
    assert t["extract_error"] is None
    assert t["unverified_reasons"] == {}


def test_goal_tampered_one_char_refuses(tmp_path):
    """負控制 1：goal 篡改一個字→goal_sha256 不符→fail-closed 拒發、0 呼叫。"""
    plan = _plan_1task()
    tid = plan.tasks[0]["task_id"]
    goal, contract = _task_io(tid)
    spec_dir = tmp_path / "specs"
    p = spec_dir / f"{tid}.json"
    spec_dir.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "schema": "vacant.g3.frozen_spec/1",
        "task_id": tid,
        "goal_sha256": _sha(goal[:-1] + ("X" if goal[-1] != "X" else "Y")),
        "contract_sha256": _sha(contract),
        "reqset": _frozen_reqset(tid).to_dict(),
    }, ensure_ascii=False), encoding="utf-8")

    fake = CountingChannel()
    with pytest.raises(ValueError, match="goal_sha256"):
        g3.run_g3(plan, BASE, tmp_path / "o", channel=fake,
                  approval=_approval(), spec_dir=spec_dir)
    assert fake.calls == [], "拒發必須 0 模型呼叫（不得降級為重新擷取）"


def test_corrupted_spec_refuses(tmp_path):
    """負控制 2：規格檔案損壞（非 JSON）→fail-closed 拒發、0 呼叫。"""
    plan = _plan_1task()
    tid = plan.tasks[0]["task_id"]
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / f"{tid}.json").write_text("{ 這不是合法 JSON", encoding="utf-8")

    fake = CountingChannel()
    with pytest.raises(ValueError, match="損壞"):
        g3.run_g3(plan, BASE, tmp_path / "o", channel=fake,
                  approval=_approval(), spec_dir=spec_dir)
    assert fake.calls == [], "拒發必須 0 模型呼叫（不得降級為重新擷取）"


def _g4_inputs(tid: str) -> dict:
    ws = G4_TASKS / tid / "workspace"
    return {"goal": (ws / "goal.md").read_text(encoding="utf-8"),
            "contract": (ws / "contract.md").read_text(encoding="utf-8")}


def test_load_frozen_spec_real_g4_specs():
    """正控制（G4 原生扁平格式）：4 份真實規格全部載入成功、task_id／條目數正確。

    改前直對 G4 規格呼叫會招 ValueError（reqset 缺失）；本測試即票面正控制。
    """
    manifest = json.loads(G4_MANIFEST.read_text(encoding="utf-8"))
    assert [t for t in manifest["tasks"]] == ["dab_725", "dab_587", "dab_657", "dab_517"]
    for tid in manifest["tasks"]:
        rs = g3.load_frozen_spec(G4_SPEC_DIR, tid, _g4_inputs(tid))
        assert rs.task_id == tid
        assert len(rs.items) == manifest["specs"][tid]["n_items"]
        assert len(rs.items) >= 1


def test_flat_spec_goal_hash_tampered_refuses(tmp_path):
    """負控制（扁平格式）：goal_sha256 改動 1 碼→fail-closed ValueError 拒發。"""
    tid = "dab_725"
    src = json.loads((G4_SPEC_DIR / f"{tid}.json").read_text(encoding="utf-8"))
    src["goal_sha256"] = ("0" if src["goal_sha256"][0] != "0" else "1") + src["goal_sha256"][1:]
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / f"{tid}.json").write_text(
        json.dumps(src, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="goal_sha256"):
        g3.load_frozen_spec(spec_dir, tid, _g4_inputs(tid))
