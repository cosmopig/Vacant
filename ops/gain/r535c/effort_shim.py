"""這支在架構裡承重什麼：**把 `reasoning_effort: "none"` 補進去，因為 agent 不送它**。

Stage C（`decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md` L-6）要求
跟 S1／S2 同一顆模型、同一個端點、同一個推論模式。前兩條靠環境變數就到位，
**第三條不行**：R535 的 S1／S2 是驅動自己寫 pi 的 `models.json`
（`samplingParams: {"reasoning_effort": "none"}`，`run_r535.py::write_pi_config`）
達成的，而 Stage C 的兩個 agent 走的是自己的設定路線，那份設定裡沒有這個欄位。

2026-09-19 在 1003（`gemma-4-12b-it-qat`）上實測，同一個端點、同一段 prompt：

    不帶旗標                        ⇒ completion_tokens_details.reasoning_tokens = 5
    帶 "reasoning_effort": "none"   ⇒ reasoning_tokens = 0

⇒ **不補就不是同一個推論模式**，而推論模式會改變 agent 的行為。所以本檔是一層
**只改一個欄位**的轉送：坐在 `vacant/vrun/wireproxy.py` 與真端點之間，
對帶 `model` 的 JSON request body 補上 `reasoning_effort`，其餘位元組原樣轉送。

⚠ **誠實邊界（改碼請保留）**

1. **wireproxy 落的 `*.req.bin` 是 agent 送出來的原文（本層之前）** ——
   所以 M7 三層量到的仍然是 agent 自己的輸入，一個位元組都沒有被本檔動過。
   這是刻意的分工：M7 問的是「agent 讀了什麼」，不是「端點收到什麼」。
2. **本檔改了送給模型的東西，它不是透明的。** 每一通都逐筆落盤
   （`shim.jsonl`：path、注入前那個欄位是什麼、body bytes 前後、回應狀態），
   要查「那一通到底送了什麼」就看那個檔，不要看這裡的原始碼。
3. **`/v1/messages` 那條路收得下這個欄位，但 LM Studio 在那條路的 `usage` 裡
   不報 `reasoning_tokens`**（2026-09-19 實測）⇒ Anthropic wire 上 **F3b 量不到**。
   那一格記 `unmeasured`，**不准當成 0**。
4. 這一層**不是安全邊界**：它只換一個欄位；header、金鑰、path、query 原樣轉送。
5. 本檔**不做協定轉換**（同 `wireproxy` 的邊界）：`/v1/messages` 進來就
   `/v1/messages` 出去。上游不會講那個協定的話，這一層救不了。
"""
from __future__ import annotations

import hashlib
import http.client
import json
import pathlib
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}
_CHUNK = 64 * 1024


def inject(body: bytes, field: str, value: str) -> tuple[bytes, dict]:
    """把 `field: value` 補進一包 JSON body。回 `(新 body, 這一通的紀錄)`。

    **只在 body 是 dict 且含 `model` 時動它**——`model` 是「這是一通模型呼叫」
    的判準。不是 JSON、不是 dict、沒有 `model` 一律原樣回（`changed: False`），
    因為那些是探針（`/api/hello`）或我們看不懂的東西，動它只會製造新變因。
    """
    rec: dict = {"changed": False, "had": None, "reason": None,
                 "bytes_in": len(body), "bytes_out": len(body)}
    if not body:
        rec["reason"] = "empty_body"
        return body, rec
    try:
        d = json.loads(body.decode("utf-8"))
    except Exception:                        # noqa: BLE001
        rec["reason"] = "not_json"
        return body, rec
    if not isinstance(d, dict):
        rec["reason"] = "not_object"
        return body, rec
    if "model" not in d:
        rec["reason"] = "no_model_field"
        return body, rec
    rec["had"] = d.get(field, "<absent>")
    if d.get(field) == value:
        rec["reason"] = "already_correct"
        return body, rec
    d[field] = value
    out = json.dumps(d, ensure_ascii=False).encode("utf-8")
    rec.update({"changed": True, "reason": "injected", "bytes_out": len(out)})
    return out, rec


