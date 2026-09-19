"""`vacant run -- <agent 命令>` V0 的擋門測試。

這一批測的是**承重件**不是便利函式，四條各對應設計裡的一句話：

  · `test_body_bytes_identical_off_vs_on`
      「只差一個開關」那條可比性證據的**可執行版本**。OFF 與 ON 送出去的
      request body 必須**逐位元相同**（sha256 與原始位元組兩邊都比）。
      這條紅了就代表 proxy 在某處 parse-and-reserialize 了，
      那樣兩臂的差就不再只有開關。
  · `test_refused_when_visible_suite_fails` ＋ `test_no_suite_is_fail_closed`
      拒交路徑：驗收沒過 ⇒ 退出碼非 0 ⇒ 收據記 refused。
      量不到（沒有套件）也算拒交，不算通過。
  · `test_receipts_verify_with_the_existing_ruler`
      收據要被**既有的**驗章器驗過（`vacant_network/vrun/verify_receipts.py`；
      `ops/gain/replay/verify_run_receipts.py` 是同一支的 re-export）。
      **不准另寫第二把尺**——所以這條直接 import 那一支。
  · `test_upstream_and_keys_are_not_in_agent_env`
      真上游與真鑰只留在 proxy 行程。

⚠ 本檔零模型呼叫：上游是一個本機假 server，agent 是一支 20 行的 Python。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vacant_network.vrun import envmap, launcher                         # noqa: E402
from vacant_network.vrun import verify_receipts as vrr                   # noqa: E402
from vacant_network.vrun.wireproxy import WireProxy, join_upstream, route  # noqa: E402

#: agent 送出去的 body。**key 的順序刻意不是字典序、空白刻意不規則**——
#: 任何一次 `json.loads`→`json.dumps` 都會把這兩件事抹平，於是 sha256 變掉。
AGENT_BODY = (b'{"model":"m","stream":false,  "messages":[{"role":"user",'
              b'"content":"hi"}],"zz_last":1,"aa_first":2}')

_FAKE_AGENT = r'''
import json, os, sys, urllib.request
base = os.environ["OPENAI_BASE_URL"]
body = {body!r}
req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body,
                             method="POST")
req.add_header("Content-Type", "application/json")
req.add_header("Authorization", "Bearer " + os.environ.get("OPENAI_API_KEY", ""))
with urllib.request.urlopen(req, timeout=30) as r:
    payload = r.read()
mode = sys.argv[1] if len(sys.argv) > 1 else "noop"
if mode == "good":
    open("solution.py", "w").write("def add(a, b):\n    return a + b\n")
elif mode == "bad":
    open("solution.py", "w").write("def add(a, b):\n    return a - b\n")
elif mode == "env":
    open("env.json", "w").write(json.dumps(dict(os.environ)))
sys.stdout.write(payload.decode("utf-8", "replace")[:80])
'''

_VISIBLE_TEST = '''
def check_add():
    from solution import add
    assert add(2, 3) == 5
'''


class _Upstream(BaseHTTPRequestHandler):
    """假上游：一半走 Content-Length、一半走 SSE，兩條路都要被轉送對。"""

    protocol_version = "HTTP/1.1"
    seen: list[dict] = []

    def log_message(self, *a):
        return

    def do_POST(self):                                   # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        type(self).seen.append({"path": self.path, "body": raw,
                                "auth": self.headers.get("Authorization")})
        if self.path.endswith("/stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for part in (b'data: {"a":1}\n\n', b'data: [DONE]\n\n'):
                self.wfile.write(b"%X\r\n%s\r\n" % (len(part), part))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            return
        payload = json.dumps({"ok": True, "echo_sha256":
                              hashlib.sha256(raw).hexdigest()}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def upstream():
    _Upstream.seen = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1},
                     daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1", _Upstream
    srv.shutdown()
    srv.server_close()


def _agent(tmp: pathlib.Path, mode: str = "noop") -> list[str]:
    p = tmp / "fake_agent.py"
    p.write_text(_FAKE_AGENT.replace("{body!r}", repr(AGENT_BODY)),
                 encoding="utf-8")
    return [sys.executable, str(p), mode]


def _ws(tmp: pathlib.Path, name: str) -> pathlib.Path:
    ws = tmp / name
    ws.mkdir(parents=True)
    (ws / "README.md").write_text("task\n", encoding="utf-8")
    return ws


def _suite(tmp: pathlib.Path) -> pathlib.Path:
    d = tmp / "visible"
    d.mkdir(parents=True, exist_ok=True)
    (d / "test_visible.py").write_text(_VISIBLE_TEST, encoding="utf-8")
    return d


def _wire(run_dir: pathlib.Path, arm: str) -> list[dict]:
    p = run_dir / f"wire_{arm}" / "index.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l]


# ── 單元：路由與 base url 拼接 ────────────────────────────────────────────
def test_route_has_exactly_two_paths():
    assert route("/v1/messages") == "anthropic"
    assert route("/v1/messages?beta=1") == "anthropic"
    assert route("/v1/chat/completions") == "openai"
    assert route("/v1/responses") == "openai"


def test_join_upstream_never_doubles_v1():
    assert join_upstream("http://h:1234/v1", "/v1/chat/completions") == \
        "http://h:1234/v1/chat/completions"
    assert join_upstream("https://api.anthropic.com", "/v1/messages") == \
        "https://api.anthropic.com/v1/messages"


# ── 負向控制：OFF 與 ON 的 body 必須逐位元相同 ──────────────────────────
def test_body_bytes_identical_off_vs_on(tmp_path, upstream, monkeypatch):
    base, seen = upstream
    monkeypatch.setenv("OPENAI_BASE_URL", base)
    monkeypatch.setenv("OPENAI_API_KEY", "REAL-KEY-do-not-leak")
    out = {}
    for on in (False, True):
        arm = launcher.ARM_ON if on else launcher.ARM_OFF
        ws = _ws(tmp_path, f"ws_{arm}")
        s = launcher.run(_agent(tmp_path), workspace=ws,
                         run_dir=tmp_path / "run", suite_dir=_suite(tmp_path),
                         vacant_on=on, task_id="bytecmp", sandbox_name="none")
        assert s["requests_seen"] == 1, s
        rows = _wire(tmp_path / "run", arm)
        raw = (tmp_path / "run" / f"wire_{arm}" /
               f"{rows[0]['call_id']}.req.bin").read_bytes()
        out[arm] = (rows[0]["request_sha256"], raw, rows[0]["mode"])

    off, onr = out[launcher.ARM_OFF], out[launcher.ARM_ON]
    assert off[2] == "tee" and onr[2] == "act"          # 真的是兩個模式
    assert off[0] == onr[0], f"sha256 不同：{off[0]} vs {onr[0]}"
    assert off[1] == onr[1] == AGENT_BODY               # 位元組本身也要原樣
    assert off[0] == hashlib.sha256(AGENT_BODY).hexdigest()
    # 上游收到的也要是同一份（證明「原樣」不是只在落盤那一側成立）
    assert [r["body"] for r in seen.seen] == [AGENT_BODY, AGENT_BODY]


def test_streaming_response_is_not_buffered_whole(tmp_path, upstream, monkeypatch):
    """SSE 路徑：上游沒有 Content-Length ⇒ 只有這一種情況才重新分塊。"""
    base, _ = upstream
    monkeypatch.setenv("OPENAI_BASE_URL", base)
    with WireProxy(wire_dir=tmp_path / "w",
                   upstreams=envmap.discover_upstreams(),
                   keys={"openai": "k", "anthropic": ""},
                   sentinel="sent", mode="tee") as px:
        import urllib.request
        req = urllib.request.Request(px.url + "/v1/chat/stream", data=b"{}",
                                     method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
    assert body == b'data: {"a":1}\n\ndata: [DONE]\n\n'
    rec = json.loads((tmp_path / "w" / "index.jsonl").read_text().splitlines()[0])
    assert rec["streamed"] is True and rec["response_bytes"] == len(body)
    assert (tmp_path / "w" / f"{rec['call_id']}.resp.bin").read_bytes() == body


# ── 真鑰／真上游不得進 agent 的 env ──────────────────────────────────────
def test_upstream_and_keys_are_not_in_agent_env(tmp_path, upstream, monkeypatch):
    base, seen = upstream
    monkeypatch.setenv("OPENAI_BASE_URL", base)
    monkeypatch.setenv("OPENAI_API_KEY", "REAL-KEY-do-not-leak")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "REAL-ANTHROPIC")
    ws = _ws(tmp_path, "ws")
    s = launcher.run(_agent(tmp_path, "env"), workspace=ws,
                     run_dir=tmp_path / "run", suite_dir=None,
                     vacant_on=True, task_id="envcheck", sandbox_name="none",
                     allow_no_suite=True)
    env = json.loads((ws / "env.json").read_text(encoding="utf-8"))
    assert env["OPENAI_BASE_URL"] == s["proxy_url"] + "/v1"
    assert env["ANTHROPIC_BASE_URL"] == s["proxy_url"]
    assert env["OPENAI_API_KEY"].startswith("vacant-run-")
    assert "REAL-KEY-do-not-leak" not in json.dumps(env)
    assert "REAL-ANTHROPIC" not in json.dumps(env)
    assert base not in json.dumps(env)
    # proxy 那一側把 sentinel 換回真鑰（否則上游會拒絕）
    assert seen.seen[0]["auth"] == "Bearer REAL-KEY-do-not-leak"


# ── 拒交路徑 ─────────────────────────────────────────────────────────────
def test_refused_when_visible_suite_fails(tmp_path, upstream, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", upstream[0])
    ws = _ws(tmp_path, "ws")
    s = launcher.run(_agent(tmp_path, "bad"), workspace=ws,
                     run_dir=tmp_path / "run", suite_dir=_suite(tmp_path),
                     vacant_on=True, task_id="refuse", sandbox_name="none")
    assert s["stop_reason"] == "visible_fail"
    assert s["accepted"] is False and s["refused"] is True
    assert launcher.exit_code(s) == launcher.EXIT_REFUSED != 0
    rows = [json.loads(l) for l in
            (tmp_path / "run" / "rows.jsonl").read_text().splitlines() if l]
    assert rows[0]["refused"] is True and rows[0]["stop_reason"] == "visible_fail"
    chain = json.loads((tmp_path / "run" / "receipts_RUN-ON.ndjson")
                       .read_text().splitlines()[-1])
    assert chain["type"] == "ws_verdict"
    assert chain["payload"]["accepted"] is False
    assert chain["payload"]["stop_reason"] == "visible_fail"


def test_accepted_when_visible_suite_passes(tmp_path, upstream, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", upstream[0])
    ws = _ws(tmp_path, "ws")
    s = launcher.run(_agent(tmp_path, "good"), workspace=ws,
                     run_dir=tmp_path / "run", suite_dir=_suite(tmp_path),
                     vacant_on=True, task_id="accept", sandbox_name="none")
    assert s["stop_reason"] == "visible_pass" and s["accepted"] is True
    assert launcher.exit_code(s) == 0
    assert s["ws_end_sha256"] != s["ws_start_sha256"]     # agent 真的寫了東西


def test_no_suite_is_fail_closed(tmp_path, upstream, monkeypatch):
    """量不到不是通過——沒有套件而沒明講放行 ⇒ 拒交。"""
    monkeypatch.setenv("OPENAI_BASE_URL", upstream[0])
    ws = _ws(tmp_path, "ws")
    s = launcher.run(_agent(tmp_path), workspace=ws, run_dir=tmp_path / "run",
                     suite_dir=None, vacant_on=True, task_id="nosuite",
                     sandbox_name="none")
    assert s["stop_reason"] == "no_suite" and s["refused"] is True
    assert launcher.exit_code(s) != 0


def test_allow_no_suite_records_null_not_true(tmp_path, upstream, monkeypatch):
    """「沒量」與「量到過」不可以在資料上同形。"""
    monkeypatch.setenv("OPENAI_BASE_URL", upstream[0])
    ws = _ws(tmp_path, "ws")
    s = launcher.run(_agent(tmp_path), workspace=ws, run_dir=tmp_path / "run",
                     suite_dir=None, vacant_on=True, task_id="ungated",
                     sandbox_name="none", allow_no_suite=True)
    assert s["accepted"] is None and s["stop_reason"] == "ungated"
    chain = json.loads((tmp_path / "run" / "receipts_RUN-ON.ndjson")
                       .read_text().splitlines()[-1])
    assert chain["payload"]["accepted_is_null"] is True


def test_off_arm_writes_wire_but_no_receipts(tmp_path, upstream, monkeypatch):
    """鐵律 3 對兩臂都成立：OFF 不 gate，但照樣逐字落盤。"""
    monkeypatch.setenv("OPENAI_BASE_URL", upstream[0])
    ws = _ws(tmp_path, "ws")
    s = launcher.run(_agent(tmp_path, "bad"), workspace=ws,
                     run_dir=tmp_path / "run", suite_dir=_suite(tmp_path),
                     vacant_on=False, task_id="offarm", sandbox_name="none")
    assert s["stop_reason"] == "ungated" and s["accepted"] is None
    assert launcher.exit_code(s) == s["agent_rc"] == 0     # 透傳，不 gate
    assert not (tmp_path / "run" / "receipts_RUN-OFF.ndjson").exists()
    assert len(_wire(tmp_path / "run", launcher.ARM_OFF)) == 1


# ── 收據要被**既有的**那把尺驗過 ─────────────────────────────────────────
def test_receipts_verify_with_the_existing_ruler(tmp_path, upstream, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", upstream[0])
    run_dir = tmp_path / "run"
    for on, mode, tid in ((False, "good", "t_off"), (True, "good", "t_on")):
        launcher.run(_agent(tmp_path, mode), workspace=_ws(tmp_path, f"ws{tid}"),
                     run_dir=run_dir, suite_dir=_suite(tmp_path), vacant_on=on,
                     task_id=tid, sandbox_name="none")
    out = vrr.verify_run(run_dir)
    assert [r["arm"] for r in out] == ["RUN-ON"]
    rec = out[0]
    assert rec["verdict"] == "OK", json.dumps(rec, ensure_ascii=False)[:600]
    assert rec["chain_ok"] is True and rec["logbook_verify_chain"] is True
    assert rec["type_counts"] == {"ws_attempt": 1, "ws_verdict": 1}
    assert rec["arms_without_receipts"] == ["RUN-OFF"]    # OFF 沒收據不是失敗


def test_tampered_workspace_hash_is_caught_by_the_same_ruler(tmp_path, upstream,
                                                             monkeypatch):
    """收據不是擺設：把 `ws_end_sha256` 改掉，既有的尺必須指名抓到。"""
    monkeypatch.setenv("OPENAI_BASE_URL", upstream[0])
    run_dir = tmp_path / "run"
    launcher.run(_agent(tmp_path, "good"), workspace=_ws(tmp_path, "ws"),
                 run_dir=run_dir, suite_dir=_suite(tmp_path), vacant_on=True,
                 task_id="t1", sandbox_name="none")
    p = run_dir / "receipts_RUN-ON.ndjson"
    lines = p.read_text(encoding="utf-8").splitlines()
    e = json.loads(lines[-1])
    e["payload"]["ws_end_sha256"] = "f" * 64
    lines[-1] = json.dumps(e, ensure_ascii=False, separators=(",", ":"),
                           sort_keys=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rec = vrr.verify_run(run_dir)[0]
    assert rec["verdict"] == "BROKEN"
    assert any(f["reason"] == "bad_signature" for f in rec["failures"])


# ── 擋門：收據不准落在工作區裡 ───────────────────────────────────────────
def test_run_dir_inside_workspace_is_refused(tmp_path):
    ws = _ws(tmp_path, "ws")
    with pytest.raises(SystemExit):
        launcher.run(["true"], workspace=ws, run_dir=ws / "out",
                     suite_dir=None, vacant_on=True, task_id="x")


def test_env_meta_is_recorded_for_the_receipt(tmp_path):
    child, meta = envmap.build_child_env("http://127.0.0.1:1/", "SENT",
                                         env={"OPENAI_API_KEY": "real"})
    assert "OPENAI_API_KEY" in meta["stripped"]
    assert child["OPENAI_API_KEY"] == "SENT"
    assert child["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:1"
    assert child["OPENAI_BASE_URL"] == "http://127.0.0.1:1/v1"
