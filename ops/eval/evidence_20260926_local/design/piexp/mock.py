#!/usr/bin/env python3
"""Scripted fake model upstream for driving pi headless (no credentials, no network).

Speaks three wire APIs that pi's models.json `api` field can select:
  openai-completions  -> POST .../chat/completions   (SSE chat.completion.chunk)
  anthropic-messages  -> POST .../messages            (SSE message_start ... message_stop)
  openai-responses    -> POST .../responses           (SSE response.* events)
Also: GET .../models.  Anything else -> 404 (logged).

Script (JSON list, env MOCK_SCRIPT): each request consumes the next step:
  {"tool": "write", "args": {...}}   -> one tool call
  {"text": "..."}                    -> plain text, stop
  {"status": 500}                    -> HTTP error
Last step repeats when the list is exhausted.
Every request is logged (path, auth header shape, body) to MOCK_LOG jsonl.
A second listener (SINK_PORT) acts as an HTTP(S) proxy sink: logs + 403, so any
unexpected outbound traffic is caught locally and never leaves the box.
"""
import json, os, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("MOCK_PORT", "18881"))
SINK_PORT = int(os.environ.get("SINK_PORT", "18882"))
LOG = os.environ.get("MOCK_LOG", "mock.jsonl")
SCRIPT = json.loads(os.environ.get("MOCK_SCRIPT", '[{"text":"ok"}]'))
_lock = threading.Lock()
_n = [0]


def log(rec):
    rec["t"] = time.time()
    with _lock, open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def next_step():
    with _lock:
        i = _n[0]
        _n[0] += 1
    return i, SCRIPT[min(i, len(SCRIPT) - 1)]


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _sse(self, events):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        for ev in events:
            self.wfile.write(ev.encode())
            self.wfile.flush()
        self.close_connection = True

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        log({"method": "GET", "path": self.path, "auth": self._auth()})
        if self.path.rstrip("/").endswith("/models"):
            return self._json(200, {"object": "list", "data": [{"id": "mock-model", "object": "model"}]})
        self._json(404, {"error": "not found"})

    def _auth(self):
        a = self.headers.get("Authorization") or ""
        x = self.headers.get("x-api-key") or ""
        return {"authorization_prefix": a[:12], "x_api_key_prefix": x[:8],
                "user_agent": self.headers.get("User-Agent", "")[:80]}

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw)
        except Exception:
            body = {"_raw": raw[:200].decode(errors="replace")}
        i, step = next_step()
        extra = {k: v for k, v in self.headers.items() if k.lower().startswith(("x-", "anthropic", "openai"))}
        log({"method": "POST", "path": self.path, "i": i, "step": step, "auth": self._auth(),
             "hdr": extra, "body": body})
        if "status" in step:
            return self._json(step["status"], {"error": {"message": "mock error", "type": "server_error"}})
        p = self.path.split("?")[0].rstrip("/")
        if p.endswith("/chat/completions"):
            return self._sse(openai_chat(step, body))
        if p.endswith("/messages"):
            return self._sse(anthropic(step, body))
        if p.endswith("/responses"):
            return self._sse(openai_responses(step, body))
        self._json(404, {"error": "unknown path"})


def openai_chat(step, body):
    cid = "chatcmpl-" + uuid.uuid4().hex[:8]
    base = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
            "model": body.get("model", "mock-model")}
    out = []
    def chunk(delta, finish=None, usage=None):
        c = dict(base, choices=[{"index": 0, "delta": delta, "finish_reason": finish}])
        if usage is not None:
            c["usage"] = usage
        out.append("data: " + json.dumps(c) + "\n\n")
    chunk({"role": "assistant", "content": ""})
    if "tool" in step:
        chunk({"tool_calls": [{"index": 0, "id": "call_" + uuid.uuid4().hex[:8], "type": "function",
                               "function": {"name": step["tool"], "arguments": ""}}]})
        chunk({"tool_calls": [{"index": 0, "function": {"arguments": json.dumps(step["args"])}}]})
        chunk({}, "tool_calls")
    else:
        chunk({"content": step.get("text", "")})
        chunk({}, "stop")
    out.append("data: " + json.dumps(dict(base, choices=[], usage={
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})) + "\n\n")
    out.append("data: [DONE]\n\n")
    return out


def sse(event, data):
    return "event: %s\ndata: %s\n\n" % (event, json.dumps(data))


