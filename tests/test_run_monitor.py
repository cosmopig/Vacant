"""run_monitor 驗收：runs 摘要/控制旗標 ＋ 來源開關 ＋ eco/lmstudio/hermes 三來源。

全程 loopback（127.0.0.1 + 隨機埠 port=0），無外網依賴，可離線跑；
lmstudio 用注入的 http_get、hermes 用注入的 ssh_run，不碰真網路/真 ssh。
"""

from __future__ import annotations

import json
import subprocess
import threading
import urllib.error
import urllib.request

from vacant_network.batch import RunControl, RunLedger
from vacant_network.run_monitor import (
    _PAGE,
    TraceStats,
    _enrich,
    _is_safe_run_id,
    make_run_monitor,
    scan_runs,
    summarize_run,
    tail_records,
)


def _serve(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t


def _url(server, path):
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _post(server, path, body):
    req = urllib.request.Request(
        _url(server, path), data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    return urllib.request.urlopen(req, timeout=5)


# === 純函式：掃描/摘要（不碰 HTTP）=============================================

def test_scan_runs_finds_subdirectories_with_ledger(tmp_path):
    (tmp_path / "not_a_run").mkdir()  # 沒有 ledger.jsonl，不該被列出
    led = RunLedger(tmp_path / "x1_pilot" / "ledger.jsonl")
    led.mark_done("M2", "t1", "s0", {"outcome": "pass", "family": "string_edge", "ts_ms": 10})
    runs = scan_runs(tmp_path)
    assert [r["run_id"] for r in runs] == ["x1_pilot"]
    assert runs[0]["total_done"] == 1


def test_scan_runs_treats_root_itself_as_single_run(tmp_path):
    RunLedger(tmp_path / "ledger.jsonl").mark_done("M0", "t1", "s0", {"outcome": "fail"})
    runs = scan_runs(tmp_path)
    assert [r["run_id"] for r in runs] == ["."]


def test_scan_runs_empty_root_is_empty_list(tmp_path):
    assert scan_runs(tmp_path / "does_not_exist") == []
    assert scan_runs(tmp_path) == []


def test_summarize_run_counts_outcomes_and_families(tmp_path):
    led = RunLedger(tmp_path / "ledger.jsonl")
    led.mark_done("M2", "t1", "s0", {"outcome": "pass", "family": "string_edge", "ts_ms": 1})
    led.mark_done("M2", "t2", "s0", {"outcome": "fail", "family": "string_edge", "ts_ms": 2})
    led.mark_done("M2", "t3", "s0", {"outcome": "infra_void", "family": "off_by_one", "ts_ms": 3})
    led.mark_done("M2", "t4", "s0",
                  {"outcome": "skipped_by_operator", "family": "off_by_one", "ts_ms": 4})
    summary = summarize_run(tmp_path, ".")
    assert summary["total_done"] == 4
    assert summary["by_outcome"] == {
        "pass": 1, "fail": 1, "infra_void": 1, "skipped_by_operator": 1,
    }
    assert summary["by_family"]["string_edge"] == {"pass": 1, "fail": 1, "other": 0}
    assert summary["by_family"]["off_by_one"] == {"pass": 0, "fail": 0, "other": 2}
    assert summary["last_activity_ms"] == 4
    assert summary["control_state"] == "running"  # 沒下過旗標＝預設值


def test_summarize_run_lists_trace_lanes(tmp_path):
    RunLedger(tmp_path / "ledger.jsonl").mark_done("M2", "t1", "s0", {"outcome": "pass"})
    (tmp_path / "M2_s0.trace.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "M0_s1.trace.jsonl").write_text("", encoding="utf-8")
    summary = summarize_run(tmp_path, ".")
    assert summary["lanes"] == ["M0_s1.trace.jsonl", "M2_s0.trace.jsonl"]


def test_summarize_run_reflects_corrupt_lines(tmp_path):
    p = tmp_path / "ledger.jsonl"
    RunLedger(p).mark_done("M2", "t1", "s0", {"outcome": "pass"})
    with p.open("a", encoding="utf-8") as f:
        f.write('{"worker":"M2","task":"t2"')  # 崩潰截斷
    summary = summarize_run(tmp_path, ".")
    assert summary["corrupt_lines"] == 1


def test_tail_records_sorted_and_limited(tmp_path):
    led = RunLedger(tmp_path / "ledger.jsonl")
    for i in range(5):
        led.mark_done("M2", f"t{i}", "s0", {"outcome": "pass", "ts_ms": 5 - i})  # 故意倒序寫入
    tail = tail_records(tmp_path, ".", limit=2)
    assert [r["ts_ms"] for r in tail] == [4, 5]  # 依 ts_ms 升冪排序後取最後 2 筆（最新的兩筆）


def test_is_safe_run_id_rejects_traversal():
    assert _is_safe_run_id(".")
    assert _is_safe_run_id("x1_pilot")
    assert not _is_safe_run_id("..")
    assert not _is_safe_run_id("../etc")
    assert not _is_safe_run_id("a/b")
    assert not _is_safe_run_id("")


# === HTTP：GET /api/runs、控制旗標 =============================================

def test_api_runs_lists_summaries(tmp_path):
    RunLedger(tmp_path / "solo" / "ledger.jsonl").mark_done(
        "M2", "t1", "s0", {"outcome": "pass", "family": "f", "ts_ms": 1}
    )
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        html = urllib.request.urlopen(_url(server, "/"), timeout=5).read().decode()
        assert "<!doctype html>" in html.lower()
        assert "cdn" not in html.lower()

        runs = json.loads(urllib.request.urlopen(_url(server, "/api/runs"), timeout=5).read())
        assert runs[0]["run_id"] == "solo"
        assert runs[0]["total_done"] == 1

        detail = json.loads(
            urllib.request.urlopen(_url(server, "/api/runs/solo"), timeout=5).read()
        )
        assert detail["by_outcome"]["pass"] == 1
    finally:
        server.shutdown()
        server.server_close()


def test_api_runs_log_endpoint(tmp_path):
    RunLedger(tmp_path / "solo" / "ledger.jsonl").mark_done(
        "M2", "t1", "s0", {"outcome": "pass", "ts_ms": 1}
    )
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        rows = json.loads(
            urllib.request.urlopen(_url(server, "/api/runs/solo/log?limit=10"), timeout=5).read()
        )
        assert len(rows) == 1 and rows[0]["task"] == "t1"
    finally:
        server.shutdown()
        server.server_close()


def test_api_unsafe_run_id_is_404(tmp_path):
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        try:
            urllib.request.urlopen(_url(server, "/api/runs/../secret"), timeout=5)
            assert False, "應該要 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_control_pause_resume_via_http(tmp_path):
    run_dir = tmp_path / "solo"
    RunLedger(run_dir / "ledger.jsonl").mark_done("M2", "t1", "s0", {"outcome": "pass"})
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        resp = json.loads(_post(server, "/api/runs/solo/control", {"cmd": "pause"}).read())
        assert resp["state"] == "paused"
        assert RunControl(run_dir / "control.json").state() == "paused"

        resp = json.loads(_post(server, "/api/runs/solo/control", {"cmd": "resume"}).read())
        assert resp["state"] == "running"
    finally:
        server.shutdown()
        server.server_close()


def test_control_stop_and_skip_via_http(tmp_path):
    run_dir = tmp_path / "."
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        resp = json.loads(_post(server, "/api/runs/./control", {"cmd": "stop"}).read())
        assert resp["state"] == "stop_after_current"

        _post(server, "/api/runs/./control", {"cmd": "skip", "task_id": "t7"})
        control = RunControl(run_dir / "control.json")
        assert control.consume_skip("t7")
    finally:
        server.shutdown()
        server.server_close()


def test_control_skip_without_task_id_is_400(tmp_path):
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        try:
            _post(server, "/api/runs/./control", {"cmd": "skip"})
            assert False, "應該要 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()
        server.server_close()


def test_control_unknown_cmd_is_400(tmp_path):
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        try:
            _post(server, "/api/runs/./control", {"cmd": "nonsense"})
            assert False, "應該要 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()
        server.server_close()


# === 來源開關（能調用所有資料、可以開關）=========================================

def test_sources_default_all_on_and_toggle_persists(tmp_path):
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        src = json.loads(urllib.request.urlopen(_url(server, "/api/sources"), timeout=5).read())
        assert src == {"runs": True, "eco": True, "lmstudio": True, "hermes": True}
        src = json.loads(_post(server, "/api/sources", {"source": "eco", "enabled": False}).read())
        assert src["eco"] is False
    finally:
        server.shutdown()
        server.server_close()
    # 開關持久化在 runs_root/monitor_config.json：新 server 讀同一 root 仍是關的
    server2 = make_run_monitor(tmp_path, port=0)
    _serve(server2)
    try:
        src = json.loads(urllib.request.urlopen(_url(server2, "/api/sources"), timeout=5).read())
        assert src["eco"] is False and src["runs"] is True
    finally:
        server2.shutdown()
        server2.server_close()


def test_disabled_source_short_circuits_upstream(tmp_path):
    calls = {"n": 0}

    def fake_get(url):
        calls["n"] += 1
        return b'{"machines": []}'

    server = make_run_monitor(tmp_path, port=0, lmstudio_url="http://hub.example",
                              http_get=fake_get)
    _serve(server)
    try:
        _post(server, "/api/sources", {"source": "lmstudio", "enabled": False})
        got = json.loads(urllib.request.urlopen(_url(server, "/api/lmstudio"), timeout=5).read())
        assert got == {"enabled": False}
        assert calls["n"] == 0  # 關掉的來源完全不打上游
        # 關閉時操作類 POST 也擋（409）
        _post(server, "/api/sources", {"source": "hermes", "enabled": False})
        try:
            _post(server, "/api/hermes/fetch", {})
            assert False, "應該要 409"
        except urllib.error.HTTPError as e:
            assert e.code == 409
    finally:
        server.shutdown()
        server.server_close()


def test_unknown_source_is_400(tmp_path):
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        try:
            _post(server, "/api/sources", {"source": "nonsense", "enabled": False})
            assert False, "應該要 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()
        server.server_close()


# === eco 來源（B：roster/scoreboard/trust/wipe）==================================

def test_eco_unconfigured_and_missing_root_never_creates(tmp_path):
    # 未設定 eco_root
    server = make_run_monitor(tmp_path / "runs", port=0)
    _serve(server)
    try:
        got = json.loads(urllib.request.urlopen(_url(server, "/api/eco"), timeout=5).read())
        assert got == {"configured": False}
    finally:
        server.shutdown()
        server.server_close()
    # 設了 eco_root 但生態不存在：誠實回報 exists=False，且絕不創建任何東西
    eco_root = tmp_path / "eco_missing"
    server2 = make_run_monitor(tmp_path / "runs", port=0, eco_root=eco_root)
    _serve(server2)
    try:
        got = json.loads(urllib.request.urlopen(_url(server2, "/api/eco"), timeout=5).read())
        assert got["configured"] is True and got["exists"] is False
        assert not eco_root.exists()  # GET 不得有生出生態的副作用
    finally:
        server2.shutdown()
        server2.server_close()


def _make_real_eco(root):
    """建一個 2 居民的小生態（名字刻意不在 DEFAULT_ROSTER，驗磁碟發現路徑）。"""
    from vacant_network.ecosystem import Ecosystem

    class ConstBrain:
        name = "const"

        def generate(self, prompt):
            return "```python\ndef solve(s):\n    return s[::-1]\n```"

    return Ecosystem(root, ConstBrain(), roster={"alice": "good", "bob": "good"})


def test_eco_snapshot_reads_existing_without_creating_defaults(tmp_path):
    eco_root = tmp_path / "eco"
    _make_real_eco(eco_root)
    on_disk_before = sorted(p.name for p in (eco_root / "residents").iterdir())

    server = make_run_monitor(tmp_path / "runs", port=0, eco_root=eco_root)
    _serve(server)
    try:
        got = json.loads(urllib.request.urlopen(_url(server, "/api/eco"), timeout=5).read())
        assert got["exists"] is True and got["trust_on"] is True
        names = sorted(r["name"] for r in got["roster"])
        assert names == ["alice", "bob"]
        assert all(r["chain_ok"] for r in got["roster"])
        assert all(r["tier"] == "?" for r in got["roster"])  # 非預設名冊 → tier 未知，不硬編
        # 監測讀取絕不補生預設居民（good_1/saboteur_1 等）
        assert sorted(p.name for p in (eco_root / "residents").iterdir()) == on_disk_before
    finally:
        server.shutdown()
        server.server_close()


def test_eco_trust_toggle_writes_state_json(tmp_path):
    eco_root = tmp_path / "eco"
    _make_real_eco(eco_root)
    server = make_run_monitor(tmp_path / "runs", port=0, eco_root=eco_root)
    _serve(server)
    try:
        res = json.loads(_post(server, "/api/eco/trust", {"on": False}).read())
        assert res == {"ok": True, "trust_on": False}
        assert json.loads((eco_root / "state.json").read_text(encoding="utf-8"))["trust_on"] is False
        got = json.loads(urllib.request.urlopen(_url(server, "/api/eco"), timeout=5).read())
        assert got["trust_on"] is False
    finally:
        server.shutdown()
        server.server_close()


def test_eco_wipe_via_http(tmp_path):
    eco_root = tmp_path / "eco"
    _make_real_eco(eco_root)
    server = make_run_monitor(tmp_path / "runs", port=0, eco_root=eco_root)
    _serve(server)
    try:
        res = json.loads(_post(server, "/api/eco/wipe", {"name": "alice"}).read())
        assert res["ok"] is True and res["name"] == "alice"
        # WIPE 事件進 ledger（事件流是真相層）
        events = (eco_root / "ledger" / "events.jsonl").read_text(encoding="utf-8")
        assert '"WIPE"' in events
        # 不存在的居民誠實拒絕
        try:
            _post(server, "/api/eco/wipe", {"name": "nobody"})
            assert False, "應該要 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()
        server.server_close()


# === lmstudio 來源（C：hub 代理）=================================================

def _fake_hub_get(overview, logs=None, events=None):
    """依 URL 分流的假 hub：overview / logs(含 only_errors) / events。"""

    def get(url):
        if "/_mon/api/overview" in url:
            return json.dumps(overview).encode()
        if "/_mon/api/logs" in url:
            if "only_errors" in url:
                return json.dumps([r for r in (logs or [])
                                   if (r.get("status_code") or 200) >= 400]).encode()
            return json.dumps(logs or []).encode()
        if "/api/events" in url:
            return json.dumps({"events": events or []}).encode()
        raise AssertionError(f"unexpected url: {url}")

    return get


def test_lmstudio_proxy_passthrough_with_probe_and_errors(tmp_path):
    fake_ov = {"totals": {"requests": 5}, "machines": [{"name": "1003", "reachable": True}]}
    logs = [
        {"machine": "1003", "path": "[gw] /v1/chat/completions", "status_code": 200,
         "latency_ms": 1000.0, "completion_tokens": 100},   # 100 tok/s
        {"machine": "1003", "path": "[gw] /v1/chat/completions", "status_code": 200,
         "latency_ms": 3000.0, "completion_tokens": 150},   # 50 tok/s
        {"machine": "1003", "path": "[gw] /v1/models", "status_code": 200,
         "latency_ms": 5.0},                                 # 非 chat：不計入探針
        {"machine": "1003", "path": "[gw] /api/v1/chat", "status_code": 400,
         "latency_ms": 3.0, "error": "max_output_tokens"},   # 錯誤：進錯誤清單
    ]
    events = [{"iso": "2026-07-22 10:00:00", "machine": "1003",
               "model": "qwen/x", "event": "loaded"}]
    server = make_run_monitor(tmp_path, port=0, lmstudio_url="http://hub.example",
                              http_get=_fake_hub_get(fake_ov, logs, events))
    _serve(server)
    try:
        got = json.loads(urllib.request.urlopen(_url(server, "/api/lmstudio"), timeout=5).read())
        assert got["configured"] is True and len(got["hubs"]) == 1
        hub = got["hubs"][0]
        assert hub["ok"] is True and hub["overview"] == fake_ov
        p = hub["probe"]["1003"]
        assert p["n"] == 2               # 只計 chat 的 200
        assert p["med_ms"] == 3000       # 兩筆的上中位
        assert p["med_tok_s"] == 100.0
        assert len(hub["errors"]) == 1 and hub["errors"][0]["status"] == 400
        assert hub["events"][0]["event"] == "loaded"
    finally:
        server.shutdown()
        server.server_close()


def test_lmstudio_multi_hub(tmp_path):
    def get(url):
        if "hub-a" in url and "/_mon/api/overview" in url:
            return b'{"totals": {"requests": 1}, "machines": []}'
        if "hub-b" in url:
            raise ConnectionError("hub-b 掛了")
        return b"[]" if "/logs" in url else b'{"events": []}'

    server = make_run_monitor(tmp_path, port=0,
                              lmstudio_url="http://hub-a,http://hub-b", http_get=get)
    _serve(server)
    try:
        got = json.loads(urllib.request.urlopen(_url(server, "/api/lmstudio"), timeout=5).read())
        assert len(got["hubs"]) == 2
        assert got["hubs"][0]["ok"] is True
        assert got["hubs"][1]["ok"] is False and "hub-b 掛了" in got["hubs"][1]["error"]
    finally:
        server.shutdown()
        server.server_close()


def test_lmstudio_unconfigured(tmp_path):
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        got = json.loads(urllib.request.urlopen(_url(server, "/api/lmstudio"), timeout=5).read())
        assert got == {"configured": False}
    finally:
        server.shutdown()
        server.server_close()


# === hermes 來源（遠端日誌收取）===================================================

def _cp(returncode, stdout=b"", stderr=b""):
    return subprocess.CompletedProcess(args=[], returncode=returncode,
                                       stdout=stdout, stderr=stderr)


def _fake_remote_ssh(files):
    """模擬遠端：實作 fetch 的 SIZE 協定（wc -c + tail -c +offset）。"""
    import re

    def run(host, command):
        m = re.search(r"tail -c \+(\d+) (?:'([^']+)'|(\S+))", command)
        off = int(m.group(1)) - 1
        path = m.group(2) or m.group(3)
        if path not in files:
            return _cp(0, stdout=b"SIZE:-1\n")
        data = files[path]
        return _cp(0, stdout=f"SIZE:{len(data)}\n".encode() + data[off:])

    return run


def test_hermes_fetch_incremental_full_history(tmp_path):
    """增量收取：第一次拉全量、追加後只拉新增段，本機保完整歷史＋sha256 索引。"""
    files = {"vacant_traces/vac_app.jsonl": b'{"call": 1}\n'}
    server = make_run_monitor(tmp_path, port=0, hermes_ssh="zongon@vm",
                              hermes_paths=("vacant_traces/vac_app.jsonl",),
                              ssh_run=_fake_remote_ssh(files))
    _serve(server)
    try:
        res = json.loads(_post(server, "/api/hermes/fetch", {}).read())
        e = res["results"][0]
        assert e["ok"] and e["new_bytes"] == 12 and e["total_bytes"] == 12
        # 遠端追加 → 第二次只拉新增
        files["vacant_traces/vac_app.jsonl"] += b'{"call": 2}\n'
        res = json.loads(_post(server, "/api/hermes/fetch", {}).read())
        e = res["results"][0]
        assert e["new_bytes"] == 12 and e["total_bytes"] == 24
        full = tmp_path / "hermes_logs" / "full_vac_app.jsonl"
        assert full.read_bytes() == files["vacant_traces/vac_app.jsonl"]  # 完整歷史，非殘尾
        # sha256 索引逐次追加
        idx = [json.loads(ln) for ln in
               (tmp_path / "hermes_logs" / "index.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(idx) == 2 and idx[-1]["total_bytes"] == 24 and idx[-1]["sha256"]
    finally:
        server.shutdown()
        server.server_close()


def test_hermes_fetch_rotation_archives_history(tmp_path):
    """遠端重鑄（變小）：本機舊史歸檔、從頭重拉——歷史永不覆蓋。"""
    files = {"vacant_traces/vac_wire.jsonl": b"AAAA-old-history\n"}
    server = make_run_monitor(tmp_path, port=0, hermes_ssh="zongon@vm",
                              hermes_paths=("vacant_traces/vac_wire.jsonl",),
                              ssh_run=_fake_remote_ssh(files))
    _serve(server)
    try:
        _post(server, "/api/hermes/fetch", {})
        files["vacant_traces/vac_wire.jsonl"] = b"NEW\n"  # 重開機重鑄，變小
        res = json.loads(_post(server, "/api/hermes/fetch", {}).read())
        e = res["results"][0]
        assert e["ok"] and e["total_bytes"] == 4
        logs = tmp_path / "hermes_logs"
        archives = list(logs.glob("archive_*_vac_wire.jsonl"))
        assert len(archives) == 1 and b"old-history" in archives[0].read_bytes()
        assert (logs / "full_vac_wire.jsonl").read_bytes() == b"NEW\n"
    finally:
        server.shutdown()
        server.server_close()


def test_hermes_fetch_missing_remote_file_honest(tmp_path):
    server = make_run_monitor(tmp_path, port=0, hermes_ssh="zongon@vm",
                              hermes_paths=("vacant_traces/vac_app.jsonl",),
                              ssh_run=_fake_remote_ssh({}))
    _serve(server)
    try:
        res = json.loads(_post(server, "/api/hermes/fetch", {}).read())
        assert res["ok"] is False
        assert "不存在" in res["results"][0]["error"]
    finally:
        server.shutdown()
        server.server_close()


def test_hermes_app_records_endpoint(tmp_path):
    logs = tmp_path / "hermes_logs"
    logs.mkdir(parents=True)
    (logs / "full_vac_app.jsonl").write_text(
        json.dumps({"t": "12:00:01", "kind": "generate", "brain": "b",
                    "latency_s": 28.5, "prompt": "題目" * 2000, "answer": "code",
                    "error": None}) + "\n", encoding="utf-8")
    server = make_run_monitor(tmp_path, port=0, hermes_ssh="zongon@vm",
                              hermes_paths=("vacant_traces/vac_app.jsonl",),
                              ssh_run=_fake_remote_ssh({}))
    _serve(server)
    try:
        rows = json.loads(urllib.request.urlopen(
            _url(server, "/api/hermes/app_records"), timeout=5).read())
        assert len(rows) == 1
        assert rows[0]["kind"] == "generate" and rows[0]["latency_s"] == 28.5
        assert len(rows[0]["prompt"]) <= 2000  # 面板只給截斷摘要，全文在磁碟
    finally:
        server.shutdown()
        server.server_close()


def test_housekeeper_auto_fetch_and_notify_dedup(tmp_path):
    """管家：自動收取有跑；停滯通知只在狀態轉變推一次（不轟炸）。"""
    import time as _time

    led = RunLedger(tmp_path / "night" / "ledger.jsonl")
    led.mark_done("M2", "t1", "s0", {"outcome": "pass", "ts_ms": 1_000})  # 遠古 → 必停滯
    files = {"vacant_traces/vac_app.jsonl": b"x\n"}
    notes = []
    server = make_run_monitor(
        tmp_path, port=0, hermes_ssh="zongon@vm",
        hermes_paths=("vacant_traces/vac_app.jsonl",),
        ssh_run=_fake_remote_ssh(files),
        hermes_auto_s=0.05, house_tick_s=0.05,
        notify_url="http://ntfy.example/topic",
        notify_post=lambda url, text: notes.append(text),
    )
    _serve(server)
    try:
        deadline = _time.time() + 3
        while _time.time() < deadline:
            if notes and (tmp_path / "hermes_logs" / "full_vac_app.jsonl").exists():
                break
            _time.sleep(0.05)
        assert (tmp_path / "hermes_logs" / "full_vac_app.jsonl").exists()  # 自動收取跑了
        assert any("night" in n and "無新進度" in n for n in notes)  # 停滯有推
        n_before = len([n for n in notes if "無新進度" in n])
        _time.sleep(0.3)
        n_after = len([n for n in notes if "無新進度" in n])
        assert n_after == n_before  # 同狀態不重複推
    finally:
        server.shutdown()
        server.server_close()


def test_pull_gateway_records(tmp_path):
    from vacant_network.run_monitor import pull_gateway_records

    led = RunLedger(tmp_path / "r1" / "ledger.jsonl")
    led.mark_done("M2", "t1", "s0", {"outcome": "pass", "ts_ms": 1_000_000})
    led.mark_done("M2", "t2", "s0", {"outcome": "pass", "ts_ms": 2_000_000})
    seen = {}

    def fake_get(url):
        seen["url"] = url
        return json.dumps({"rows": [{"id": 1, "model": "m"}]}).encode()

    res = pull_gateway_records(tmp_path, "r1", "http://hub:8766", http_get=fake_get)
    assert res["ok"] and res["count"] == 1
    assert "since=880" in seen["url"] and "until=2120" in seen["url"]  # ±120s 窗口
    saved = json.loads((tmp_path / "r1" / "gateway_records.json").read_text(encoding="utf-8"))
    assert saved["meta"]["count"] == 1 and saved["rows"][0]["id"] == 1


def test_pull_gateway_records_no_stamps_honest(tmp_path):
    from vacant_network.run_monitor import pull_gateway_records

    (tmp_path / "empty").mkdir()
    RunLedger(tmp_path / "empty" / "ledger.jsonl")  # 空 run
    res = pull_gateway_records(tmp_path, "empty", "http://hub:8766",
                               http_get=lambda u: b"[]")
    assert res["ok"] is False and "時間戳" in res["error"]


def test_hermes_auth_failure_shows_key_hint(tmp_path):
    def fake_ssh(host, command):
        return _cp(255, stderr=b"user1@vm: Permission denied (publickey,password).")

    server = make_run_monitor(tmp_path, port=0, hermes_ssh="user1@vm",
                              hermes_paths=("/tmp/vac_app.jsonl",), ssh_run=fake_ssh)
    _serve(server)
    try:
        res = json.loads(_post(server, "/api/hermes/fetch", {}).read())
        assert res["ok"] is False
        assert "Permission denied" in res["results"][0]["error"]
        assert "金鑰" in res["hint"] and "user1@vm" in res["hint"]  # 誠實失敗＋一行修法
    finally:
        server.shutdown()
        server.server_close()


def test_hermes_error_strips_ssh_noise(tmp_path):
    """真正的錯誤（No such file）不能被 ssh 的 PQ 警告噪音蓋住。"""
    noisy = (b"** WARNING: connection is not using a post-quantum key exchange algorithm.\n"
             b"** This session may be vulnerable to \"store now, decrypt later\" attacks.\n"
             b"tail: cannot open '/tmp/vac_app.jsonl' for reading: No such file or directory\n")

    def fake_ssh(host, command):
        return _cp(1, stderr=noisy)

    server = make_run_monitor(tmp_path, port=0, hermes_ssh="u@vm",
                              hermes_paths=("/tmp/vac_app.jsonl",), ssh_run=fake_ssh)
    _serve(server)
    try:
        res = json.loads(_post(server, "/api/hermes/fetch", {}).read())
        err = res["results"][0]["error"]
        assert "No such file" in err
        assert "post-quantum" not in err  # 噪音被濾掉
    finally:
        server.shutdown()
        server.server_close()


def test_hermes_unconfigured(tmp_path):
    server = make_run_monitor(tmp_path, port=0)
    _serve(server)
    try:
        got = json.loads(urllib.request.urlopen(_url(server, "/api/hermes"), timeout=5).read())
        assert got["configured"] is False
        res = json.loads(_post(server, "/api/hermes/fetch", {}).read())
        assert res["ok"] is False and "--hermes-ssh" in res["error"]
    finally:
        server.shutdown()
        server.server_close()


# === B-6：進度/速率/ETA ==========================================================

def test_summarize_run_rate_and_eta_with_manifest(tmp_path):
    led = RunLedger(tmp_path / "ledger.jsonl")
    base = 1_000_000
    for i in range(5):  # 每 30 秒完成一格 → 速率 2/min
        led.mark_done("M2", f"t{i}", "s0",
                      {"outcome": "pass", "family": "f", "ts_ms": base + i * 30_000})
    (tmp_path / "manifest.json").write_text(
        json.dumps({"planned_total": 10}), encoding="utf-8")
    s = summarize_run(tmp_path, ".")
    assert s["planned_total"] == 10
    assert s["rate_per_min"] == 2.0
    assert s["eta_min"] == 2  # 剩 5 格 ÷ 2/min
    assert s["first_ts_ms"] == base  # 簡易檢視「執行時長」的起點


def test_summarize_run_no_manifest_is_honest_none(tmp_path):
    led = RunLedger(tmp_path / "ledger.jsonl")
    led.mark_done("M2", "t1", "s0", {"outcome": "pass", "ts_ms": 1_000_000})
    s = summarize_run(tmp_path, ".")
    assert s["planned_total"] is None
    assert s["eta_min"] is None  # 不猜總數＝不給假 ETA


def test_summarize_run_corrupt_manifest_tolerated(tmp_path):
    RunLedger(tmp_path / "ledger.jsonl").mark_done("M2", "t1", "s0", {"outcome": "pass"})
    (tmp_path / "manifest.json").write_text("{broken", encoding="utf-8")
    assert summarize_run(tmp_path, ".")["planned_total"] is None


# === sparkline 分桶（監測台 signal-row 的趨勢小圖資料源）==========================

def test_spark_buckets_count_and_zero_fill(tmp_path):
    # 桶 0 兩格（1 pass 1 fail）、桶 2 一格（pass）→ 中間桶 1 補零
    led = RunLedger(tmp_path / "ledger.jsonl")
    led.mark_done("M2", "t1", "s0", {"outcome": "pass", "ts_ms": 10_000})
    led.mark_done("M2", "t2", "s0", {"outcome": "fail", "ts_ms": 20_000})
    led.mark_done("M2", "t3", "s0", {"outcome": "pass", "ts_ms": 10_000 + 2 * 300_000})
    s = summarize_run(tmp_path, ".")
    assert s["spark"] == {"bucket_s": 300, "t0_ms": 0,
                          "buckets": [[2, 1], [0, 0], [1, 1]]}


def test_spark_none_when_no_ts_or_single_bucket(tmp_path):
    # 無時戳 → None（畫不出線就不給假資料）
    RunLedger(tmp_path / "a" / "ledger.jsonl").mark_done(
        "M2", "t1", "s0", {"outcome": "pass"})
    assert summarize_run(tmp_path / "a", ".")["spark"] is None
    # 全部擠在同一個 5 分鐘桶 → 也是 None（<2 個非空桶）
    led = RunLedger(tmp_path / "b" / "ledger.jsonl")
    led.mark_done("M2", "t1", "s0", {"outcome": "pass", "ts_ms": 1_000})
    led.mark_done("M2", "t2", "s0", {"outcome": "pass", "ts_ms": 2_000})
    assert summarize_run(tmp_path / "b", ".")["spark"] is None


def test_ack_marks_autoclears_on_new_activity_and_unack(tmp_path):
    # 停滯知悉（triage）：monitor 端標記，不碰 ledger；新進度自動失效
    led = RunLedger(tmp_path / "r1" / "ledger.jsonl")
    led.mark_done("M0", "t1", "s0", {"outcome": "pass", "ts_ms": 1_000})
    (tmp_path / "r1" / "manifest.json").write_text(
        json.dumps({"planned_total": 5}), encoding="utf-8")
    server = make_run_monitor(tmp_path, port=0, stall_min=0.001)
    _serve(server)
    try:
        runs = json.loads(urllib.request.urlopen(_url(server, "/api/runs"), timeout=5).read())
        assert runs[0]["stalled"] is True and runs[0]["acked"] is False
        assert runs[0]["stall_min"] == 0.001  # 前端「閒置對門檻」對照格用
        assert runs[0]["late_min"] == 0.0005  # 未設 --late-min → stall 的一半
        assert runs[0]["late"] is False       # 已 stalled → late 讓位（互斥）
        _post(server, "/api/runs/r1/ack", {"on": True})
        runs = json.loads(urllib.request.urlopen(_url(server, "/api/runs"), timeout=5).read())
        assert runs[0]["acked"] is True
        # 有新進度 → 自動解除（知悉只蓋住當時那一次停滯）
        led.mark_done("M0", "t2", "s0", {"outcome": "pass", "ts_ms": 9_999_999_999_999})
        runs = json.loads(urllib.request.urlopen(_url(server, "/api/runs"), timeout=5).read())
        assert runs[0]["acked"] is False
        # 顯式取消也要通
        _post(server, "/api/runs/r1/ack", {"on": True})
        _post(server, "/api/runs/r1/ack", {"on": False})
        runs = json.loads(urllib.request.urlopen(_url(server, "/api/runs"), timeout=5).read())
        assert runs[0]["acked"] is False
    finally:
        server.shutdown()


def test_spark_caps_at_36_buckets(tmp_path):
    # 時間跨 40 桶 → 只留最後 36 桶（3 小時窗），t0_ms 對齊截窗後的首桶
    led = RunLedger(tmp_path / "ledger.jsonl")
    for i in range(41):  # 桶 0..40 各一格
        led.mark_done("M2", f"t{i}", "s0",
                      {"outcome": "pass", "ts_ms": i * 300_000 + 1})
    s = summarize_run(tmp_path, ".")
    assert len(s["spark"]["buckets"]) == 36
    assert s["spark"]["t0_ms"] == 5 * 300_000  # 桶 5 起（40-35）
    assert all(b == [1, 1] for b in s["spark"]["buckets"])


# === B-5：token 認證 ==============================================================

def test_post_requires_token_when_configured(tmp_path):
    server = make_run_monitor(tmp_path, port=0, token="s3cret")
    _serve(server)
    try:
        # 沒帶 token 的 POST → 401；GET 讀取不擋
        try:
            _post(server, "/api/sources", {"source": "eco", "enabled": False})
            assert False, "應該要 401"
        except urllib.error.HTTPError as e:
            assert e.code == 401
        src = json.loads(urllib.request.urlopen(_url(server, "/api/sources"), timeout=5).read())
        assert src["eco"] is True  # 剛剛那發被擋掉、沒生效
        # 帶對 token → 通過
        req = urllib.request.Request(
            _url(server, "/api/sources"),
            data=json.dumps({"source": "eco", "enabled": False}).encode(),
            headers={"Content-Type": "application/json", "X-Vacant-Token": "s3cret"},
            method="POST")
        res = json.loads(urllib.request.urlopen(req, timeout=5).read())
        assert res["eco"] is False
    finally:
        server.shutdown()
        server.server_close()


def test_non_loopback_bind_without_token_refused(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        make_run_monitor(tmp_path, port=0, host="0.0.0.0")


# === B-4：遠端生態鏡像 ============================================================

def _tar_of_dir(root):
    """把一個目錄打成 tar bytes（模擬遠端 `tar -C root -cf - .` 的 stdout）。"""
    import io
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        tf.add(root, arcname=".")
    return buf.getvalue()


def test_mirror_eco_roundtrip_and_readonly(tmp_path):
    # 「遠端」生態：真的建一個（含簽章 logbook），tar 給假 ssh_run 回傳
    remote_eco = tmp_path / "remote_eco"
    _make_real_eco(remote_eco)
    tar_bytes = _tar_of_dir(remote_eco)

    def fake_ssh(host, command):
        assert "tar" in command and "/home/user1/.vacant-mcp" in command
        return _cp(0, stdout=tar_bytes)

    runs_root = tmp_path / "runs"
    server = make_run_monitor(
        runs_root, port=0, eco_root=tmp_path / "local_eco_absent",
        hermes_ssh="user1@vm", hermes_eco_root="/home/user1/.vacant-mcp",
        ssh_run=fake_ssh)
    _serve(server)
    try:
        # 鏡像前：本機不存在
        got = json.loads(urllib.request.urlopen(_url(server, "/api/eco"), timeout=5).read())
        assert got["exists"] is False
        # 拉鏡像
        res = json.loads(_post(server, "/api/hermes/mirror_eco", {}).read())
        assert res["ok"] is True and res["files"] > 0
        assert (runs_root / "eco_mirror" / ".mirrored_at").exists()
        # 鏡像後：eco 面板讀到複本，標 mirror=True，roster/簽章鏈齊全
        got = json.loads(urllib.request.urlopen(_url(server, "/api/eco"), timeout=5).read())
        assert got["exists"] is True and got["mirror"] is True
        assert sorted(r["name"] for r in got["roster"]) == ["alice", "bob"]
        assert all(r["chain_ok"] for r in got["roster"])  # 簽章鏈在複本上仍可驗
        assert got["mirrored_at_ms"] is not None
        # 鏡像唯讀：trust/wipe 一律拒絕
        res = json.loads(_post(server, "/api/eco/trust", {"on": False}).read())
        assert res["ok"] is False and "唯讀" in res["error"]
        try:
            _post(server, "/api/eco/wipe", {"name": "alice"})
            assert False, "應該要 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()
        server.server_close()


def test_mirror_eco_auth_failure_hint(tmp_path):
    def fake_ssh(host, command):
        return _cp(255, stderr=b"user1@vm: Permission denied (publickey,password).")

    server = make_run_monitor(tmp_path, port=0, hermes_ssh="user1@vm",
                              hermes_eco_root="/home/user1/.vacant-mcp", ssh_run=fake_ssh)
    _serve(server)
    try:
        res = json.loads(_post(server, "/api/hermes/mirror_eco", {}).read())
        assert res["ok"] is False and "金鑰" in res["hint"]
    finally:
        server.shutdown()
        server.server_close()


def test_local_eco_takes_precedence_over_mirror(tmp_path):
    runs_root = tmp_path / "runs"
    local_eco = tmp_path / "local_eco"
    _make_real_eco(local_eco)
    # 先放一份鏡像（內容無所謂，驗優先序）
    remote_eco = tmp_path / "remote_eco"
    _make_real_eco(remote_eco)

    def fake_ssh(host, command):
        return _cp(0, stdout=_tar_of_dir(remote_eco))

    server = make_run_monitor(runs_root, port=0, eco_root=local_eco,
                              hermes_ssh="u@vm", hermes_eco_root="/r", ssh_run=fake_ssh)
    _serve(server)
    try:
        _post(server, "/api/hermes/mirror_eco", {})
        got = json.loads(urllib.request.urlopen(_url(server, "/api/eco"), timeout=5).read())
        assert got["mirror"] is False  # 本機存在 → 本機優先
        assert got["root"] == str(local_eco)
    finally:
        server.shutdown()
        server.server_close()


# === TraceStats（infra_void 只在 trace 不在 ledger）＋停滯判定 ====================

def _trace_line(task, outcome, ts, policy="M2", seed="s0"):
    return json.dumps({
        "policy": policy, "seed": seed, "task": task, "family": "f",
        "outcome": outcome, "ts_ms": ts,
        "prompt_sha": "x", "answer": "很長的模型輸出" * 50,  # 大欄位：必須被丟棄
    }, ensure_ascii=False) + "\n"


def test_trace_stats_counts_void_and_strips_big_fields(tmp_path):
    p = tmp_path / "M2_s0.trace.jsonl"
    p.write_text(
        _trace_line("t1", "pass", 1000) + _trace_line("t2", "infra_void", 2000)
        + _trace_line("t3", "fail", 3000),
        encoding="utf-8")
    ts = TraceStats()
    got = ts.for_run(tmp_path)
    assert got["trace_total"] == 3 and got["trace_void"] == 1
    assert got["void_rate"] == round(1 / 3, 4)
    assert got["trace_last_ts_ms"] == 3000
    assert [r["task"] for r in got["recent"]] == ["t1", "t2", "t3"]
    assert all("answer" not in r and "prompt_sha" not in r for r in got["recent"])


def test_trace_stats_incremental_append(tmp_path):
    p = tmp_path / "M2_s0.trace.jsonl"
    p.write_text(_trace_line("t1", "pass", 1000), encoding="utf-8")
    ts = TraceStats()
    assert ts.for_run(tmp_path)["trace_total"] == 1
    with p.open("a", encoding="utf-8") as f:
        f.write(_trace_line("t2", "infra_void", 2000))
    got = ts.for_run(tmp_path)
    assert got["trace_total"] == 2 and got["trace_void"] == 1  # 只讀新增段也數對


def test_trace_stats_ignores_partial_last_line(tmp_path):
    p = tmp_path / "M2_s0.trace.jsonl"
    p.write_text(_trace_line("t1", "pass", 1000) + '{"task": "t2", "outc',
                 encoding="utf-8")  # 正在寫入中的半行
    ts = TraceStats()
    got = ts.for_run(tmp_path)
    assert got["trace_total"] == 1 and got["trace_corrupt"] == 0  # 半行留給下一輪，不算損壞
    # 半行補完後，下一輪讀到
    with p.open("a", encoding="utf-8") as f:
        f.write('ome": "pass", "ts_ms": 2000}\n')
    assert ts.for_run(tmp_path)["trace_total"] == 2


def test_trace_stats_truncation_resets_file(tmp_path):
    p = tmp_path / "M2_s0.trace.jsonl"
    p.write_text(_trace_line("t1", "pass", 1000) * 3, encoding="utf-8")
    ts = TraceStats()
    assert ts.for_run(tmp_path)["trace_total"] == 3
    p.write_text(_trace_line("t9", "fail", 9000), encoding="utf-8")  # 重鑄（變短）
    got = ts.for_run(tmp_path)
    assert got["trace_total"] == 1 and [r["task"] for r in got["recent"]] == ["t9"]


def test_enrich_stalled_finished_and_empty():
    now = 10_000_000
    base = {"total_done": 5, "last_activity_ms": now - 20 * 60_000,
            "planned_total": None}
    trace = {"trace_total": 5, "trace_last_ts_ms": now - 20 * 60_000}
    # 20 分鐘沒動、門檻 15 分鐘 → 停滯
    assert _enrich(base, trace, 15.0, now)["stalled"] is True
    # 門檻 30 分鐘 → 不算停滯
    assert _enrich(base, trace, 30.0, now)["stalled"] is False
    # 已達 planned_total → finished，永不報停滯
    done = _enrich({**base, "planned_total": 5}, trace, 15.0, now)
    assert done["finished"] is True and done["stalled"] is False
    # 從沒有任何活動的空 run → 不報（沒開始不等於卡住）
    empty = _enrich({"total_done": 0, "last_activity_ms": 0, "planned_total": None},
                    {"trace_total": 0, "trace_last_ts_ms": 0}, 15.0, now)
    assert empty["stalled"] is False and empty["idle_s"] is None


def test_enrich_late_ladder():
    """late 是 up→late→down 階梯的琥珀中間態：與 stalled 互斥、finished/空 run 不報。"""
    now = 10_000_000
    trace = {"trace_total": 5, "trace_last_ts_ms": 0}
    mk = lambda idle_min: {"total_done": 5, "planned_total": None,
                           "last_activity_ms": now - idle_min * 60_000}
    # 10 分鐘沒動：過 late 門檻（預設 stall 的一半＝7.5m）、未達 stall → late
    r = _enrich(mk(10), trace, 15.0, now)
    assert r["late"] is True and r["stalled"] is False
    # 20 分鐘：進入 stalled，late 讓位（互斥）
    r = _enrich(mk(20), trace, 15.0, now)
    assert r["stalled"] is True and r["late"] is False
    # 5 分鐘：兩者皆非
    r = _enrich(mk(5), trace, 15.0, now)
    assert r["late"] is False and r["stalled"] is False
    # 顯式 late_min 覆寫預設減半
    r = _enrich(mk(5), trace, 15.0, now, late_min=3.0)
    assert r["late"] is True
    # finished 永不報 late
    r = _enrich({**mk(60), "planned_total": 5}, trace, 15.0, now)
    assert r["finished"] is True and r["late"] is False and r["stalled"] is False
    # 空 run 不報
    r = _enrich({"total_done": 0, "last_activity_ms": 0, "planned_total": None},
                {"trace_total": 0, "trace_last_ts_ms": 0}, 15.0, now)
    assert r["late"] is False


def test_summarize_run_by_worker_breakdown(tmp_path):
    led = RunLedger(tmp_path / "ledger.jsonl")
    led.mark_done("M0", "t1", "s0", {"outcome": "fail", "ts_ms": 1})
    led.mark_done("M2", "t1", "s0", {"outcome": "pass", "ts_ms": 2})
    led.mark_done("M2", "t2", "s0", {"outcome": "pass", "ts_ms": 3})
    s = summarize_run(tmp_path, ".")
    assert s["by_worker"]["M0·s0"] == {"pass": 0, "fail": 1, "other": 0}
    assert s["by_worker"]["M2·s0"] == {"pass": 2, "fail": 0, "other": 0}


def test_api_runs_enriched_and_trace_tail(tmp_path):
    run = tmp_path / "solo"
    RunLedger(run / "ledger.jsonl").mark_done(
        "M2", "t1", "s0", {"outcome": "pass", "family": "f", "ts_ms": 1_000})
    (run / "M2_s0.trace.jsonl").write_text(
        _trace_line("t1", "pass", 1_000) + _trace_line("t2", "infra_void", 2_000),
        encoding="utf-8")
    server = make_run_monitor(tmp_path, port=0, stall_min=15.0)
    _serve(server)
    try:
        runs = json.loads(urllib.request.urlopen(_url(server, "/api/runs"), timeout=5).read())
        r = runs[0]
        assert r["trace_void"] == 1 and r["void_rate"] == 0.5
        assert r["stalled"] is True  # ts=秒級假時戳＝很久以前 → 停滯（有活動、未完成）
        assert "by_worker" in r
        tail = json.loads(urllib.request.urlopen(
            _url(server, "/api/runs/solo/trace_tail"), timeout=5).read())
        assert [t["task"] for t in tail] == ["t1", "t2"]
        assert tail[1]["outcome"] == "infra_void"  # ledger 看不到的 void，trace tail 看得到
    finally:
        server.shutdown()
        server.server_close()


# === 整合：真的透過 HTTP 暫停一條正在跑的 run_x1 =================================

def test_pause_via_http_actually_blocks_running_x1(tmp_path):
    from vacant_network.identity import Identity
    from vacant_network.logbook import Logbook
    from vacant_network.memory import MemoryStream
    from vacant_network.x1 import make_family_sequence, run_x1

    tasks = make_family_sequence("string_edge", 3)
    run_dir = tmp_path / "solo"
    control = RunControl(run_dir / "control.json")

    class SlowBrain:
        def __init__(self):
            self.calls = 0

        def generate(self, prompt):
            self.calls += 1
            if self.calls == 2:
                # 第一題做完後，趁第二題開始前用 HTTP 把它暫停住
                server = make_run_monitor(tmp_path, port=0)
                _serve(server)
                try:
                    _post(server, "/api/runs/solo/control", {"cmd": "pause"})
                finally:
                    server.shutdown()
                    server.server_close()
            return "```python\ndef solve(s):\n    return s\n```"

    brain = SlowBrain()
    result = {}

    def _run():
        result["records"] = run_x1(
            brain, "M0", tasks, stream=MemoryStream(Logbook(), Identity.generate()),
            ledger=RunLedger(run_dir / "ledger.jsonl"), control=control,
        )

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=2)
    # 還在 paused 阻塞中：迴圈跑不完，執行緒不該已經結束
    assert t.is_alive()
    assert control.state() == "paused"

    control.resume()
    t.join(timeout=5)
    assert not t.is_alive()
    assert len(result["records"]) == 3


# === hermes 即時串流（HermesLive：直播＋退避重連＋上線自動補收）===================

class _FakeLiveProc:
    """假常駐 ssh：stdout 吐完給定 bytes 後 EOF；stderr 空。"""

    def __init__(self, out: bytes):
        import io
        self.stdout = io.BytesIO(out)
        self.stderr = io.BytesIO(b"")
        self.killed = False

    def kill(self):
        self.killed = True


class _StubHermesForLive:
    """HermesLive 只碰這幾個成員——鴨子型別替身，數 catchup 次數。"""

    def __init__(self):
        self.ssh_host = "user@host"
        self.paths = ("vacant_traces/vac_app.jsonl", "vacant_traces/vac_wire.jsonl")
        self.eco_remote_root = ""
        self.mirror_dir = None
        self.fetch_calls = 0

    def fetch(self):
        self.fetch_calls += 1
        return {"ok": True}


def test_hermes_live_streams_lines_then_marks_offline_and_catches_up():
    import time as _time

    from vacant_network.run_monitor import HermesLive

    stub = _StubHermesForLive()
    stop = threading.Event()
    app_line = json.dumps({"t": "18:00:00", "kind": "generate",
                           "brain": "lmstudio:qwen", "caller": "hermes",
                           "latency_s": 1.2, "prompt": "p" * 3000, "answer": "ok"})
    data = ("VACANT_LIVE_READY\n"
            "==> vacant_traces/vac_app.jsonl <==\n"
            + app_line + "\n"
            + "not-json line\n").encode()
    procs = []

    def popen(host, cmd):
        assert host == "user@host"
        assert "tail -n 0 -F" in cmd and "vac_app" in cmd and "vac_wire" in cmd
        p = _FakeLiveProc(data if not procs else b"")  # 重連後：立刻 EOF
        procs.append(p)
        return p

    live = HermesLive(stub, stop, popen=popen)
    live.start()
    deadline = _time.time() + 5
    snap = {}
    while _time.time() < deadline:
        snap = live.snapshot(limit=10)
        if (snap["status"] == "offline" and len(snap["entries"]) >= 2
                and stub.fetch_calls >= 1):
            break
        _time.sleep(0.02)
    stop.set()
    live.close()
    live.join(timeout=3)

    assert snap["status"] == "offline"          # EOF 後誠實標離線
    assert snap["retry_in_s"] == 5.0            # 第一次失敗 → 5s 後重連
    assert stub.fetch_calls >= 1                # 上線轉換自動補收
    e0, e1 = snap["entries"][0], snap["entries"][1]
    assert e0["file"] == "vac_app.jsonl"        # tail 多檔頭正確歸檔
    assert e0["rec"]["kind"] == "generate"
    assert e0["rec"]["caller"] == "hermes"
    assert len(e0["rec"]["prompt"]) == 2000     # 白名單摘要截斷
    assert "rec" not in e1 and e1["raw"] == "not-json line"  # 非 JSON 保原文


def test_hermes_live_backoff_caps_at_60s():
    from vacant_network.run_monitor import HermesLive

    got = [HermesLive.backoff_delay(n) for n in (1, 2, 3, 4, 5, 6, 99)]
    assert got == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0, 60.0]


def test_hermes_live_route_reports_status_and_default_off(tmp_path):
    import time as _time

    # 未開 hermes_live：路由誠實回 running:false
    server = make_run_monitor(tmp_path / "a", port=0, hermes_ssh="u@h")
    _serve(server)
    try:
        got = json.loads(urllib.request.urlopen(
            _url(server, "/api/hermes/live"), timeout=5).read())
        assert got == {"running": False}
    finally:
        server.shutdown()

    # 開了：狀態機在跑（connecting/online/offline 之一），entries 為 list
    def popen(host, cmd):
        return _FakeLiveProc(b"VACANT_LIVE_READY\n")

    server2 = make_run_monitor(tmp_path / "b", port=0, hermes_ssh="u@h",
                               hermes_live=True, live_popen=popen)
    _serve(server2)
    try:
        deadline = _time.time() + 5
        got = {}
        while _time.time() < deadline:
            got = json.loads(urllib.request.urlopen(
                _url(server2, "/api/hermes/live"), timeout=5).read())
            if got.get("status") in ("online", "offline"):
                break
            _time.sleep(0.02)
        assert got["running"] is True
        assert got["status"] in ("online", "offline")
        assert isinstance(got["entries"], list)
    finally:
        server2.shutdown()


def test_humanize_trace_translates_wire_and_app_records():
    from vacant_network.run_monitor import _humanize_trace

    # wire：方向 + method → 人話
    assert _humanize_trace({"dir": "hermes->vacant", "msg": {"method": "ping"}}) \
        == "Hermes → vacant：確認在線（ping）"
    assert _humanize_trace({"dir": "hermes->vacant",
                            "msg": {"method": "tools/call", "params": {"name": "delegate"}}}) \
        == "Hermes → vacant：呼叫工具「delegate」"
    assert _humanize_trace({"dir": "vacant->hermes", "msg": {"result": {}}}) \
        == "vacant → Hermes：回覆 OK"
    assert _humanize_trace({"dir": "vacant->hermes",
                            "msg": {"result": {"tools": [1, 2, 3]}}}) \
        == "vacant → Hermes：回覆工具清單（3 個工具）"
    # app：kind/brain/latency/caller → 人話
    got = _humanize_trace({"kind": "generate", "brain": "lmstudio:qwen",
                           "latency_s": 2.5, "caller": "hermes", "verified": True})
    assert "模型呼叫「generate」" in got and "lmstudio:qwen" in got
    assert "2.5s" in got and "hermes" in got and "已驗證通過" in got
    # 認不出的：None（面板保留原文）
    assert _humanize_trace({"weird": 1}) is None


# === 唯讀公開模式（--readonly：對外展示的安全閘）================================

def test_readonly_blocks_all_posts_but_serves_reads(tmp_path):
    RunLedger(tmp_path / "r1" / "ledger.jsonl").mark_done(
        "M0", "t1", "s0", {"outcome": "pass", "ts_ms": 10})
    server = make_run_monitor(tmp_path, port=0, readonly=True)
    _serve(server)
    try:
        # 讀取照常
        runs = json.loads(urllib.request.urlopen(_url(server, "/api/runs"), timeout=5).read())
        assert runs and runs[0]["run_id"] == "r1"
        mode = json.loads(urllib.request.urlopen(_url(server, "/api/mode"), timeout=5).read())
        assert mode == {"readonly": True}
        man = json.loads(urllib.request.urlopen(_url(server, "/manifest.json"), timeout=5).read())
        assert man["name"] == "Vacant 監測台" and man["display"] == "standalone"
        # 任何操作一律 403（含 sources 切換與 hermes 收取）
        for path in ("/api/sources", "/api/hermes/fetch", "/api/runs/r1/control",
                     "/api/runs/r1/ack"):
            try:
                _post(server, path, {"source": "eco", "enabled": False, "cmd": "pause"})
                raise AssertionError(f"{path} 不該成功")
            except urllib.error.HTTPError as e:
                assert e.code == 403, (path, e.code)
                assert "唯讀" in json.loads(e.read()).get("error", "")
    finally:
        server.shutdown()


def test_readonly_allows_public_bind_without_token_and_normal_mode_reports_false(tmp_path):
    # 唯讀模式沒有操作面，允許非 loopback 無 token 繫結（僅表示不再 raise）
    server = make_run_monitor(tmp_path / "a", port=0, host="127.0.0.1", readonly=True)
    server.server_close()  # 沒 serve 過的 server 不能 shutdown()（會永久等 serve loop）
    # 一般模式 /api/mode 回 false（前端據此不掛唯讀徽章）
    server2 = make_run_monitor(tmp_path / "b", port=0)
    _serve(server2)
    try:
        mode = json.loads(urllib.request.urlopen(_url(server2, "/api/mode"), timeout=5).read())
        assert mode == {"readonly": False}
    finally:
        server2.shutdown()


def test_readonly_css_hides_ops_only_not_navigation():
    # 唯讀模式的隱藏必須是 opt-in（.op-only）而非藏掉所有 button/input——
    # 否則公開版連「最近紀錄」展開、搜尋、篩選都會消失（曾經的回歸）。
    assert "body.readonly .op-only" in _PAGE
    assert "body.readonly button" not in _PAGE
    assert "body.readonly input" not in _PAGE
    # 操作件（會發 POST 的）都掛了 op-only：來源開關、run 控制、eco、hermes
    assert _PAGE.count("op-only") >= 8


def test_page_is_integrated_single_view():
    # 單頁整合：詳細版面為主，主從式 runs 元件（人話列＋側面板）在批次執行區內；
    # 雙檢視切換已退役（不留 view-simple/localStorage 痕跡）
    for anchor in ('id="sv-dtext"', 'id="sv-list"', 'id="sv-panel"', 'id="sv-segs"',
                   'class="kpis"', 'id="sec-eco"'):
        assert anchor in _PAGE, anchor
    assert "view-simple" not in _PAGE
    assert "vacant_mon_view" not in _PAGE


# === GitHub 歸檔 runs：從 git ref 讀上游 runs/，ls-remote 對照遠端 ===============

import shutil as _shutil

import pytest as _pytest

from vacant_network.run_monitor import GitHubRuns, _gh_arm_stats

_needs_git = _pytest.mark.skipif(_shutil.which("git") is None, reason="沒有 git")


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, stdin=subprocess.DEVNULL)


def _index_entry(name, kind="real_run", subkind="gain_run", has_summary=True, **kw):
    files = [{"name": "summary.json"}] if has_summary else []
    return {"name": name, "kind": kind, "subkind": subkind, "date": kw.pop("date", "2026-09-01"),
            "files": files, "n_rows_by_arm": kw.pop("n_rows_by_arm", {}),
            "infra_void": kw.pop("infra_void", 0), "complete": kw.pop("complete", True),
            "bank": {"family": "mbppplus"}, **kw}


def _write_upstream(repo, entries, summaries):
    runs = repo / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "INDEX.json").write_text(json.dumps({"generated_by": "test", "runs": entries}),
                                     encoding="utf-8")
    for name, s in summaries.items():
        (runs / name).mkdir(exist_ok=True)
        (runs / name / "summary.json").write_text(
            s if isinstance(s, str) else json.dumps(s), encoding="utf-8")


def _commit(repo, msg):
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)


@_pytest.fixture
def gh_pair(tmp_path):
    """upstream（扮演 GitHub）＋ clone（扮演本機）。"""
    up = tmp_path / "upstream"
    up.mkdir()
    _git(up, "init", "-q", "-b", "main")
    _write_upstream(up, [
        _index_entry("g_a", infra_void=5),
        _index_entry("g_r530", n_rows_by_arm={}),
        _index_entry("g_bad"),
        _index_entry("matrix_x", subkind="agent_matrix_run", has_summary=False,
                     n_rows_by_arm={"M": 4}, complete=None),
        _index_entry("g_dead", kind="aborted", subkind="no_summary", has_summary=False),
        _index_entry("_analysis_r1", kind="analysis", subkind="loop_round_recompute"),
        _index_entry("_smoke", kind="smoke", subkind="probe_or_smoke"),
    ], {
        "g_a": {"arms": {"OFF5": {"tasks": 60, "processed": 60, "infra_void": 5,
                                  "accepted_and_meets_demand": 45}}},
        "g_r530": {"arms": ["A-SOLO"], "arms_stats": {"A-SOLO": {"processed": 5,
                                                                 "infra_void": 0, "deliv": 1}}},
        "g_bad": "{not json",
        "_analysis_r1": {"arms": {}},
    })
    _commit(up, "init")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(up), str(clone)], check=True,
                   capture_output=True, stdin=subprocess.DEVNULL)
    return up, clone


