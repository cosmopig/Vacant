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

## 兩種聽法：TCP ＝ 常駐端點，AF_UNIX ＝ **enclosure 的那扇門**（2026-09-20）

`unix_path=` 一給，本 proxy 就改聽一個**路徑型 unix socket**，其餘一個字不動
（同一個 handler、同一份 journal、同一條 `sentinel` 規則）。理由是 enclosure：
`bwrap --unshare-all` 之下 TCP／DNS／抽象 socket 全部穿不過去，**只有路徑型
unix socket 穿得過 network namespace**——所以那是唯一做得出「一扇門」的形狀。

⚠ **這扇門一定要會終結 HTTP，不可以是 byte pipe。** byte pipe 不看內容 ⇒
enclosure 裡的 agent 照樣可以對它送**任何**請求，只要對面那台主機收——洞從
「任意主機」縮小到「那一台上游」，**不是關掉**。會終結 HTTP 才談得上
`path_policy`、才有 journal、才有那句「每一次都經過 Vacant」。

## `path_policy`：`"any"`（預設＝舊行為）／`"model"`（只放模型 API path）

`"model"` 之下，不在 `MODEL_PATHS` 名單上的 path **在開任何連線之前**就回 403
（`GET /admin` 不會變成一條到上游的隧道），請求本體照樣逐位元落盤（鐵律 3）、
照樣算進 `requests_seen`，並多記一個 `refused_path`。

⚠ **誠實邊界**：這是 **path 層**的閘門，不是內容層的。名單上的 path 之下要送
什麼 body 它不管（`/v1/chat/completions` 仍然什麼都塞得進去）；名單本身也只是
**我們認得的那幾條**，上游多一條新的模型路徑而我們沒加就是誤擋——那是
fail-closed 的方向，而且會在 journal 裡看得見。**擋得住 `/admin` ≠ 擋得住
「把資料塞進一個合法的模型請求裡帶出去」**，後者這一層擋不到。

## 誠實邊界（改碼請保留）

1. **records，不 verifies**：proxy 只證明「這些 bytes 經過我」，不證明上游
   真的照著跑，也**不阻止 agent 走別的路徑繞過它**。要讓「接上就逃不掉」
   為真，必須加出網封鎖（`block_egress.sh`，需要 root）**或把 agent 關進
   enclosure**（`ops/vacantrun/enclosure_20260920/`：路**不存在**，不是路被擋）。
2. **中介的是模型通道，不是 agent 的行為**：框架自己發起的動作（自動 lint、
   git checkpoint、內建重試）不經過模型通道，這裡看不到也擋不到。
3. **一律 base_url 轉向，不做透明 MITM**：不需要裝 CA。透明攔截會系統性
   削弱 TLS，而且會把「被中介到」與「TLS 被削弱」綁在一起。
4. **沒人指定的上游 ⇒ fail-closed 本機 sink，不是公開 API**（2026-09-19）。
   `envmap.SINK_UPSTREAM` 的那條路由在**開任何連線之前**就回 502，
   不解析 DNS、不送任何 bytes、離線也成立。要走公開 API 得明講
   （`--allow-public-upstream` 或 `VACANT_RUN_ALLOW_PUBLIC_UPSTREAM=1`）。
   ⚠ **這擋的是「沒人指定的那條路由」**，不是「出網」：使用者自己把上游
   指到公開 API 照樣放行（那是明講的），agent 繞過 proxy 直連也照樣擋不住。
5. **原理上的洞**：OpenAI Responses API ＋ `store:true` ＋ `previous_response_id`
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
import socketserver
import stat as _stat
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, TypedDict, cast

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


#: `path_policy="model"` 放行的 path。**這是一份名單不是一條規則**——
#: 跟 `envmap` 那份環境變數名單同一種東西：認介面、不認框架。
#:
#: ⚠ 比對是**逐段**的（`p == a` 或 `p.startswith(a + "/")`），不是裸 prefix：
#:   裸 prefix 之下 `/v1/modelsXXX` 會被當成 `/v1/models` 放行。
MODEL_PATHS: tuple[str, ...] = (
    # OpenAI 相容
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/responses",
    "/v1/embeddings",
    "/v1/models",
    # Anthropic（`/v1/messages/count_tokens` 由逐段比對一併涵蓋）
    "/v1/messages",
    "/v1/complete",
)


