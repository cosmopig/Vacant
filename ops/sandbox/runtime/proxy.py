"""本機 Ollama 記帳代理：關思考、保留串流、每通依 run_tag 記帳。"""
from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time


def route(path: str) -> tuple[str | None, str]:
    match = re.fullmatch(r'/t/([A-Za-z0-9_.-]{1,120})(/v1/[^?]+)', path)
    if match:
        return match[1], match[2]
    if path.startswith('/v1/'):
        return None, path
    raise ValueError('expected /t/<run_tag>/v1/... or /v1/...')


class Proxy(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, log: Path, upstream=('127.0.0.1', 11434)):
        super().__init__(address, Handler)
        self.log = log
        self.upstream = upstream
        self.lock = threading.Lock()
        log.parent.mkdir(parents=True, exist_ok=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_POST(self):
        started = time.time()
        row = {'ts_start': started, 'run_tag': None, 'path': self.path,
               'think': False, 'reasoning_effort': 'none', 'usage': {}}
        conn = None
        sent = False
        try:
            tag, path = route(self.path)
            row['run_tag'] = tag
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8 * 1024 * 1024:
                raise ValueError('invalid request length')
            body = json.loads(self.rfile.read(length))
            body.update(think=False, reasoning_effort='none')
            row['model'] = body.get('model')
            if body.get('stream'):
                body['stream_options'] = {**body.get('stream_options', {}), 'include_usage': True}
            conn = http.client.HTTPConnection(*self.server.upstream, timeout=600)
            conn.request('POST', path, json.dumps(body), {'Content-Type': 'application/json'})
            response = conn.getresponse()
            row['status'] = response.status
            self.send_response(response.status)
            self.send_header('Content-Type', response.getheader('Content-Type', 'application/json'))
            self.send_header('Connection', 'close')
            self.end_headers()
            sent = True
            if body.get('stream'):
                for line in response:
                    self.wfile.write(line)
                    self.wfile.flush()
                    if line.startswith(b'data: '):
                        try:
                            event = json.loads(line[6:])
                            if event.get('usage'):
                                row['usage'] = event['usage']
                        except ValueError:
                            pass
            else:
                data = response.read()
                self.wfile.write(data)
                try:
                    row['usage'] = json.loads(data).get('usage', {})
                except ValueError:
                    pass
        except Exception as exc:
            row['error'] = f'{type(exc).__name__}: {exc}'
            if not sent:
                self.send_error(400 if conn is None else 502, 'proxy request failed')
        finally:
            row['latency_s'] = round(time.time() - started, 3)
            with self.server.lock, self.server.log.open('a') as log:
                log.write(json.dumps(row) + '\n')
            if conn is not None:
                conn.close()
            self.close_connection = True

    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18080)
    parser.add_argument('--log', type=Path, default=Path.home() / 'sandbox-rt/calls.jsonl')
    args = parser.parse_args()
    Proxy(('127.0.0.1', args.port), args.log).serve_forever()


if __name__ == '__main__':
    main()
