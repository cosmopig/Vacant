"""dashboard 驗收（12 §4.3）：單頁 HTML / JSON API / SSE 重放。

全程 loopback（127.0.0.1 + 隨機埠 port=0），無外網依賴，可離線跑。
"""

from __future__ import annotations

import json
import threading
import urllib.request

from vacant.dashboard import make_dashboard


def _serve(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t


def _url(server, path):
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _write_events(root, records):
    d = root / "ledger"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "events.jsonl").open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_index_and_json_api(tmp_path):
    roster = [{"name": "alice", "vacant_id": "abc123", "tier": "T2", "credit": 0.9,
               "n_obs": 5.0, "deliveries": 4, "flags": [], "episodes": 3, "chain_ok": True}]
    sb = {"off": {"n": 2, "pass": 1, "calls": 2}, "on": {"n": 2, "pass": 2, "calls": 2},
          "paired_delta": 0.5}
    server = make_dashboard(tmp_path, lambda: roster, lambda: sb, port=0)
    _serve(server)
    try:
        # GET / → 自足 HTML 單頁（無 CDN、無框架標記）
        html = urllib.request.urlopen(_url(server, "/"), timeout=5).read().decode()
        assert "<!doctype html>" in html.lower()
        assert "EventSource('/events')" in html
        assert "cdn" not in html.lower()  # 無外部 CDN 依賴
        assert "信任觀測台" in html

        # GET /api/roster → 注入的名冊
        got = json.loads(urllib.request.urlopen(_url(server, "/api/roster"), timeout=5).read())
        assert got == roster

        # GET /api/scoreboard → 注入的計分板
        gsb = json.loads(urllib.request.urlopen(_url(server, "/api/scoreboard"), timeout=5).read())
        assert gsb["paired_delta"] == 0.5
    finally:
        server.shutdown()
        server.server_close()


def test_sse_replays_existing_events(tmp_path):
    # 先寫幾行假事件，SSE 連上後應把既有行重放出來
    _write_events(tmp_path, [
        {"ts_ms": 1, "type": "ROUTE", "trust_on": True, "to": "alice", "tier": "T2", "mode": "ucb"},
        {"ts_ms": 2, "type": "REVIEW", "trust_on": True, "reviewer": "bob",
         "target": "alice", "verdict": "PASS", "weight": 0.8},
        {"ts_ms": 3, "type": "SLASH", "trust_on": True, "target": "mallory", "reason": "bad"},
    ])
    server = make_dashboard(tmp_path, lambda: [], lambda: {}, port=0)
    _serve(server)
    try:
        resp = urllib.request.urlopen(_url(server, "/events"), timeout=5)
        # 讀到第一個 data: 事件就斷線（驗重放到達）
        first = None
        deadline_lines = 0
        for raw in resp:
            deadline_lines += 1
            line = raw.decode().rstrip("\n")
            if line.startswith("data: "):
                first = json.loads(line[len("data: "):])
                break
            if deadline_lines > 20:
                break
        resp.close()
        assert first is not None
        assert first["type"] == "ROUTE"
        assert first["to"] == "alice"
    finally:
        server.shutdown()
        server.server_close()


def test_missing_ledger_is_tolerated(tmp_path):
    # ledger 尚未存在時 SSE 不應炸；連上拿到 : connected 註解即可
    server = make_dashboard(tmp_path, lambda: [], lambda: {}, port=0)
    _serve(server)
    try:
        resp = urllib.request.urlopen(_url(server, "/events"), timeout=5)
        line = resp.readline().decode()
        assert line.startswith(":")  # SSE comment，連線建立
        resp.close()
    finally:
        server.shutdown()
        server.server_close()
