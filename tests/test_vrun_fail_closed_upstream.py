"""門檻三：**沒指定的 upstream 不准安靜落到公開 API**。

這支在架構裡承重什麼
────────────────────
`9eeb1d9e` 加了 `upstreams_defaulted`，但它**只修了「看不見」，路還在**。
2026-09-19 的兩個實例：

  · **Claude Code** 啟動探 `$ANTHROPIC_BASE_URL/api/hello`，被 `route()`
    判成 openai wire。那一跑若沒指定 openai 上游 ⇒ 落到
    `DEFAULT_UPSTREAM["openai"]` ＝ `https://api.openai.com`，**真的出網**。
  · **pi 的 40 格**每一格 `upstreams_defaulted: ['anthropic']`
    （沒有流量走過去，但路留著）。

修法選 **(b)：指到一個會拒絕的本機 sink**，不是 (a) 拒絕啟動。理由：
**「這條路由沒人指定」不等於「這一跑會用到這條路」**——pi 那 40 格
anthropic 零流量，在流量發生之前就拒絕啟動等於用一個沒量到的東西判一個罪
（鐵律 3 的同一條紀律），而且會把既有的跑整批擋掉。

本檔的四條，**每一條都對應裁決裡的一句判準**：

  · `test_sink_refuses_in_process_without_opening_a_connection`
      被擋下來的那一通**死在本機**：回 502、原文落盤、`blocked` 計數 +1，
      而且 `error` 是我們自己的 fail-closed 字串**不是 DNS 錯誤**
      ——後者才代表「真的去連了」。
  · `test_claude_code_hello_probe_is_blocked_end_to_end`
      逐字重現那一通：只釘 anthropic，agent 打 `<proxy>/api/hello`。
  · `test_explicit_flag_reopens_the_road`
      **逃生口要真的存在**：明講之後 upstream 解析回公開 API。
  · `test_pinned_both_upstreams_is_byte_for_byte_unaffected`
      五 agent 矩陣那批（兩條都釘死）**完全不受影響**。

⚠ 本檔零外部網路：上游是本機假 server，sink 那條路連 socket 都沒開。
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vacant_network.vrun import envmap, launcher                         # noqa: E402
from vacant_network.vrun.wireproxy import WireProxy                      # noqa: E402

#: 一支只打一通 `<proxy>/api/hello` 的假 agent——**Claude Code 啟動探測的形狀**。
#: 用 `VACANT_RUN_PROXY`（launcher 一定會設）而不是 `ANTHROPIC_BASE_URL`，
#: 這樣這支 agent 不必知道 `envmap` 的名單長什麼樣。
_HELLO_PROBE = r'''
import os, sys, urllib.error, urllib.request
base = os.environ["VACANT_RUN_PROXY"].rstrip("/")
try:
    with urllib.request.urlopen(base + "/api/hello", timeout=30) as r:
        sys.stdout.write("status=%d" % r.status)
except urllib.error.HTTPError as e:
    sys.stdout.write("status=%d body=%s" % (e.code, e.read().decode()[:400]))
open("probe.txt", "w").write("done")
'''


class _Upstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: list[str] = []

    def log_message(self, *a):
        return

    def _any(self):
        type(self).seen.append(self.path)
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

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


def test_sink_refuses_in_process_without_opening_a_connection(tmp_path, upstream):
    """沒人指定的那條路由 ⇒ **擋在本機**，一個 byte 都不出去。"""
    base, seen = upstream
    with WireProxy(wire_dir=tmp_path / "w",
                   upstreams={"openai": envmap.SINK_UPSTREAM,
                              "anthropic": base},
                   keys={"openai": "REAL-KEY", "anthropic": ""},
                   sentinel="sent", mode="act") as px:
        req = urllib.request.Request(px.url + "/v1/chat/completions",
                                     data=b'{"model":"m"}', method="POST")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=30)
        assert e.value.code == 502
        body = json.loads(e.value.read().decode("utf-8"))
        px.quiesce()
        stats = dict(px.stats)

    # 訊息要講得出**要設哪個環境變數**，不是只說「錯了」
    assert body["error"] == "vacant_run_unspecified_upstream"
    assert body["wire"] == "openai"
    assert "VACANT_RUN_UPSTREAM_OPENAI" in body["message"]
    assert envmap.ALLOW_PUBLIC_VAR in body["message"]

    # 被擋下來**也是發生過的事**：照樣算進 requests_seen（鐵律 3）
    assert stats["requests_seen"] == 1
    assert stats["blocked"] == 1
    assert stats["errors"] == 1
    assert stats["by_wire"] == {"openai": 1}

    rec = json.loads((tmp_path / "w" / "index.jsonl")
                     .read_text(encoding="utf-8").splitlines()[0])
    assert rec["status"] == 502 and rec["blocked"] is True
    assert rec["upstream"] == envmap.SINK_UPSTREAM
    # ⚠ **這一條就是「沒開連線」的證據**：真的去連 `.invalid` 會拿到
    #   `gaierror`／`socket.gaierror` 之類的 repr，而不是我們的字串。
    assert rec["error"] == "unspecified_upstream_sink"
    assert "gaierror" not in rec["error"] and "Errno" not in rec["error"]
    # 請求本體逐位元落盤（被擋掉也要留證據）
    assert (tmp_path / "w" / f"{rec['call_id']}.req.bin").read_bytes() == \
        b'{"model":"m"}'
    assert seen.seen == [], "假上游收到東西了——sink 那條路不該碰到任何伺服器"


def test_claude_code_hello_probe_is_blocked_end_to_end(tmp_path, upstream,
                                                       monkeypatch):
    """逐字重現 2026-09-19 那一通：只釘 anthropic，`/api/hello` 走 openai。"""
    base, seen = upstream
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_ANTHROPIC", base)
    monkeypatch.delenv("VACANT_RUN_UPSTREAM_OPENAI", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("OPENAI_BASE", raising=False)
    monkeypatch.delenv(envmap.ALLOW_PUBLIC_VAR, raising=False)
    agent = tmp_path / "probe.py"
    agent.write_text(_HELLO_PROBE, encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    s = launcher.run([sys.executable, str(agent)], workspace=ws,
                     run_dir=tmp_path / "run", suite_dir=None,
                     vacant_on=True, task_id="hello_probe",
                     sandbox_name="none", allow_no_suite=True)

    assert s["upstreams_defaulted"] == ["openai"]
    assert s["upstreams_sinked"] == ["openai"]
    assert s["upstreams_public_allowed"] is False
    assert s["upstreams"]["openai"]["fallback"] == "sink"
    assert s["upstreams"]["openai"]["url"] == envmap.SINK_UPSTREAM
    # 那一通**發生過**（requests_seen 照算），但**被擋住了**
    assert s["requests_seen"] == 1 and s["wire_blocked"] == 1
    assert s["wire_by_protocol"] == {"openai": 1}
    assert seen.seen == [], "只釘了 anthropic，不該有東西打到任何伺服器"
    # run_<ARM>.json 落盤同一份（事後稽核只看得到這個檔）
    d = json.loads((tmp_path / "run" / "run_RUN-ON.json")
                   .read_text(encoding="utf-8"))
    assert d["upstreams_sinked"] == ["openai"] and d["wire_blocked"] == 1


def test_explicit_flag_reopens_the_road(tmp_path, monkeypatch):
    """**逃生口要真的存在**，而且旗標與環境變數兩個入口都算數。

    這裡只看 upstream 的解析結果，**不送任何 bytes**——負控制不必真的出網。
    """
    monkeypatch.delenv("VACANT_RUN_UPSTREAM_OPENAI", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("OPENAI_BASE", raising=False)
    monkeypatch.delenv(envmap.ALLOW_PUBLIC_VAR, raising=False)

    # 預設：sink
    assert envmap.describe_upstreams()["openai"]["fallback"] == "sink"
    # 環境變數版本
    monkeypatch.setenv(envmap.ALLOW_PUBLIC_VAR, "1")
    assert envmap.public_upstream_allowed() is True
    d = envmap.describe_upstreams(allow_public=envmap.public_upstream_allowed())
    assert d["openai"]["fallback"] == "public"
    assert d["openai"]["url"].startswith("https://api.openai.com")
    # 旗標版本：parser 認得它，而且預設是 False
    ns = launcher.build_parser().parse_args(["--", "true"])
    assert ns.allow_public_upstream is False
    ns2 = launcher.build_parser().parse_args(["--allow-public-upstream",
                                              "--", "true"])
    assert ns2.allow_public_upstream is True


def test_pinned_both_upstreams_is_byte_for_byte_unaffected(tmp_path, upstream,
                                                           monkeypatch):
    """五 agent 矩陣那批：兩條上游都釘死 ⇒ **一個欄位都不變、照樣送得出去**。"""
    base, seen = upstream
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_ANTHROPIC", base)
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", base + "/v1")
    monkeypatch.delenv(envmap.ALLOW_PUBLIC_VAR, raising=False)
    agent = tmp_path / "probe.py"
    agent.write_text(_HELLO_PROBE, encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    s = launcher.run([sys.executable, str(agent)], workspace=ws,
                     run_dir=tmp_path / "run", suite_dir=None,
                     vacant_on=True, task_id="pinned", sandbox_name="none",
                     allow_no_suite=True)
    assert s["upstreams_defaulted"] == []
    assert s["upstreams_sinked"] == []
    assert s["wire_blocked"] == 0
    assert s["requests_seen"] == 1
    assert seen.seen == ["/api/hello"], "釘死的上游應該照樣收得到那一通"
