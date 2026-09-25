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
