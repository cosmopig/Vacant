"""dashboard 驗收（12 §4.3）：單頁 HTML / JSON API / SSE 重放。

全程 loopback（127.0.0.1 + 隨機埠 port=0），無外網依賴，可離線跑。
"""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest

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
        # GET / → 自足 HTML 單頁（無 CDN、無框架標記）。
        # 腳本／樣式改由 /static/ 供應（同源、隨套件安裝），SSE 客戶端在 app.js。
        html = urllib.request.urlopen(_url(server, "/"), timeout=5).read().decode()
        assert "<!doctype html>" in html.lower()
        assert "/static/app.js" in html
        assert "cdn" not in html.lower()  # 無外部 CDN 依賴
        assert "信任觀測台" in html
        js = urllib.request.urlopen(_url(server, "/static/app.js"), timeout=5).read().decode()
        assert "EventSource('/events')" in js
        assert "//" not in js.split("EventSource")[0].split("\n")[-1]  # 非註解掉的死碼

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


# --- GET /api/snapshot（17 §P0-3）---------------------------------------------
from vacant.dashboard import build_snapshot, ledger_head


def test_snapshot_shape_and_ledger_seq(tmp_path):
    """snapshot 五鍵齊、ledger_seq 與實際事件數一致。"""
    events = [{"ts_ms": i, "type": "ROUTE"} for i in range(5)]
    _write_events(tmp_path, events)
    roster = [{"name": "alice"}]
    sb = {"on": {"n": 1}, "off": {"n": 2}}
    server = make_dashboard(tmp_path, lambda: roster, lambda: sb, port=0)
    _serve(server)
    try:
        got = json.loads(urllib.request.urlopen(_url(server, "/api/snapshot"), timeout=5).read())
        assert got["roster"] == roster
        assert got["scoreboard"] == sb
        assert got["ledger_seq"] == 5           # 與實際事件數一致
        assert len(got["ledger_head_hash"]) == 64
        assert got["ts_ms"] > 0
    finally:
        server.shutdown()
        server.server_close()


def test_snapshot_head_recompute_consistent(tmp_path):
    """head hash 重算一致；加一筆事件 → seq+1、head 改變（竄改可偵測）。"""
    _write_events(tmp_path, [{"ts_ms": 1, "type": "ROUTE"}])
    ledger = tmp_path / "ledger" / "events.jsonl"
    seq1, head1 = ledger_head(ledger)
    assert seq1 == 1
    snap = build_snapshot(ledger, list, dict)
    assert snap["ledger_seq"] == seq1 and snap["ledger_head_hash"] == head1

    _write_events(tmp_path, [{"ts_ms": 2, "type": "AUDIT"}])
    seq2, head2 = ledger_head(ledger)
    assert seq2 == 2
    assert head2 != head1  # 追加改變 head（對帳錨）


def test_snapshot_empty_ledger(tmp_path):
    """無 ledger：seq=0、head＝創世值（明白的初始狀態，非錯誤）。"""
    seq, head = ledger_head(tmp_path / "ledger" / "events.jsonl")
    assert seq == 0
    assert head == "0" * 64


# --- 觀測面：身份／全景／宣稱階梯（2026-07-26 儀表板改版）--------------------
def test_state_endpoint_returns_full_panorama(tmp_path):
    """/api/state 是首屏的唯一取數點：缺席的 provider 要降級成空集合，
    不可讓面板拿到半殘資料卻以為是真的。"""
    _write_events(tmp_path, [{"type": "ROUTE", "ts_ms": 1, "task_id": "t1"}])
    sb = {"off": {"n": 0, "pass": 0, "calls": 0}, "on": {"n": 0, "pass": 0, "calls": 0}}
    server = make_dashboard(tmp_path, lambda: [], lambda: sb, port=0)
    _serve(server)
    try:
        d = json.loads(urllib.request.urlopen(_url(server, "/api/state")).read())
    finally:
        server.shutdown()
    assert d["identities"] == [] and d["activity"] == []
    assert d["system"] is None            # provider 缺席 → None，不是假物件
    assert d["counters"] == {}
    assert [r["step"] for r in d["claim_ladder"]] == ["A", "B", "C-1", "C-3"]


