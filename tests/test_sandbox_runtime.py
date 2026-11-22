"""記帳代理的離線協定測試，不呼叫模型。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import urllib.error
import urllib.request

import pytest

from ops.sandbox.runtime.proxy import Proxy, route


def test_routes():
    assert route('/t/A-b_1/v1/chat/completions') == ('A-b_1', '/v1/chat/completions')
    assert route('/v1/chat/completions') == (None, '/v1/chat/completions')
    with pytest.raises(ValueError):
        route('/t/../bad')


def test_proxy_attribution_and_errors(tmp_path):
    seen = []

    class Upstream(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append((self.path, body))
            usage = {'prompt_tokens': 12, 'completion_tokens': 3}
            self.send_response(200)
            self.end_headers()
            if body.get('stream'):
                self.wfile.write(b'data: ' + json.dumps({'usage': usage}).encode() + b'\n\ndata: [DONE]\n\n')
            else:
                self.wfile.write(json.dumps({'usage': usage}).encode())

        def log_message(self, *_):
            pass

    upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    proxy = Proxy(('127.0.0.1', 0), tmp_path / 'calls.jsonl', upstream.server_address)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (upstream, proxy)]
    for thread in threads:
        thread.start()
    try:
        for stream in (False, True):
            req = urllib.request.Request(
                f'http://127.0.0.1:{proxy.server_port}/t/run-1/v1/chat/completions',
                json.dumps({'model': 'fake', 'stream': stream}).encode(),
                {'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response:
                assert response.read()
        req = urllib.request.Request(f'http://127.0.0.1:{proxy.server_port}/invalid', b'{}')
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(req, timeout=5)
        assert error.value.code == 400
    finally:
        for server in (proxy, upstream):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join()
    rows = [json.loads(line) for line in (tmp_path / 'calls.jsonl').read_text().splitlines()]
    assert len(rows) == 3
    assert all(r['run_tag'] == 'run-1' and r['usage']['completion_tokens'] == 3 for r in rows[:2])
    assert rows[-1]['error']
    assert all(path == '/v1/chat/completions' and body['think'] is False
               and body['reasoning_effort'] == 'none' for path, body in seen)
