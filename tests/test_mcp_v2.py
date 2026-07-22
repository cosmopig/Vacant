"""工具面 v2（12 §3）測試：直接呼叫 mcp_server 的純函式實作（不跑 MCP server 本體）。

策略：monkeypatch 模組的 `_eco` 回傳一個真 Ecosystem（tmp root ＋ 假腦），驗各工具
回傳字串內容；error path 用「沒設 VACANT_MCP_MODEL」驗 delegate/residents 回 error JSON。
"""
from __future__ import annotations

import json

from vacant import mcp_server
from vacant.ecosystem import Ecosystem
from vacant.receipt import sha256_canonical


class FakeBrain:
    name = "fake"

    def generate(self, prompt: str) -> str:
        return "```python\ndef solve(s):\n    return s[::-1]\n```"


class WrongBrain:
    name = "wrong"

    def generate(self, prompt: str) -> str:
        return "def solve(s):\n    return s"


# run_python check：solve 必須把字串反轉
TESTS = {"type": "run_python", "code": "assert solve('abc') == 'cba'"}


def _fake_eco(tmp_path):
    return Ecosystem(tmp_path / "eco", FakeBrain())


def test_delegate_returns_answer_trustcard_and_task_id(tmp_path, monkeypatch):
    eco = _fake_eco(tmp_path)
    monkeypatch.setattr(mcp_server, "_eco", lambda: eco)

    out = mcp_server._delegate_impl("reverse a string", TESTS)
    # 答案（反轉的 solve code）
    assert "def solve" in out
    # 三行信任狀渲染的特徵（trust on 預設）
    assert "trust card" in out
    assert "交付" in out and "peer 通過" in out and "鏈頭" in out
    # task_id 尾巴
    assert "task_id=" in out
    tid = out.split("task_id=")[-1].strip()
    assert len(tid) == 12


def test_trust_card_impl_full_json(tmp_path, monkeypatch):
    eco = _fake_eco(tmp_path)
    monkeypatch.setattr(mcp_server, "_eco", lambda: eco)
    out = mcp_server._delegate_impl("reverse", TESTS)
    tid = out.split("task_id=")[-1].strip()

    card = json.loads(mcp_server._trust_card_impl(tid))
    assert card["task_id"] == tid
    assert "deliverer" in card and "host_sig" in card

    missing = json.loads(mcp_server._trust_card_impl("deadbeef0000"))
    assert "error" in missing


def test_receipt_impl_full_json(tmp_path, monkeypatch):
    eco = _fake_eco(tmp_path)
    monkeypatch.setattr(mcp_server, "_eco", lambda: eco)
    out = mcp_server._delegate_impl("reverse", TESTS)
    request_id = out.split("signed_receipt=", 1)[1].splitlines()[0]
    bundle = json.loads(mcp_server._receipt_impl(request_id))
    receipt = bundle["receipt"]
    assert receipt["request_id"] == request_id
    assert receipt["verified"] is True
    assert "answer_sha256" in receipt and "sig" in receipt
    assert bundle["trust_card"]["task_id"] == receipt["task_id"]
    assert "error" in json.loads(mcp_server._receipt_impl("../../identity.key"))


def test_receipt_lookup_keeps_request_specific_card_for_repeated_task(tmp_path, monkeypatch):
    eco = _fake_eco(tmp_path)
    monkeypatch.setattr(mcp_server, "_eco", lambda: eco)
    first = mcp_server._delegate_impl("same reverse task", TESTS)
    first_id = first.split("signed_receipt=", 1)[1].splitlines()[0]
    second = mcp_server._delegate_impl("same reverse task", TESTS)
    second_id = second.split("signed_receipt=", 1)[1].splitlines()[0]
    assert first_id != second_id
    first_bundle = json.loads(mcp_server._receipt_impl(first_id))
    assert sha256_canonical(first_bundle["trust_card"]) == \
        first_bundle["receipt"]["trust_card_sha256"]


def test_residents_impl_shows_flags(tmp_path, monkeypatch):
    eco = _fake_eco(tmp_path)
    monkeypatch.setattr(mcp_server, "_eco", lambda: eco)
    out = mcp_server._residents_impl()
    # 表頭 + 每個 roster 名字
    assert "credit" in out and "flags" in out
    for name in eco.residents:
        assert name in out
    # 新生態未觀測：INSUFFICIENT_DATA / PROBATION 如實顯示
    assert "INSUFFICIENT_DATA" in out
    assert "PROBATION" in out


def test_scoreboard_impl(tmp_path, monkeypatch):
    eco = _fake_eco(tmp_path)
    monkeypatch.setattr(mcp_server, "_eco", lambda: eco)
    mcp_server._delegate_impl("reverse", TESTS)
    out = mcp_server._scoreboard_impl()
    assert "trust OFF" in out and "trust ON" in out
    assert "paired_delta" in out


def test_report_impl(tmp_path, monkeypatch):
    eco = _fake_eco(tmp_path)
    monkeypatch.setattr(mcp_server, "_eco", lambda: eco)
    # 真交付的 task_id → 受理
    out = mcp_server._delegate_impl("reverse", TESTS)
    tid = out.rsplit("task_id=", 1)[-1].strip()
    ack = json.loads(mcp_server._report_impl(tid, "FAIL", evidence="bad"))
    assert ack["ack"] is True
    assert ack["verdict"] == "FAIL"
    # 不存在的 task_id → 拒收（無驗簽仲裁通道的下界防線：不受理無中生有的指控）
    rej = json.loads(mcp_server._report_impl("deadbeef0000", "FAULT"))
    assert rej["ack"] is False and "error" in rej


def test_delegate_error_path_without_model(tmp_path, monkeypatch):
    # 沒設 VACANT_MCP_MODEL 且未 monkeypatch _eco：delegate 回 error JSON，不拋、不用假腦
    monkeypatch.setattr(mcp_server, "_ECO", None)
    monkeypatch.delenv("VACANT_MCP_MODEL", raising=False)
    out = mcp_server._delegate_impl("anything", TESTS)
    err = json.loads(out)
    assert "error" in err
    assert "VACANT_MCP_MODEL" in err["error"]


def test_delegate_is_fail_closed_when_all_attempts_fail(tmp_path, monkeypatch):
    eco = Ecosystem(tmp_path / "eco", WrongBrain())
    monkeypatch.setattr(mcp_server, "_eco", lambda: eco)
    out = json.loads(mcp_server._delegate_impl("reverse", TESTS, attempts=2))
    assert "error" in out
    assert "did not pass" in out["error"]


def test_fastmcp_registers_product_tools_and_attempt_schema():
    tools = {tool.name: tool for tool in mcp_server.mcp._tool_manager.list_tools()}
    assert {"delegate", "trust_card", "receipt", "residents", "report", "scoreboard"} <= set(tools)
    attempts = tools["delegate"].parameters["properties"]["attempts"]
    assert attempts["default"] == 3 and attempts["type"] == "integer"


def test_residents_error_path_without_model(monkeypatch):
    monkeypatch.setattr(mcp_server, "_ECO", None)
    monkeypatch.delenv("VACANT_MCP_MODEL", raising=False)
    out = mcp_server._residents_impl()
    assert "error" in json.loads(out)
