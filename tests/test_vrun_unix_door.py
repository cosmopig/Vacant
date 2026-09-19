"""enclosure 的那扇門：**會終結 HTTP 的 unix-socket proxy**（2026-09-20）。

守的是三條性質，每一條都配一個負控制（沒有負控制的「擋住了」等於沒量）：

1. 門在 unix socket 上**講 HTTP**（不是 byte pipe）：模型 path 過得去、
   落得了 journal。
2. **非模型 path 被擋在門上**，而且**上游一個 byte 都沒收到**。
   ⚠ 負控制在 `path_policy="any"` 那一格：同一支探針、同一個 `/admin`，
     政策關掉就**真的到得了上游** ⇒ 403 是政策造成的，不是探針壞了。
3. **門不持有金鑰**（`sentinel=""`）：`Authorization` 原樣穿透、header 不落盤。
   ⚠ 負控制：上游真的看到那一串（否則「穿透」可能只是「被丟掉」）。
"""
from __future__ import annotations

import http.client
import json
import os
import pathlib
import socket
import stat
import subprocess
import sys
import threading
import time

import pytest

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from vacant_network.vrun import proxyd
from vacant_network.vrun.wireproxy import (MODEL_PATHS, WireProxy,
                                           is_model_path)


# ── 假上游：**逐通記下 path 與 Authorization** ─────────────────────────
class _Upstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: list[dict] = []

    def log_message(self, *a):          # noqa: D102 - 靜音
        return

    def _any(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        type(self).seen.append({"path": self.path,
                                "auth": self.headers.get("Authorization"),
                                "body": body})
        payload = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_POST = _any                                      # noqa: N815


@pytest.fixture()
def upstream():
    _Upstream.seen = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1},
                     daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", _Upstream
    srv.shutdown()
    srv.server_close()


class _UnixHTTPConnection(http.client.HTTPConnection):
    """在路徑型 unix socket 上講 HTTP——**enclosure 內那支轉送器的等價物**。"""

    def __init__(self, sock_path: str, timeout: float = 20.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self._sock_path = sock_path

    def connect(self) -> None:          # noqa: D102
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self._sock_path)
        self.sock = s


@pytest.fixture()
def sockdir():
    """socket 專用的**短**目錄。

    ⚠ `sun_path` 在 macOS 上只有 104 byte、Linux 108，而 pytest 的 `tmp_path`
      （`/private/var/folders/…/pytest-of-…/pytest-N/<test name>0`）本身就吃掉
      九成 ⇒ 直接 `OSError: AF_UNIX path too long`。這不是本檔要測的東西。
    """
    import shutil
    import tempfile
    d = tempfile.mkdtemp(prefix="vdoor", dir="/tmp")
    yield pathlib.Path(d)
    shutil.rmtree(d, ignore_errors=True)


def _door(tmp_path: pathlib.Path, sockdir: pathlib.Path, base: str, *,
          policy: str = "model", name: str = "relay.sock") -> WireProxy:
    return WireProxy(wire_dir=tmp_path / "w",
                     upstreams={"openai": base, "anthropic": base},
                     keys={},                 # ⚠ 門不持有任何真鑰
                     sentinel="",             # ⚠ ⇒ 換鑰那一段整段不執行
                     mode="tee",
                     unix_path=sockdir / name,
                     path_policy=policy)


def _rows(tmp_path: pathlib.Path) -> list[dict]:
    p = tmp_path / "w" / "index.jsonl"
    if not p.is_file():
        return []
    return [json.loads(x) for x in
            p.read_text(encoding="utf-8").splitlines() if x.strip()]


# ── 1. path 名單是逐段比對，不是裸 prefix ──────────────────────────────
def test_is_model_path_matches_by_segment_not_prefix():
    assert is_model_path("/v1/chat/completions")
    assert is_model_path("/v1/messages")
    assert is_model_path("/v1/messages/count_tokens")      # 子路徑要過
    assert is_model_path("/v1/models/gemma-4-12b-it-qat")
    assert is_model_path("/v1/models?limit=1")             # query 不影響
    # 負控制：裸 prefix 比對之下這幾條會**誤放**
    assert not is_model_path("/v1/modelsX")
    assert not is_model_path("/v1/messagesevil")
    assert not is_model_path("/admin")
    assert not is_model_path("/v1/files")
    assert not is_model_path("/")


