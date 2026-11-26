"""tests/test_e1_claude.py — E1′ Claude Code agent 模式單元與整合測試（假 claude 二進位、白名單代理、負控制）。"""
from __future__ import annotations

import http.server
import json
import os
import pathlib
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops.e1 import PLAN_SCHEMA, atomic_write_json
from ops.e1.analyze_e1 import analyze_root
from ops.e1.build_code_chains import build_code_chains
from ops.e1.build_doc_chains import build_doc_chains
from ops.e1.negative_controls import run_claude_negative_controls
from ops.e1.netproxy import AllowlistUnixProxy
from ops.e1.run_e1 import (
    CLAUDE_ALLOWED_TOOLS,
    CLAUDE_DISALLOWED_TOOLS,
    E1Runner,
    build_claude_cli_argv,
    load_plan,
    usage_from_claude_log,
)
from ops.e1.selftest import make_synthetic_evalplus


def _unix_exchange(sock_path: pathlib.Path, req: bytes) -> bytes:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect(str(sock_path))
    try:
        s.sendall(req)
        chunks: list[bytes] = []
        while True:
            b = s.recv(4096)
            if not b:
                break
            chunks.append(b)
        return b"".join(chunks)
    finally:
        s.close()


class TestClaudeArgvAndUsage(unittest.TestCase):
    def test_build_claude_cli_argv_flags_and_tools(self) -> None:
        argv = build_claude_cli_argv("claude-haiku-5-5", "Add func foo(x).")
        self.assertEqual(argv[:2], ["claude", "-p"])
        self.assertIn("--output-format", argv)
        self.assertEqual(argv[argv.index("--output-format") + 1], "stream-json")
        self.assertIn("--verbose", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-haiku-5-5")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "bypassPermissions")
        self.assertEqual(argv[argv.index("--tools") + 1], CLAUDE_ALLOWED_TOOLS)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], CLAUDE_ALLOWED_TOOLS)
        self.assertEqual(argv[argv.index("--disallowedTools") + 1], CLAUDE_DISALLOWED_TOOLS)
        for tool in ("Bash", "Read", "Edit", "Write", "Glob", "Grep"):
            self.assertIn(tool, argv[argv.index("--tools") + 1])
        self.assertNotIn("WebFetch", argv[argv.index("--tools") + 1])
        self.assertNotIn("WebSearch", argv[argv.index("--tools") + 1])
        self.assertIn("--no-session-persistence", argv)
        self.assertIn("--strict-mcp-config", argv)
        self.assertIn("--disable-slash-commands", argv)
        self.assertEqual(argv[-2:], ["--", "Add func foo(x)."])

    def test_usage_from_claude_log_stream_json_full(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            lp = pathlib.Path(td) / "agent.log"
            lines = [
                {"type": "system", "subtype": "init", "model": "claude-haiku-5-5"},
                {"type": "assistant", "message": {"id": "msg_1", "model": "claude-haiku-5-5",
                                                  "usage": {"input_tokens": 100, "output_tokens": 20}}},
                {"type": "assistant", "message": {"id": "msg_1", "model": "claude-haiku-5-5",
                                                  "usage": {"input_tokens": 100, "output_tokens": 20}}},
                {"type": "assistant", "message": {"id": "msg_2", "model": "claude-haiku-5-5",
                                                  "usage": {"input_tokens": 150, "output_tokens": 35}}},
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "num_turns": 3,
                    "total_cost_usd": 0.012345,
                    "usage": {
                        "input_tokens": 250,
                        "output_tokens": 55,
                        "cache_creation_input_tokens": 1200,
                        "cache_read_input_tokens": 4500,
                    },
                },
            ]
            lp.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
            u = usage_from_claude_log(lp)
            self.assertEqual(
                u,
                {
                    "calls": 2,
                    "errors": 0,
                    "input": 250,
                    "output": 55,
                    "cache_creation_input_tokens": 1200,
                    "cache_read_input_tokens": 4500,
                    "num_turns": 3,
                    "cost_usd": 0.012345,
                    "final_error": None,
                },
            )

    def test_usage_from_claude_log_rate_limit_or_api_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            lp = pathlib.Path(td) / "agent.log"
            lines = [
                {"type": "system", "subtype": "init"},
                {
                    "type": "assistant",
                    "is_api_error_message": True,
                    "error": "rate_limit",
                    "message": {
                        "id": "err_1",
                        "model": "<synthetic>",
                        "content": [{"type": "text", "text": "You've hit your 5-hour limit"}],
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    },
                },
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": True,
                    "num_turns": 1,
                    "total_cost_usd": 0,
                    "result": "You've hit your 5-hour limit",
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            ]
            lp.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
            u = usage_from_claude_log(lp)
            self.assertIsNotNone(u)
            assert u is not None
            self.assertEqual(u["calls"], 0)
            self.assertEqual(u["errors"], 1)
            self.assertEqual(u["cost_usd"], 0.0)
            self.assertIn("5-hour limit", u["final_error"] or "")

    def test_usage_from_claude_log_partial_timeout_and_non_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            lp = pathlib.Path(td) / "partial.log"
            lp.write_text(
                json.dumps({"type": "system", "subtype": "init"}) + "\n"
                + json.dumps({
                    "type": "assistant",
                    "message": {
                        "id": "m1",
                        "model": "claude-haiku-5-5",
                        "usage": {
                            "input_tokens": 40,
                            "output_tokens": 12,
                            "cache_creation_input_tokens": 300,
                            "cache_read_input_tokens": 500,
                        },
                    },
                }) + "\n",
                encoding="utf-8",
            )
            u = usage_from_claude_log(lp)
            self.assertIsNotNone(u)
            assert u is not None
            self.assertEqual(u["calls"], 1)
            self.assertEqual(u["input"], 40)
            self.assertEqual(u["output"], 12)
            self.assertEqual(u["cache_creation_input_tokens"], 300)
            self.assertEqual(u["cache_read_input_tokens"], 500)
            self.assertIsNone(u["cost_usd"])

            bad = pathlib.Path(td) / "bad.log"
            bad.write_text("segfault before json\n", encoding="utf-8")
            self.assertIsNone(usage_from_claude_log(bad))

    def test_load_plan_claude_mode_without_providers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            cdir = tp / "chains" / "c1"
            cdir.mkdir(parents=True)
            atomic_write_json(cdir / "chain.json", {"chain_id": "c1", "kind": "code"})
            plan_p = tp / "plan.json"
            atomic_write_json(
                plan_p,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "claude_plan",
                    "chains": [str(cdir)],
                    "arms": ["B0"],
                    "model": {"agent": "claude", "model": "claude-haiku-5-5"},
                },
            )
            plan = load_plan(plan_p)
            self.assertEqual(plan["_model"]["agent"], "claude")
            self.assertEqual(plan["_model"]["model"], "claude-haiku-5-5")
            self.assertEqual(plan["_model"]["providers"], ["anthropic"])


