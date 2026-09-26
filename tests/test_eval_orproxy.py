"""ops/eval/orproxy.py：不碰網路的部分——白名單、預算閘、記帳加總、金鑰遮蔽、續跑重建。"""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from ops.eval import orproxy as P

KEY = "sk-or-v1-" + "0" * 64


def _serve(tmp_path, budget=1.0):
    cfg = {"budget_usd": budget, "models": {"small/model": {"provider": {"order": ["x/fp4"], "allow_fallbacks": False}}}}
    led = P.Ledger(tmp_path / "led", budget, KEY)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), P.make_handler(cfg, led, KEY))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, led


def _post(srv, path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{srv.server_port}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_model_outside_allowlist_is_refused_before_any_upstream_call(tmp_path):
    srv, led = _serve(tmp_path)
    try:
        code, body = _post(srv, "/t/a/api/v1/chat/completions", {"model": "big/expensive", "messages": []})
        assert code == 403 and "allowlist" in body["error"]
        assert not (tmp_path / "led" / "ledger.jsonl").exists()
    finally:
        srv.shutdown()


def test_budget_exhausted_refuses_new_requests(tmp_path):
    srv, led = _serve(tmp_path, budget=0.001)
    led.write({"x": 1}, {"tag": "t", "model": "small/model", "status": 200, "usage": {}, "cost": 0.002})
    try:
        code, body = _post(srv, "/api/v1/chat/completions", {"model": "small/model", "messages": []})
        assert code == 402 and "budget" in body["error"]
    finally:
        srv.shutdown()


def test_only_chat_completions_is_proxied(tmp_path):
    srv, _ = _serve(tmp_path)
    try:
        code, _ = _post(srv, "/api/v1/embeddings", {"model": "small/model"})
        assert code == 404
    finally:
        srv.shutdown()


def test_ledger_sums_by_tag_and_model_and_redacts_the_key(tmp_path):
    led = P.Ledger(tmp_path / "led", 5.0, KEY)
    u = {"prompt_tokens": 100, "completion_tokens": 20, "reasoning_tokens": 5, "cached_tokens": 0}
    led.write({"response": f"echo {KEY}"}, {"tag": "a", "model": "m", "status": 200, "usage": u, "cost": 0.001})
    led.write({"response": "ok"}, {"tag": "b", "model": "m", "status": 429, "usage": {}, "cost": None})
    s = json.loads((tmp_path / "led" / "summary.json").read_text())
    assert s["by_tag"]["a"]["prompt_tokens"] == 100 and s["by_tag"]["a"]["cost_usd"] == 0.001
    assert s["by_model"]["m"]["requests"] == 2 and s["by_model"]["m"]["ok"] == 1
    assert s["spent_usd"] == 0.001
    io = (tmp_path / "led" / "io.jsonl").read_text()
    assert KEY not in io and "[REDACTED]" in io


def test_restart_rebuilds_spend_from_the_same_ledger(tmp_path):
    led = P.Ledger(tmp_path / "led", 5.0, KEY)
    led.write({}, {"tag": "a", "model": "m", "status": 200, "usage": {}, "cost": 0.25})
    again = P.Ledger(tmp_path / "led", 5.0, KEY)
    assert again.spent == 0.25 and again.summary["by_tag"]["a"]["requests"] == 1


def test_usage_fields_are_read_from_openrouter_shape():
    u = P._usage_of({"prompt_tokens": 15, "completion_tokens": 64, "cost": 9.52e-06,
                     "prompt_tokens_details": {"cached_tokens": 3},
                     "completion_tokens_details": {"reasoning_tokens": 64}})
    assert u == {"prompt_tokens": 15, "completion_tokens": 64, "reasoning_tokens": 64,
                 "cached_tokens": 3, "cost": 9.52e-06}


def test_path_carries_tag_and_thinking_condition():
    assert P.split_path("/t/run1/think/off/api/v1/chat/completions") == ("run1", "off", "/api/v1/chat/completions")
    assert P.split_path("/t/run1/api/v1/chat/completions") == ("run1", None, "/api/v1/chat/completions")
    assert P.split_path("/api/v1/chat/completions") == ("untagged", None, "/api/v1/chat/completions")


def test_thinking_condition_overrides_what_the_agent_sent():
    body = {"model": "m", "messages": [], "reasoning_effort": "high", "reasoning": {"enabled": True}, "stream": True}
    off = P.prepare_request(body, {"order": ["x/fp4"]}, "off")
    assert off["reasoning"] == {"enabled": False} and "reasoning_effort" not in off
    assert off["provider"] == {"order": ["x/fp4"]} and off["usage"] == {"include": True}
    assert off["stream_options"]["include_usage"] is True
    on = P.prepare_request(body, {}, "on")
    assert on["reasoning"] == {"enabled": True, "effort": "medium"}
    untouched = P.prepare_request(body, {}, None)
    assert untouched["reasoning_effort"] == "high" and untouched["reasoning"] == {"enabled": True}
    assert body["reasoning_effort"] == "high"  # 原本文不被改（io.jsonl 記的是 agent 送來的原樣）


def test_unknown_thinking_value_is_refused(tmp_path):
    srv, _ = _serve(tmp_path)
    try:
        code, body = _post(srv, "/t/a/think/maybe/api/v1/chat/completions", {"model": "small/model", "messages": []})
        assert code == 400 and "think" in body["error"]
    finally:
        srv.shutdown()


def test_per_run_cap_refuses_only_that_run_and_records_the_refusal(tmp_path):
    cfg = {"budget_usd": 5.0, "tag_cap_usd": 0.01, "host_id": "h1",
           "models": {"small/model": {"provider": {"order": ["x/fp4"]}}}}
    led = P.Ledger(tmp_path / "led", 5.0, KEY)
    led.write({}, {"tag": "run1", "model": "small/model", "status": 200, "usage": {}, "cost": 0.02})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), P.make_handler(cfg, led, KEY))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        code, body = _post(srv, "/t/run1/api/v1/chat/completions", {"model": "small/model", "messages": []})
        assert code == 402 and "per-run" in body["error"]
        ref = [json.loads(x) for x in (tmp_path / "led" / "refusals.jsonl").read_text().splitlines()]
        assert ref == [dict(ref[0], tag="run1", reason="per-run cap", host="h1")]
    finally:
        srv.shutdown()