def test_gh_arm_stats_three_layouts_and_honest_none():
    layout, arms = _gh_arm_stats({}, {"arms": {"ON": {"tasks": 10, "infra_void": 2,
                                                       "accepted_and_meets_demand": 7}}})
    # 沒有 processed 也沒有 n_rows_by_arm ⇒ done 不猜
    assert layout == "gain_arms" and arms[0]["done"] is None and arms[0]["delivered"] == 7
    layout, arms = _gh_arm_stats({"n_rows_by_arm": {"ON": 8}},
                                 {"arms": {"ON": {"infra_void": 2,
                                                  "accepted_and_meets_demand": 7}}})
    assert arms[0]["done"] == 10  # rows 不含 void 列：8＋2
    layout, arms = _gh_arm_stats({"n_rows_by_arm": {"M": 4}}, None)
    assert layout == "index_only" and arms == [
        {"arm": "M", "planned": None, "done": 4, "delivered": None, "void": None}]
    # bool 不准被當成數字（isinstance(True, int) 為真）
    _, arms = _gh_arm_stats({}, {"arms": {"X": {"processed": True,
                                                 "accepted_and_meets_demand": 3}}})
    assert arms[0]["done"] is None


@_needs_git
def test_github_runs_reads_ref_lists_by_index_kind(gh_pair):
    _, clone = gh_pair
    gh = GitHubRuns(clone, fetch_every_s=0)
    rows = {r["run_id"]: r for r in gh.runs()}
    # analysis／smoke 依 INDEX 定義不列；aborted 照列
    assert set(rows) == {"g_a", "g_r530", "g_bad", "matrix_x", "g_dead"}
    a = rows["g_a"]
    assert (a["total_delivered"], a["total_done"], a["infra_void"]) == (45, 60, 5)
    assert a["arms"] == [{"arm": "OFF5", "planned": 60, "done": 60,
                          "delivered": 45, "void": 5}]
    r530 = rows["g_r530"]
    assert r530["layout"] == "gain_arms_stats" and r530["total_delivered"] == 1
    # 壞掉的 summary.json：數字是 None，不是 0
    assert rows["g_bad"]["total_delivered"] is None and rows["g_bad"]["arms"] == []
    assert rows["matrix_x"]["layout"] == "index_only" and rows["matrix_x"]["total_done"] == 4
    st = gh.status()
    assert st["by_kind"] == {"real_run": 4, "aborted": 1, "analysis": 1, "smoke": 1}
    assert st["listed"] == 5 and st["read_error"] is None


