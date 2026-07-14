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
    assert r["evidence"]["discovery"] == []


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
    assert r["evidence"]["discovery"] == []


# 4. discovered_not_selected：有 tools/list + reply，但沒有 vacant tools/call
def test_adoption_discovered_not_selected():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={
            "tools": [{"name": "verify_fix"}, {"name": "a2a_call"}]
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
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "a2a_call", "arguments": {}}),
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
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}, {"name": "get_reputation"}]}),
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": [{"type": "text", "text": "ok"}]}),
        _mk("hermes->vacant", "tools/call", mid=3, params={"name": "get_reputation", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=3, result={"content": [{"type": "text", "text": "score: 5"}]}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "adopted"


# 9. evidence 包含正確的索引
def test_adoption_evidence_indices():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),       # idx 0
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": []}),  # idx 1
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix"}),  # idx 2
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": []}),  # idx 3
    ]
    r = analyze_adoption(records)
    assert r["state"] == "adopted"
    assert r["evidence"]["discovery"] == [0]
    assert r["evidence"]["selection"] == [2]
    assert r["evidence"]["reply_ok"] == [3]


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
    assert r["state"] == "adopted"  # 只要有 tools/call + reply，就是 adopted


# 13. empty tools list：tools/list 回覆空清單 → discovered_not_selected（有 discovery 但無 vacant tool）
def test_adoption_empty_tools_list():
    records = [
        _mk("hermes->vacant", "tools/list", mid=1),
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": []}),
    ]
    r = analyze_adoption(records)
    assert r["state"] == "discovered_not_selected"


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
        _mk("vacant->hermes", "tools/list", mid=1, result={"tools": [{"name": "verify_fix"}, {"name": "a2a_call"}]}),
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": [{"type": "text", "text": "ok"}]}),  # ok
        _mk("hermes->vacant", "tools/call", mid=3, params={"name": "a2a_call", "arguments": {}}),
        _mk("vacant->hermes", "tools/call", mid=3, error={"code": -32603, "message": "fail"}),  # err
    ]
    r = analyze_adoption(records)
    assert r["state"] == "selected_failed"


# 20. evidence indices with mixed garbage：確認索引正確跳過非 parseable record
def test_adoption_evidence_with_garbage():
    records = [
        {"dir": "hermes->vacant", "msg": {"jsonrpc": "2.0", "method": "tools/list", "id": 1}},  # idx 0, discovery
        "garbage",  # idx 1, skipped
        _mk("hermes->vacant", "tools/call", mid=2, params={"name": "verify_fix"}),  # idx 2, selection
        {"dir": "vacant->hermes"},  # idx 3, dict but no msg → not parseable
        _mk("vacant->hermes", "tools/call", mid=2, result={"content": []}),  # idx 4, reply_ok
    ]
    r = analyze_adoption(records)
    assert r["state"] == "adopted"
    assert r["evidence"]["discovery"] == [0]
    assert r["evidence"]["selection"] == [2]
    assert r["evidence"]["reply_ok"] == [4]