class EffortShim:
    """一個 ephemeral-port 的轉送層。`start()` 之後 `url` 才有值。"""

    def __init__(self, *, upstream: str, log_path: str | pathlib.Path,
                 field: str = "reasoning_effort", value: str = "none",
                 host: str = "127.0.0.1", timeout_s: float = 900.0):
        self.upstream = upstream.rstrip("/")
        if self.upstream.endswith("/v1"):
            # 同 `wireproxy.join_upstream`：base 的 `/v1` 先拿掉再接完整 path，
            # 否則 `/v1` 會出現兩次（所有 base url 設錯的第一名成因）。
            self.upstream = self.upstream[: -len("/v1")]
        self.field, self.value = field, value
        self.timeout_s = timeout_s
        self.log_path = pathlib.Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._host, self._port = host, 0
        self._srv: ThreadingHTTPServer | None = None
        self._lock = threading.Lock()
        self.stats = {"seen": 0, "injected": 0, "passthrough": 0, "errors": 0}

    # -- 落盤 -------------------------------------------------------------
    def _log(self, rec: dict) -> None:
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def start(self) -> "EffortShim":
        shim = self

        class _H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):   # noqa: D102
                return

            def _go(self, method: str) -> None:
                shim._handle(self, method)

            def do_GET(self):                    # noqa: N802,D102
                self._go("GET")

            def do_POST(self):                   # noqa: N802,D102
                self._go("POST")

            def do_HEAD(self):                   # noqa: N802,D102
                self._go("HEAD")

            def do_PUT(self):                    # noqa: N802,D102
                self._go("PUT")

            def do_DELETE(self):                 # noqa: N802,D102
                self._go("DELETE")

        srv = ThreadingHTTPServer((self._host, 0), _H)
        srv.daemon_threads = True
        self._port = srv.server_address[1]
        self._srv = srv
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        if self._srv is not None:
            self._srv.shutdown()
            self._srv.server_close()
            self._srv = None

    def __enter__(self) -> "EffortShim":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # -- 一通 -------------------------------------------------------------
    @staticmethod
    def _read_body(h: BaseHTTPRequestHandler) -> bytes:
        te = (h.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" in te:
            out = b""
            while True:
                line = h.rfile.readline().strip()
                if not line:
                    break
                n = int(line.split(b";")[0], 16)
                if n == 0:
                    h.rfile.readline()
                    break
                out += h.rfile.read(n)
                h.rfile.readline()
            return out
        n = int(h.headers.get("Content-Length") or 0)
        return h.rfile.read(n) if n else b""

    def _handle(self, h: BaseHTTPRequestHandler, method: str) -> None:
        t0 = time.time()
        body = self._read_body(h)
        sent, irec = inject(body, self.field, self.value)
        rec: dict = {"ts": t0, "method": method, "path": h.path,
                     "field": self.field, "value": self.value, **irec,
                     "request_sha256_in": hashlib.sha256(body).hexdigest(),
                     "request_sha256_out": hashlib.sha256(sent).hexdigest()}
        self.stats["seen"] += 1
        self.stats["injected" if irec["changed"] else "passthrough"] += 1

        out_headers = [(k, v) for k, v in h.headers.items()
                       if k.lower() not in _HOP_BY_HOP
                       and k.lower() not in ("host", "content-length")]
        out_headers.append(("Content-Length", str(len(sent))))
        u = urllib.parse.urlsplit(self.upstream + h.path)
        conn = None
        try:
            cls = (http.client.HTTPSConnection if u.scheme == "https"
                   else http.client.HTTPConnection)
            conn = cls(u.hostname, u.port, timeout=self.timeout_s)
            conn.request(method, u.path + (f"?{u.query}" if u.query else ""),
                         body=sent, headers=dict(out_headers))
            resp = conn.getresponse()
            h.send_response(resp.status)
            passthrough_len = resp.getheader("Content-Length")
            for k, v in resp.getheaders():
                if k.lower() in _HOP_BY_HOP or k.lower() == "content-length":
                    continue
                h.send_header(k, v)
            if passthrough_len is not None:
                h.send_header("Content-Length", passthrough_len)
            else:
                h.send_header("Transfer-Encoding", "chunked")
            h.end_headers()
            total = 0
            while True:
                # `read1` 不是 `read`：SSE 上 `read(n)` 會等湊滿才回來。
                chunk = resp.read1(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if method != "HEAD":
                    if passthrough_len is not None:
                        h.wfile.write(chunk)
                    else:
                        h.wfile.write(b"%X\r\n%s\r\n" % (len(chunk), chunk))
                    h.wfile.flush()
            if passthrough_len is None and method != "HEAD":
                h.wfile.write(b"0\r\n\r\n")
                h.wfile.flush()
            rec.update({"status": resp.status, "response_bytes": total,
                        "error": None})
        except Exception as exc:             # noqa: BLE001 - 也要落盤
            self.stats["errors"] += 1
            rec.update({"status": 0, "response_bytes": 0, "error": repr(exc)})
            try:
                h.send_response(502)
                h.send_header("Content-Length", "0")
                h.end_headers()
            except Exception:                # noqa: BLE001
                pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:            # noqa: BLE001
                    pass
        rec["elapsed_s"] = round(time.time() - t0, 3)
        self._log(rec)


def selftest(verbose: bool = True) -> dict:
    """負控制在前：**沒有 `model` 的 body 不准被動到**。

    五條，任一條紅就是量具壞了（而量具壞掉的形狀正是「安靜地照跑」）。
    """
    cases = [
        ("沒有 model ⇒ 不動", b'{"hello":1}', False),
        ("不是 JSON ⇒ 不動", b'not json at all', False),
        ("空 body ⇒ 不動", b'', False),
        ("有 model ⇒ 注入", b'{"model":"m","messages":[]}', True),
        ("已經對了 ⇒ 不動",
         b'{"model":"m","reasoning_effort":"none"}', False),
    ]
    rows, ok = [], True
    for name, body, want_changed in cases:
        out, rec = inject(body, "reasoning_effort", "none")
        good = rec["changed"] == want_changed
        if want_changed:
            good = good and json.loads(out)["reasoning_effort"] == "none"
        else:
            good = good and out == body
        ok = ok and good
        rows.append({"case": name, "want_changed": want_changed,
                     "got_changed": rec["changed"], "reason": rec["reason"],
                     "pass": good})
        if verbose:
            print(f"  [{'OK ' if good else 'RED'}] {name}"
                  f"  changed={rec['changed']} reason={rec['reason']}")
    return {"ok": ok, "rows": rows}


if __name__ == "__main__":                   # pragma: no cover - 手動跑
    import sys
    r = selftest()
    print("selftest:", "OK" if r["ok"] else "RED")
    sys.exit(0 if r["ok"] else 1)