@_needs_git
def test_github_runs_ignores_uncommitted_worktree_edits(gh_pair):
    _, clone = gh_pair
    (clone / "runs" / "g_a" / "summary.json").write_text(
        json.dumps({"arms": {"OFF5": {"processed": 60, "infra_void": 0,
                                      "accepted_and_meets_demand": 60}}}), encoding="utf-8")
    rows = {r["run_id"]: r for r in GitHubRuns(clone, fetch_every_s=0).runs()}
    assert rows["g_a"]["total_delivered"] == 45  # 讀 origin/main 的位元組，不讀工作樹


@_needs_git
def test_github_runs_detects_behind_then_fetch_syncs(gh_pair):
    up, clone = gh_pair
    gh = GitHubRuns(clone, fetch_every_s=0)
    gh.check_remote()
    assert gh.status()["in_sync"] is True
    # GitHub 上多了一個 run
    entries = json.loads((up / "runs" / "INDEX.json").read_text(encoding="utf-8"))["runs"]
    _write_upstream(up, entries + [_index_entry("g_new", date="2026-10-01")],
                    {"g_new": {"arms": {"ON": {"processed": 3, "infra_void": 0,
                                               "accepted_and_meets_demand": 2}}}})
    _commit(up, "new run")
    gh.check_remote()
    st = gh.status()
    assert st["in_sync"] is False and st["local_sha"] != st["remote_sha"]
    assert "g_new" not in {r["run_id"] for r in gh.runs()}
    assert gh.fetch()["ok"] is True
    st = gh.status()
    assert st["in_sync"] is True
    rows = gh.runs()
    assert rows[0]["run_id"] == "g_new"  # 依日期新到舊
    assert rows[0]["total_delivered"] == 2