# ── 串流裡的錯誤（2026-09-25 校準：Darkbloom 先回 200、再用 data 塊說 429）───────────
from http.server import BaseHTTPRequestHandler  # noqa: E402

RATE = (b": OPENROUTER PROCESSING\n\n: OPENROUTER PROCESSING\n\n"
        b'data: {"id":"gen-x","choices":[],"error":{"code":429,"message":"Provider returned error",'
        b'"metadata":{"error_type":"rate_limit_exceeded"}}}\n\n')
GOOD = (b": OPENROUTER PROCESSING\n\n"
        b'data: {"id":"gen-y","provider":"P","choices":[{"delta":{"content":"hi"}}]}\n\n'
        b'data: {"id":"gen-y","choices":[],"usage":{"prompt_tokens":10,"completion_tokens":2,'
        b'"cost":0.0001}}\n\ndata: [DONE]\n\n')
LATE = (b'data: {"id":"gen-z","choices":[{"delta":{"content":"part"}}]}\n\n'
        b'data: {"id":"gen-z","choices":[],"error":{"code":502,"message":"upstream died"}}\n\n')


def _upstream(script):
    """假的 OpenRouter：依序回 `script` 裡的串流本文（全部都是 HTTP 200）。"""
    calls = []

    class U(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            body = script[min(len(calls), len(script) - 1)]
            calls.append(1)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), U)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, calls


def _serve_stream(tmp_path, monkeypatch, script):
    up, calls = _upstream(script)
    monkeypatch.setattr(P, "UPSTREAM", f"http://127.0.0.1:{up.server_port}")
    cfg = {"budget_usd": 1.0, "retry_waits": [0, 0, 0, 0],
           "models": {"small/model": {"provider": {"order": ["x/fp4"], "allow_fallbacks": False}}}}
    led = P.Ledger(tmp_path / "led", 1.0, KEY)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), P.make_handler(cfg, led, KEY))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, up, calls


