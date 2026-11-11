"""G3 臂名實相符（conformance）與「假完整 R-loop」抓假測試（P0；0 真模型呼叫）。

背景（2026-11-11 日報 P0）：g3.py 舊版的三臂與宣稱有重大落差——
- ``native_pi`` 只是 ARM_SPECS 裡的名稱＋提示文字，實際三臂全走 GlmChannel
  （單回合、無工具），沒有啟動 pi；
- ``full_rloop`` 宣告 localized_repair=True／reverify_all=True，實際只有
  「必要答案項 @name[...] 是否出現」的正規表示式檢查——格式完整但數字錯誤的
  草稿完全抓不到；
- 測試全綠卻沒有測到上述行為差異。

本測試檔的三個驗收（一一對應）：
1. conformance 門：native_pi 未接 pi_agent → 三臂計畫 --fire 拒發（RC 3、
   0 模型呼叫），訊息點名臂與缺失機制；全接線的兩臂計畫 → arm_conformance OK。
2. 格式完整但數字錯誤的草稿：full_rloop 用 checks 程式重算抓到 FAIL、
   第 2 輪反饋帶逐條 FAIL 狀態與可見反例（不含重算期望值）、模型修正後
   重驗 PASS，diff 如實記 FAIL→PASS。
3. reqlist_only 不得免費獲得同一能力：同任務同清單，1 輪、無重驗反饋段落。
"""
from __future__ import annotations

import dataclasses
import json
import pathlib

import pytest

import vacant_network.reqloop.g3 as g3
import vacant_network.reqloop.g3gate as g3gate

REPO = pathlib.Path(__file__).resolve().parent.parent

BUDGET = {
    "max_cells": g3gate.MAX_CELLS,
    "timeout_s_per_round": g3gate.MAX_TIMEOUT_S_PER_ROUND,
    "daily_token_cap": g3gate.MAX_DAILY_TOKEN_CAP,
    "quota_fail_closed": True,
    "model_entry": "glm",
    "hard_token_cap": False,
    "cost_missing": "UNKNOWN",
}

GOAL = """# Task

Write your final answer to answer.txt. Count the number of rows whose
travel status field equals the value 1 in the data file.

## Answer format

@n_rows[int_value] where "int_value" is the count as an integer.

## Data

The data file for this task is `data/pax.csv`.
"""

CSV = "row_id,travel_status\n" + "\n".join(
    f"r{i},{1 if i < 7 else 0}" for i in range(10)) + "\n"

CONTRACT = """# Contract

Write your final answer to `answer.txt` in the root of this workspace.

- Put each answer item on its own line, in the form `@name[value]`, using exactly
  the names given under "Answer format" in the task. This task expects 1 item(s):
  `@n_rows[...]`.
- Only the `@name[value]` items in `answer.txt` are read.
"""

#: 擷取模型回的清單：quote 逐字取自 GOAL、deliverable 在原文點名（answer.txt）、
#: verifier 用 checks 白名單內的 kv_recomputed（count_if 可靠重算）。
EXTRACT_ITEMS = [{
    "id": "r1",
    "quote": "Count the number of rows whose\ntravel status field equals the value 1 in the data file.",
    "deliverable": "answer.txt",
    "kind": "explicit",
    "verifier": "kv_recomputed",
    "params": {"key": "n_rows", "data_file": "data/pax.csv",
               "recompute": {"type": "count_if", "col": "travel_status",
                              "eq": 1}},
}]


def _approval() -> dict:
    return {
        "schema": g3gate.APPROVAL_SCHEMA,
        "approved": True,
        "epic": "vq-1zf",
        "by": "測試核准者（假通道；非真發射）",
    }