def anthropic(step, body):
    mid = "msg_" + uuid.uuid4().hex[:8]
    out = [sse("message_start", {"type": "message_start", "message": {
        "id": mid, "type": "message", "role": "assistant", "model": body.get("model", "mock-model"),
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 1}}})]
    if "tool" in step:
        out.append(sse("content_block_start", {"type": "content_block_start", "index": 0,
               "content_block": {"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:8],
                                 "name": step["tool"], "input": {}}}))
        out.append(sse("content_block_delta", {"type": "content_block_delta", "index": 0,
               "delta": {"type": "input_json_delta", "partial_json": json.dumps(step["args"])}}))
        stop = "tool_use"
    else:
        out.append(sse("content_block_start", {"type": "content_block_start", "index": 0,
               "content_block": {"type": "text", "text": ""}}))
        out.append(sse("content_block_delta", {"type": "content_block_delta", "index": 0,
               "delta": {"type": "text_delta", "text": step.get("text", "")}}))
        stop = "end_turn"
    out.append(sse("content_block_stop", {"type": "content_block_stop", "index": 0}))
    out.append(sse("message_delta", {"type": "message_delta",
           "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 5}}))
    out.append(sse("message_stop", {"type": "message_stop"}))
    return out


def openai_responses(step, body):
    rid = "resp_" + uuid.uuid4().hex[:8]
    resp = {"id": rid, "object": "response", "created_at": int(time.time()), "status": "in_progress",
            "model": body.get("model", "mock-model"), "output": []}
    out = [sse("response.created", {"type": "response.created", "response": resp})]
    if "tool" in step:
        item = {"type": "function_call", "id": "fc_" + uuid.uuid4().hex[:8],
                "call_id": "call_" + uuid.uuid4().hex[:8], "name": step["tool"], "arguments": "",
                "status": "in_progress"}
        out.append(sse("response.output_item.added", {"type": "response.output_item.added",
                                                      "output_index": 0, "item": item}))
        args = json.dumps(step["args"])
        out.append(sse("response.function_call_arguments.delta", {
            "type": "response.function_call_arguments.delta", "output_index": 0,
            "item_id": item["id"], "delta": args}))
        out.append(sse("response.function_call_arguments.done", {
            "type": "response.function_call_arguments.done", "output_index": 0,
            "item_id": item["id"], "arguments": args}))
        done_item = dict(item, arguments=args, status="completed")
    else:
        item = {"type": "message", "id": "msg_" + uuid.uuid4().hex[:8], "role": "assistant",
                "status": "in_progress", "content": []}
        out.append(sse("response.output_item.added", {"type": "response.output_item.added",
                                                      "output_index": 0, "item": item}))
        out.append(sse("response.content_part.added", {"type": "response.content_part.added",
               "item_id": item["id"], "output_index": 0, "content_index": 0,
               "part": {"type": "output_text", "text": "", "annotations": []}}))
        t = step.get("text", "")
        out.append(sse("response.output_text.delta", {"type": "response.output_text.delta",
               "item_id": item["id"], "output_index": 0, "content_index": 0, "delta": t}))
        out.append(sse("response.output_text.done", {"type": "response.output_text.done",
               "item_id": item["id"], "output_index": 0, "content_index": 0, "text": t}))
        part = {"type": "output_text", "text": t, "annotations": []}
        out.append(sse("response.content_part.done", {"type": "response.content_part.done",
               "item_id": item["id"], "output_index": 0, "content_index": 0, "part": part}))
        done_item = dict(item, status="completed", content=[part])
    out.append(sse("response.output_item.done", {"type": "response.output_item.done",
                                                 "output_index": 0, "item": done_item}))
    fin = dict(resp, status="completed", output=[done_item],
               usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                      "input_tokens_details": {"cached_tokens": 0},
                      "output_tokens_details": {"reasoning_tokens": 0}})
    out.append(sse("response.completed", {"type": "response.completed", "response": fin}))
    return out


class Sink(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _deny(self):
        log({"sink": True, "method": self.command, "path": self.path,
             "host": self.headers.get("Host")})
        self.send_response(403)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_CONNECT = do_GET = do_POST = do_PUT = do_HEAD = _deny


if __name__ == "__main__":
    s1 = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    s2 = ThreadingHTTPServer(("127.0.0.1", SINK_PORT), Sink)
    threading.Thread(target=s2.serve_forever, daemon=True).start()
    print("mock on %d, sink on %d" % (PORT, SINK_PORT), flush=True)
    s1.serve_forever()
