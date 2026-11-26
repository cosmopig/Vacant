"""ops.e1.netproxy — 宿主端 UNIX socket 白名單代理（供 `--unshare-net` 的 Claude worker 沙箱使用）。

這支在架構裡承重什麼
====================
讓跑在 `bwrap --unshare-net` 的 Claude Code worker 在**完全沒有宿主網路命名空間**的前提下，
只能透過綁進沙箱的單一 UNIX socket 連到白名單主機：
1. **HTTP CONNECT（HTTPS 隧道）**：僅放行白名單 `(host, port)`（預設 `api.anthropic.com:443` 以及經實測
   CLI 運作確實必要的最小主機清單，記於 `ops/e1/DESIGN_LOG.md`）；其餘一律回 `403 Forbidden`。
2. **明文 HTTP**：僅放行本機來源伺服器虛擬主機（`*.e1-sources.example`、`*.d2-sources.example`，port 80），
   由宿主直接轉發到本跑的 `source_server.py`（`127.0.0.1:<source_server_port>`）；其餘一律回 `403 Forbidden`。
3. **宿主側稽核日誌**：每一筆代理請求（含放行與被拒）皆寫入 JSONL（時間、method、host、port、allowed、
   status、bytes_up、bytes_down、bytes、wall_s、reason）。

誠實邊界（改碼請保留）
----------------------
- 本代理不解密 TLS（CONNECT 為透傳隧道），因此它保證的是「沙箱內行程只能與白名單 `(host, port)` 建立連線」，
  不檢查 TLS 內部的 HTTP 路徑或負載內容。
- 代理與 `--unshare-net` 組合後，沙箱內直連任何外部 IP（如 `1.1.1.1:443`）皆在核心層失敗（`ENETUNREACH`），
  且經代理 CONNECT 到非白名單主機皆被宿主拒絕（`403`）。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import socket
import tempfile
import threading
import time
import urllib.parse
from typing import Iterable

from . import utc_now_iso

#: 預設允許 HTTP CONNECT 的 (host, port) 白名單（宿主端強制執行）
DEFAULT_ALLOWED_CONNECT_HOSTS: tuple[tuple[str, int], ...] = (
    ("api.anthropic.com", 443),
)

#: 預設允許明文 HTTP 轉發到本機 source_server 的主機名後綴
DEFAULT_ALLOWED_HTTP_SUFFIXES: tuple[str, ...] = (
    ".e1-sources.example",
    ".d2-sources.example",
)

_MAX_HEADER_BYTES = 65536
_HOST_RE = re.compile(r"^[a-z0-9_](?:[a-z0-9_.-]*[a-z0-9])?$")


def _parse_connect_authority(target: str) -> tuple[str, int] | None:
    """解析 `CONNECT host:port`（亦支援 `[ipv6]:port`）；不合法回傳 None。"""
    t = target.strip()
    if not t or any(c.isspace() for c in t) or "@" in t or "/" in t:
        return None
    if t.startswith("["):
        idx = t.rfind("]:")
        if idx < 0:
            return None
        host = t[1:idx].strip().lower()
        port_s = t[idx + 2 :]
    else:
        if t.count(":") != 1:
            return None
        host, port_s = t.split(":", 1)
        host = host.strip().lower().rstrip(".")
    if not host or not port_s.isdigit():
        return None
    port = int(port_s)
    if port < 1 or port > 65535:
        return None
    return host, port


def _parse_host_port(host_hdr: str, default_port: int = 80) -> tuple[str, int] | None:
    s = host_hdr.strip()
    if not s or any(c.isspace() for c in s) or "@" in s or "/" in s:
        return None
    if ":" in s:
        h, ps = s.rsplit(":", 1)
        if not ps.isdigit():
            return None
        p = int(ps)
        if p < 1 or p > 65535:
            return None
        return h.strip().lower().rstrip("."), p
    return s.lower().rstrip("."), default_port


def _send_simple_response(cli: socket.socket, status: int, reason: str, body: str) -> None:
    body_b = body.encode("utf-8")
    resp = (
        f"HTTP/1.1 {status} {reason}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body_b)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("ascii") + body_b
    try:
        cli.sendall(resp)
    except OSError:
        pass


class AllowlistUnixProxy:
    """宿主端 UNIX socket HTTP/CONNECT 白名單代理。"""

    def __init__(
        self,
        *,
        allowed_connect: Iterable[tuple[str, int]] = DEFAULT_ALLOWED_CONNECT_HOSTS,
        source_server_port: int | None = None,
        allowed_http_suffixes: Iterable[str] = DEFAULT_ALLOWED_HTTP_SUFFIXES,
        log_path: pathlib.Path | None = None,
        sock_path: pathlib.Path | None = None,
        connect_timeout_s: float = 20.0,
    ) -> None:
        self.allowed_connect: set[tuple[str, int]] = {
            (h.strip().lower().rstrip("."), int(p)) for h, p in allowed_connect
        }
        self.source_server_port: int | None = int(source_server_port) if source_server_port else None
        self.allowed_http_suffixes: tuple[str, ...] = tuple(
            s.strip().lower() for s in allowed_http_suffixes if s and s.strip()
        )
        self.log_path: pathlib.Path | None = log_path
        self.connect_timeout_s = float(connect_timeout_s)

        self._tmp_dir: tempfile.TemporaryDirectory[str] | None = None
        if sock_path is None:
            self._tmp_dir = tempfile.TemporaryDirectory(prefix="e1px_")
            self.sock_path = pathlib.Path(self._tmp_dir.name) / "p.sock"
        else:
            self.sock_path = pathlib.Path(sock_path)

        self._srv: socket.socket | None = None
        self._stop = threading.Event()
        self._accept_th: threading.Thread | None = None
        self._lock = threading.Lock()
        self._active_socks: set[socket.socket] = set()
        self.events: list[dict] = []

    def _track(self, sock: socket.socket, add: bool) -> None:
        with self._lock:
            (self._active_socks.add if add else self._active_socks.discard)(sock)

    def _log_event(self, ev: dict) -> None:
        with self._lock:
            self.events.append(ev)
            if self.log_path is not None:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev, ensure_ascii=False, sort_keys=True) + "\n")

    def _is_allowed_http_host(self, host: str, port: int) -> bool:
        if port != 80:
            return False
        if not _HOST_RE.match(host):
            return False
        return any(host.endswith(suf) and len(host) > len(suf) for suf in self.allowed_http_suffixes)

    def start(self) -> pathlib.Path:
        if self._srv is not None:
            return self.sock_path
        self.sock_path.parent.mkdir(parents=True, exist_ok=True)
        if self.sock_path.exists():
            self.sock_path.unlink()
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(self.sock_path))
        os.chmod(self.sock_path, 0o600)
        srv.listen(128)
        self._srv = srv
        self._stop.clear()
        self._accept_th = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_th.start()
        return self.sock_path

    def stop(self) -> None:
        self._stop.set()
        if self._srv is not None:
            try:
                self._srv.close()
            except OSError:
                pass
            self._srv = None
        with self._lock:
            socks = list(self._active_socks)
        for s in socks:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass
        if self._accept_th is not None:
            self._accept_th.join(timeout=3.0)
            self._accept_th = None
        try:
            if self.sock_path.exists():
                self.sock_path.unlink()
        except OSError:
            pass
        if self._tmp_dir is not None:
            self._tmp_dir.cleanup()
            self._tmp_dir = None

    def __enter__(self) -> "AllowlistUnixProxy":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    def _accept_loop(self) -> None:
        assert self._srv is not None
        while not self._stop.is_set():
            try:
                cli, _ = self._srv.accept()
            except OSError:
                break
            threading.Thread(target=self._handle_conn, args=(cli,), daemon=True).start()

    def _read_request_head(self, cli: socket.socket) -> tuple[bytes, bytes] | None:
        cli.settimeout(15.0)
        buf = bytearray()
        while True:
            idx = buf.find(b"\r\n\r\n")
            if idx != -1:
                return bytes(buf[: idx + 4]), bytes(buf[idx + 4 :])
            if len(buf) >= _MAX_HEADER_BYTES:
                return None
            try:
                chunk = cli.recv(4096)
            except OSError:
                return None
            if not chunk:
                return None
            buf.extend(chunk)

    def _handle_conn(self, cli: socket.socket) -> None:
        self._track(cli, True)
        t0 = time.monotonic()
        try:
            head_rem = self._read_request_head(cli)
            if head_rem is None:
                _send_simple_response(cli, 400, "Bad Request", "malformed or empty request\n")
                return
            head_b, rem = head_rem
            lines = head_b[:-4].split(b"\r\n")
            if not lines:
                _send_simple_response(cli, 400, "Bad Request", "empty request line\n")
                return
            try:
                req_line = lines[0].decode("latin-1")
            except UnicodeDecodeError:
                _send_simple_response(cli, 400, "Bad Request", "bad request line\n")
                return
            parts = req_line.split(" ")
            if len(parts) != 3 or not parts[2].startswith("HTTP/"):
                _send_simple_response(cli, 400, "Bad Request", "bad request line\n")
                return
            method, target, _version = parts
            method_u = method.upper()

            if method_u == "CONNECT":
                self._handle_connect(cli, target, rem, t0)
            else:
                self._handle_http(cli, method_u, target, lines, rem, t0)
        finally:
            self._track(cli, False)
            try:
                cli.close()
            except OSError:
                pass

    def _handle_connect(self, cli: socket.socket, target: str, rem: bytes, t0: float) -> None:
        parsed = _parse_connect_authority(target)
        if parsed is None:
            _send_simple_response(cli, 400, "Bad Request", "invalid CONNECT target\n")
            self._log_event({
                "ts_utc": utc_now_iso(),
                "method": "CONNECT",
                "host": target[:120],
                "port": 0,
                "allowed": False,
                "status": 400,
                "bytes_up": 0,
                "bytes_down": 0,
                "bytes": 0,
                "wall_s": round(time.monotonic() - t0, 3),
                "reason": "invalid_connect_target",
            })
            return

        host, port = parsed
        if (host, port) not in self.allowed_connect:
            _send_simple_response(cli, 403, "Forbidden", f"CONNECT to {host}:{port} refused by E1 allowlist\n")
            self._log_event({
                "ts_utc": utc_now_iso(),
                "method": "CONNECT",
                "host": host,
                "port": port,
                "allowed": False,
                "status": 403,
                "bytes_up": 0,
                "bytes_down": 0,
                "bytes": 0,
                "wall_s": round(time.monotonic() - t0, 3),
                "reason": "host_not_allowlisted",
            })
            return

        try:
            up = socket.create_connection((host, port), timeout=self.connect_timeout_s)
        except OSError as exc:
            _send_simple_response(cli, 502, "Bad Gateway", f"upstream connect failed: {exc}\n")
            self._log_event({
                "ts_utc": utc_now_iso(),
                "method": "CONNECT",
                "host": host,
                "port": port,
                "allowed": True,
                "status": 502,
                "bytes_up": 0,
                "bytes_down": 0,
                "bytes": 0,
                "wall_s": round(time.monotonic() - t0, 3),
                "reason": f"upstream_error:{type(exc).__name__}",
            })
            return

        self._track(up, True)
        bytes_up = 0
        bytes_down = 0
        try:
            cli.settimeout(None)
            up.settimeout(None)
            cli.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            if rem:
                up.sendall(rem)
                bytes_up += len(rem)

            counts = [bytes_up, bytes_down]

            def _pump(src: socket.socket, dst: socket.socket, idx: int) -> None:
                try:
                    while True:
                        chunk = src.recv(65536)
                        if not chunk:
                            break
                        dst.sendall(chunk)
                        counts[idx] += len(chunk)
                except OSError:
                    pass
                finally:
                    try:
                        dst.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass

            t_up = threading.Thread(target=_pump, args=(cli, up, 0), daemon=True)
            t_dn = threading.Thread(target=_pump, args=(up, cli, 1), daemon=True)
            t_up.start()
            t_dn.start()
            t_up.join()
            t_dn.join()
            bytes_up, bytes_down = counts
        finally:
            self._track(up, False)
            try:
                up.close()
            except OSError:
                pass
            self._log_event({
                "ts_utc": utc_now_iso(),
                "method": "CONNECT",
                "host": host,
                "port": port,
                "allowed": True,
                "status": 200,
                "bytes_up": bytes_up,
                "bytes_down": bytes_down,
                "bytes": bytes_up + bytes_down,
                "wall_s": round(time.monotonic() - t0, 3),
            })

    def _handle_http(
        self,
        cli: socket.socket,
        method: str,
        target: str,
        raw_lines: list[bytes],
        rem: bytes,
        t0: float,
    ) -> None:
        hdr_map: dict[str, str] = {}
        fwd_headers: list[bytes] = []
        for raw_h in raw_lines[1:]:
            if b":" not in raw_h:
                continue
            k_b, v_b = raw_h.split(b":", 1)
            k_l = k_b.decode("latin-1").strip().lower()
            v_s = v_b.decode("latin-1").strip()
            hdr_map[k_l] = v_s
            if k_l in ("proxy-connection", "connection"):
                continue
            fwd_headers.append(raw_h)

        u = urllib.parse.urlsplit(target)
        host: str | None = None
        port: int = 80
        if u.scheme:
            if u.scheme.lower() != "http" or "@" in u.netloc:
                _send_simple_response(cli, 403, "Forbidden", "only plain HTTP to local source server is allowed\n")
                self._log_event({
                    "ts_utc": utc_now_iso(),
                    "method": method,
                    "host": (u.hostname or target)[:120],
                    "port": u.port or 80,
                    "allowed": False,
                    "status": 403,
                    "bytes_up": 0,
                    "bytes_down": 0,
                    "bytes": 0,
                    "wall_s": round(time.monotonic() - t0, 3),
                    "reason": "unsupported_scheme",
                })
                return
            host = (u.hostname or "").lower().rstrip(".")
            port = u.port or 80
            if "host" in hdr_map:
                hp = _parse_host_port(hdr_map["host"], default_port=80)
                if hp is None or hp[0] != host:
                    _send_simple_response(cli, 400, "Bad Request", "Host header mismatch\n")
                    self._log_event({
                        "ts_utc": utc_now_iso(),
                        "method": method,
                        "host": host,
                        "port": port,
                        "allowed": False,
                        "status": 400,
                        "bytes_up": 0,
                        "bytes_down": 0,
                        "bytes": 0,
                        "wall_s": round(time.monotonic() - t0, 3),
                        "reason": "host_header_mismatch",
                    })
                    return
        elif "host" in hdr_map:
            hp = _parse_host_port(hdr_map["host"], default_port=80)
            if hp is not None:
                host, port = hp

        if not host or not self._is_allowed_http_host(host, port):
            _send_simple_response(cli, 403, "Forbidden", f"HTTP to {host or target}:{port} refused by E1 allowlist\n")
            self._log_event({
                "ts_utc": utc_now_iso(),
                "method": method,
                "host": (host or target)[:120],
                "port": port,
                "allowed": False,
                "status": 403,
                "bytes_up": 0,
                "bytes_down": 0,
                "bytes": 0,
                "wall_s": round(time.monotonic() - t0, 3),
                "reason": "host_not_allowlisted",
            })
            return

        if self.source_server_port is None:
            _send_simple_response(cli, 502, "Bad Gateway", "no local source server configured\n")
            self._log_event({
                "ts_utc": utc_now_iso(),
                "method": method,
                "host": host,
                "port": port,
                "allowed": False,
                "status": 502,
                "bytes_up": 0,
                "bytes_down": 0,
                "bytes": 0,
                "wall_s": round(time.monotonic() - t0, 3),
                "reason": "no_source_server",
            })
            return

        # 讀取可選請求主體（若 Content-Length > 0）
        content_length = 0
        if "content-length" in hdr_map and hdr_map["content-length"].isdigit():
            content_length = int(hdr_map["content-length"])
        body_buf = bytearray(rem)
        while len(body_buf) < content_length:
            try:
                chunk = cli.recv(min(65536, content_length - len(body_buf)))
            except OSError:
                break
            if not chunk:
                break
            body_buf.extend(chunk)

        req_out = b"\r\n".join([raw_lines[0], *fwd_headers, b"Connection: close", b"", b""]) + bytes(body_buf)
        try:
            up = socket.create_connection(("127.0.0.1", self.source_server_port), timeout=self.connect_timeout_s)
        except OSError as exc:
            _send_simple_response(cli, 502, "Bad Gateway", f"source server connect failed: {exc}\n")
            self._log_event({
                "ts_utc": utc_now_iso(),
                "method": method,
                "host": host,
                "port": port,
                "allowed": True,
                "status": 502,
                "bytes_up": 0,
                "bytes_down": 0,
                "bytes": 0,
                "wall_s": round(time.monotonic() - t0, 3),
                "reason": f"source_server_error:{type(exc).__name__}",
            })
            return

        self._track(up, True)
        bytes_up = len(req_out)
        bytes_down = 0
        resp_status = 0
        try:
            up.settimeout(30.0)
            up.sendall(req_out)
            first_chunk = True
            while True:
                chunk = up.recv(65536)
                if not chunk:
                    break
                if first_chunk:
                    first_chunk = False
                    nl = chunk.find(b"\r\n")
                    st_line = (chunk[:nl] if nl != -1 else chunk[:64]).decode("latin-1", "replace")
                    sp = st_line.split(" ")
                    if len(sp) >= 2 and sp[1].isdigit():
                        resp_status = int(sp[1])
                cli.sendall(chunk)
                bytes_down += len(chunk)
        except OSError:
            pass
        finally:
            self._track(up, False)
            try:
                up.close()
            except OSError:
                pass
            self._log_event({
                "ts_utc": utc_now_iso(),
                "method": method,
                "host": host,
                "port": port,
                "allowed": True,
                "status": resp_status or 502,
                "bytes_up": bytes_up,
                "bytes_down": bytes_down,
                "bytes": bytes_up + bytes_down,
                "wall_s": round(time.monotonic() - t0, 3),
            })