def build_base(tmp_path: pathlib.Path) -> pathlib.Path:
    base = tmp_path / "base"
    ws = base / "tasks" / "dab_t1" / "workspace"
    ws.mkdir(parents=True)
    (base / "tasks" / "dab_t1" / "instruction.txt").write_text(
        "Read goal.md and contract.md in this directory and do what they say.\n",
        encoding="utf-8")
    (ws / "goal.md").write_text(GOAL, encoding="utf-8")
    (ws / "contract.md").write_text(CONTRACT, encoding="utf-8")
    (ws / "data").mkdir()
    (ws / "data" / "pax.csv").write_text(CSV, encoding="utf-8")

    files: dict[str, str] = {}
    tdir = base / "tasks" / "dab_t1"
    for f in sorted(tdir.rglob("*")):
        if f.is_file():
            files[str(f.relative_to(tdir))] = g3gate.sha256_file(f)
    arms = ["reqlist_only", "full_rloop"]
    manifest = {
        "schema": g3gate.PLAN_SCHEMA,
        "frozen_at": "2026-11-11T00:00:00+00:00",
        "ticket": "t-conformance（測試合成任務；非預註冊）",
        "purpose": "conformance 測試合成 manifest",
        "arms": arms,
        "arm_defs": {a: "（合成）" for a in arms},
        "tasks": [{"task_id": "dab_t1", "files": files}],
        "seen_set": [],
        "seen_set_source": "（合成：空已見集合）",
        "bank": {"name": "synthetic", "dir": str(base),
                 "n_total": 1, "ordering": ["dab_t1"]},
        "budget": dict(BUDGET),
        "scoring": {},
        "leak_guard": "",
        "approval": {"required": True, "by": "human"},
    }
    (base / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return base


def load_plan(base: pathlib.Path, *, arms: tuple[str, ...]) -> g3gate.G3Plan:
    plan = g3gate.G3Plan.load(base / "manifest.json")
    return dataclasses.replace(plan, arms=tuple(arms))


class ScriptedChannel(g3.Channel):
    """假通道：擷取回 EXTRACT_ITEMS；作答依 (task/arm, round) 劇本回稿。"""

    def __init__(self, answers: dict[str, list[str]]) -> None:
        self.answers = answers          # "tid/arm" -> [r1, r2, ...] 逐輪
        self.calls: list[dict] = []
        self._next: dict[str, int] = {}

    def call(self, *, prompt: str, model: str, purpose: str,
             timeout_s: float) -> tuple[str, g3.RoundUsage]:
        self.calls.append({"prompt": prompt, "purpose": purpose, "model": model})
        if "擷取需求" in purpose:
            return json.dumps(EXTRACT_ITEMS, ensure_ascii=False), \
                g3.RoundUsage(1, 100, 5)
        arm = purpose.split("/")[1].rsplit(" ", 1)[0]
        tid = purpose.split("/")[0].split()[-1]
        key = f"{tid}/{arm}"
        n = self._next.get(key, 0)
        self._next[key] = n + 1
        answer = self.answers[key][n]
        return answer, g3.RoundUsage(1, 100, 5)


# ── conformance：臂名實不符 → 拒發（RC 3、0 模型呼叫）────────────────


def test_frozen_three_arm_plan_refuses_to_fire(tmp_path):
    """native_pi 預註冊要求 pi_agent、實作未接線→三臂計畫 --fire 拒發。"""
    base = build_base(tmp_path)
    appr = tmp_path / "approval.json"
    appr.write_text(json.dumps(_approval()), encoding="utf-8")
    fake = ScriptedChannel({"dab_t1/native_pi": ["@n_rows[7]\n"]})
    # 先把 manifest 的 arms 換成三臂（含 native_pi）而不動凍結輸入
    plan3 = load_plan(base, arms=("native_pi", "reqlist_only", "full_rloop"))
    with pytest.raises(g3.G3ArmsNotConformant) as ei:
        g3.run_g3(plan3, base, tmp_path / "out", channel=fake,
                  approval=_approval())
    assert "native_pi" in str(ei.value)
    assert "pi_agent" in str(ei.value)
    assert fake.calls == [], "拒發＝0 模型呼叫"


def test_fire_cli_three_arms_rc3_zero_calls(tmp_path, capsys):
    base = build_base(tmp_path)
    # manifest 檔本身改成三臂（g3.main 讀檔）
    mp = base / "manifest.json"
    raw = json.loads(mp.read_text(encoding="utf-8"))
    raw["arms"] = ["native_pi", "reqlist_only", "full_rloop"]
    raw["arm_defs"]["native_pi"] = "原生 pi：再檢查修正一次（合成重現）"
    mp.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    appr = tmp_path / "approval.json"
    appr.write_text(json.dumps(_approval()), encoding="utf-8")
    fake = ScriptedChannel({"dab_t1/native_pi": ["@n_rows[7]\n"],
                             "dab_t1/reqlist_only": ["@n_rows[7]\n"],
                             "dab_t1/full_rloop": ["@n_rows[7]\n"]})
    rc = g3.main(["--fire", "--approval", str(appr),
                  "--manifest", str(mp), "--out", str(tmp_path / "o")],
                 channel=fake)
    assert rc == g3gate.RC_APPROVED_NOT_WIRED == 3
    assert fake.calls == []
    out = capsys.readouterr().out
    assert "ARMS NOT CONFORMANT" in out
    assert "native_pi" in out and "pi_agent" in out


def test_two_arm_plan_conformance_ok():
    plan2 = dataclasses.replace(
        g3gate.G3Plan.load(REPO / "ops" / "reqloop" / "g3_gate" / "manifest.json"),
        arms=("reqlist_only", "full_rloop"))
    ok, problems = g3.arm_conformance(plan2)
    assert ok, problems
    assert problems == []


# ── 抓假：「格式完整但數字錯誤」的草稿必須被抓到並修復 ──────────────


def test_full_rloop_catches_wrong_number_repair_reverify(tmp_path):
    """full_rloop 用 checks 程式重算抓數字錯誤；反饋只修缺口；修後重驗 PASS。"""
    base = build_base(tmp_path)
    plan2 = load_plan(base, arms=("reqlist_only", "full_rloop"))
    fake = ScriptedChannel({
        # 格式完整（@n_rows 項在、無漏項）但數字錯誤：重算值是 7，草稿寫 999
        "dab_t1/full_rloop": ["@n_rows[999]\n", "@n_rows[7]\n"],
        "dab_t1/reqlist_only": ["@n_rows[999]\n"],
    })
    out = tmp_path / "out"
    result = g3.run_g3(plan2, base, out, channel=fake, approval=_approval())

    full = next(c for c in result["cells"]
                if c["arm"] == "full_rloop" and c["task"] == "dab_t1")
    # 兩輪：r1 抓到 FAIL → r2 修復；重驗後 FAIL→PASS 入 diff
    assert len(full["rounds"]) == 2
    cv = full["content_reverify"]
    assert cv["enabled"] is True
    assert [r["verdict"] for r in cv["rounds"]] == ["FAIL", "PASS"]
    assert cv["final_verdict"] == "PASS"
    assert cv["diff"]["fixed"] == ("r1",)
    assert cv["diff"]["regressed"] == ()
    claims_r1 = cv["rounds"][0]["claims"]
    assert claims_r1[0]["status"] == "FAIL"
    assert claims_r1[0]["id"] == "r1"

    # r2 反饋是 localized 的：帶上一稿原文、逐條 FAIL 狀態與可見反例；
    # 反例依 checks 設計不含重算期望值（7 不得以期望值身分出現）
    p2 = [c for c in fake.calls
          if c["purpose"] == "G3 dab_t1/full_rloop r2"][0]["prompt"]
    assert "上一稿與缺口" in p2
    assert "@n_rows[999]" in p2, "必須帶上一稿原文（可見回饋的對象）"
    assert "逐條需求驗證結果" in p2
    assert "[FAIL]" in p2
    assert "mismatch_with_recomputation" in p2
    assert "只修未滿足的條目" in p2
    # 防洩漏：反饋只帶「你的值與重算不符」，檢查器反例依設計不含重算期望值
    assert "重算值" not in p2, "反饋不得把重算期望值寫進缺口證據"
    ev = claims_r1[0]["evidence"]
    assert ev["expected_in_evidence"] is False, "kv_recomputed 反例不得帶重算期望值"

    # r1 草稿已落盤供審計（逐輪工作目錄）
    r1_ws = out / "cells" / "dab_t1__full_rloop" / "round_1" / "answer.txt"
    assert r1_ws.is_file() and "@n_rows[999]" in r1_ws.read_text(encoding="utf-8")


def test_required_answer_names_ignores_template_placeholder():
    """契約範本的 `@name[value]` 是格式說明，不是必要答案項名。

    舊解析把 "name" 也算進必要項：真情況下沒有模型會輸出 `@name[...]`，
    「缺項」恆真——這是結構性檢查的假缺口來源之一（全部 4 題 dab 契約都中）。
    """
    names = g3.required_answer_names(CONTRACT)
    assert names == ["n_rows"]
    # 沒有列舉句的契約：退回全文掃描，剔除 placeholder
    no_list = CONTRACT.replace(
        "This task expects 1 item(s):\n  `@n_rows[...]`.", "")
    assert "name" not in g3.required_answer_names(no_list)


def test_full_rloop_verdict_unknown_when_extraction_unverifiable(tmp_path):
    """擷取清單全是 unverified（無可靠檢查器）→ 重驗如實 UNKNOWN，
    不得假裝 PASS；沒有已確認缺口→不花第 2 輪（I-4：未測得≠通過）。"""
    base = build_base(tmp_path)
    plan2 = load_plan(base, arms=("full_rloop",))

    class UnverifiedChannel(ScriptedChannel):
        def call(self, **kw):
            if "擷取需求" in kw["purpose"]:
                self.calls.append({"prompt": kw["prompt"], "purpose": kw["purpose"]})
                return json.dumps([{
                    "id": "r1",
                    "quote": GOAL.splitlines()[2].strip(),
                    "deliverable": "answer.txt",
                    "kind": "explicit",
                    "unverified": True,
                }], ensure_ascii=False), g3.RoundUsage(1, 100, 5)
            return super().call(**kw)

    fake = UnverifiedChannel({
        "dab_t1/full_rloop": ["@n_rows[999]\n"],
    })
    result = g3.run_g3(plan2, base, tmp_path / "out", channel=fake,
                       approval=_approval())
    full = result["cells"][0]
    assert len(full["rounds"]) == 1, "UNKNOWN 不是缺口——不花第 2 輪"
    cv = full["content_reverify"]
    assert cv["enabled"] is True           # 有清單→有重驗，只是結果 UNKNOWN
    assert cv["rounds"][0]["verdict"] == "UNKNOWN"
    assert cv["final_verdict"] == "UNKNOWN"


def test_reqlist_only_never_gains_reverify(tmp_path):
    """同任務、同擷取清單：reqlist_only 1 輪、無逐條重算反饋段落。"""
    base = build_base(tmp_path)
    plan2 = load_plan(base, arms=("reqlist_only", "full_rloop"))
    fake = ScriptedChannel({
        "dab_t1/full_rloop": ["@n_rows[999]\n", "@n_rows[7]\n"],
        "dab_t1/reqlist_only": ["@n_rows[999]\n"],
    })
    result = g3.run_g3(plan2, base, tmp_path / "out", channel=fake,
                       approval=_approval())
    req = next(c for c in result["cells"]
               if c["arm"] == "reqlist_only" and c["task"] == "dab_t1")
    assert len(req["rounds"]) == 1
    assert req["content_reverify"]["enabled"] is False
    assert req["content_reverify"]["rounds"] == []
    assert req["content_reverify"]["final_verdict"] is None
    # 它的 prompt 帶需求清單（臂定義）但不帶逐條重算反饋
    p1 = [c for c in fake.calls
          if c["purpose"] == "G3 dab_t1/reqlist_only r1"][0]["prompt"]
    assert "【需求清單" in p1
    assert "逐條需求驗證結果" not in p1
    # full_rloop 修復反饋也不會洩給 reqlist_only 的 prompt
    for c in fake.calls:
        if c["purpose"].endswith("reqlist_only r1"):
            assert "[FAIL]" not in c["prompt"]


# ── conformance 靜態一致性：ARM_SPECS 的宣告必須有 ARM_WIRED 支撐 ────


def test_declared_flags_backed_by_wiring():
    for arm, spec in g3.ARM_SPECS.items():
        wired = g3.ARM_WIRED[arm]
        if spec["requirement_list"]:
            assert wired["requirement_list"] is True, f"{arm}: 宣告清單未接線"
        if spec["localized_repair"] or spec["reverify_all"]:
            assert wired["localized_repair"] is True and \
                wired["content_reverify"] is True, f"{arm}: 宣告修復/重驗未接線"
        if spec["content_reverify"]:
            assert wired["content_reverify"] is True, f"{arm}: 宣告重驗未接線"


def test_arm_required_is_not_emptied_by_mistake():
    """ARM_REQUIRED 是預註冊要求（單一事實來源）；清空即失去 conformance 意義
    ——native_pi 必須仍然要求 pi_agent。"""
    assert g3.ARM_REQUIRED["native_pi"] == {"pi_agent": True}
    assert g3.ARM_REQUIRED["full_rloop"]["content_reverify"] is True
    assert g3.ARM_REQUIRED["reqlist_only"]["requirement_list"] is True
