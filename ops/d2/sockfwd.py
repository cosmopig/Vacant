#!/usr/bin/env python3
"""最小的 TCP⇄unix socket 轉送器＋白名單（只用標準函式庫）。給 `bwrap_expT_agent.sh` 的網路隔離用（2026-11-28）。

沙箱用 --unshare-net，裡面只有 loopback。外面把出口代理的 TCP 埠接成 <live>/tmp/egress.sock（`unix2tcp`，帶白名單）；
沙箱裡把 127.0.0.1:<同一個埠> 接回那個 socket 檔（`tcp2unix`）。agent 只能經過這裡再到出口代理（會被記錄），直連外網會失敗。

白名單（unix2tcp）：
  --allow h:p,…        放行的目標（主機:埠）。runner 給的是：這一格自己的來源主機 `<組>-r<次>.d2-sources.example:80`，
                       以及 cfg/models.json 裡 LM Studio 端點的 IP:埠（執行時讀，不寫進 repo）。其他主機、其他 IP 一律拒絕。
  --model h:p,…        其中屬於模型端點的目標：只放行推論路徑（/v1/chat/completions、/v1/completions、/v1/models）。
                       /v1/responses 刻意不放：LM Studio 的 Responses API 可在 body 帶 remote MCP 工具，等於經模型主機連外。
                       管理／下載 API 回 403（或在通道裡當場斷線）並記錄。
  --log 檔             被擋的請求一筆一行（agent「想連外」的行為紀錄）。
每一個請求都檢查：用 HTTP/1.1 請求串流剖析器（依 Content-Length／chunked 找出每個請求的邊界），涵蓋連線的第一個請求、
keep-alive 後續的每個請求、CONNECT 通道裡的明文 HTTP 請求（LM Studio 是 http，通道裡是明文）。
Transfer-Encoding 與 Content-Length 並存、重複的 Content-Length、非 chunked 的 Transfer-Encoding、請求行或標頭格式不合 ⇒ 斷線並記錄（防請求走私）。
用法：sockfwd.py unix2tcp <socket 路徑> <host:port> [--allow …] [--model …] [--log 檔]
      sockfwd.py tcp2unix <host:port> <socket 路徑>
"""
import json, os, re, socket, sys, threading, time

MODEL_PATHS = ("/v1/chat/completions", "/v1/completions", "/v1/models")
REQLINE = re.compile(rb"([A-Z]{3,8}) (\S+) HTTP/1\.[01]")
HDR = re.compile(rb"([!#$%&'*+.^_`|~0-9A-Za-z-]+):[ \t]*(.*?)[ \t]*")


def log_block(logf, **kw):
    if logf:
        with open(logf, "a") as f:
            f.write(json.dumps({"ts": time.time(), "blocked": True, **kw}) + "\n")


def parse_target(meth: str, tgt: str):
    if meth == "CONNECT":
        h, _, pt = tgt.rpartition(":")
        return h.strip("[]").lower(), int(pt or 443), None
    if "://" in tgt:
        rest = tgt.split("://", 1)[1]
        hostport, _, path = rest.partition("/")
        h, _, pt = hostport.partition(":")
        return h.lower(), int(pt or 80), "/" + path
    return None, None, tgt


