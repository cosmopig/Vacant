"""SMOKE-TEST ONLY scripted OpenAI-compatible upstream.

Returns a fixed, hand-written sequence of tool calls (ls -> read -> bash test ->
edit -> bash test -> final text) so the pi wiring, the proxy and the trajectory
parser can be exercised while the real qwen3.8:27b endpoint is down.
Trajectories produced with this upstream are NOT model behaviour and must never
be reported as results; run_baseline.py tags them `"upstream":"MOCK"`.
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPT = [
    ("bash", {"command": "ls -R"}),
    ("read", {"path": "tests/test_pricing.py"}),
    ("bash", {"command": "python -m pytest -q"}),
    ("edit", {"path": "pricing.py", "edits": [{"oldText": "discount = COUPON_RATE", "newText": "discount += COUPON_RATE"}]}),
    ("bash", {"command": "python -m pytest -q"}),
    (None, "MOCK: done (scripted smoke test, not a model)."),
]


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        d = json.dumps({"data": [{"id": "mock"}]}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        n_tool = sum(1 for m in req["messages"] if m.get("role") == "tool")
        name, args = SCRIPT[min(n_tool, len(SCRIPT) - 1)]
        if name:
            delta = {"role": "assistant", "content": f"Step {n_tool+1}: calling {name}.",
                     "tool_calls": [{"index": 0, "id": f"call_{n_tool}", "type": "function",
                                     "function": {"name": name, "arguments": json.dumps(args)}}]}
            fin = "tool_calls"
        else:
            delta, fin = {"role": "assistant", "content": args}, "stop"
        chunks = [
            {"id": "x", "object": "chat.completion.chunk", "created": int(time.time()), "model": "mock",
             "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
            {"id": "x", "object": "chat.completion.chunk", "created": int(time.time()), "model": "mock",
             "choices": [{"index": 0, "delta": {}, "finish_reason": fin}],
             "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}},
        ]
        body = b"".join(b"data: " + json.dumps(c).encode() + b"\n\n" for c in chunks) + b"data: [DONE]\n\n"
        self.send_response(200); self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18099), H).serve_forever()