def is_model_path(path: str) -> bool:
    """這一條 path 是不是「模型 API」。**唯一的判準在這裡。**

    ⚠ 誠實邊界：回 `True` 只代表**這條路是模型通道**，不代表那一通請求安全。
      本函式一個 byte 的 body 都沒看過。
    """
    p = urllib.parse.urlsplit(path).path
    return any(p == a or p.startswith(a + "/") for a in MODEL_PATHS)


class _Stats(TypedDict):
    """`WireProxy.stats` 的形狀。**只在型別層存在**：執行期仍是一個普通 dict，
    一個位元組都沒有多寫。寫出來的理由是 `response_sha256` 那一欄——它**允許
    `None`**（infra_void：上游沒回話那一通），而 `wire_digest()` 簽的就是這串
    含 `None` 的配對。少寫這個 `| None` 會讓型別檢查誤以為那一欄不會有洞，
    而那個洞正是收據裡要看得見的東西。
    """
    requests_seen: int
    by_wire: dict[str, int]
    errors: int
    #: **被 fail-closed 擋下來的通數**（沒人指定那條路由的上游 ⇒ sink）。
    #: 它是 `errors` 的子集，但必須另外數：一個連不上的真上游與一個
    #: 「這條路根本沒人指定」在收據上不可以同形。
    blocked: int
    #: **被 path 政策擋下來的通數**（`path_policy="model"` ＋ 非模型 path）。
    #: 跟 `blocked` 分開數，理由同上：「上游沒人指定」與「這條路不准走」在
    #: 收據上不可以同形，混成一個數字之後就分不出門是壞的還是門在做事。
    #: 它也是 `errors` 的子集。
    refused_path: int
    request_sha256: list[str]
    response_sha256: list[str | None]
    #: `stop()` 排空逾時 ⇒ 這份統計**不完整**（少算的通數不明）。
    #: `False` ＝排空成功，不是「沒檢查」。
    quiesce_timeout: bool


def join_upstream(base: str, path: str, wire: str | None = None) -> str:
    """把進來的 path 接到上游 base 上。

    兩種 base 都要對：`http://h:1234/v1`（LM Studio 慣例）與
    `https://api.anthropic.com`（根）。作法是**先把 base 尾巴的 `/v1` 拿掉**
    再接完整 path——不這樣做，`/v1` 會出現兩次，而那是所有「base url 設錯」
    的第一名成因。

    第三種（2026-09-24，第一次接真實公開上游時抓到）：**OpenAI 相容、但根不是 `/v1`**，
    例如 Gemini 的 `https://generativelanguage.googleapis.com/v1beta/openai`。
    OpenAI SDK／pi 的慣例是 `baseUrl + "/chat/completions"`——base 本身就是 API 根，
    版本段已經在裡面。舊規則會接成 `…/v1beta/openai/v1/chat/completions` ⇒ 404，
    使用者的 provider 一接上 Vacant 就壞。所以 **`wire == "openai"`、base 帶路徑、
    而且結尾不是 `/v1`** 時，把 client 那邊的 `/v1` 前綴拿掉再接。

    ⚠ 只動 openai 這條：Anthropic SDK 的慣例相反（base **不含** `/v1`，client 自己補
      `/v1/messages`），自訂路徑的 anthropic 閘道照舊接完整 path。
    ⚠ base 沒有路徑（`http://h:1234`、`https://api.openai.com`）照舊接完整 path
      ——那是「使用者省略了 `/v1`」的常見寫法。代價：根就是 API 根、不吃 `/v1` 的服務
      （路徑為空但端點是 `/chat/completions`）仍然接錯；本規則沒有辦法從字串分辨那一種。
    ⚠ `wire=None` ＝舊行為，一個位元組都不變（其他呼叫者不受影響）。
    """
    b = base.rstrip("/")
    if b.endswith("/v1"):
        return b[: -len("/v1")] + path
    if wire == "openai" and (path == "/v1" or path.startswith(("/v1/", "/v1?"))):
        if urllib.parse.urlsplit(b).path not in ("", "/"):
            return b + path[len("/v1"):]
    return b + path


