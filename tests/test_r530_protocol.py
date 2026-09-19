"""R530：工具協定（native／text）——**兩種模式的資料不得混算**，所以兩邊都要驗。

2026-09-13 的冒煙把預註冊 §二-4 的預設值推翻了一次（文字協定不通、原生 `tools`
通）。這一批測的是**推翻之後的那一份**：正規化、兩種協定的訊息角色、
以及「協定是實驗條件、要落盤」這件事。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.r530 import brain_native as bn  # noqa: E402
from ops.gain.r530 import openwork_arms as oa  # noqa: E402
from ops.gain.r530 import sandbox as sb, tasks as taskmod  # noqa: E402
from vacant_network.identity import Identity  # noqa: E402
from vacant_network.logbook import Logbook  # noqa: E402


# ── tool_calls 正規化 ─────────────────────────────────────────────────────
def test_normalise_reads_a_well_formed_call():
    out = bn._normalise_tool_calls([{
        "id": "7", "type": "function",
        "function": {"name": "run_bash",
                     "arguments": json.dumps({"command": "ls -la"})}}])
    assert out == [{"id": "7", "name": "run_bash", "command": "ls -la",
                    "timeout_s": None}]


def test_normalise_clamps_the_requested_timeout_at_call_time():
    out = bn._normalise_tool_calls([{
        "id": "1", "function": {"name": "run_bash",
                                "arguments": json.dumps({"command": "x",
                                                         "timeout_s": 9999})}}])
    assert out[0]["timeout_s"] == 9999, "正規化不夾，夾在執行端"
    sandbox = sb.NoneSandbox()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        _msg, rec = oa._run_one_command(
            "true", sandbox, pathlib.Path(td), pathlib.Path(td) / "c.jsonl",
            timeout_s=9999)
    assert rec["timeout_s"] == oa.OPENWORK_BUDGET["tool_timeout_max_s"], \
        "模型要 9999 秒也只給得到上限——預算不是模型說了算"


def test_normalise_keeps_broken_calls_instead_of_dropping_them():
    """**模型試圖做什麼比模型做成了什麼更值得留著看**（localagent 的同一條）。"""
    out = bn._normalise_tool_calls([
        {"id": "1", "function": {"name": "run_python", "arguments": "{}"}},
        {"id": "2", "function": {"name": "run_bash", "arguments": "not json"}},
        {"id": "3", "function": {"name": "run_bash", "arguments": "{}"}},
    ])
    assert len(out) == 3
    assert all("error" in c for c in out)
    assert "unknown tool" in out[0]["error"]
    assert "not valid JSON" in out[1]["error"]
    assert "no `command`" in out[2]["error"]


# ── 兩種協定的訊息角色 ────────────────────────────────────────────────────
def test_native_tool_results_go_back_as_role_tool():
    call = {"id": "abc", "name": "run_bash", "command": "ls"}
    m = oa._tool_reply("native", call, "exit=0")
    assert m == {"role": "tool", "tool_call_id": "abc", "content": "exit=0"}


def test_text_tool_results_go_back_as_role_user_with_the_frozen_header():
    """端點只收 user／assistant，所以文字協定的工具結果只能以 user 回灌；
    V/GT 稽核靠凍結表頭把它認回 `tool`。"""
    call = {"id": "", "name": "run_bash", "command": "ls"}
    body = oa.TOOL_RESULT_TEMPLATE.format(
        header=oa.TOOL_RESULT_HEADER, command="ls", rc=0, stdout="", stderr="")
    m = oa._tool_reply("text", call, body)
    assert m["role"] == "user"
    assert m["content"].startswith(oa.TOOL_RESULT_HEADER)
    from ops.gain.harness_vgt_audit import classify_texts_r530
    roles = [r for r, _i, _t in classify_texts_r530(
        {"system": "s", "messages": [m]})]
    assert roles == ["system", "tool"]


def test_wire_keeps_tool_call_id_and_tool_calls():
    a = bn._wire({"role": "assistant", "content": "",
                  "tool_calls": [{"id": "1"}]})
    assert a["tool_calls"] == [{"id": "1"}]
    t = bn._wire({"role": "tool", "content": "x", "tool_call_id": "1"})
    assert t["tool_call_id"] == "1"
    u = bn._wire({"role": "user", "content": "hi"})
    assert "tool_calls" not in u and "tool_call_id" not in u


# ── 協定 dispatch 走得通（離線，零網路）────────────────────────────────────
class _FakeNativeBrain:
    """假裝成 `NativeToolBrain`：第一輪叫一次 bash 寫出參考解，第二輪收工。"""

    tool_protocol = "native"

    def __init__(self, source: str) -> None:
        self.source = source
        self.calls = 0

    def propose(self, messages, *, system, meta=None, role="r530"):
        self.calls += 1
        usage = {"prompt_tokens": 100, "completion_tokens": 50,
                 "total_tokens": 150}
        wrote = any(m.get("role") == "tool" for m in messages)
        if not wrote:
            raw = [{"id": "c1", "type": "function",
                    "function": {"name": "run_bash", "arguments": json.dumps(
                        {"command": "cat > solution.py <<'R530EOF'\n"
                                    + self.source + "\nR530EOF"})}}]
            return {"text": "", "tool_calls": bn._normalise_tool_calls(raw),
                    "usage": usage, "finish_reason": "tool_calls",
                    "raw": {"tool_calls": raw}}
        return {"text": "Done.", "tool_calls": [], "usage": usage,
                "finish_reason": "stop", "raw": {}}


def test_native_protocol_runs_a_whole_cell(tmp_path):
    task = taskmod.load_task("ow_01_csvjson")
    good = (task["gauge_dir"] / "good.py").read_text(encoding="utf-8")
    paths = oa.CellPaths(
        template_dir=task["template_dir"], visible_dir=task["visible_dir"],
        hidden_dir=task["hidden_dir"], cell_dir=tmp_path / "cell",
        verify_root=tmp_path / "_verify", ws_archive_dir=tmp_path / "ws")
    book, ident = Logbook(), Identity.generate()
    row = oa.run_cell(task, _FakeNativeBrain(good), arm="A-GATE",
                      seed="smoke-native", paths=paths,
                      sandbox=sb.NoneSandbox(),
                      calls_path=tmp_path / "calls.jsonl",
                      book=book, ident=ident)
    assert row["tool_protocol"] == "native"
    assert row["accepted"] is True and row["stop_reason"] == "visible_pass"
    assert row["hidden_passed"] == row["hidden_total"] == 14
    assert row["deliv"] is True
    assert row["tool_calls"] == 1
    # 兩個分量分開落盤（多輪迴圈的 prompt 會重送，混在一起看不出來）
    assert row["prompt_tokens"] > 0 and row["completion_tokens"] > 0
    assert row["tokens"] == row["prompt_tokens"] + row["completion_tokens"]


def test_unknown_tool_is_answered_not_crashed(tmp_path):
    class _BadToolBrain(_FakeNativeBrain):
        """第一輪叫一個不存在的工具，第二輪才好好寫檔，第三輪收工。"""

        def propose(self, messages, *, system, meta=None, role="r530"):
            self.calls += 1
            if self.calls == 1:
                raw = [{"id": "z", "function": {"name": "run_python",
                                                "arguments": "{}"}}]
                return {"text": "", "tool_calls": bn._normalise_tool_calls(raw),
                        "usage": {"total_tokens": 10},
                        "finish_reason": "tool_calls", "raw": {"tool_calls": raw}}
            if self.calls == 2:
                raw = [{"id": "c1", "type": "function",
                        "function": {"name": "run_bash", "arguments": json.dumps(
                            {"command": "cat > solution.py <<'R530EOF'\n"
                                        + self.source + "\nR530EOF"})}}]
                return {"text": "", "tool_calls": bn._normalise_tool_calls(raw),
                        "usage": {"total_tokens": 10},
                        "finish_reason": "tool_calls", "raw": {"tool_calls": raw}}
            return {"text": "Done.", "tool_calls": [],
                    "usage": {"total_tokens": 10},
                    "finish_reason": "stop", "raw": {}}

    task = taskmod.load_task("ow_02_ratelimit")
    good = (task["gauge_dir"] / "good.py").read_text(encoding="utf-8")
    paths = oa.CellPaths(
        template_dir=task["template_dir"], visible_dir=task["visible_dir"],
        hidden_dir=task["hidden_dir"], cell_dir=tmp_path / "cell",
        verify_root=tmp_path / "_verify", ws_archive_dir=tmp_path / "ws")
    row = oa.run_cell(task, _BadToolBrain(good), arm="A-SOLO",
                      seed="smoke-bad", paths=paths, sandbox=sb.NoneSandbox(),
                      calls_path=tmp_path / "calls.jsonl")
    assert row["accepted"] is True
    body = (tmp_path / "calls.jsonl").read_text(encoding="utf-8")
    assert "unknown tool" in body, "叫錯工具要落盤，不是靜靜吞掉"


def test_tool_protocols_are_a_closed_set():
    assert bn.TOOL_PROTOCOLS == ("native", "text")
    from ops.gain.r530.run_r530 import main as run_main
    with pytest.raises(SystemExit):
        run_main(["--out", "runs/_smoke/x", "--seed", "smoke-x",
                  "--backend", "none", "--smoke", "--tool-protocol", "nope"])


def test_smoke_budget_requires_smoke():
    from ops.gain.r530.run_r530 import main as run_main
    with pytest.raises(SystemExit) as e:
        run_main(["--out", "runs/g_r530_real", "--decision", "x.md",
                  "--seed", "g-r530-s1", "--backend", "none", "--smoke-budget"])
    assert "--smoke-budget" in str(e.value), (
        "這一條要排在 DECISION 閘門**之前**：它是參數一致性，"
        "不該被另一個閘門的訊息蓋掉")


def test_frozen_budget_constant_is_untouched_by_the_smoke_profile():
    """冒煙預算是一份**替代品**，不是對凍結常數的修改——原始碼裡的值不准變。"""
    import ast
    src = (ROOT / "ops" / "gain" / "r530" / "openwork_arms.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    node = next(n for n in tree.body
                if isinstance(n, ast.Assign)
                and getattr(n.targets[0], "id", None) == "OPENWORK_BUDGET")
    # 逐鍵讀字面值：`gate_test_timeout_s` 綁的是一個名字不是常數，
    # 整份 literal_eval 會炸——炸掉會讓這條防呆變成「跳過」。
    frozen = {k.value: v.value for k, v in zip(node.value.keys, node.value.values)
              if isinstance(v, ast.Constant)}
    # Fable 2026-09-14（第二次裁決）：三臂上限相同、實際用量各自落盤。
    # `A-CONF` 三份 × 每份 24 通 ＝ 72 ＝ 整格上限。
    assert frozen["max_model_calls"] == 72
    assert frozen["max_calls_per_attempt"] == 24
    assert frozen["max_conf_attempts"] == 3
    assert frozen["max_completion_tokens"] == 120_000
    assert frozen["max_context_tokens"] == 200_000
    assert frozen["max_wall_s"] == 7_200
    assert frozen["max_gate_rounds"] == 5
    assert (frozen["max_conf_attempts"] * frozen["max_calls_per_attempt"]
            == frozen["max_model_calls"]), (
        "三份的配額加起來要等於整格上限，否則「上限相同」只是字面上相同")
    assert "max_tokens" not in frozen, (
        "舊的 total_tokens 上限要整個拿掉，不是留著當備用——"
        "留著會讓「用哪一個」變成一個可以事後選的東西")