# ── 2. 門在 unix socket 上講 HTTP，模型 path 過得去 ────────────────────
def test_unix_door_speaks_http_and_forwards_model_path(tmp_path, sockdir,
                                                        upstream):
    base, seen = upstream
    px = _door(tmp_path, sockdir, base).start()
    try:
        assert px.endpoint == f"unix:{sockdir / 'relay.sock'}"
        with pytest.raises(RuntimeError):      # unix 門沒有 http:// URL
            _ = px.url
        c = _UnixHTTPConnection(str(sockdir / "relay.sock"))
        c.request("POST", "/v1/chat/completions", body=b'{"model":"m"}',
                  headers={"Content-Type": "application/json"})
        r = c.getresponse()
        got = r.read()
        c.close()
        px.quiesce()
        stats = dict(px.stats)
    finally:
        px.stop()

    assert r.status == 200 and got == b'{"ok":true}'
    assert [x["path"] for x in seen.seen] == ["/v1/chat/completions"]
    assert stats["requests_seen"] == 1 and stats["refused_path"] == 0
    rec = _rows(tmp_path)[0]
    assert rec["status"] == 200 and rec["path"] == "/v1/chat/completions"
    # 逐位元落盤（鐵律 3）在 unix 這條路上也要成立
    assert (tmp_path / "w" / f"{rec['call_id']}.req.bin").read_bytes() == \
        b'{"model":"m"}'


# ── 3. 非模型 path 被擋在門上，上游沒看到 ＋ **政策關掉就到得了** ───────
def test_non_model_path_is_refused_and_never_reaches_upstream(tmp_path,
                                                              sockdir,
                                                              upstream):
    base, seen = upstream

    # (a) 政策開著：403，而且上游的 seen 裡**沒有** /admin
    px = _door(tmp_path, sockdir, base, policy="model").start()
    try:
        c = _UnixHTTPConnection(str(sockdir / "relay.sock"))
        c.request("GET", "/admin")
        r = c.getresponse()
        body = json.loads(r.read().decode("utf-8"))
        c.close()
        px.quiesce()
        stats = dict(px.stats)
    finally:
        px.stop()

    assert r.status == 403, "拒絕要是 403（拒絕），不是 502（故障）"
    assert body["error"] == "vacant_door_non_model_path"
    assert body["path"] == "/admin"
    assert "/v1/chat/completions" in body["message"]       # 講得出名單
    assert seen.seen == [], f"上游竟然收到了：{seen.seen}"
    # 被擋下來**也是發生過的事**：照樣進 journal、照樣算進 requests_seen
    assert stats["requests_seen"] == 1
    assert stats["refused_path"] == 1
    assert stats["errors"] == 1
    assert stats["blocked"] == 0, "path 被擋不可以混進 blocked（上游沒人指定）"
    rec = _rows(tmp_path)[0]
    assert rec["status"] == 403 and rec["refused_path"] is True
    assert rec["upstream"] is None                          # 連都沒連

    # (b) **負控制**：同一支探針、同一條 /admin，政策換成 any ⇒ 真的到得了上游
    px2 = _door(tmp_path, sockdir, base, policy="any", name="relay2.sock").start()
    try:
        c = _UnixHTTPConnection(str(sockdir / "relay2.sock"))
        c.request("GET", "/admin")
        r2 = c.getresponse()
        r2.read()
        c.close()
        px2.quiesce()
    finally:
        px2.stop()
    assert r2.status == 200
    assert [x["path"] for x in seen.seen] == ["/admin"], \
        "負控制沒成立 ⇒ 上面那個 403 可能只是探針壞了"


# ── 4. 門不持有金鑰：Authorization 原樣穿透、header 不落盤 ─────────────
def test_door_holds_no_key_and_authorization_passes_through(tmp_path,
                                                            sockdir,
                                                            upstream):
    base, seen = upstream
    px = _door(tmp_path, sockdir, base).start()
    assert px.keys == {} and px.sentinel == ""
    try:
        c = _UnixHTTPConnection(str(sockdir / "relay.sock"))
        c.request("POST", "/v1/messages", body=b"{}",
                  headers={"Authorization": "Bearer CALLER-OWNED-KEY"})
        c.getresponse().read()
        c.close()
        px.quiesce()
    finally:
        px.stop()
    # 負控制的另一半：上游**真的**看到那一串（不是被門丟掉了）
    assert seen.seen[0]["auth"] == "Bearer CALLER-OWNED-KEY"
    # 而且它沒有上碟：整個 wire 目錄掃不到那一串
    blob = b"".join(p.read_bytes() for p in (tmp_path / "w").rglob("*")
                    if p.is_file())
    assert b"CALLER-OWNED-KEY" not in blob


