"""可觀測性：MCP tee-proxy 原樣轉送並側錄、verify-fix 迴圈可回呼、trace 可渲染。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

_ECHO_SERVER = (
    "import sys\n"
    "for line in sys.stdin:\n"
    "    sys.stdout.write('{\"jsonrpc\": \"2.0\", \"id\": 1, \"result\": "
    "{\"content\": [{\"type\": \"text\", \"text\": \"pong\"}]}}\\n')\n"
    "    sys.stdout.flush()\n"
)


def test_tee_proxy_relays_and_logs_both_directions(tmp_path):
    echo = tmp_path / "echo.py"
    echo.write_text(_ECHO_SERVER)
    log = tmp_path / "wire.jsonl"
    req = ('{"jsonrpc": "2.0", "id": 1, "method": "tools/call", '
           '"params": {"name": "verify_fix", "arguments": {"prompt": "p"}}}\n')
    r = subprocess.run(
        [sys.executable, "-m", "vacant.mcp_trace", str(log), "--", sys.executable, str(echo)],
        input=req.encode(), capture_output=True, timeout=30,
        cwd=str(_ROOT), env={**os.environ, "PYTHONPATH": str(_ROOT)},
    )
    assert b"pong" in r.stdout                       # 子行程回應原樣被轉送出去（透明）
    recs = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]
    dirs = {rr.get("dir") for rr in recs}
    assert "hermes->vacant" in dirs and "vacant->hermes" in dirs   # 雙向都側錄到
    req_rec = next(rr for rr in recs if rr.get("dir") == "hermes->vacant" and "msg" in rr)
    assert req_rec["msg"]["params"]["name"] == "verify_fix"        # 確實錄到呼叫內容


def test_on_step_fires_fail_then_pass():
    from vacant.agent import Vacant

    class FailThenPass:
        name = "ftp"

        def __init__(self) -> None:
            self.n = 0

        def generate(self, prompt: str) -> str:
            self.n += 1
            return "RIGHT" if self.n >= 2 else "WRONG"

    seen: list[tuple[int, bool]] = []
    v = Vacant(FailThenPass(), k=3)
    r = v.solve("q", lambda a: a == "RIGHT", on_step=lambda i, a, ok: seen.append((i, ok)))
    assert seen == [(1, False), (2, True)]           # 觀測到「先錯後對」的迴圈
    assert r.verified and r.calls == 2


def test_trace_renderer_detects_vacant_call(tmp_path, capsys):
    from vacant.cli import cmd_trace

    log = tmp_path / "wire.jsonl"
    rows = [
        {"t": "00:00:01", "dir": "hermes->vacant", "msg": {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "mcp_vacant_verify_fix",
                       "arguments": {"prompt": "reverse hello",
                                     "check": {"type": "equals", "value": "olleh"}}}}},
        {"t": "00:00:03", "dir": "vacant->hermes", "msg": {
            "jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"type": "text", "text": "{\"verified\": true, \"calls\": 2}"}]}}},
        {"t": "00:00:03", "tool": "verify_fix", "check": "equals",
         "attempts": [{"attempt": 1, "passed": False}, {"attempt": 2, "passed": True}],
         "calls": 2, "verified": True},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    rc = cmd_trace(argparse.Namespace(file=str(log)))
    out = capsys.readouterr().out
    assert rc == 0
    assert "verify_fix" in out
    assert "= 1 次" in out          # 偵測到 1 次 vacant 呼叫
    assert "#1✗ #2✓" in out         # 迴圈逐步：第1次失敗、第2次通過


# ---------------------------------------------------------------------------
# Adoption-state classifier unit tests (HERMES-observability)
# ---------------------------------------------------------------------------

from vacant.mcp_trace import analyze_adoption


def _mk(dir_: str, method: str, mid: int | None = None, params: dict | None = None,
        result: dict | None = None, error: dict | None = None) -> dict:
    """建立一條 trace record（簡化版，不含時間戳）。"""
    rec: dict = {"dir": dir_, "msg": {"jsonrpc": "2.0", "method": method}}
    if mid is not None:
        rec["msg"]["id"] = mid
    if params is not None:
        rec["msg"]["params"] = params
    if result is not None:
        rec["msg"]["result"] = result
    if error is not None:
        rec["msg"]["error"] = error
    return rec


# 1. infra_void：空記錄
def test_adoption_infra_void_empty():
    r = analyze_adoption([])
    assert r["state"] == "infra_void"
    assert r["consideration"] == "unobservable"
    assert r["evidence"]["discovery_request"] == []


# 2. infra_void：所有行都是無效 JSON（以 dict 表示，msg 不存在）
def test_adoption_infra_void_all_invalid():
    records = [{"dir": "hermes->vacant"}, {"raw": "garbage"}]
    r = analyze_adoption(records)
    assert r["state"] == "infra_void"


# 3. not_observed：只有 initialize handshake，沒有 tools/list（initialize 不算 discovery）
def test_adoption_not_observed_no_discovery():
    records = [
        _mk("hermes->vacant", "initialize", mid=0),
        _mk("vacant->hermes", "initialize", mid=0, result={"protocolVersion": 1}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "not_observed"
    # discovery 應為空（只有 initialize，沒有 tools/list）
    assert r["evidence"]["discovery_request"] == []


# 4. discovered_not_selected：有 tools/list + reply，但沒有 vacant tools/call
def test_adoption_discovered_not_selected():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={
            "tools": [{"name": "verify_fix"}, {"name": "delegate"}]
        }),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "discovered_not_selected"


# 5. selected_failed：有 tools/call，但回覆是 error
def test_adoption_selected_failed_with_error():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1, params={"name": "list"}),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}]}),
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=2, error={"code": -32603, "message": "internal error"}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "selected_failed"


# 6. selected_failed：有 tools/call，但完全沒有回覆（missing reply）
def test_adoption_selected_failed_no_reply():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}]}),
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "delegate", "arguments": {}}),
        # 沒有 vacant->hermes 回覆 id=2
    ]
    r = analyze_adoption(records)
    assert r["state"] == "selected_failed"


# 7. adopted：有 tools/call + 成功 result
def test_adoption_adopted():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}]}),
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=2, result={
            "content": [{"type": "text", "text": '{"verified": true}'}]
        }),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "adopted"


# 8. adopted：多個 tools/call 都有成功回覆
def test_adoption_adopted_multiple():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}, {"name": "trust_card"}]}),
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": [{"type": "text", "text": "ok"}]}),
        _mk("hermes->vacant", "tools/call", mid=3, params={"name": "trust_card", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=3, result={"content": [{"type": "text", "text": "score: 5"}]}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "adopted"


# 9. evidence 包含正確的索引
def test_adoption_evidence_indices():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),       # idx 0
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": []}),  # idx 1: empty discovery
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix"}),  # idx 2
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": []}),  # idx 3
    ]
    r = analyze_adoption(records)
    assert r["state"] == "infra_void"  # empty tools list → infra_void
    assert r["evidence"]["discovery_request"] == [0]
    assert r["evidence"]["discovery_reply"] == [1]
    assert r["evidence"]["selection"] == [2]
    assert r["evidence"]["reply_ok"] == [3]
    assert r["evidence"]["anomaly"] == [1]
    assert r["consideration"] == "unobservable"


# 10. consideration 固定為 unobservable
def test_adoption_consideration_unobservable():
    records = [_mk("hermes->vacant", "tools/list", mid=1)]
    r = analyze_adoption(records)
    assert r["consideration"] == "unobservable"


# 11. 非 vacant 工具不應被視為 selection
def test_adoption_non_vacant_tool_ignored():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}, {"name": "external_api"}]}),
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "external_api", "arguments": {}}),  # 非 vacant
    ]
    r = analyze_adoption(records)
    assert r["state"] == "discovered_not_selected"


# 12. tools/list 回覆中沒有 vacant 工具，但 Hermes 仍呼叫了 vacant tool（edge case）
def test_adoption_tools_list_no_vacant_but_call_exists():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "other_tool"}]}),
        # Hermes 仍然呼叫了 verify_fix（可能 tools/list 結果有延遲或不同來源）
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": [{"type": "text", "text": "ok"}]}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "infra_void"  # discovery 未公告精確 Vacant tool，證據鏈無效


# 13. empty tools list：tools/list 回覆空清單 → infra_void（無可用工具）
def test_adoption_empty_tools_list():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": []}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "infra_void"  # empty tools list → infra_void (no capabilities advertised)


# 14. mixed parseable/unparseable：部分 record 是 raw string，部分是有效 dict → 不 crash
def test_adoption_mixed_parseable_unparseable():
    records = [
        {"dir": "hermes->vacant", "msg": {"jsonrpc": "2.0", "method": "tools/list", "id": 1}},  # idx 0, parseable
        "this is raw garbage not a dict at all",  # idx 1, non-dict → should be skipped safely
        {"dir": "vacant->hermes", "msg": {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "verify_fix"}]}}},  # idx 2, parseable
    ]
    r = analyze_adoption(records)
    assert r["state"] == "discovered_not_selected"


# 15. tools/call without prior discovery：有 tools/call 但沒有 tools/list → not_observed
def test_adoption_call_without_discovery():
    records = [
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": [{"type": "text", "text": "ok"}]}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "not_observed"


# 16. initialize-only：只有 initialize handshake，沒有 tools/list → not_observed（簡化版）
def test_adoption_initialize_only():
    records = [
        _mk("hermes->vacant", "initialize", mid=0),
        _mk("vacant->hermes", "initialize", mid=0, result={"protocolVersion": 1}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "not_observed"


# 17. raw garbage only：所有行都是非 dict → infra_void
def test_adoption_raw_garbage_only():
    records = ["garbage line 1", "another bad line", {"raw": "partial"}]
    r = analyze_adoption(records)
    assert r["state"] == "infra_void"


# 18. mixed parseable + raw garbage → 不 crash，正確分類為 discovered_not_selected
def test_adoption_mixed_with_garbage():
    records = [
        {"dir": "hermes->vacant", "msg": {"jsonrpc": "2.0", "method": "tools/list", "id": 1}},  # idx 0
        "corrupted data here",  # idx 1, non-dict
        {"dir": "vacant->hermes", "raw": "also corrupted"},  # idx 2, dict but no msg → not parseable
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}]}),  # idx 3
    ]
    r = analyze_adoption(records)
    assert r["state"] == "discovered_not_selected"


# 19. selected_failed：部分 selection 成功、部分失敗 → selected_failed（任一失敗即為 failed）
def test_adoption_mixed_success_failure():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}, {"name": "delegate"}]}),
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": [{"type": "text", "text": "ok"}]}),  # ok
        _mk("hermes->vacant", "tools/call", mid=3, params={"name": "delegate", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=3, error={"code": -32603, "message": "fail"}),  # err
    ]
    r = analyze_adoption(records)
    assert r["state"] == "selected_failed"


# 20. evidence indices with mixed garbage：確認索引正確跳過非 parseable record
def test_adoption_evidence_with_garbage():
    records = [
        {"dir": "hermes->vacant", "msg": {"jsonrpc": "2.0", "method": "tools/list", "id": 1}},  # idx 0, discovery
        "garbage",  # idx 1, skipped
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}]}),  # idx 2
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix"}),  # idx 3, selection
        {"dir": "vacant->hermes"},  # idx 4, dict but no msg → not parseable
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": []}),  # idx 5, reply_ok
    ]
    r = analyze_adoption(records)
    assert r["state"] == "adopted"
    assert r["evidence"]["discovery_request"] == [0]
    assert r["evidence"]["discovery_reply"] == [2]
    assert r["evidence"]["selection"] == [3]
    assert r["evidence"]["reply_ok"] == [5]


# ---------------------------------------------------------------------------
# Paired adoption design: trust_mode wiring & deterministic seed pairing
# ---------------------------------------------------------------------------

from vacant.mcp_trace import generate_wire_traces


def test_paired_adoption_design():
    """配對實驗設計驗證：

    1. trust_config.mode 會寫入每筆 trace record 的 ``_trust_mode`` 欄位。
    2. 同 seed + 同 scenario → 兩臂（on/off）產生結構相同的 trace，僅 _trust_mode 不同。
    3. analyze_adoption() 忽略 _trust_mode，分類結果一致。
    """
    scenarios = ["adopted", "discovered_not_selected", "selected_failed", "not_observed"]

    for scenario in scenarios:
        # --- 產生兩臂 trace（同 seed、不同 trust mode）-------------------------
        traces_on = generate_wire_traces(scenario, seed=42, trust_config={"mode": "on"})
        traces_off = generate_wire_traces(scenario, seed=42, trust_config={"mode": "off"})

        # 1. 每筆 trace 都含 _trust_mode，且值正確
        for rec in traces_on:
            assert "_trust_mode" in rec, f"{scenario}: on-arm record missing _trust_mode"
            assert rec["_trust_mode"] == "on", f"{scenario}: expected 'on', got {rec['_trust_mode']!r}"

        for rec in traces_off:
            assert "_trust_mode" in rec, f"{scenario}: off-arm record missing _trust_mode"
            assert rec["_trust_mode"] == "off", f"{scenario}: expected 'off', got {rec['_trust_mode']!r}"

        # 2. 移除 _trust_mode 後兩臂 trace 結構相同（配對基礎）
        def _strip_trust(traces: list[dict]) -> list[dict]:
            return [{k: v for k, v in rec.items() if k != "_trust_mode"} for rec in traces]

        assert _strip_trust(traces_on) == _strip_trust(traces_off), (
            f"{scenario}: on/off arms differ beyond _trust_mode"
        )

        # 3. analyze_adoption 忽略 _trust_mode，分類一致
        result_on = analyze_adoption(traces_on)
        result_off = analyze_adoption(traces_off)
        assert result_on["state"] == result_off["state"], (
            f"{scenario}: adoption state differs between on/off arms"
        )

    # 4. 無 trust_config → 不附加 _trust_mode（向後相容）
    traces_no_cfg = generate_wire_traces("adopted", seed=1)
    for rec in traces_no_cfg:
        assert "_trust_mode" not in rec, "without trust_config should not add _trust_mode"

    # 5. 不同 seed → 結構相同但內容可能因隨機而異（僅驗證不 crash）
    traces_s1 = generate_wire_traces("adopted", seed=1)
    traces_s2 = generate_wire_traces("adopted", seed=2)
    assert len(traces_s1) == len(traces_s2), "different seeds should produce same length"


# ---------------------------------------------------------------------------
# Strict discovery evidence contract
# ---------------------------------------------------------------------------

def test_discovery_missing_reply_is_infra_void():
    r = analyze_adoption([_mk("hermes->vacant", "tools/list", mid=7)])
    assert r["state"] == "infra_void"
    assert r["evidence"]["discovery_request"] == [0]
    assert r["evidence"]["discovery_reply"] == []
    assert r["evidence"]["anomaly"] == [0]
    assert r["consideration"] == "unobservable"


def test_discovery_reply_in_wrong_direction_is_infra_void():
    records = [
        _mk("hermes->vacant", "tools/list", mid=7),
        {"dir": "hermes->vacant", "msg": {
            "jsonrpc": "2.0", "id": 7,
            "result": {"tools": [{"name": "verify_fix"}]},
        }},
    ]
    r = analyze_adoption(records)
    assert r["state"] == "infra_void"
    assert r["evidence"]["anomaly"] == [0]


def test_discovery_result_must_be_dict():
    records = [
        _mk("hermes->vacant", "tools/list", mid=7),
        _mk("vacant->hermes", "tools/list", mid=7, result="malformed"),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "infra_void"
    assert r["evidence"]["discovery_reply"] == [1]
    assert r["evidence"]["anomaly"] == [1]


def test_discovery_tools_must_be_list():
    records = [
        _mk("hermes->vacant", "tools/list", mid=7),
        _mk("vacant->hermes", "tools/list", mid=7, result={"tools": "verify_fix"}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "infra_void"
    assert r["evidence"]["anomaly"] == [1]


def test_discovery_requires_exact_vacant_tool():
    records = [
        _mk("hermes->vacant", "tools/list", mid=7),
        _mk("vacant->hermes", "tools/list", mid=7, result={
            "tools": [{"name": "prefix_verify_fix_suffix"}, {"name": "other_tool"}],
        }),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "infra_void"
    assert r["evidence"]["anomaly"] == [1]


def test_discovery_full_success_has_six_evidence_groups():
    records = [
        _mk("hermes->vacant", "tools/list", mid=7),
        _mk("vacant->hermes", "tools/list", mid=7, result={
            "tools": [{"name": "verify_fix"}, {"name": "other_tool"}],
        }),
        _mk("hermes->vacant", "tools/call", mid=8, params={"name": "verify_fix"}),
        _mk("vacant->hermes", "tools/call", mid=8, result={"content": []}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "adopted"
    assert r["consideration"] == "unobservable"
    assert set(r["evidence"]) == {
        "discovery_request", "discovery_reply", "selection",
        "reply_ok", "reply_err", "anomaly",
    }
    assert r["evidence"] == {
        "discovery_request": [0], "discovery_reply": [1],
        "selection": [2], "reply_ok": [3], "reply_err": [], "anomaly": [],
    }


# ---------------------------------------------------------------------------
# Strict selection / execution contract
# ---------------------------------------------------------------------------

def _valid_discovery() -> list[dict]:
    return [
        _mk("hermes->vacant", "tools/list", mid=101),
        _mk("vacant->hermes", "tools/list", mid=101, result={
            "tools": [{"name": "verify_fix"}, {"name": "mcp_vacant_delegate"}],
        }),
    ]


def test_selection_rejects_arbitrary_vacant_substring():
    records = _valid_discovery() + [
        _mk("hermes->vacant", "tools/call", mid=102,
            params={"name": "prefix_verify_fix_suffix"}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "discovered_not_selected"
    assert r["evidence"]["selection"] == []


def test_selection_accepts_mcp_vacant_prefix_with_exact_suffix():
    records = _valid_discovery() + [
        _mk("hermes->vacant", "tools/call", mid=102,
            params={"name": "mcp_vacant_verify_fix"}),
        _mk("vacant->hermes", "tools/call", mid=102, result={"content": []}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "adopted"
    assert r["evidence"]["selection"] == [2]
    assert r["evidence"]["reply_ok"] == [3]


def test_selection_rejects_slash_and_dot_aliases():
    for alias in ("vacant/verify_fix", "vacant.verify_fix", "mcp_vacant_verify_fix_extra"):
        records = _valid_discovery() + [
            _mk("hermes->vacant", "tools/call", mid=102, params={"name": alias}),
        ]
        r = analyze_adoption(records)
        assert r["state"] == "discovered_not_selected", alias
        assert r["evidence"]["selection"] == []


def test_execution_jsonrpc_error_is_selected_failed():
    records = _valid_discovery() + [
        _mk("hermes->vacant", "tools/call", mid=102, params={"name": "verify_fix"}),
        _mk("vacant->hermes", "tools/call", mid=102,
            error={"code": -32603, "message": "failure"}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "selected_failed"
    assert r["evidence"]["reply_err"] == [3]


def test_execution_missing_reply_is_selected_failed_and_anomalous():
    records = _valid_discovery() + [
        _mk("hermes->vacant", "tools/call", mid=102, params={"name": "verify_fix"}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "selected_failed"
    assert r["evidence"]["anomaly"] == [2]


def test_execution_result_is_error_true_is_selected_failed():
    records = _valid_discovery() + [
        _mk("hermes->vacant", "tools/call", mid=102, params={"name": "verify_fix"}),
        _mk("vacant->hermes", "tools/call", mid=102,
            result={"isError": True, "content": [{"type": "text", "text": "failed"}]}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "selected_failed"
    assert r["evidence"]["reply_err"] == [3]
    assert r["evidence"]["reply_ok"] == []


def test_execution_wrong_direction_reply_is_selected_failed():
    records = _valid_discovery() + [
        _mk("hermes->vacant", "tools/call", mid=102, params={"name": "verify_fix"}),
        _mk("hermes->vacant", "tools/call", mid=102, result={"content": []}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "selected_failed"
    assert r["evidence"]["anomaly"] == [2]


def test_execution_malformed_result_is_selected_failed_and_anomalous():
    records = _valid_discovery() + [
        _mk("hermes->vacant", "tools/call", mid=102, params={"name": "verify_fix"}),
        _mk("vacant->hermes", "tools/call", mid=102, result="malformed"),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "selected_failed"
    assert r["evidence"]["reply_err"] == [3]
    assert r["evidence"]["anomaly"] == [3]


def test_execution_success_requires_same_id_correct_direction_result():
    records = _valid_discovery() + [
        _mk("hermes->vacant", "tools/call", mid=102, params={"name": "verify_fix"}),
        _mk("vacant->hermes", "tools/call", mid=999, result={"content": []}),
        _mk("vacant->hermes", "tools/call", mid=102,
            result={"isError": False, "content": []}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "adopted"
    assert r["evidence"]["reply_ok"] == [4]
    assert r["evidence"]["reply_err"] == []
    assert r["evidence"]["anomaly"] == []


def test_real_wire_20260709_delegate_chain_is_adopted():
    """去敏後保留真實 wire.jsonl 的方向、method、id、tools 與 envelope。"""
    records = [
        {"dir": "proxy", "msg": {}},
        _mk("hermes->vacant", "initialize", mid=0),
        {"dir": "vacant->hermes", "msg": {
            "jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": "2024-11-05"},
        }},
        {"dir": "hermes->vacant", "msg": {
            "jsonrpc": "2.0", "method": "notifications/initialized",
        }},
        _mk("hermes->vacant", "tools/list", mid=1),
        {"dir": "vacant->hermes", "msg": {
            "jsonrpc": "2.0", "id": 1, "result": {"tools": [
                {"name": "delegate"}, {"name": "trust_card"},
                {"name": "residents"}, {"name": "report"},
                {"name": "scoreboard"}, {"name": "verify_fix"},
            ]},
        }},
        _mk("hermes->vacant", "tools/call", mid=2,
            params={"name": "delegate", "arguments": {}}),
        {"dir": "vacant->hermes", "msg": {
            "jsonrpc": "2.0", "id": 2,
            "result": {"isError": False, "content": [{"type": "text"}]},
        }},
    ]
    r = analyze_adoption(records)
    assert r["state"] == "adopted"
    assert r["evidence"] == {
        "discovery_request": [4], "discovery_reply": [5],
        "selection": [6], "reply_ok": [7], "reply_err": [], "anomaly": [],
    }
    assert r["consideration"] == "unobservable"


def _session(tool="verify_fix", call_id=2, include_reply=True, prompts=False):
    rows = [
        {"dir": "proxy", "msg": {}},
        _mk("hermes->vacant", "initialize", mid=0),
        _mk("vacant->hermes", "initialize", mid=0, result={"protocolVersion": "x"}),
        _mk("hermes->vacant", "notifications/initialized"),
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1,
            result={"tools": [{"name": tool}]}),
    ]
    if prompts:
        rows.extend([
            _mk("hermes->vacant", "prompts/list", mid=9),
            _mk("vacant->hermes", "prompts/list", mid=9, result={"prompts": []}),
        ])
    rows.append(_mk("hermes->vacant", "tools/call", mid=call_id,
                    params={"name": tool, "arguments": {}}))
    if include_reply:
        rows.append(_mk("vacant->hermes", "tools/call", mid=call_id,
                        result={"isError": False, "content": []}))
    return rows


def test_batch_two_adopted_sessions_keep_separate_same_ids():
    from vacant.mcp_trace import analyze_adoption_sessions

    first = _session("delegate")
    second = _session("scoreboard")
    reports = analyze_adoption_sessions(first + second)
    assert [r["state"] for r in reports] == ["adopted", "adopted"]
    assert reports[0]["source_range"] == [0, 7]
    assert reports[1]["source_range"] == [8, 15]
    assert reports[0]["evidence"]["selection"] == [6]
    assert reports[1]["evidence"]["selection"] == [14]


def test_split_uses_repeated_initialize_without_proxy():
    from vacant.mcp_trace import analyze_adoption_sessions

    first = _session()[1:]
    second = _session("trust_card")[1:]
    reports = analyze_adoption_sessions(first + second)
    assert [r["source_range"] for r in reports] == [[0, 6], [7, 13]]
    assert [r["state"] for r in reports] == ["adopted", "adopted"]


def test_batch_does_not_pair_reply_across_session_boundary():
    from vacant.mcp_trace import analyze_adoption_sessions

    first = _session(include_reply=False)
    second = _session()[:-2]
    second.append(_mk("vacant->hermes", "tools/call", mid=2,
                      result={"isError": False, "content": []}))
    reports = analyze_adoption_sessions(first + second)
    assert reports[0]["state"] == "selected_failed"
    assert reports[0]["evidence"]["reply_ok"] == []
    assert reports[1]["state"] == "discovered_not_selected"


def test_batch_truncated_tail_is_its_own_infra_void_session():
    from vacant.mcp_trace import analyze_adoption_sessions

    tail = [
        {"dir": "proxy", "msg": {}},
        _mk("hermes->vacant", "initialize", mid=0),
        _mk("hermes->vacant", "tools/list", mid=1),
    ]
    reports = analyze_adoption_sessions(_session() + tail)
    assert [r["state"] for r in reports] == ["adopted", "infra_void"]
    assert reports[1]["source_range"] == [8, 10]


def test_split_ignores_garbage_before_first_proxy():
    from vacant.mcp_trace import analyze_adoption_sessions

    reports = analyze_adoption_sessions([{"junk": True}, "bad"] + _session())
    assert len(reports) == 1
    assert reports[0]["source_range"] == [2, 9]
    assert reports[0]["state"] == "adopted"


def test_batch_allows_prompts_list_inside_session():
    from vacant.mcp_trace import analyze_adoption_sessions

    reports = analyze_adoption_sessions(_session("verify_fix", prompts=True))
    assert reports[0]["state"] == "adopted"
    assert reports[0]["evidence"]["selection"] == [8]
    assert reports[0]["evidence"]["reply_ok"] == [9]


def test_split_empty_input_returns_no_sessions():
    from vacant.mcp_trace import analyze_adoption_sessions, split_mcp_sessions

    assert split_mcp_sessions([]) == []
    assert analyze_adoption_sessions([]) == []


# ---------------------------------------------------------------------------
# Friction taxonomy v2 (HERMES-adoption-friction-v2)：把 analyze_adoption()
# 的粗粒度 state 分解成 discovery / selection / argument_construction /
# execution / task_outcome 五個獨立階段。只依賴 wire trace 的結構性證據，
# 不解析或推論訊息內容的語意正確性（不窺看答案）。Phase-1 20/20 的
# state / evidence / consideration 判準凍結不變——本節測試只驗證新增的
# stages 分解視圖，並確認它不會覆寫既有分類。
# ---------------------------------------------------------------------------

from vacant.mcp_trace import analyze_friction, propose_v2_interventions


def test_friction_discovered_not_selected_stage_breakdown():
    """implicit 風格 T05/T06 固定案例：發現成功、未選用。"""
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={
            "tools": [{"name": "verify_fix"}, {"name": "delegate"}]
        }),
    ]
    r = analyze_friction(records)
    assert r["state"] == "discovered_not_selected"          # Phase-1 判準不變
    assert r["stages"] == {
        "discovery": "valid",
        "selection": "absent",
        "argument_construction": "not_applicable",
        "execution": "not_applicable",
        "task_outcome": "unobservable",
    }
    assert r["consideration"] == "unobservable"


def test_friction_selected_failed_one_error_one_success_stage_breakdown():
    """explicit 風格 T08 固定案例：一錯一成功呼叫，state 仍保留 selected_failed。"""
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={
            "tools": [{"name": "verify_fix"}, {"name": "delegate"}]
        }),
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": [{"type": "text", "text": "ok"}]}),
        _mk("hermes->vacant", "tools/call", mid=3, params={"name": "delegate", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=3, error={"code": -32603, "message": "fail"}),
    ]
    r = analyze_friction(records)
    assert r["state"] == "selected_failed"                  # 凍結判準：一錯一成功仍為 selected_failed
    assert r["stages"]["discovery"] == "valid"
    assert r["stages"]["selection"] == "made"
    assert r["stages"]["argument_construction"] == "empty"
    assert r["stages"]["execution"] == "error"
    assert r["stages"]["task_outcome"] == "unobservable"


def test_friction_adopted_with_arguments_present():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}]}),
        _mk("hermes->vacant", "tools/call", mid=2, params={
            "name": "verify_fix",
            "arguments": {"prompt": "reverse hello"},
        }),
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": []}),
    ]
    r = analyze_friction(records)
    assert r["state"] == "adopted"
    assert r["stages"] == {
        "discovery": "valid",
        "selection": "made",
        "argument_construction": "present",
        "execution": "ok",
        "task_outcome": "unobservable",
    }


def test_friction_not_observed_discovery_absent():
    records = [
        _mk("hermes->vacant", "initialize", mid=0),
        _mk("vacant->hermes", "initialize", mid=0, result={"protocolVersion": 1}),
    ]
    r = analyze_friction(records)
    assert r["state"] == "not_observed"
    assert r["stages"]["discovery"] == "absent"
    assert r["stages"]["selection"] == "not_applicable"
    assert r["stages"]["execution"] == "not_applicable"
    assert r["stages"]["task_outcome"] == "unobservable"


def test_friction_infra_void_discovery_invalid_when_empty_tools():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": []}),
    ]
    r = analyze_friction(records)
    assert r["state"] == "infra_void"
    assert r["stages"]["discovery"] == "invalid"
    assert r["stages"]["selection"] == "not_applicable"


def test_friction_execution_missing_reply_stage():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}]}),
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix", "arguments": {}}),
        # 沒有回覆
    ]
    r = analyze_friction(records)
    assert r["state"] == "selected_failed"
    assert r["stages"]["execution"] == "missing_reply"


def test_friction_does_not_widen_or_override_frozen_state():
    """analyze_friction() 的 state/evidence/consideration 必須與 analyze_adoption()
    完全一致，只是疊加新的 stages 分解視圖——不得重跑或改寫 Phase-1 判準。"""
    scenarios = ["adopted", "discovered_not_selected", "selected_failed", "not_observed"]
    for scenario in scenarios:
        trace = generate_wire_traces(scenario, seed=7)
        base = analyze_adoption(trace)
        friction = analyze_friction(trace)
        assert friction["state"] == base["state"]
        assert friction["evidence"] == base["evidence"]
        assert friction["consideration"] == base["consideration"]
        assert set(friction["stages"]) == {
            "discovery", "selection", "argument_construction",
            "execution", "task_outcome",
        }


def test_v2_interventions_are_preregistration_schema_only():
    """v2 介入清單必須是聲明式、尚未執行、非因果宣稱的 schema——
    不得把 Phase-1 explicit/implicit 的描述差（如 +10pp）當作因果 effect。"""
    proposals = propose_v2_interventions()
    assert isinstance(proposals, list) and len(proposals) > 0
    valid_stages = {"discovery", "selection", "argument_construction", "execution", "task_outcome"}
    seen_ids = set()
    for item in proposals:
        assert set(item) == {"id", "stage", "hypothesis", "preregistered", "executed", "claim_level"}
        assert item["stage"] in valid_stages
        assert item["preregistered"] is False
        assert item["executed"] is False
        assert item["claim_level"] == "descriptive"
        assert isinstance(item["hypothesis"], str) and item["hypothesis"]
        assert item["id"] not in seen_ids
        seen_ids.add(item["id"])
        assert "effect" not in item
        assert "delta" not in item
