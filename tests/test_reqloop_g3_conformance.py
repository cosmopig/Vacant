"""G3 臂名實相符（conformance）、「假完整 R-loop」抓假與 PiChannel 機制測試（0 真模型呼叫）。

背景（2026-11-11 日報 P0）：g3.py 舊版的三臂與宣稱有重大落差——
- ``native_pi`` 只是 ARM_SPECS 裡的名稱＋提示文字，實際三臂全走 GlmChannel
  （單回合、無工具），沒有啟動 pi；
- ``full_rloop`` 宣告 localized_repair=True／reverify_all=True，實際只有
  「必要答案項 @name[...] 是否出現」的正規表示式檢查——格式完整但數字錯誤的
  草稿完全抓不到；
- 測試全綠卻沒有測到上述行為差異。

AMEND-1（2026-11-11 人類裁決）：native_pi 接真 pi 工具迴圈＋本地模型
（PiChannel；provider/model 由 manifest budget 如實宣告 glm+local_pi）。

本測試檔的驗收（一一對應）：
1. conformance：ARM_WIRED 對照 ARM_REQUIRED 逐臂核對（三臂含 native_pi
   全綠＝pi_agent 已接線）；pi 臂缺 pi_channel 注入→拒發（0 模型呼叫）；
   預算門：native_pi 未宣告 local_pi 入口→拒。
2. 格式完整但數字錯誤的草稿：full_rloop 用 checks 程式重算抓到 FAIL、
   第 2 輪反饋帶逐條 FAIL 狀態與可見反例（不含重算期望值）、模型修正後
   重驗 PASS，diff 如實記 FAIL→PASS。
3. reqlist_only 不得免費獲得同一能力：同任務同清單，1 輪、無重驗反饋段落。
4. PiChannel 機制：workspace＝任務輸入複本（原檔不動）、answer.txt 讀回、
   raw usage 解析（缺值＝UNKNOWN 不填 0）、agent 失敗→G3CallError
   （該格 error、不重試、管線繼續）。
"""
from __future__ import annotations

import dataclasses
import json
import pathlib

import pytest

import vacant_network.reqloop.g3 as g3
import vacant_network.reqloop.g3gate as g3gate

REPO = pathlib.Path(__file__).resolve().parent.parent