class TestAllowlistUnixProxy(unittest.TestCase):
    def test_connect_refuses_non_allowlisted_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            log_p = pathlib.Path(td) / "proxy.jsonl"
            with AllowlistUnixProxy(log_path=log_p) as px:
                r1 = _unix_exchange(px.sock_path, b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
                r2 = _unix_exchange(px.sock_path, b"CONNECT api.anthropic.com:80 HTTP/1.1\r\nHost: api.anthropic.com:80\r\n\r\n")
                r3 = _unix_exchange(px.sock_path, b"CONNECT 1.1.1.1:443 HTTP/1.1\r\nHost: 1.1.1.1:443\r\n\r\n")
            self.assertTrue(r1.startswith(b"HTTP/1.1 403 "))
            self.assertTrue(r2.startswith(b"HTTP/1.1 403 "))
            self.assertTrue(r3.startswith(b"HTTP/1.1 403 "))
            logged = [json.loads(ln) for ln in log_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertEqual(len(logged), 3)
            self.assertEqual([(e["host"], e["port"], e["allowed"], e["status"]) for e in logged], [
                ("example.com", 443, False, 403),
                ("api.anthropic.com", 80, False, 403),
                ("1.1.1.1", 443, False, 403),
            ])

    def test_connect_allows_allowlisted_target_and_counts_bytes(self) -> None:
        # 啟動本機回音 TCP 伺服器模擬白名單上游
        echo_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        echo_srv.bind(("127.0.0.1", 0))
        echo_srv.listen(4)
        echo_port = echo_srv.getsockname()[1]

        def _echo() -> None:
            try:
                conn, _ = echo_srv.accept()
                with conn:
                    data = conn.recv(4096)
                    conn.sendall(b"ECHO:" + data)
            except OSError:
                pass

        th = threading.Thread(target=_echo, daemon=True)
        th.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                log_p = pathlib.Path(td) / "proxy.jsonl"
                with AllowlistUnixProxy(allowed_connect=[("127.0.0.1", echo_port)], log_path=log_p) as px:
                    cli = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    cli.settimeout(5.0)
                    cli.connect(str(px.sock_path))
                    with cli:
                        req = f"CONNECT 127.0.0.1:{echo_port} HTTP/1.1\r\nHost: 127.0.0.1:{echo_port}\r\n\r\n".encode()
                        cli.sendall(req)
                        resp_hdr = cli.recv(4096)
                        self.assertIn(b"200 Connection Established", resp_hdr)
                        cli.sendall(b"hello-tunnel")
                        cli.shutdown(socket.SHUT_WR)
                        echoed = cli.recv(4096)
                        self.assertEqual(echoed, b"ECHO:hello-tunnel")
                th.join(timeout=2.0)
                logged = [json.loads(ln) for ln in log_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
                self.assertEqual(len(logged), 1)
                ev = logged[0]
                self.assertTrue(ev["allowed"])
                self.assertEqual(ev["host"], "127.0.0.1")
                self.assertEqual(ev["port"], echo_port)
                self.assertEqual(ev["bytes_up"], len(b"hello-tunnel"))
                self.assertEqual(ev["bytes_down"], len(b"ECHO:hello-tunnel"))
                self.assertEqual(ev["bytes"], len(b"hello-tunnel") + len(b"ECHO:hello-tunnel"))
        finally:
            echo_srv.close()

    def test_http_forwards_allowed_source_hosts_and_refuses_others(self) -> None:
        class _Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_a: object) -> None:
                pass

            def do_GET(self) -> None:  # noqa: N802
                body = f"OK:{self.headers.get('Host')}:{self.path}".encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        src_port = httpd.server_address[1]
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                log_p = pathlib.Path(td) / "proxy.jsonl"
                with AllowlistUnixProxy(source_server_port=src_port, log_path=log_p) as px:
                    ok_d2 = _unix_exchange(
                        px.sock_path,
                        b"GET http://s01.d2-sources.example/p1.html HTTP/1.1\r\nHost: s01.d2-sources.example\r\n\r\n",
                    )
                    ok_e1 = _unix_exchange(
                        px.sock_path,
                        b"GET http://doc_s16.e1-sources.example/index.html HTTP/1.1\r\nHost: doc_s16.e1-sources.example\r\n\r\n",
                    )
                    bad_ext = _unix_exchange(
                        px.sock_path,
                        b"GET http://example.com/secret HTTP/1.1\r\nHost: example.com\r\n\r\n",
                    )
                    bad_port = _unix_exchange(
                        px.sock_path,
                        b"GET http://s01.d2-sources.example:8080/p1.html HTTP/1.1\r\nHost: s01.d2-sources.example:8080\r\n\r\n",
                    )
                    bad_smuggle = _unix_exchange(
                        px.sock_path,
                        b"GET http://s01.d2-sources.example/p1.html HTTP/1.1\r\nHost: evil.example\r\n\r\n",
                    )
                self.assertIn(b"200 OK", ok_d2)
                self.assertIn(b"OK:s01.d2-sources.example:", ok_d2)
                self.assertIn(b"200 OK", ok_e1)
                self.assertIn(b"OK:doc_s16.e1-sources.example:", ok_e1)
                self.assertTrue(bad_ext.startswith(b"HTTP/1.1 403 "))
                self.assertTrue(bad_port.startswith(b"HTTP/1.1 403 "))
                self.assertTrue(bad_smuggle.startswith(b"HTTP/1.1 400 "))
                logged = [json.loads(ln) for ln in log_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
                self.assertEqual(len(logged), 5)
                self.assertTrue(logged[0]["allowed"] and logged[0]["bytes_down"] > 0)
                self.assertTrue(logged[1]["allowed"] and logged[1]["bytes_down"] > 0)
                self.assertFalse(logged[2]["allowed"])
                self.assertFalse(logged[3]["allowed"])
                self.assertFalse(logged[4]["allowed"])
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestClaudeNegativeControls(unittest.TestCase):
    def test_claude_negative_controls_pass(self) -> None:
        rep = run_claude_negative_controls()
        self.assertTrue(rep["passed"], f"Claude 負控制未通過：{rep}")
        self.assertEqual(rep["leaks"], [])
        self.assertTrue(rep["eval_net_isolated"])
        for k in (
            "work_rw",
            "home_isolated",
            "env_telemetry_disabled",
            "proxy_env_set",
            "claude_home_only_creds",
            "creds_readable",
            "creds_readonly",
        ):
            self.assertTrue(rep["sanity"][k], f"sanity[{k}] failed: {rep['sanity']}")
        for k in (
            "direct_tcp_external_blocked",
            "direct_tcp_host_loopback_blocked",
            "proxy_connect_refused",
            "proxy_http_refused",
            "proxy_logged_refusal",
        ):
            self.assertTrue(rep["net"][k], f"net[{k}] failed: {rep['net']}")

    def test_claude_negative_controls_catch_intentional_leak(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            fake_claude_dir = tp / "host_claude"
            fake_claude_dir.mkdir()
            (fake_claude_dir / ".credentials.json").write_text('{"tok":"ok"}\n', encoding="utf-8")
            leaked_settings = fake_claude_dir / "settings.json"
            leaked_settings.write_text('{"secret":"host"}\n', encoding="utf-8")
            rep = run_claude_negative_controls(
                host_claude_dir=fake_claude_dir,
                extra_worker_binds=[(leaked_settings, str(leaked_settings))],
            )
            self.assertFalse(rep["passed"])
            self.assertTrue(any("settings.json" in lk["name"] for lk in rep["leaks"]))

    def test_claude_negative_controls_cli_exits_zero(self) -> None:
        r = subprocess.run(
            [sys.executable, str(REPO_ROOT / "ops" / "e1" / "negative_controls.py"), "--agent", "claude"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(r.returncode, 0, f"stdout={r.stdout}\nstderr={r.stderr}")
        self.assertIn("PASS", r.stdout)

    def test_runner_refuses_claude_plan_when_negative_controls_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            ep_dir = make_synthetic_evalplus(tp / "ep", n_he=10, n_mbpp=10)
            cdir = tp / "chains"
            build_code_chains(seed=11, n=1, out_dir=cdir, evalplus_dir=ep_dir, min_init=8, max_init=8, verify_sha256=False)
            creds = tp / ".credentials.json"
            creds.write_text('{"fake":true}\n', encoding="utf-8")
            plan_p = tp / "plan.json"
            atomic_write_json(
                plan_p,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "claude_nc_fail",
                    "chains_dir": str(cdir),
                    "arms": ["B0"],
                    "model": {
                        "agent": "claude",
                        "model": "claude-haiku-5-5",
                        "credentials_path": str(creds),
                    },
                    "jobs": 1,
                },
            )
            runner = E1Runner(plan_p, tp / "root", allow_uncommitted=True)
            with mock.patch("ops.e1.run_e1.run_claude_negative_controls", return_value={"passed": False, "leaks": [{"name": "mock"}]}):
                with self.assertRaises(SystemExit) as ctx:
                    runner.run()
            self.assertIn("負控制失敗", str(ctx.exception))


_FAKE_CLAUDE_PY = r"""#!/usr/bin/env python3
import json, os, pathlib, re, sys, urllib.request

# 驗證沙箱隔離環境
assert os.getcwd() == "/work", f"bad cwd: {os.getcwd()}"
assert os.environ.get("HOME") == "/sandbox_home", f"bad HOME: {os.environ.get('HOME')}"
assert os.environ.get("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC") == "1"
assert os.environ.get("DISABLE_TELEMETRY") == "1"
assert os.environ.get("DISABLE_AUTOUPDATER") == "1"
assert os.environ.get("NO_PROXY") == ""
assert os.environ.get("HTTP_PROXY", "").startswith("http://127.0.0.1:")
assert os.environ.get("HTTPS_PROXY") == os.environ.get("HTTP_PROXY")
cdir = pathlib.Path("/sandbox_home/.claude")
assert sorted(os.listdir(cdir)) == [".credentials.json"], f"unexpected .claude entries: {os.listdir(cdir)}"

# 記錄 argv 供宿主端檢查
prompt = sys.argv[-1]
assert "-p" in sys.argv
assert "--output-format" in sys.argv and sys.argv[sys.argv.index("--output-format") + 1] == "stream-json"
assert "--verbose" in sys.argv
assert "--model" in sys.argv and sys.argv[sys.argv.index("--model") + 1] == "claude-haiku-5-5"
assert "--permission-mode" in sys.argv and sys.argv[sys.argv.index("--permission-mode") + 1] == "bypassPermissions"
tools_val = sys.argv[sys.argv.index("--tools") + 1]
assert "WebFetch" not in tools_val and "WebSearch" not in tools_val

sol = pathlib.Path("/work/solution.py")
rep = pathlib.Path("/work/report.md")

if sol.is_file():
    src = sol.read_text(encoding="utf-8")
    m_add = re.search(r"def\s+(synth_(add|mul)_(\d+))\s*\(", prompt)
    m_ren = re.search(r"Rename the existing function `([A-Za-z_]\w*)` in `solution\.py` to `([A-Za-z_]\w*)`", prompt)
    if m_add:
        fn, kind, num_s = m_add.group(1), m_add.group(2), m_add.group(3)
        op = "+" if kind == "add" else "*"
        src = src.rstrip() + f"\n\n\ndef {fn}(x):\n    return x {op} {num_s}\n"
        sol.write_text(src, encoding="utf-8")
    elif m_ren:
        old_fn, new_fn = m_ren.group(1), m_ren.group(2)
        src = re.sub(rf"\bdef\s+{re.escape(old_fn)}\b", f"def {new_fn}", src, count=1)
        sol.write_text(src, encoding="utf-8")
elif rep.is_file():
    m_url = re.search(r"http://[^\s]+", prompt)
    assert m_url is not None, f"no url in prompt: {prompt}"
    idx_url = m_url.group(0).rstrip(".")
    base = idx_url.rsplit("/", 1)[0]
    # 真實透過 HTTP_PROXY -> proxy_bridge -> UNIX socket -> AllowlistUnixProxy -> source_server 抓取網頁
    with urllib.request.urlopen(idx_url, timeout=10) as r:
        idx_html = r.read().decode("utf-8")
    hrefs = re.findall(r'href="([^"]+\.html)"', idx_html)
    vals = {}
    for h in hrefs:
        with urllib.request.urlopen(f"{base}/{h}", timeout=10) as r:
            page = r.read().decode("utf-8")
        for k, v in re.findall(r"<tr><td>([^<]+)</td><td>([^<]+)</td></tr>", page):
            vals[k.strip()] = v.strip()
    lines = []
    for ln in rep.read_text(encoding="utf-8").splitlines():
        if ln.startswith("- ") and ": " in ln:
            pref, _old = ln.split(": ", 1)
            key = pref[2:].strip()
            if key in vals:
                lines.append(f"{pref}: {vals[key]}")
                continue
        lines.append(ln)
    rep.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(json.dumps({"type": "system", "subtype": "init", "cwd": "/work", "model": "claude-haiku-5-5", "argv": sys.argv}))
print(json.dumps({
    "type": "assistant",
    "message": {
        "id": "msg_fake_1",
        "model": "claude-haiku-5-5",
        "usage": {"input_tokens": 111, "output_tokens": 22, "cache_creation_input_tokens": 300, "cache_read_input_tokens": 400},
    },
}))
print(json.dumps({
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "num_turns": 2,
    "total_cost_usd": 0.0025,
    "usage": {"input_tokens": 111, "output_tokens": 22, "cache_creation_input_tokens": 300, "cache_read_input_tokens": 400},
}))
"""


class TestClaudeRunnerWithFakeBinary(unittest.TestCase):
    def test_claude_runner_code_and_doc_end_to_end_through_allowlist_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            fake_claude = tp / "fake_claude"
            fake_claude.write_text(_FAKE_CLAUDE_PY, encoding="utf-8")
            fake_claude.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

            creds = tp / ".credentials.json"
            creds.write_text('{"claudeAiOauth":{"accessToken":"fake"}}\n', encoding="utf-8")

            # 1. Code chain
            ep_dir = make_synthetic_evalplus(tp / "ep", n_he=10, n_mbpp=10)
            code_cdir = tp / "code_chains"
            build_code_chains(seed=5, n=1, out_dir=code_cdir, evalplus_dir=ep_dir, min_init=8, max_init=8, verify_sha256=False)
            code_plan = tp / "plan_code.json"
            atomic_write_json(
                code_plan,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "claude_fake_code",
                    "chains_dir": str(code_cdir),
                    "arms": ["B0"],
                    "model": {
                        "agent": "claude",
                        "model": "claude-haiku-5-5",
                        "claude_bin": str(fake_claude),
                        "credentials_path": str(creds),
                    },
                    "jobs": 1,
                    "attempt_timeout_s": 30,
                },
            )
            code_root = tp / "run_code"
            E1Runner(code_plan, code_root, allow_uncommitted=True).run()
            code_summ = analyze_root(code_root)
            self.assertEqual(code_summ["arms"]["B0"]["primary_final_all_pass_rate"], 1.0)
            self.assertAlmostEqual(code_summ["arms"]["B0"]["cost_usd_total"], 0.0125, places=6)
            recs = [json.loads(x) for x in (code_root / "results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(recs), 5)
            for r in recs:
                self.assertEqual(r["cost_usd"], 0.0025)
                self.assertEqual(r["tokens_in"], 111)
                self.assertEqual(r["tokens_out"], 22)
                self.assertEqual(r["cache_creation_input_tokens"], 300)
                self.assertEqual(r["cache_read_input_tokens"], 400)
                self.assertEqual(r["num_turns"], 2)
                self.assertEqual(r["attempts"][0]["cost_usd"], 0.0025)
                self.assertEqual(r["attempts"][0]["usage"]["cost_usd"], 0.0025)

            # 2. Doc chain (驗證經由沙箱橋接器→UNIX socket→宿主白名單代理→source_server)
            mat = tp / "mat"
            s0 = mat / "sets" / "s1" / "cycle_0" / "site"
            s1 = mat / "sets" / "s1" / "cycle_1" / "site"
            s0.mkdir(parents=True)
            s1.mkdir(parents=True)
            (s0 / "index.html").write_text('<a href="p1.html">p1</a>', encoding="utf-8")
            (s1 / "index.html").write_text('<a href="p1.html">p1</a>', encoding="utf-8")
            (s0 / "p1.html").write_text("<table><tr><td>A</td><td>10</td></tr><tr><td>B</td><td>5</td></tr></table>", encoding="utf-8")
            (s1 / "p1.html").write_text("<table><tr><td>A</td><td>10</td></tr><tr><td>B</td><td>9</td></tr></table>", encoding="utf-8")
            (mat / "sets" / "s1" / "template.md").write_text("# T\n- A: ____\n- B: ____\n", encoding="utf-8")
            atomic_write_json(
                mat / "manifest.json",
                {
                    "schema": "vacant.d2.manifest/1",
                    "sets": [{
                        "set": "s1",
                        "index": "index.html",
                        "pages": ["p1.html"],
                        "claims": [
                            {"id": "c1", "template_line": "- A: "},
                            {"id": "c2", "template_line": "- B: "},
                        ],
                        "truth": [{"c1": "10", "c2": "5"}, {"c1": "10", "c2": "9"}],
                        "cycles": [{"cycle": 1, "changed_claims": ["c2"]}],
                    }],
                },
            )
            doc_cdir = tp / "doc_chains"
            build_doc_chains(materials_dir=mat, out_dir=doc_cdir)
            doc_plan = tp / "plan_doc.json"
            atomic_write_json(
                doc_plan,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "claude_fake_doc",
                    "chains_dir": str(doc_cdir),
                    "arms": ["B0"],
                    "model": {
                        "agent": "claude",
                        "model": "claude-haiku-5-5",
                        "claude_bin": str(fake_claude),
                        "credentials_path": str(creds),
                    },
                    "jobs": 1,
                    "attempt_timeout_s": 30,
                },
            )
            doc_root = tp / "run_doc"
            E1Runner(doc_plan, doc_root, allow_uncommitted=True).run()
            doc_summ = analyze_root(doc_root)
            self.assertEqual(doc_summ["arms"]["B0"]["primary_final_all_pass_rate"], 1.0)
            self.assertAlmostEqual(doc_summ["arms"]["B0"]["cost_usd_total"], 0.0025, places=6)

            # 檢查宿主側代理日誌有記下 doc_s1.e1-sources.example 的請求與位元組數
            px_events = [json.loads(ln) for ln in (doc_root / "proxy.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertGreaterEqual(len(px_events), 2)
            self.assertTrue(all(ev["host"] == "doc_s1.e1-sources.example" and ev["allowed"] and ev["status"] == 200 and ev["bytes"] > 0 for ev in px_events))


if __name__ == "__main__":
    unittest.main()