def _post_stream(srv):
    req = urllib.request.Request(
        f"http://127.0.0.1:{srv.server_port}/t/s/api/v1/chat/completions",
        data=json.dumps({"model": "small/model", "stream": True, "messages": []}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _ledger(tmp_path):
    return [json.loads(x) for x in (tmp_path / "led" / "ledger.jsonl").read_text().splitlines()]


def test_a_rate_limit_inside_a_200_stream_is_retried_not_passed_to_the_agent(tmp_path, monkeypatch):
    srv, up, calls = _serve_stream(tmp_path, monkeypatch, [RATE, RATE, GOOD])
    try:
        code, body = _post_stream(srv)
        assert code == 200 and b'"hi"' in body and b"rate_limit" not in body
        assert len(calls) == 3
        (rec,) = _ledger(tmp_path)
        assert rec["status"] == 200 and rec["retried_stream_errors"] == 2 and not rec["stream_error"]
        assert rec["usage"]["prompt_tokens"] == 10 and rec["cost"] == 0.0001
    finally:
        srv.shutdown()
        up.shutdown()


def test_a_stream_error_that_never_clears_becomes_a_real_http_error(tmp_path, monkeypatch):
    srv, up, calls = _serve_stream(tmp_path, monkeypatch, [RATE])
    try:
        code, body = _post_stream(srv)
        assert code == 429 and b"rate_limit_exceeded" in body
        assert len(calls) == 5                                   # 第一次＋重試 4 次
        (rec,) = _ledger(tmp_path)
        assert rec["status"] == 429 and rec["stream_error"]["code"] == 429
        s = json.loads((tmp_path / "led" / "summary.json").read_text())
        assert s["by_tag"]["s"]["ok"] == 0
    finally:
        srv.shutdown()
        up.shutdown()


def test_an_error_after_content_started_is_recorded_and_not_counted_ok(tmp_path, monkeypatch):
    srv, up, calls = _serve_stream(tmp_path, monkeypatch, [LATE])
    try:
        code, body = _post_stream(srv)
        assert code == 200 and b"part" in body and b"upstream died" in body
        (rec,) = _ledger(tmp_path)
        assert rec["stream_error"]["code"] == 502
        s = json.loads((tmp_path / "led" / "summary.json").read_text())
        assert s["by_tag"]["s"]["ok"] == 0 and s["by_tag"]["s"]["requests"] == 1
    finally:
        srv.shutdown()
        up.shutdown()


# ── 本機算力（2026-09-26）：兩台 LM Studio，同一題的 A、C 指定同一台 ─────────────────────────────

def test_route_carries_tag_upstream_and_thinking():
    assert P.split_route("/t/g-A-7/up/w401/think/off/api/v1/chat/completions") == \
        ("g-A-7", "w401", "off", "/api/v1/chat/completions")
    assert P.split_route("/t/x/think/on/api/v1/models") == ("x", None, "on", "/api/v1/models")
    assert P.split_path("/t/g/up/1003/think/off/api/v1/x") == ("g", "off", "/api/v1/x")


def test_local_request_forces_reasoning_effort_and_drops_openrouter_fields():
    body = {"model": "m", "messages": [], "reasoning": {"enabled": True}, "reasoning_effort": "high",
            "provider": {"order": ["x"]}, "stream": True}
    sent = P.prepare_request(body, {"order": ["y"]}, "off", local=True)
    assert sent["reasoning_effort"] == "none"
    assert "provider" not in sent and "usage" not in sent and "reasoning" not in sent
    assert sent["stream_options"] == {"include_usage": True}
    assert P.prepare_request(body, {}, "on", local=True)["reasoning_effort"] == "medium"
    assert body["reasoning_effort"] == "high"          # 原本送來的照樣記在 request_from_agent


def test_local_mode_routes_to_the_named_machine_without_a_key(tmp_path):
    from http.server import BaseHTTPRequestHandler
    seen = []

    class Up(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            seen.append((self.path, self.headers.get("Authorization"),
                         json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            b = json.dumps({"id": "c1", "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                            "usage": {"prompt_tokens": 3, "completion_tokens": 1}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    up = ThreadingHTTPServer(("127.0.0.1", 0), Up)
    threading.Thread(target=up.serve_forever, daemon=True).start()
    cfg = {"budget_usd": 1e9, "models": {"gemma-4-12b-it-qat": {}},
           "upstreams": {"a": f"http://127.0.0.1:{up.server_port}", "b": "http://127.0.0.1:9"}}
    led = P.Ledger(tmp_path / "led", 1e9, "")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), P.make_handler(cfg, led, ""))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        code, body = _post(srv, "/t/run1/up/a/think/off/api/v1/chat/completions",
                           {"model": "gemma-4-12b-it-qat", "messages": [{"role": "user", "content": "hi"}]})
        assert code == 200 and body["choices"][0]["message"]["content"] == "ok"
        path, auth, sent = seen[0]
        assert path == "/v1/chat/completions" and auth is None and sent["reasoning_effort"] == "none"
        led_file = tmp_path / "led" / "ledger.jsonl"
        for _ in range(100):                                 # 帳在回應送出之後才寫
            if led_file.exists():
                break
            __import__("time").sleep(0.02)
        rec = json.loads(led_file.read_text().splitlines()[0])
        assert rec["upstream"] == "a" and rec["cost"] is None and rec["usage"]["prompt_tokens"] == 3
        code, body = _post(srv, "/t/run1/up/zzz/api/v1/chat/completions", {"model": "gemma-4-12b-it-qat"})
        assert code == 400 and "upstream" in body["error"]
        code, body = _post(srv, "/t/run1/api/v1/chat/completions", {"model": "gemma-4-12b-it-qat"})
        assert code == 400                                   # 本機模式一定要指定哪一台
    finally:
        srv.shutdown()
        up.shutdown()