class Parser:
    """客戶端→上游方向的 HTTP/1.1 請求串流剖析與白名單檢查。feed() 回傳 False ⇒ 立刻斷線（原因已記錄）。"""

    def __init__(self, allow, model, logf):
        self.allow, self.model, self.logf = allow, model, logf
        self.buf = b""; self.state = "headers"; self.remaining = 0; self.tunnel = None; self.requests = 0

    def _block(self, **kw):
        log_block(self.logf, **kw); return False

    def _check(self, meth, tgt):
        h, pt, path = parse_target(meth, tgt)
        if h is None:
            if self.tunnel is None:
                return self._block(reason="origin_form_without_tunnel", line=f"{meth} {tgt}"[:200])
            dest = self.tunnel
        else:
            dest = f"{h}:{pt}"
            if dest not in self.allow:
                return self._block(reason="host_not_allowed", host=h, port=pt, method=meth)
            if meth == "CONNECT":
                self.tunnel = dest
                return True
        if dest in self.model and not (path or "").split("?")[0].startswith(MODEL_PATHS):
            return self._block(reason="model_path_not_allowed", host=dest, path=(path or "")[:120], method=meth)
        return True

    def feed(self, data: bytes) -> bool:
        self.buf += data
        while True:
            if self.state == "headers":
                i = self.buf.find(b"\r\n\r\n")
                if i < 0:
                    if len(self.buf) > 65536:
                        return self._block(reason="header_too_large")
                    return True
                head, self.buf = self.buf[:i], self.buf[i + 4:]
                lines = head.split(b"\r\n")
                m = REQLINE.fullmatch(lines[0])
                if not m:
                    return self._block(reason="malformed_request_line", line=lines[0][:120].decode("latin-1", "replace"))
                hdrs = {}
                for ln in lines[1:]:
                    hm = HDR.fullmatch(ln)
                    if not hm:
                        return self._block(reason="malformed_header", line=ln[:120].decode("latin-1", "replace"))
                    k = hm.group(1).lower()
                    if k in (b"content-length", b"transfer-encoding") and k in hdrs:
                        return self._block(reason="duplicate_" + k.decode())
                    hdrs[k] = hm.group(2)
                meth, tgt = m.group(1).decode(), m.group(2).decode("latin-1", "replace")
                if not self._check(meth, tgt):
                    return False
                self.requests += 1
                te, cl = hdrs.get(b"transfer-encoding"), hdrs.get(b"content-length")
                if te is not None and cl is not None:
                    return self._block(reason="te_and_cl_together")
                if meth == "CONNECT":
                    continue                     # 之後是通道內容：裡面的明文 HTTP 請求照樣剖析
                if te is not None:
                    if te.strip().lower() != b"chunked":
                        return self._block(reason="unsupported_transfer_encoding")
                    self.state = "chunk_size"
                elif cl is not None:
                    if not cl.isdigit():
                        return self._block(reason="bad_content_length")
                    self.remaining = int(cl)
                    self.state = "body" if self.remaining else "headers"
            elif self.state in ("body", "chunk_data"):
                take = min(self.remaining, len(self.buf))
                self.buf = self.buf[take:]; self.remaining -= take
                if self.remaining:
                    return True
                self.state = "headers" if self.state == "body" else "chunk_size"
            elif self.state == "chunk_size":
                i = self.buf.find(b"\r\n")
                if i < 0:
                    return True
                line, self.buf = self.buf[:i].split(b";")[0].strip(), self.buf[i + 2:]
                try:
                    n = int(line, 16)
                except ValueError:
                    return self._block(reason="bad_chunk_size")
                if n == 0:
                    self.state = "trailer"
                else:
                    self.remaining = n + 2; self.state = "chunk_data"
            elif self.state == "trailer":
                i = self.buf.find(b"\r\n")
                if i < 0:
                    return True
                line, self.buf = self.buf[:i], self.buf[i + 2:]
                if line == b"":
                    self.state = "headers"


def guarded_pipe(src, dst, parser):
    try:
        while True:
            d = src.recv(65536)
            if not d:
                break
            if parser is not None and not parser.feed(d):
                break
            dst.sendall(d)
    except OSError:
        pass
    finally:
        for s_ in (src, dst):
            try:
                s_.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def handle(c, connect, mk_parser):
    parser = mk_parser() if mk_parser else None
    first = b""
    if parser is not None:
        c.settimeout(30)
        try:
            while parser.requests == 0:          # 第一個請求檢查通過之前不連上游
                d = c.recv(65536)
                if not d:
                    c.close(); return
                first += d
                if not parser.feed(d):
                    try:
                        c.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                    except OSError:
                        pass
                    c.close(); return
        except OSError:
            c.close(); return
        c.settimeout(None)
    try:
        u = connect()
    except OSError:
        c.close(); return
    if first:
        u.sendall(first)
    threading.Thread(target=guarded_pipe, args=(c, u, parser), daemon=True).start()
    guarded_pipe(u, c, None)


def serve(listener, connect, mk_parser=None):
    while True:
        c, _ = listener.accept()
        threading.Thread(target=handle, args=(c, connect, mk_parser), daemon=True).start()


def main():
    mode, a, b = sys.argv[1:4]
    opt = sys.argv[4:]
    get = lambda f: opt[opt.index(f) + 1] if f in opt else None
    if mode == "unix2tcp":
        if os.path.exists(a):
            os.unlink(a)
        l = socket.socket(socket.AF_UNIX); l.bind(a); l.listen(64)
        h, p = b.rsplit(":", 1)
        mk = None
        if get("--allow") is not None:
            allow = {x.lower() for x in get("--allow").split(",") if x}
            model = {x.lower() for x in (get("--model") or "").split(",") if x}
            logf = get("--log")
            mk = lambda: Parser(allow | model, model, logf)
        serve(l, lambda: socket.create_connection((h, int(p))), mk)
    elif mode == "tcp2unix":
        h, p = a.rsplit(":", 1)
        l = socket.socket(socket.AF_INET); l.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); l.bind((h, int(p))); l.listen(64)
        def conn():
            s = socket.socket(socket.AF_UNIX); s.connect(b); return s
        serve(l, conn)
    else:
        raise SystemExit("mode must be unix2tcp or tcp2unix")


if __name__ == "__main__":
    main()