class _ThreadingUnixHTTPServer(socketserver.ThreadingMixIn,
                               socketserver.UnixStreamServer):
    """`ThreadingHTTPServer` 的 AF_UNIX 版。**只多做四件事**，逐條寫明理由：

    1. `HTTPServer.server_bind()` 會 `host, port = self.server_address[:2]`
       ——AF_UNIX 的 `server_address` 是一個**字串路徑**，切片切出來是兩個
       字元 ⇒ 直接壞。所以這裡不繼承 `HTTPServer`，改自己補
       `server_name`／`server_port`（handler 只在 log 用得到，而 log 被靜音）。
    2. bind 之前先清掉殘留的 socket 檔。`AF_UNIX` 沒有 `SO_REUSEADDR`
       這種東西，上一次沒收乾淨就會 `EADDRINUSE`。
    3. bind 之後 `chmod 0o600`——**這是門的第一道權限**：同一台機器上的
       其他 uid 連不進來（`--ro-bind` 進 enclosure 之後仍然是同一個 uid）。
       ⚠ 誠實邊界：同 uid 的行程照樣連得進來，本 socket **不做身分驗證**。
    4. `server_close()` 把 socket 檔刪掉，否則下一次要靠第 2 條救。
       ⚠ **只刪自己 bind 成功的那一個**（`_bound`）。`socketserver.TCPServer`
       的 `__init__` 在 `server_bind()` 失敗時會順手叫 `server_close()`——
       沒有這個旗標的話，一個「bind 失敗」會把別人的檔案刪掉。
       2026-09-20 在 `test_stale_socket_file_does_not_block_rebind` 當場量到。
    """

    #: `UnixStreamServer` 已經是 AF_UNIX，寫出來是給讀碼的人看的。
    address_family = socket.AF_UNIX
    daemon_threads = True
    #: ⚠ 兩個都關掉：AF_UNIX 上 `SO_REUSEADDR` 無意義、`SO_REUSEPORT` 會
    #:   在某些核心上直接 `ENOPROTOOPT` 炸在 `server_bind()` 裡。
    allow_reuse_address = False
    allow_reuse_port = False
    #: bind 成功了沒有。`server_close()` 只刪自己 bind 出來的那個檔。
    _bound = False

    def server_bind(self) -> None:                   # noqa: D102
        path = pathlib.Path(cast(str, self.server_address))
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # ⚠ 只清 socket 檔。殘留的是普通檔案／目錄就讓 bind 去炸——
            #   「那條路徑上有別的東西」要看得見，不可以安靜地刪掉它。
            if _stat.S_ISSOCK(path.lstat().st_mode):
                path.unlink()
        except FileNotFoundError:
            pass
        super().server_bind()
        self._bound = True
        os.chmod(self.server_address, 0o600)         # type: ignore[arg-type]
        self.server_name = "localhost"
        self.server_port = 0

    def server_close(self) -> None:                  # noqa: D102
        sock_path = self.server_address
        bound = self._bound
        self._bound = False
        super().server_close()
        if not bound:
            return
        try:
            os.unlink(cast(str, sock_path))
        except OSError:
            pass