def test_state_uses_injected_providers(tmp_path):
    ident = {"name": "alice", "vacant_id": "zQmAlice", "stream_id": "s1",
             "chain_ok": True, "genesis_proven": True, "credit": 0.9, "n_obs": 4.0,
             "dims": {}, "dim_obs": {}, "flags": [], "probation": False,
             "deliveries": 3, "episodes": 2, "checkpoints": 0}
    providers = {
        "identities": lambda: [ident],
        "identity_detail": lambda i: {**ident, "entries": [], "tasks": [],
                                      "checkpoint_chain": []} if i == "zQmAlice" else None,
        "activity": lambda: [{"task_id": "t1", "deliverer": "alice"}],
        "counters": lambda: {"ROUTE": 1},
        "integrity": lambda: {"ledger_seq": 1, "ledger_head": "h", "chains": [],
                              "all_chains_ok": True},
        "system_info": lambda: {"trust_on": True, "n_identities": 1},
    }
    sb = {"off": {"n": 0, "pass": 0}, "on": {"n": 0, "pass": 0}}
    server = make_dashboard(tmp_path, lambda: [], lambda: sb, port=0, providers=providers)
    _serve(server)
    try:
        d = json.loads(urllib.request.urlopen(_url(server, "/api/state")).read())
        detail = json.loads(urllib.request.urlopen(
            _url(server, "/api/identity?id=zQmAlice")).read())
        try:
            urllib.request.urlopen(_url(server, "/api/identity?id=nobody"))
            unknown_status = 200
        except urllib.error.HTTPError as e:
            unknown_status = e.code
    finally:
        server.shutdown()
    assert d["identities"][0]["vacant_id"] == "zQmAlice"
    assert d["system"]["n_identities"] == 1
    assert detail["name"] == "alice"
    assert unknown_status == 404  # 查無此身份必須是 404，不可回空物件裝作有


def test_static_assets_and_no_path_traversal(tmp_path):
    server = make_dashboard(tmp_path, lambda: [], lambda: {}, port=0)
    _serve(server)
    try:
        css = urllib.request.urlopen(_url(server, "/static/app.css"))
        assert css.status == 200 and b"--accent" in css.read()
        for bad in ("/static/../ecosystem.py", "/static/..%2Fecosystem.py", "/static/.env"):
            try:
                urllib.request.urlopen(_url(server, bad))
                got = 200
            except urllib.error.HTTPError as e:
                got = e.code
            assert got == 404, f"路徑穿越未被擋：{bad}"
    finally:
        server.shutdown()


def test_claim_ladder_never_defaults_to_met():
    """宣稱階梯的預設必須是「未達」——寧可顯示未達，不可預設已達。"""
    from vacant.dashboard import claim_ladder
    empty = claim_ladder(integrity={}, scoreboard={})
    assert all(r["met"] is False for r in empty)

    # A 階只在「有事件且所有鏈可驗」時才成立
    ok = claim_ladder(
        integrity={"ledger_seq": 5, "all_chains_ok": True, "chains": [{"name": "a"}]},
        scoreboard={})
    assert ok[0]["met"] is True
    broken = claim_ladder(
        integrity={"ledger_seq": 5, "all_chains_ok": False, "chains": [{"name": "a"}]},
        scoreboard={})
    assert broken[0]["met"] is False

    # C-1／C-3 不可由面板判定為已達，無論資料多好看
    rich = claim_ladder(
        integrity={"ledger_seq": 999, "all_chains_ok": True, "chains": []},
        scoreboard={"on": {"n": 500, "pass": 500}, "off": {"n": 500, "pass": 1}})
    assert rich[2]["met"] is False and rich[3]["met"] is False


def test_cost_reports_per_pass_not_just_totals(tmp_path):
    """成本切面必須算得出「每次通過的呼叫數」——只報總量會讓信任層的代價隱形。"""
    from vacant.cli import EchoLikeBrain
    from vacant.ecosystem import Ecosystem
    eco = Ecosystem(tmp_path, EchoLikeBrain(), root_mode="demo")
    eco.toggle(True)
    for i in range(3):
        eco.delegate(f"reverse {i}",
                     {"type": "run_python", "code": "assert solve('ab') == 'ba'", "timeout": 8})
    c = eco.cost()
    assert c["on"]["deliveries"] == 3
    assert c["on"]["calls"] >= 3
    assert c["on"]["calls_per_delivery"] == pytest.approx(c["on"]["calls"] / 3)
    # 沒有 off 臂資料時回 None，不可回 0（0 會被讀成「不用錢」）
    assert c["off"]["deliveries"] == 0
    assert c["off"]["calls_per_delivery"] is None
    assert c["off"]["calls_per_pass"] is None


def test_task_endpoint_serves_the_trust_card_itself(tmp_path):
    """活動列要能點進信任狀本體——那是「做了什麼」的最終證物。"""
    card = {"task_id": "abc", "trust_on": True,
            "deliverer": {"name": "alice", "credit": {"score": 0.9, "flags": []}},
            "reviews": [{"reviewer": "bob", "verdict": "PASS", "weight": 0.5, "sig": "ff"}],
            "audit": {"performed": True, "passed": True}, "chain_head": "h" * 64}
    providers = {"trust_card": lambda t: card if t == "abc" else None}
    server = make_dashboard(tmp_path, lambda: [], lambda: {}, port=0, providers=providers)
    _serve(server)
    try:
        got = json.loads(urllib.request.urlopen(_url(server, "/api/task?id=abc")).read())
        try:
            urllib.request.urlopen(_url(server, "/api/task?id=zzz"))
            missing = 200
        except urllib.error.HTTPError as e:
            missing = e.code
    finally:
        server.shutdown()
    assert got["task_id"] == "abc"
    assert got["reviews"][0]["sig"] == "ff"   # 簽章存全文，讓第三方可獨立重驗
    assert missing == 404