BUDGET_GLM = {
    "max_cells": g3gate.MAX_CELLS,
    "timeout_s_per_round": g3gate.MAX_TIMEOUT_S_PER_ROUND,
    "daily_token_cap": g3gate.MAX_DAILY_TOKEN_CAP,
    "quota_fail_closed": True,
    "model_entry": "glm",
    "hard_token_cap": False,
    "cost_missing": "UNKNOWN",
}
# AMEND-1：native_pi 接真 pi＋本地模型——manifest 如實宣告 glm+local_pi
# AMEND-2（2026-11-11）：pi 臂在場→每格牆時 cap 必須在案（timeout_s_per_round_pi；
# glm 的 timeout_s_per_round 仍 300s）
BUDGET_GLM_PI = {
    **BUDGET_GLM,
    "model_entry": "glm+local_pi",
    "pi_provider": "lms1003qwen",
    "pi_model": "qwen/qwen3.8-27b",
    "timeout_s_per_round_pi": g3gate.MAX_TIMEOUT_S_PER_ROUND_PI,
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


def build_base(tmp_path: pathlib.Path,
               *, arms: tuple[str, ...] = ("reqlist_only", "full_rloop")) -> pathlib.Path:
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
    budget = BUDGET_GLM_PI if "native_pi" in arms else BUDGET_GLM
    manifest = {
        "schema": g3gate.PLAN_SCHEMA,
        "frozen_at": "2026-11-11T00:00:00+00:00",
        "ticket": "t-conformance（測試合成任務；非預註冊）",
        "purpose": "conformance 測試合成 manifest",
        "arms": list(arms),
        "arm_defs": {a: "（合成）" for a in arms},
        "tasks": [{"task_id": "dab_t1", "files": files}],
        "seen_set": [],
        "seen_set_source": "（合成：空已見集合）",
        "bank": {"name": "synthetic", "dir": str(base),
                 "n_total": 1, "ordering": ["dab_t1"]},
        "budget": dict(budget),
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


# ── conformance／native_pi：AMEND-1 後的行為與拒發條件 ──────────────


class FakePiChannel(g3.Channel):
    """跑管線用的假 pi 通道（endpoint 同 PiChannel；workspace 機制另測）。"""

    def __init__(self, *, answer: str = "@n_rows[7]\n",
                 tokens: int | None = 100) -> None:
        self.calls: list[dict] = []
        self.answer = answer
        self.tokens = tokens

    def call(self, *, prompt: str, model: str, purpose: str,
             timeout_s: float) -> tuple[str, g3.RoundUsage]:
        self.calls.append({"prompt": prompt, "purpose": purpose})
        return self.answer, g3.RoundUsage(1, self.tokens, 5)


def test_three_arm_plan_conformance_static_ok():
    """AMEND-1：三臂（含 native_pi）的靜態 conformance 全綠——pi_agent 已接線。"""
    ok, problems = g3.arm_conformance(
        g3gate.G3Plan.load(REPO / "ops" / "reqloop" / "g_gate/manifest.json"
                           if False else REPO / "ops" / "reqloop" / "g3_gate" / "manifest.json"))
    assert ok, problems
    assert problems == []


def test_two_arm_plan_conformance_ok():
    plan2 = dataclasses.replace(
        g3gate.G3Plan.load(REPO / "ops" / "reqloop" / "g3_gate" / "manifest.json"),
        arms=("reqlist_only", "full_rloop"))
    ok, problems = g3.arm_conformance(plan2)
    assert ok, problems


def test_three_arm_plan_without_pi_channel_refuses(tmp_path):
    """pi 臂缺 pi_channel 注入→拒發（G3ArmsNotConformant）、0 模型呼叫
    ——核准過了也不發（conformance 的執行期半邊）。"""
    base = build_base(tmp_path, arms=("native_pi", "reqlist_only", "full_rloop"))
    fake = ScriptedChannel({
        "dab_t1/native_pi": ["@n_rows[7]\n"],
        "dab_t1/reqlist_only": ["@n_rows[7]\n"],
        "dab_t1/full_rloop": ["@n_rows[7]\n"],
    })
    fake_pi = FakePiChannel()
    plan3 = load_plan(base, arms=("native_pi", "reqlist_only", "full_rloop"))
    with pytest.raises(g3.G3ArmsNotConformant) as ei:
        g3.run_g3(plan3, base, tmp_path / "out", channel=fake,
                  approval=_approval())
    assert "pi_channel" in str(ei.value)
    assert fake.calls == [] and fake_pi.calls == [], "拒發＝0 模型呼叫"


def test_fire_cli_three_arms_rc0_with_pi_channel(tmp_path, capsys):
    """AMEND-1：三臂計畫 --fire（核准＋假 glm 通道＋假 pi 通道）跑通 3 格。"""
    base = build_base(tmp_path, arms=("native_pi", "reqlist_only", "full_rloop"))
    appr = tmp_path / "approval.json"
    appr.write_text(json.dumps(_approval()), encoding="utf-8")
    fake = ScriptedChannel({
        "dab_t1/reqlist_only": ["@n_rows[7]\n"],
        "dab_t1/full_rloop": ["@n_rows[7]\n"],
    })
    fake_pi = FakePiChannel()
    rc = g3.main(["--fire", "--approval", str(appr),
                  "--manifest", str(base / "manifest.json"),
                  "--out", str(tmp_path / "o")],
                 channel=fake, pi_channel=fake_pi)
    assert rc == 0
    assert len(fake_pi.calls) == 1, "native_pi 格由 pi 通道服務"
    assert fake_pi.calls[0]["purpose"] == "G3 dab_t1/native_pi r1"
    # pi 臂 prompt 以凍結 instruction 為本；不帶資料預覽
    assert "Read goal.md and contract.md" in fake_pi.calls[0]["prompt"]
    assert "--- goal.md ---" not in fake_pi.calls[0]["prompt"]
    # glm 臂同跑（reqlist/full_rloop 各 1 格）
    assert len(fake.calls) == 1 + 2, "擷取 1＋glm 作答 2"
    out = capsys.readouterr().out
    assert "G3 FIRE DONE" in out


def test_check_budget_requires_local_pi_entry_for_native_pi(tmp_path):
    """預算門（AMEND-1）：arms 含 native_pi 而 model_entry 未宣告
    glm+local_pi → 拒；宣告了但缺 pi_provider/pi_model 也拒。"""
    base = build_base(tmp_path, arms=("native_pi", "reqlist_only", "full_rloop"))
    plan3 = load_plan(base, arms=("native_pi", "reqlist_only", "full_rloop"))
    # (a) 原樣（glm+local_pi 齊宣告）→ 過
    g3gate.check_budget(plan3)
    # (b) native_pi 臂＋glm 入口 → 拒（名實不符即拒）
    bad1 = dataclasses.replace(
        plan3, budget={k: v for k, v in plan3.budget.items()
                       if k not in ("pi_provider", "pi_model")} | {"model_entry": "glm"})
    with pytest.raises(ValueError, match="native_pi"):
        g3gate.check_budget(bad1)
    # (c) glm+local_pi 但缺 pi_provider → 拒（fail-closed，不得空字串頂替）
    bad2 = dataclasses.replace(
        plan3, budget=dict(plan3.budget, pi_provider=""))
    with pytest.raises(ValueError, match="pi_provider"):
        g3gate.check_budget(bad2)


# ── PiChannel：workspace／讀回／usage／錯誤語義（AMEND-1）─────────────


def _noop_build(prompt, ws):
    return {"argv": ["fake-pi", "-p", prompt], "note": "test"}


def _fake_pi_run(answer_text: str = "@n_rows[7]\n", *, write_answer: bool = True,
                 rc: int = 0, timed_out: bool = False,
                 spawn_error=None, usage_lines=None):
    def run(launch, *, workspace, timeout_s, log_dir):
        log_dir.mkdir(parents=True, exist_ok=True)
        out_log = log_dir / "agent_stdout.log"
        out_log.write_text(
            "\n".join(usage_lines) if usage_lines else "", encoding="utf-8")
        if write_answer:
            (pathlib.Path(workspace) / "answer.txt").write_text(
                answer_text, encoding="utf-8")
        return {"rc": rc, "timed_out": timed_out, "wall_ms": 12345,
                "spawn_error": spawn_error, "budget_exceeded": None,
                "stdout_log": str(out_log),
                "stderr_log": str(log_dir / "agent_stderr.log")}
    return run


_USAGE_LINE = json.dumps({
    "type": "message_end",
    "message": {"role": "assistant", "usage": {"input": 100, "output": 50}},
})


def test_pi_channel_workspace_answer_and_usage(tmp_path):
    base = tmp_path / "base"
    ws = base / "tasks" / "dab_t1" / "workspace"
    ws.mkdir(parents=True)
    (ws / "goal.md").write_text("# Task\n", encoding="utf-8")
    (ws / "contract.md").write_text("# Contract\n", encoding="utf-8")
    (ws / "data").mkdir()
    (ws / "data" / "pax.csv").write_text(CSV, encoding="utf-8")
    goal_sha = g3gate.sha256_file(ws / "goal.md")
    out = tmp_path / "out"
    chan = g3.PiChannel(base, out_root=out, build=_noop_build,
                        run=_fake_pi_run(usage_lines=[_USAGE_LINE]))
    text, usage = chan.call(prompt="p", model="deepseek41",
                            purpose="G3 dab_t1/native_pi r1", timeout_s=300)
    assert text == "@n_rows[7]\n"
    assert usage.tokens == 150, "usage＝raw usage input+output（100+50）"
    assert usage.calls == 1
    assert usage.wall_ms == 12345
    # 工作區＝任務輸入複本（goal/contract/data）＋answer.txt，逐輪快照保留供審計
    cell_ws = out / "cells" / "dab_t1__native_pi" / "round_1"
    assert (cell_ws / "answer.txt").read_text(encoding="utf-8") == "@n_rows[7]\n"
    assert (cell_ws / "goal.md").is_file() and (cell_ws / "data" / "pax.csv").is_file()
    # 原任務檔不被改動（讀任務檔案是輸入，不是工作區）
    assert g3gate.sha256_file(ws / "goal.md") == goal_sha


def test_pi_channel_usage_missing_is_unknown_not_zero(tmp_path):
    base = tmp_path / "base"
    ws = base / "tasks" / "dab_t1" / "workspace"
    ws.mkdir(parents=True)
    (ws / "goal.md").write_text("# Task\n", encoding="utf-8")
    chan = g3.PiChannel(base, out_root=tmp_path / "out", build=_noop_build,
                        run=_fake_pi_run(usage_lines=None))
    text, usage = chan.call(prompt="p", model="deepseek41",
                            purpose="G3 dab_t1/native_pi r1", timeout_s=300)
    assert text == "@n_rows[7]\n"
    assert usage.tokens is None, "raw usage 缺值＝UNKNOWN（None），絕不填 0"
    assert usage.calls == 1, "session 計 1（API 呼叫數沒量到就計 session 數）"


@pytest.mark.parametrize("run_kwargs, message", [
    ({"rc": 2}, "pi rc=2"),
    ({"timed_out": True}, "pi timed out"),
    ({"spawn_error": "FileNotFoundError: pi"}, "pi spawn"),
])
def test_pi_channel_agent_failures_are_call_errors(tmp_path, run_kwargs, message):
    base = tmp_path / "base"
    ws = base / "tasks" / "dab_t1" / "workspace"
    ws.mkdir(parents=True)
    (ws / "goal.md").write_text("# Task\n", encoding="utf-8")
    chan = g3.PiChannel(base, out_root=tmp_path / "out", build=_noop_build,
                        run=_fake_pi_run(**run_kwargs))
    with pytest.raises(g3.G3CallError, match=message):
        chan.call(prompt="p", model="deepseek41",
                  purpose="G3 dab_t1/native_pi r1", timeout_s=300)


def test_pi_channel_missing_deliverable_is_call_error(tmp_path):
    """agent 跑完（rc=0）但沒寫 answer.txt → G3CallError（如實記，不猜內容）。"""
    base = tmp_path / "base"
    ws = base / "tasks" / "dab_t1" / "workspace"
    ws.mkdir(parents=True)
    (ws / "goal.md").write_text("# Task\n", encoding="utf-8")
    chan = g3.PiChannel(base, out_root=tmp_path / "out", build=_noop_build,
                        run=_fake_pi_run(write_answer=False))
    with pytest.raises(g3.G3CallError, match="answer.txt"):
        chan.call(prompt="p", model="deepseek41",
                  purpose="G3 dab_t1/native_pi r1", timeout_s=300)


def test_pi_channel_bad_purpose_rejected(tmp_path):
    base = tmp_path / "base"
    (base / "tasks").mkdir(parents=True)
    chan = g3.PiChannel(base, out_root=tmp_path / "out", build=_noop_build,
                        run=_fake_pi_run())
    with pytest.raises(g3.G3CallError, match="purpose"):
        chan.call(prompt="p", model="m", purpose="不是格 purpose", timeout_s=10)


def test_pi_channel_supports_g4_purpose_and_tasks_dir(tmp_path):
    """G4 通道呼叫（票 P20261113_1307-1）：PiChannel 支援 G4 purpose 格式＋自訂 tasks_dir。

    改動前此 purpose 會拋 G3CallError（regex 硬編碼 ``G3``；且 G4 任務工作區在
    ops/reqloop/g3_2/tasks、不在 base/tasks）——本測改動前必紅。
    """
    # 自訂 tasks_dir（G4 任務工作區）；base 下刻意沒有 tasks/ 子樹
    tasks = tmp_path / "g3_2" / "tasks"
    ws = tasks / "dab_725" / "workspace"
    ws.mkdir(parents=True)
    (ws / "goal.md").write_text("# Task\n", encoding="utf-8")
    (ws / "contract.md").write_text("# Contract\n", encoding="utf-8")
    base = tmp_path / "base"
    base.mkdir()
    out = tmp_path / "out"
    chan = g3.PiChannel(base, out_root=out, build=_noop_build,
                        run=_fake_pi_run(usage_lines=[_USAGE_LINE]),
                        tasks_dir=tasks)
    # G4 purpose＋自訂 tasks_dir 正常執行（讀回 answer.txt、usage 如實）
    text, usage = chan.call(prompt="p", model="qwen/qwen3.8-27b",
                            purpose="G4 dab_725/native_pi r1", timeout_s=300)
    assert text == "@n_rows[7]\n"
    assert usage.tokens == 150 and usage.calls == 1
    # 工作區取自自訂 tasks_dir（不是 base/tasks）
    cell_ws = out / "cells" / "dab_725__native_pi" / "round_1"
    assert (cell_ws / "answer.txt").read_text(encoding="utf-8") == "@n_rows[7]\n"
    # 舊 G3 purpose＋tasks_dir=None 預設＝舊行為（base/tasks/<tid>/workspace）
    ws3 = base / "tasks" / "dab_t1" / "workspace"
    ws3.mkdir(parents=True)
    (ws3 / "goal.md").write_text("# Task\n", encoding="utf-8")
    chan_default = g3.PiChannel(base, out_root=out, build=_noop_build,
                                run=_fake_pi_run())
    text3, _ = chan_default.call(prompt="p", model="m",
                                 purpose="G3 dab_t1/native_pi r1", timeout_s=300)
    assert text3 == "@n_rows[7]\n"
    # 負控制：非 G3/G4 的 purpose 仍拒絕（fail-closed 未破）
    with pytest.raises(g3.G3CallError, match="purpose"):
        chan.call(prompt="p", model="m", purpose="G5 dab_725/native_pi r1",
                  timeout_s=10)
    # _ArmChannelRouter：G4 的 native_pi 也分流到 pi 通道；其他臂走原通道
    class _Rec(g3.Channel):
        def __init__(self) -> None:
            self.hit: list[str] = []

        def call(self, *, prompt: str, model: str, purpose: str,
                 timeout_s: float) -> tuple[str, g3.RoundUsage]:
            self.hit.append(purpose)
            return "glm", g3.RoundUsage(calls=1, tokens=None, wall_ms=None)

    other = _Rec()
    router = g3._ArmChannelRouter(channel=other, pi_channel=chan)
    text_r, _ = router.call(prompt="p", model="m",
                            purpose="G4 dab_725/native_pi r1", timeout_s=300)
    assert text_r == "@n_rows[7]\n" and other.hit == []
    text_o, _ = router.call(prompt="p", model="m",
                            purpose="G4 dab_725/reqlist_only r1", timeout_s=300)
    assert text_o == "glm" and other.hit == ["G4 dab_725/reqlist_only r1"]


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