class WireProxy:
    """一個 ephemeral-port 的反向代理。`start()` 之後 `url` 才有值。

    `unix_path=` 給了就改聽路徑型 unix socket，`url` 換成 `endpoint`。
    """

    def __init__(self, *, wire_dir: str | os.PathLike, upstreams: dict[str, str],
                 keys: dict[str, str], sentinel: str, mode: str = "tee",
                 host: str = "127.0.0.1", port: int = 0,
                 timeout_s: float = 3600.0,
                 unix_path: str | os.PathLike | None = None,
                 path_policy: str = "any") -> None:
        if mode not in ("tee", "act"):
            raise ValueError(f"mode 只有 tee／act，收到 {mode!r}")
        if path_policy not in ("any", "model"):
            raise ValueError(f"path_policy 只有 any／model，收到 {path_policy!r}")
        # ⚠ **一個 proxy 一扇門。** 兩個 listener 共用一份 `index.jsonl` 的話，
        #   「這一通從哪裡進來的」就要多一個欄位才分得出來，而收據上多一個
        #   可以是空的欄位比少一個 listener 貴。要兩扇門就起兩支。
        self.unix_path = pathlib.Path(unix_path) if unix_path else None
        self.path_policy = path_policy
        self.wire_dir = pathlib.Path(wire_dir)
        self.wire_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.wire_dir / "index.jsonl"
        self.upstreams = dict(upstreams)
        self.keys = dict(keys)
        self.sentinel = sentinel
        self.mode = mode
        self.timeout_s = timeout_s
        self._lock = threading.Lock()
        # ⚠ 「手上還有幾通沒處理完」。`requests_seen` 是在**回應送出之後**才加的，
        #   所以 agent 拿到回應、寫完檔、退出時，handler 執行緒可能還沒跑到那一行
        #   ⇒ 呼叫端這時候讀 `stats` 會**少算**。2026-09-18 在 CI（ubuntu py3.13）
        #   上實際發生過：`requests_seen` 逐次是 [1, 1, 0]，而第三通其實有發生。
        #   少算 `requests_seen` 特別嚴重，因為它是我們宣稱「中介真的發生了」的
        #   **唯一**證據（§4.5：「我設了設定」不是證據）。
        self._inflight = 0
        self._idle = threading.Condition()
        self._srv: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None
        self._host, self._port = host, port
        #: 收據要用的統計。**不含 body**——body 在檔案裡。
        self.stats: _Stats = {"requests_seen": 0, "by_wire": {}, "errors": 0,
                              "blocked": 0, "refused_path": 0,
                              "request_sha256": [], "response_sha256": [],
                              "quiesce_timeout": False}

    # ── 生命週期 ──────────────────────────────────────────────────────
    @property
    def endpoint(self) -> str:
        """這支在哪裡聽。TCP ⇒ `http://h:p`；unix ⇒ `unix:<路徑>`。

        ⚠ 不要把 unix 那一支硬塞成 URL。agent 只認得 HTTP base URL，
          所以 enclosure 內另外有一段 `127.0.0.1:<port> → 這個 socket` 的
          轉送器（`door_guest.py`）——那一段是**圍牆內**的 byte pipe，
          它繞不過本檔，因為 HTTP 是在**本檔**這一側被終結的。
        """
        if self.unix_path is not None:
            return f"unix:{self.unix_path}"
        return self.url

    @property
    def url(self) -> str:
        if self.unix_path is not None:
            raise RuntimeError(
                "這支聽的是 unix socket，沒有 http:// URL——用 `endpoint`")
        if self._srv is None:
            raise RuntimeError("proxy 還沒 start()")
        # typeshed 把 `server_address` 的主機欄寫成 `str | bytes | bytearray`
        # （AF_UNIX 那一支用得到 bytes）。本 proxy 只綁 AF_INET／AF_INET6，
        # `getsockname()` 在那兩支一定回 `(str, int)` ⇒ 這裡 cast 而不是
        # `type: ignore`，f-string 的其餘部分照樣被檢查。**執行期是恆等函式。**
        h, p = cast("tuple[str, int]", self._srv.server_address[:2])
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

        srv: socketserver.TCPServer
        if self.unix_path is not None:
            srv = _ThreadingUnixHTTPServer(str(self.unix_path), _H)
        else:
            srv = ThreadingHTTPServer((self._host, self._port), _H)
        srv.daemon_threads = True                    # type: ignore[attr-defined]
        self._srv = srv
        self._thread = threading.Thread(target=srv.serve_forever,
                                        kwargs={"poll_interval": 0.2},
                                        daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        # ⚠ 先排空再關。`shutdown()` 只停掉 accept 迴圈，**不等在途的 handler
        #   執行緒**（`ThreadingHTTPServer` 的 daemon 執行緒會被直接丟掉）⇒
        #   關完才讀 `stats` 一樣會少算。排不空就記在 `stats["quiesce_timeout"]`，
        #   讓「這份統計不完整」在收據裡看得到，而不是靜悄悄少一通。
        if not self.quiesce():
            with self._lock:
                self.stats["quiesce_timeout"] = True
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
        with self._idle:
            self._inflight += 1
        try:
            self._handle_inner(h, method)
        finally:
            with self._idle:
                self._inflight -= 1
                self._idle.notify_all()

    def quiesce(self, timeout_s: float = 10.0) -> bool:
        """等到手上沒有未處理完的請求為止。回 `True`＝真的排空了。

        呼叫端在讀 `stats` **之前**必須先呼叫這支，否則會少算（見 `_inflight`
        的註解）。回 `False` 代表逾時仍有在途請求——那時候 `stats` 是不完整的，
        **呼叫端要把這件事落盤**，不可以當成「就是這麼多通」。
        `infra_void` 的同一條紀律：沒量完不等於量到了。
        """
        deadline = time.time() + timeout_s
        with self._idle:
            while self._inflight > 0:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return False
                self._idle.wait(remaining)
        return True

    def _handle_inner(self, h: BaseHTTPRequestHandler, method: str) -> None:
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

        # ── path 政策：這條路不是模型 API ⇒ **不開連線**，回 403 ────────
        #  順序在 sink 之前，理由是「誰拒絕的」要講得準：這一通是**門**不讓它
        #  走，不是「上游沒人指定」。兩個原因撞在一起時記門的那一個。
        if self.path_policy == "model" and not is_model_path(h.path):
            self._refuse_nonmodel_path(h, method, wire, call_id, rec_t0=t0,
                                       req_sha=req_sha, path=h.path)
            return

        # ── fail-closed：這條路由沒有人指定上游 ─────────────────────────
        #  舊行為是落到 `envmap.DEFAULT_UPSTREAM` ＝ **公開 API，真的出網**
        #  （Claude Code 的 `/api/hello` 探測就是這樣去了 api.openai.com）。
        #  這裡在**開任何連線之前**就回絕：不組 header（所以真鑰連碰都沒碰）、
        #  不解析 DNS、不送任何 bytes。請求本體仍然逐位元落盤（鐵律 3），
        #  而且照樣算進 `requests_seen`——**「被擋下來」也是發生過的事**。
        base = self.upstreams[wire]
        if envmap.is_sink(base):
            self._refuse_unspecified(h, method, wire, call_id, rec_t0=t0,
                                     req_sha=req_sha, path=h.path, base=base)
            return

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

        target = join_upstream(base, h.path, wire)
        u = urllib.parse.urlsplit(target)
        # `dict[str, Any]`：一列索引裡混了 str／int／float／bool／None，
        # 不標的話會被推成 `dict[str, object]`，接著 `rec.get("response_sha256")`
        # 就不能餵回 `stats`。標註**不改任何值**。
        rec: dict[str, Any] = {
            "call_id": call_id, "ts": t0, "mode": self.mode, "wire": wire,
            "method": method, "path": h.path, "upstream": target,
            "request_sha256": req_sha, "request_bytes": len(sent),
            "body_rewritten": rewritten}

        conn = None
        try:
            cls = (http.client.HTTPSConnection if u.scheme == "https"
                   else http.client.HTTPConnection)
            # `type: ignore[arg-type]`：`urlsplit().hostname` 的靜態型別是
            # `str | None`（沒有 netloc 時為 None），而 http.client 只收 str。
            # **不補 `or ""` 之類的預設值**：upstream base_url 沒有主機名就是
            # 設定錯誤，補了會把「設定錯」悄悄變成「連到別的地方」。讓它照原樣
            # 炸在這裡、由外層的 except 寫成 `error` 落盤（鐵律 3）。
            conn = cls(u.hostname, u.port,  # type: ignore[arg-type]
                       timeout=self.timeout_s)
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
        self._finish(rec, t0, wire, req_sha)

    def _finish(self, rec: dict, t0: float, wire: str, req_sha: str) -> None:
        """一通結束：落索引 ＋ 更新統計。**只有這一份**。

        sink 那條路與正常轉送共用這一支，否則兩邊的計數遲早會漂——而
        `requests_seen` 是我們宣稱「中介真的發生了」的唯一證據，它漂掉
        比少一個欄位嚴重得多。
        """
        rec["elapsed_s"] = round(time.time() - t0, 4)
        self._index(rec)
        with self._lock:
            self.stats["requests_seen"] += 1
            self.stats["by_wire"][wire] = self.stats["by_wire"].get(wire, 0) + 1
            self.stats["request_sha256"].append(req_sha)
            self.stats["response_sha256"].append(rec.get("response_sha256"))
            if rec.get("error"):
                self.stats["errors"] += 1
            if rec.get("blocked"):
                self.stats["blocked"] += 1
            if rec.get("refused_path"):
                self.stats["refused_path"] += 1

    def _refuse_nonmodel_path(self, h: BaseHTTPRequestHandler, method: str,
                              wire: str, call_id: str, *, rec_t0: float,
                              req_sha: str, path: str) -> None:
        """不是模型 API 的 path：**擋在門上**，一個 byte 都不往上游送。

        這一支存在的理由，是門從 byte pipe 升級成 proxy 的**全部意義**：
        byte pipe 之下 `GET /admin` 會原樣隧道到上游，只要對面收就成立；
        會終結 HTTP 之後，門自己看得懂 path，於是「唯一那條路」才真的只有
        模型通道那麼寬。

        ⚠ 回的是 **403 不是 502**，跟 `_refuse_unspecified` 的口徑**刻意相反**：
          那邊是「你要的上游從來不存在」（＝上游壞了，502 是實話）；
          這邊是「上游好得很，但這條路我不讓你走」——那是**拒絕**不是故障，
          寫成 502 會讓人（和 SDK 的重試邏輯）以為重試一下就會通。
          也刻意**不用 401／407**：那兩個會讓 SDK 跑去換憑證。
        """
        payload = json.dumps({
            "error": "vacant_door_non_model_path",
            "wire": wire,
            "path": path,
            "method": method,
            "message": (
                f"這扇門只轉送模型 API 的 path，`{path}` 不在名單上，"
                f"所以這一通被擋在門上——一個 byte 都沒有往上游送。"
                f"名單：{'／'.join(MODEL_PATHS)}。"
                f"（門仍然把這一通逐位元落盤了：call_id={call_id}）"),
        }, ensure_ascii=False, indent=2).encode("utf-8")
        (self.wire_dir / f"{call_id}.resp.bin").write_bytes(payload)
        rec: dict[str, Any] = {
            "call_id": call_id, "ts": rec_t0, "mode": self.mode, "wire": wire,
            "method": method, "path": path, "upstream": None,
            "request_sha256": req_sha,
            "request_bytes": len(
                (self.wire_dir / f"{call_id}.req.bin").read_bytes()),
            "body_rewritten": False, "status": 403,
            "error": "non_model_path", "refused_path": True,
            "response_sha256": hashlib.sha256(payload).hexdigest(),
            "response_bytes": len(payload), "streamed": False}
        try:
            h.send_response(403)
            h.send_header("Content-Type", "application/json; charset=utf-8")
            h.send_header("Content-Length", str(len(payload)))
            h.end_headers()
            if method != "HEAD":
                h.wfile.write(payload)
                h.wfile.flush()
        except Exception:                            # noqa: BLE001
            pass
        self._finish(rec, rec_t0, wire, req_sha)

    def _refuse_unspecified(self, h: BaseHTTPRequestHandler, method: str,
                            wire: str, call_id: str, *, rec_t0: float,
                            req_sha: str, path: str, base: str) -> None:
        """沒人指定上游的那條路由：**擋在本機**，回 502 ＋ 一段講得出所以然的 JSON。

        為什麼是「指到一個會拒絕的 sink」而不是「拒絕啟動」：
        **「這條路由沒人指定」不等於「這一跑會用到這條路」**。pi 的 40 格
        `upstreams_defaulted: ['anthropic']` 而 anthropic 零流量——在流量發生
        之前就拒絕啟動，等於用一個沒量到的東西判一個罪，而且會把 40 格既有
        的跑全部擋掉。指到 sink 的話：沒流量的跑**逐位元不變**，有流量的跑
        **當場死在本機**且原文留在 wire log 裡。

        ⚠ 回的是 502 不是 403：對 agent 來說這是「上游壞了」，那是實話——
          它要的那個上游從來沒有存在過。用 4xx 會讓某些 SDK 認成
          「我的金鑰不對」而去走別的憑證路徑。
        """
        names = dict(envmap.UPSTREAM_VARS).get(wire, ())
        msg = {
            "error": "vacant_run_unspecified_upstream",
            "wire": wire,
            "path": path,
            "message": (
                f"`vacant run` 沒有收到 {wire} 這條路由的上游位址，"
                f"所以這一通被擋在本機——一個 byte 都沒有出去。"
                f"要指定上游：{'／'.join(names)}。"
                f"真的要走公開 API（{envmap.DEFAULT_UPSTREAM.get(wire)}）"
                f"就明講 `--allow-public-upstream` 或 "
                f"{envmap.ALLOW_PUBLIC_VAR}=1。"),
        }
        payload = json.dumps(msg, ensure_ascii=False, indent=2).encode("utf-8")
        (self.wire_dir / f"{call_id}.resp.bin").write_bytes(payload)
        rec: dict[str, Any] = {
            "call_id": call_id, "ts": rec_t0, "mode": self.mode, "wire": wire,
            "method": method, "path": path, "upstream": base,
            "request_sha256": req_sha, "request_bytes": 0,
            "body_rewritten": False, "status": 502,
            "error": "unspecified_upstream_sink", "blocked": True,
            "response_sha256": hashlib.sha256(payload).hexdigest(),
            "response_bytes": len(payload), "streamed": False}
        rec["request_bytes"] = len(
            (self.wire_dir / f"{call_id}.req.bin").read_bytes())
        try:
            h.send_response(502)
            h.send_header("Content-Type", "application/json; charset=utf-8")
            h.send_header("Content-Length", str(len(payload)))
            h.end_headers()
            if method != "HEAD":
                h.wfile.write(payload)
                h.wfile.flush()
        except Exception:                        # noqa: BLE001
            pass
        self._finish(rec, rec_t0, wire, req_sha)

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