def test_github_not_configured_is_honest(tmp_path):
    gh = GitHubRuns(None)
    assert gh.status() == {"configured": False} and gh.runs() == []
    gh = GitHubRuns(tmp_path, fetch_every_s=0)  # 不是 git repo
    assert gh.runs() == []
    assert gh.status()["read_error"]


@_needs_git
def test_github_http_endpoints_and_readonly_fetch_refused(gh_pair, tmp_path):
    _, clone = gh_pair
    server = make_run_monitor(tmp_path / "runs", port=0, github_repo=clone,
                              github_fetch_s=0)
    _serve(server)
    try:
        st = json.loads(urllib.request.urlopen(_url(server, "/api/github"), timeout=10).read())
        assert st["configured"] is True and st["listed"] == 5
        rows = json.loads(urllib.request.urlopen(_url(server, "/api/github/runs"),
                                                 timeout=10).read())
        assert {r["run_id"] for r in rows} >= {"g_a", "g_dead"}
        res = json.loads(_post(server, "/api/github/fetch", {}).read())
        assert res["ok"] is True and res["status"]["in_sync"] is True
    finally:
        server.shutdown()
        server.server_close()
    ro = make_run_monitor(tmp_path / "runs", port=0, github_repo=clone, readonly=True)
    _serve(ro)
    try:
        with _pytest.raises(urllib.error.HTTPError) as ei:
            _post(ro, "/api/github/fetch", {})
        assert ei.value.code == 403
    finally:
        ro.shutdown()
        ro.server_close()


def test_page_has_github_section():
    assert 'id="sec-github"' in _PAGE and "/api/github" in _PAGE


def test_eco_old_wire_format_reports_incompatible_not_500(tmp_path):
    from vacant_network.run_monitor import EcoView

    root = tmp_path / "eco"
    (root / "residents" / "alice").mkdir(parents=True)

    class _Boom(EcoView):
        def _build(self, root):
            raise ValueError("registry state is corrupt; refusing to reset trust history")

        def _discover_names(self, root):
            return ["alice"]

    snap = _Boom(root).snapshot()
    assert snap["incompatible"] is True and snap["exists"] is True
    assert "refusing" in snap["error"]