# ── 5. socket 檔的權限與收尾 ───────────────────────────────────────────
def test_socket_file_is_0600_and_unlinked_on_stop(tmp_path, sockdir, upstream):
    base, _ = upstream
    sock = sockdir / "relay.sock"
    px = _door(tmp_path, sockdir, base).start()
    try:
        st = sock.lstat()
        assert stat.S_ISSOCK(st.st_mode)
        assert stat.S_IMODE(st.st_mode) == 0o600
    finally:
        px.stop()
    assert not sock.exists(), "收工要把 socket 檔刪掉，否則下一次要靠清殘留救"


def test_stale_socket_file_does_not_block_rebind(tmp_path, sockdir, upstream):
    """負控制：AF_UNIX 沒有 SO_REUSEADDR，殘留檔沒清就會 EADDRINUSE。"""
    base, _ = upstream
    sock = sockdir / "relay.sock"
    px = _door(tmp_path, sockdir, base).start()
    px.stop()
    sock.write_bytes(b"")               # 故意留一個**不是 socket** 的殘留檔
    with pytest.raises(OSError):
        _door(tmp_path, sockdir, base).start()   # 不是 socket ⇒ 不准亂刪，要炸
    sock.unlink()
    px2 = _door(tmp_path, sockdir, base).start()
    px2.stop()


# ── 6. TCP 那條路的語意一個字都沒改 ────────────────────────────────────
def test_tcp_path_is_unchanged_default_policy_is_any(tmp_path, upstream):
    base, seen = upstream
    with WireProxy(wire_dir=tmp_path / "w",
                   upstreams={"openai": base, "anthropic": base},
                   keys={}, sentinel="", mode="tee") as px:
        assert px.path_policy == "any"          # 預設沒變
        assert px.unix_path is None
        assert px.url.startswith("http://127.0.0.1:")
        assert px.endpoint == px.url
        import urllib.request
        urllib.request.urlopen(px.url + "/admin", timeout=20).read()
        px.quiesce()
    assert [x["path"] for x in seen.seen] == ["/admin"]


# ── 7. proxyd 的旗標：一個 proxy 一扇門，預設跟著聽法走 ────────────────
def test_proxyd_requires_exactly_one_listener():
    for argv in ([], ["--port", "1", "--unix", "/tmp/x.sock"]):
        with pytest.raises(SystemExit):
            proxyd.main(argv + ["--state", "/tmp/vacant-state-does-not-exist"])


def test_proxyd_unix_defaults_to_model_policy(tmp_path, sockdir, upstream):
    """`--unix` 沒給 `--path-policy` 時要 fail-closed 到 `model`。

    跑**真的子行程**而不是 in-process thread：`run_daemon` 的收尾靠 SIGTERM，
    在 pytest 行程裡送 SIGTERM 會把 pytest 一起殺掉。
    """
    base, seen = upstream
    sock = sockdir / "d.sock"
    state = tmp_path / "state"
    root = pathlib.Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root))
    p = subprocess.Popen(
        [sys.executable, "-m", "vacant_network.vrun.proxyd",
         "--unix", str(sock), "--state", str(state),
         "--upstream", f"openai={base}"],
        cwd=str(root), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sp = state / "proxyd" / "state.json"
    try:
        for _ in range(300):
            if sp.is_file() and sock.exists():
                break
            if p.poll() is not None:
                raise AssertionError(f"proxyd 當場死了：{p.communicate()[0]}")
            time.sleep(0.05)
        assert sp.is_file() and sock.exists(), "proxyd 沒起來（量具先確認活著）"
        st = json.loads(sp.read_text(encoding="utf-8"))
        assert st["listen"] == "unix" and st["path_policy"] == "model"
        assert st["unix_path"] == str(sock) and st["port"] is None

        # 正控制先跑：模型 path 通得過 ⇒ 證明門是活的
        c = _UnixHTTPConnection(str(sock))
        c.request("POST", "/v1/chat/completions", body=b"{}")
        assert c.getresponse().status == 200
        c.close()
        # 再跑負控制：/admin 403，上游只看得到剛剛那一通
        c = _UnixHTTPConnection(str(sock))
        c.request("GET", "/admin")
        assert c.getresponse().status == 403
        c.close()
        assert [x["path"] for x in seen.seen] == ["/v1/chat/completions"]
    finally:
        p.terminate()
        p.wait(timeout=30)
    assert not sock.exists(), "收工要把 socket 檔刪掉"
