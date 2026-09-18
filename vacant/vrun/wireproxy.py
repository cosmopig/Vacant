"""這支在架構裡承重什麼：`vacant run` 的模型通道，**兩臂共用同一條**。

擴自 `ops/gain/r534/wire_tap.py`（R534 的逐字落盤底座），補掉它被點名的四個缺口：

  R534 wire_tap                    本檔
  ────────────────────────────────────────────────────────────────────
  只收 GET／POST                   全部方法（含 chunked request body）
  單一 upstream                    雙路徑路由（`/v1/messages` ↔ 其餘）
  整條 response 累積在記憶體       串流直送＋落盤，記憶體只有一個 64 KiB buffer
  強制改 `Transfer-Encoding`       上游給 Content-Length 就照抄，只有上游本來
                                   就是串流才重新分塊

## 設計鐵律：OFF 模式不准 parse-and-reserialize

`VACANT=0`（tee）與 `VACANT=1`（act）走的是**同一個函式**，body 一律
`bytes → bytes` 原樣轉送：不 `json.loads`、不 `json.dumps`、不碰 key 順序、
不碰空白。理由是可比性——重序列化會改 key 順序與空白 ⇒ body sha256 變掉 ⇒
「兩臂只差一個開關」那條證據就沒了。R534 已經證過這個性質（四格第一通請求
body 拿掉 `reasoning_effort` 與 cache key 之後 sha256 逐位元相同）。
`tests/test_vacant_run.py::test_body_bytes_identical_off_vs_on` 是它的可執行版本。

本檔把這條**寫進程式碼**（`_handle` 裡的那個 `raise RuntimeError`，不是 `assert`
——`python -O` 會把 assert 拿掉，而這是規格不是偵錯）：送出去的 `body` 物件
必須就是讀進來的那一個（`is` 相同），中間沒有任何一步碰過它。

## 兩臂的差別**不在 wire 上**

`mode="act"` 目前多做的事只有兩件：(1) 多算一份 body sha256 進索引；
(2) 留一個 `on_wire` 掛鉤給 V1。**V0 的 `on_wire` 恆回 None**，也就是
永遠不改寫。要改寫得先解決「偽造模型發言會傷到 Vacant 自己『紀錄忠實』的
立論根基」那個問題，那是 V1 的事。

## 落盤形狀（鐵律 3：全 I/O 逐字落盤，兩臂都成立）

    wire/index.jsonl          一通一列的索引（含 sha256、狀態、耗時）
    wire/<call_id>.req.bin    request body **原始位元組**
    wire/<call_id>.resp.bin   response body **原始位元組**

`wire_tap.py` 把 body 以 `utf-8 errors=replace` 塞進 JSONL——那對 SSE 與
任何非 UTF-8 的位元組是**有損**的，而有損的紀錄不能拿來算 sha256。
這裡改成原始位元組落盤、索引只放摘要。

## 誠實邊界（改碼請保留）

1. **records，不 verifies**：proxy 只證明「這些 bytes 經過我」，不證明上游
   真的照著跑，也**不阻止 agent 走別的路徑繞過它**。要讓「接上就逃不掉」
   為真，必須加出網封鎖（`block_egress.sh`，需要 root）。
2. **中介的是模型通道，不是 agent 的行為**：框架自己發起的動作（自動 lint、
   git checkpoint、內建重試）不經過模型通道，這裡看不到也擋不到。
3. **一律 base_url 轉向，不做透明 MITM**：不需要裝 CA。透明攔截會系統性
   削弱 TLS，而且會把「被中介到」與「TLS 被削弱」綁在一起。
4. **原理上的洞**：OpenAI Responses API ＋ `store:true` ＋ `previous_response_id`
   ——對話狀態在 OpenAI 伺服器上，逐字落盤在那條路上直接破功（Codex CLI 走
   這條）；不走 HTTP 的模型（llama.cpp in-process、MLX）根本沒有 wire；
   Bedrock SigV4 改 body 會毀簽章（本檔不改 body，但換 Authorization 會毀）。
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import pathlib
import socket
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import envmap

#: 串流轉送的區塊大小。純效能參數，不影響位元組內容。
_CHUNK = 1 << 16

#: hop-by-hop header：依 RFC 7230 §6.1 不得原樣轉送。
_HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
})

#: 路由：path 前綴 → wire 名。**只有兩條**，多一條就是規格變更。
#: Anthropic 的 Messages API 是 `/v1/messages`；其餘（`/v1/chat/completions`、
#: `/v1/completions`、`/v1/responses`、`/v1/models`、`/v1/embeddings`…）
#: 一律走 OpenAI 相容那一條。
def route(path: str) -> str:
    """這一條請求屬於哪個 wire protocol。**唯一的判準在這裡。**"""
    p = urllib.parse.urlsplit(path).path
    if p.startswith("/v1/messages") or p.startswith("/v1/complete"):
        return "anthropic"
    return "openai"


def join_upstream(base: str, path: str) -> str:
    """把進來的 path 接到上游 base 上。

    兩種 base 都要對：`http://h:1234/v1`（LM Studio 慣例）與
    `https://api.anthropic.com`（根）。作法是**先把 base 尾巴的 `/v1` 拿掉**
    再接完整 path——不這樣做，`/v1` 會出現兩次，而那是所有「base url 設錯」
    的第一名成因。
    """
    b = base.rstrip("/")
    if b.endswith("/v1"):
        b = b[: -len("/v1")]
    return b + path


class WireProxy:
    """一個 ephemeral-port 的反向代理。`start()` 之後 `url` 才有值。"""

    def __init__(self, *, wire_dir: str | os.PathLike, upstreams: dict[str, str],
                 keys: dict[str, str], sentinel: str, mode: str = "tee",
                 host: str = "127.0.0.1", port: int = 0,
                 timeout_s: float = 3600.0) -> None:
        if mode not in ("tee", "act"):
            raise ValueError(f"mode 只有 tee／act，收到 {mode!r}")
        self.wire_dir = pathlib.Path(wire_dir)
        self.wire_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.wire_dir / "index.jsonl"
        self.upstreams = dict(upstreams)
        self.keys = dict(keys)
        self.sentinel = sentinel
        self.mode = mode
        self.timeout_s = timeout_s
        self._lock = threading.Lock()
        self._srv: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._host, self._port = host, port
        #: 收據要用的統計。**不含 body**——body 在檔案裡。
        self.stats = {"requests_seen": 0, "by_wire": {}, "errors": 0,
                      "request_sha256": [], "response_sha256": []}

    # ── 生命週期 ──────────────────────────────────────────────────────
    @property
    def url(self) -> str:
        if self._srv is None:
            raise RuntimeError("proxy 還沒 start()")
        h, p = self._srv.server_address[:2]
        return f"http://{h}:{p}"

    def start(self) -> "WireProxy":
        proxy = self

        class _H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "vacant-run/0"

            def log_message(self, fmt, *args):   # noqa: D102 - 靜音預設 stderr
                return

            def handle_one_request(self):        # noqa: D102
                try:
                    super().handle_one_request()
                except (ConnectionResetError, BrokenPipeError):
                    self.close_connection = True

        for m in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
            setattr(_H, f"do_{m}",
                    (lambda method: lambda h: proxy._handle(h, method))(m))

        srv = ThreadingHTTPServer((self._host, self._port), _H)
        srv.daemon_threads = True
        self._srv = srv
        self._thread = threading.Thread(target=srv.serve_forever,
                                        kwargs={"poll_interval": 0.2},
                                        daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._srv is not None:
            self._srv.shutdown()
            self._srv.server_close()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def __enter__(self) -> "WireProxy":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # ── 落盤 ──────────────────────────────────────────────────────────
    def _index(self, rec: dict) -> None:
        with self._lock:
            with self.index_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())    # 中途被砍也要留得住（鐵律 3）

    # ── 掛鉤（V1 的預留；V0 恆為 None ＝ 永不改寫）────────────────────
    def on_wire(self, wire: str, path: str, body: bytes) -> bytes | None:
        """V1 的注入點。**V0 一律回 None**，也就是 body 原樣轉送。

        回 None 以外的東西就等於偽造模型發言／偽造使用者發言，那會傷到
        Vacant 自己「紀錄忠實」的立論根基，所以它不是一個預設行為，
        而是一個必須另外裁決才准打開的東西。
        """
        return None

    # ── 主路徑 ────────────────────────────────────────────────────────
    def _read_request_body(self, h: BaseHTTPRequestHandler) -> bytes:
        """把 client 的 request body 讀成位元組。chunked 也要吃得下。"""
        te = (h.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" in te:
            buf = bytearray()
            while True:
                line = h.rfile.readline(1 << 16).strip()
                if not line:
                    break
                size = int(line.split(b";")[0], 16)
                if size == 0:
                    h.rfile.readline()          # 收掉 trailer 的空行
                    break
                buf += h.rfile.read(size)
                h.rfile.read(2)                 # CRLF
            return bytes(buf)
        length = int(h.headers.get("Content-Length") or 0)
        return h.rfile.read(length) if length else b""

    def _handle(self, h: BaseHTTPRequestHandler, method: str) -> None:
        call_id = uuid.uuid4().hex
        t0 = time.time()
        wire = route(h.path)
        body = self._read_request_body(h)

        # ⚠ 鐵律：這裡之後 body 不再被碰。`act` 的掛鉤 V0 恆回 None。
        sent = body
        rewritten = False
        if self.mode == "act":
            hooked = self.on_wire(wire, h.path, body)
            if hooked is not None:              # pragma: no cover - V0 到不了
                sent, rewritten = hooked, True
        # ⚠ **不用 `assert`**：`python -O` 會把 assert 整行拿掉，而這一條是規格
        #   不是偵錯——它被拿掉的那一天，body 被悄悄重序列化也不會有人知道。
        if not rewritten and sent is not body:
            raise RuntimeError("OFF/ON 都不准重序列化 body：body 物件被換過了")

        req_sha = hashlib.sha256(sent).hexdigest()
        (self.wire_dir / f"{call_id}.req.bin").write_bytes(sent)

        # header：拿掉 hop-by-hop 與 Host，把 sentinel 換回真鑰。
        out_headers: list[tuple[str, str]] = []
        auth_name, auth_tmpl = envmap.AUTH_HEADERS[wire]
        key = self.keys.get(wire, "")
        swapped = False
        for k, v in h.headers.items():
            lk = k.lower()
            if lk in _HOP_BY_HOP or lk in ("host", "content-length"):
                continue
            if self.sentinel and self.sentinel in v:
                if not key:
                    continue        # 沒有真鑰就整個拿掉，別把 sentinel 送出去
                v = auth_tmpl.format(key=key) if lk == auth_name else \
                    v.replace(self.sentinel, key)
                swapped = True
            out_headers.append((k, v))
        if key and not swapped and not any(
                k.lower() == auth_name for k, _ in out_headers):
            out_headers.append((auth_name, auth_tmpl.format(key=key)))
        out_headers.append(("Content-Length", str(len(sent))))

        target = join_upstream(self.upstreams[wire], h.path)
        u = urllib.parse.urlsplit(target)
        rec = {"call_id": call_id, "ts": t0, "mode": self.mode, "wire": wire,
               "method": method, "path": h.path, "upstream": target,
               "request_sha256": req_sha, "request_bytes": len(sent),
               "body_rewritten": rewritten}

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
                # 上游本來就是串流（SSE）⇒ 只有這一種情況才重新分塊。
                h.send_header("Transfer-Encoding", "chunked")
            h.end_headers()

            sha = hashlib.sha256()
            total = 0
            with (self.wire_dir / f"{call_id}.resp.bin").open("wb") as f:
                while True:
                    # `read1` 而不是 `read`：`read(n)` 會**等到湊滿 n 個位元組**
                    # 才回來，SSE 上那等於把 token 累積到 64 KiB 才吐給 client。
                    # `read1` 一個 syscall 有多少給多少 ⇒ 串流是真的串流。
                    chunk = resp.read1(_CHUNK)  # 記憶體只有這一塊
                    if not chunk:
                        break
                    sha.update(chunk)
                    total += len(chunk)
                    f.write(chunk)
                    if method != "HEAD":
                        if passthrough_len is not None:
                            h.wfile.write(chunk)
                        else:
                            h.wfile.write(b"%X\r\n%s\r\n" % (len(chunk), chunk))
                        h.wfile.flush()
            if passthrough_len is None and method != "HEAD":
                h.wfile.write(b"0\r\n\r\n")
                h.wfile.flush()
            rec.update({"status": resp.status, "error": None,
                        "response_sha256": sha.hexdigest(),
                        "response_bytes": total,
                        "streamed": passthrough_len is None})
        except Exception as exc:                 # noqa: BLE001 - infra_void 也要落盤
            rec.update({"status": 0, "error": repr(exc),
                        "response_sha256": None, "response_bytes": 0})
            try:
                h.send_response(502)
                h.send_header("Content-Length", "0")
                h.end_headers()
            except Exception:                    # noqa: BLE001
                pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:                # noqa: BLE001
                    pass
        rec["elapsed_s"] = round(time.time() - t0, 4)
        self._index(rec)
        with self._lock:
            self.stats["requests_seen"] += 1
            self.stats["by_wire"][wire] = self.stats["by_wire"].get(wire, 0) + 1
            self.stats["request_sha256"].append(req_sha)
            self.stats["response_sha256"].append(rec.get("response_sha256"))
            if rec.get("error"):
                self.stats["errors"] += 1

    # ── 摘要 ──────────────────────────────────────────────────────────
    def wire_digest(self) -> str:
        """整條 wire 的 sha256——收據裡 `conversation_sha256` 欄位的來源。

        ⚠ **口徑講清楚**：這**不是**「對話」的摘要。sidecar 版本簽的是
          provider 訊息陣列（`role`/`content`），本檔簽的是**依序的
          (request body sha256, response body sha256) 清單**。理由是 V0 刻意
          不 parse body——要算訊息陣列的摘要就得 parse，而 parse 是通往
          reserialize 的第一步。兩者不可互相替代，收據裡另有
          `conversation_digest_kind` 欄位標明是哪一種。
        """
        with self._lock:
            pairs = list(zip(self.stats["request_sha256"],
                             self.stats["response_sha256"]))
        return hashlib.sha256(
            json.dumps(pairs, separators=(",", ":")).encode("utf-8")).hexdigest()


def free_port(host: str = "127.0.0.1") -> int:
    """借一個 ephemeral port 再還回去——只給「要先知道埠號」的呼叫端用。"""
    s = socket.socket()
    s.bind((host, 0))
    port = s.getsockname()[1]
    s.close()
    return port
