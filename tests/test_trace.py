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
