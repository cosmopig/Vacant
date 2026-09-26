"""OpenRouter 記帳代理：評估跑真模型時，每一通模型呼叫都經過這裡。

這支在架構裡承重什麼：鐵律 3（全 I/O JSONL 落盤、retry×4）用在「公開題庫照官方方式跑」
的評估上。agent（pi／OpenCode／…，可能在 Harbor 的任務容器裡）只知道這個代理的網址和一把
假金鑰；真金鑰只在這個行程裡讀一次，不進容器、不進 log。

它做五件事：
1. **轉送**：OpenAI 相容的 `/api/v1/chat/completions`（串流與非串流）原樣轉給 OpenRouter。
2. **釘住模型與供應商**：只放行設定檔裡列的模型；每一通請求都被加上 `provider`
   （`order`、`quantizations`、`allow_fallbacks: false`），同一次評估不會悄悄換供應商或量化。
   設定檔裡的推論參數不覆寫 agent 送來的值——官方跑法決定參數，這裡只記錄。
3. **記帳**：強制 `usage.include`（串流另加 `stream_options.include_usage`），每一通的
   token（輸入、輸出、推理、快取）與費用記進 `ledger.jsonl`；`summary.json` 是按標籤／模型的加總。
4. **全文紀錄**：請求本文與回應本文（串流就是原始 SSE）逐通寫進 `io.jsonl`。
   Authorization 標頭不記；回應裡若出現金鑰字串會被遮掉（防呆，正常不會出現）。
5. **預算閘**：累計費用到上限就拒絕新請求（HTTP 402），寧可讓那一跑失敗被記成 infra_void，
   也不超支。

標籤：網址前綴 `/t/<tag>/` 會被記成這一通的標籤（例如 `/t/tb2-pi-A-task17/api/v1/...`），
用來把花費拆到每一格；沒有前綴就是 `untagged`。

思考開關：標籤後面可以接 `think/on` 或 `think/off`（例如 `/t/<tag>/think/off/api/v1/...`）。
這是實驗條件，不是 agent 的選擇，所以由代理強制：`on`＝`reasoning: {enabled: true, effort: medium}`、
`off`＝`reasoning: {enabled: false}`，並拿掉 agent 自己送的 `reasoning_effort`。agent 原本送了什麼
照樣記在 `io.jsonl` 的 `request_from_agent`；每一通的推理 token 記在帳本，關思考的條件事後可以逐通查
「推理 token 是不是 0」。

每一跑的上限：設定檔的 `tag_cap_usd` 是同一個標籤（＝同一跑）累計費用的上限，到了就回 402。
它是所有條件都一樣的安全網，不是實驗設計的一部分；被它擋下的請求記在 `refusals.jsonl`。

重試：上游 429／5xx／連線錯誤最多重試 4 次（預設 2、4、8、16 秒退避，設定檔 `retry_waits` 可改），
只在還沒送任何位元組給 agent 之前重試；每一次嘗試都各記一筆。
**串流裡的錯誤**：OpenRouter 對串流請求常先回 HTTP 200、送幾行 `: OPENROUTER PROCESSING`，再用一個
`data: {"error": {"code": 429, …}}` 表示供應商拒絕（2026-09-25 校準實測：Darkbloom 的 `rate_limit_exceeded`）。
所以串流要先讀到**第一個 data 塊**才決定：是錯誤 ⇒ 照上面的規則重試、重試完還是錯就回 agent 一個**真的**
HTTP 錯誤（不是假的 200）；帳本的 `status` 記成那個錯誤碼、`stream_error` 記內容。內容開始之後才出現的錯誤
沒辦法重試，照樣轉給 agent，帳本記 `stream_error`、不算 `ok`。

本機算力（2026-09-26 加）：設定檔有 `upstreams`（`{名字: 基底網址}`，例如兩台跑 LM Studio 的機器）時，
網址要帶 `/t/<tag>/up/<名字>/…`，請求轉到那一台的 `/v1/chat/completions`，不帶金鑰、不加 OpenRouter 專用欄位
（`provider`、`usage.include`、`reasoning` 物件）；思考開關改用 `reasoning_effort`（`off`＝`none`、`on`＝`medium`）。
同一題的 A、C 由呼叫端指定同一台（兩台的設定不一定一樣：2026-09-26 實測 1003 會照 `reasoning_effort` 開關思考，
w401c-15 永遠不思考）。本機沒有費用：帳本的 `cost` 是 `null`，預算閘不作用；其餘（全文紀錄、逐通帳、重試）照舊。

誠實邊界：
- 費用以 OpenRouter 回應裡的 `usage.cost` 為準；`vacant eval` 結束時另外用 `/api/v1/key`
  對一次總帳。回應沒帶 cost（例如上游中斷）時那一通記成 `cost: null`，不猜。
- 這是記帳與紀錄，不是隔離：agent 若自己另找網路出口打別的模型，這裡看不到
  （Harbor 的任務容器網路設定決定這點，要另外記進環境清單）。
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UPSTREAM = "https://openrouter.ai"
RETRY_WAITS = (2, 4, 8, 16)
RETRY_STATUS = {429, 500, 502, 503, 504}
THINK = {"on": {"enabled": True, "effort": "medium"}, "off": {"enabled": False}}


LOCAL_THINK = {"on": "medium", "off": "none"}


def split_route(p: str) -> tuple[str, str | None, str | None, str]:
    """`/t/<tag>/[up/<名字>/][think/<on|off>/]<rest>` → (tag, upstream, think, "/<rest>")。"""
    if not p.startswith("/t/"):
        return "untagged", None, None, p
    tag, _, tail = p[3:].partition("/")
    up = think = None
    if tail.startswith("up/"):
        up, _, tail = tail[len("up/"):].partition("/")
    if tail.startswith("think/"):
        think, _, tail = tail[len("think/"):].partition("/")
    return tag or "untagged", up, think, "/" + tail


def split_path(p: str) -> tuple[str, str | None, str]:
    """`/t/<tag>/[think/<on|off>/]<rest>` → (tag, think, "/<rest>")；沒有前綴 → ("untagged", None, p)。"""
    tag, _up, think, rest = split_route(p)
    return tag, think, rest


def prepare_request(body: dict, provider: dict, think: str | None, *, local: bool = False) -> dict:
    """agent 送來的本文 → 送給上游的本文。OpenRouter：釘供應商、強制記帳、（有條件時）強制思考開關；
    本機（`local`）：只強制思考開關（`reasoning_effort`），不加 OpenRouter 專用欄位。"""
    sent = dict(body)
    if local:
        sent.pop("provider", None)
        sent.pop("usage", None)
        sent.pop("reasoning", None)
        if think is not None:
            sent["reasoning_effort"] = LOCAL_THINK[think]
    else:
        sent["provider"] = provider
        sent["usage"] = {"include": True}
        if think is not None:
            sent.pop("reasoning_effort", None)
            sent["reasoning"] = dict(THINK[think])
    if sent.get("stream"):
        sent["stream_options"] = dict(sent.get("stream_options") or {}, include_usage=True)
    return sent


class Ledger:
    """io.jsonl／ledger.jsonl／summary.json 三個檔；一把鎖序列化寫入。"""

    def __init__(self, out: Path, budget_usd: float, key: str):
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.budget = budget_usd
        self._key = key
        self._lock = threading.Lock()
        self.spent = 0.0
        self.summary: dict = {"by_tag": {}, "by_model": {}, "total": _zero()}
        led = out / "ledger.jsonl"
        if led.exists():  # 續跑：從既有帳本重建累計（同一個輸出目錄＝同一筆預算）
            for line in led.read_text().splitlines():
                try:
                    self._add(json.loads(line))
                except (ValueError, KeyError):
                    continue

    def _redact(self, s: str) -> str:
        return s.replace(self._key, "[REDACTED]") if self._key and self._key in s else s

    def _add(self, rec: dict) -> None:
        for bucket in (self.summary["by_tag"].setdefault(rec["tag"], _zero()),
                       self.summary["by_model"].setdefault(rec.get("model") or "?", _zero()),
                       self.summary["total"]):
            bucket["requests"] += 1
            bucket["ok"] += int(rec.get("status") == 200 and not rec.get("stream_error"))
            u = rec.get("usage") or {}
            for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "cached_tokens"):
                bucket[k] += int(u.get(k) or 0)
            if rec.get("cost") is not None:
                bucket["cost_usd"] = round(bucket["cost_usd"] + float(rec["cost"]), 8)
        if rec.get("cost") is not None:
            self.spent += float(rec["cost"])

    def over_budget(self) -> bool:
        with self._lock:
            return self.spent >= self.budget

    def tag_spent(self, tag: str) -> float:
        with self._lock:
            return float(self.summary["by_tag"].get(tag, {}).get("cost_usd", 0.0))

    def refuse(self, rec: dict) -> None:
        with self._lock:
            with (self.out / "refusals.jsonl").open("a") as f:
                f.write(json.dumps(rec) + "\n")

    def write(self, io_rec: dict, led_rec: dict) -> None:
        with self._lock:
            with (self.out / "io.jsonl").open("a") as f:
                f.write(self._redact(json.dumps(io_rec, ensure_ascii=False)) + "\n")
            with (self.out / "ledger.jsonl").open("a") as f:
                f.write(json.dumps(led_rec) + "\n")
            self._add(led_rec)
            s = dict(self.summary, spent_usd=round(self.spent, 8), budget_usd=self.budget)
            (self.out / "summary.json").write_text(json.dumps(s, indent=1))


def _peek_stream(r) -> tuple[list[bytes], dict | None]:
    """讀到第一個 `data:` 塊為止（前面的 `: OPENROUTER PROCESSING` 保活行照樣留著）。
    回 (讀過的行, 錯誤物件或 None)。第一塊就是錯誤、而且沒有任何內容 ⇒ 那是供應商拒絕，不是回答。"""
    head: list[bytes] = []
    for line in r:
        head.append(line)
        s = line.strip()
        if not s.startswith(b"data:"):
            continue
        payload = s[5:].strip()
        if payload in (b"[DONE]", b""):
            return head, None
        try:
            obj = json.loads(payload)
        except ValueError:
            return head, None
        if isinstance(obj, dict) and obj.get("error") and not any(
                (c.get("delta") or {}).get("content") or (c.get("delta") or {}).get("tool_calls")
                for c in obj.get("choices") or [] if isinstance(c, dict)):
            return head, obj["error"] if isinstance(obj["error"], dict) else {"message": str(obj["error"])}
        return head, None
    return head, None


def _error_code(err: dict) -> int:
    try:
        code = int(err.get("code"))
    except (TypeError, ValueError):
        return 502
    return code if 400 <= code <= 599 else 502


def _chain(head, rest):
    yield from head
    yield from rest


def _zero() -> dict:
    return {"requests": 0, "ok": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "reasoning_tokens": 0, "cached_tokens": 0, "cost_usd": 0.0}


def _usage_of(u: dict | None) -> dict:
    u = u or {}
    ptd = u.get("prompt_tokens_details") or {}
    ctd = u.get("completion_tokens_details") or {}
    return {"prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": ctd.get("reasoning_tokens"), "cached_tokens": ptd.get("cached_tokens"),
            "cost": u.get("cost")}


def make_handler(cfg: dict, ledger: Ledger, key: str):
    models = cfg["models"]  # {model_id: {"provider": {...}}}
    upstreams = cfg.get("upstreams") or {}  # 本機算力：{名字: 基底網址}
    tag_cap = cfg.get("tag_cap_usd")
    host_id = cfg.get("host_id") or socket.gethostname()

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):  # 不往 stderr 灌每一通
            pass

        def _send_json(self, code: int, obj: dict) -> None:
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _target(self, up: str | None, path: str) -> str | None:
            """上游網址：本機模式 → 那一台的 `/v1/…`；OpenRouter → `UPSTREAM + path`。名字不對 → None。"""
            if not upstreams:
                return UPSTREAM + path
            if up not in upstreams:
                return None
            return upstreams[up].rstrip("/") + path.removeprefix("/api")

        def _auth(self) -> dict:
            return {} if upstreams else {"Authorization": f"Bearer {key}"}

        def do_GET(self):  # /models 之類的唯讀查詢原樣轉送（不記帳）
            tag, up, _think, path = split_route(self.path)
            if not path.startswith("/api/v1/models"):
                return self._send_json(404, {"error": "not proxied"})
            url = self._target(up, path)
            if url is None:
                return self._send_json(400, {"error": f"unknown upstream {up!r}"})
            req = urllib.request.Request(url, headers=self._auth())
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    body = r.read()
                    self.send_response(r.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except urllib.error.HTTPError as e:
                self._send_json(e.code, {"error": e.read().decode(errors="replace")[:500]})

        def do_POST(self):
            tag, up, think, path = split_route(self.path)
            self._think = think
            self._up = up
            t0 = time.time()
            if upstreams and up not in upstreams:
                return self._send_json(400, {"error": f"unknown upstream {up!r}; use /t/<tag>/up/<name>/…"})
            if think is not None and think not in THINK:
                return self._send_json(400, {"error": f"think must be on or off, got {think!r}"})
            if not path.rstrip("/").endswith("/chat/completions"):
                return self._send_json(404, {"error": f"only chat/completions is proxied, got {path}"})
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                body = json.loads(raw)
            except ValueError:
                return self._send_json(400, {"error": "body is not JSON"})
            model = body.get("model")
            if model not in models:
                return self._send_json(403, {"error": f"model {model!r} is not in this evaluation's allowlist"})
            if ledger.over_budget():
                ledger.refuse({"ts": t0, "tag": tag, "model": model, "reason": "evaluation budget", "host": host_id})
                return self._send_json(402, {"error": "evaluation budget exhausted"})
            if tag_cap is not None and ledger.tag_spent(tag) >= float(tag_cap):
                ledger.refuse({"ts": t0, "tag": tag, "model": model, "reason": "per-run cap", "host": host_id})
                return self._send_json(402, {"error": f"per-run spending cap {tag_cap} USD reached for {tag}"})
            sent = prepare_request(body, models[model].get("provider") or {}, think, local=bool(upstreams))
            url = self._target(up, "/api/v1/chat/completions")
            stream = bool(sent.get("stream"))
            data = json.dumps(sent).encode()
            attempts = []
            waits = tuple(cfg.get("retry_waits") or RETRY_WAITS)
            for i in range(len(waits) + 1):
                req = urllib.request.Request(url, data=data, headers={
                    **self._auth(), "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/cosmopig/vacant", "X-Title": "vacant-eval"})
                try:
                    r = urllib.request.urlopen(req, timeout=float(cfg.get("timeout_s") or 600))
                except urllib.error.HTTPError as e:
                    err = e.read().decode(errors="replace")
                    attempts.append({"status": e.code, "error": err[:2000], "t": round(time.time() - t0, 2)})
                    if e.code in RETRY_STATUS and i < len(waits):
                        time.sleep(waits[i])
                        continue
                    self._finish(tag, model, body, sent, e.code, err, None, attempts, t0, stream)
                    return self._send_json(e.code, {"error": err[:2000]})
                except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                    attempts.append({"status": None, "error": repr(e)[:500], "t": round(time.time() - t0, 2)})
                    if i < len(waits):
                        time.sleep(waits[i])
                        continue
                    self._finish(tag, model, body, sent, 502, repr(e), None, attempts, t0, stream)
                    return self._send_json(502, {"error": "upstream unreachable"})
                head: list[bytes] = []
                if stream:
                    head, err_obj = _peek_stream(r)
                    if err_obj is not None:
                        code = _error_code(err_obj)
                        attempts.append({"status": r.status, "stream_error": err_obj,
                                         "t": round(time.time() - t0, 2)})
                        r.close()
                        if code in RETRY_STATUS and i < len(waits):
                            time.sleep(waits[i])
                            continue
                        self._finish(tag, model, body, sent, code, b"".join(head).decode(errors="replace"),
                                     {"stream_error": err_obj}, attempts, t0, stream)
                        return self._send_json(code, {"error": err_obj})
                attempts.append({"status": r.status, "t": round(time.time() - t0, 2)})
                return self._relay(r, tag, model, body, sent, attempts, t0, stream, head)

        def _relay(self, r, tag, model, body, sent, attempts, t0, stream, head=()):
            if not stream:
                resp = r.read().decode(errors="replace")
                self.send_response(r.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp.encode())))
                self.end_headers()
                self.wfile.write(resp.encode())
                try:
                    parsed = json.loads(resp)
                except ValueError:
                    parsed = None
                return self._finish(tag, model, body, sent, r.status, resp, parsed, attempts, t0, stream)
            self.send_response(r.status)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            chunks, last_obj, meta = [], None, {}
            client_gone = False
            for line in _chain(head, r):
                chunks.append(line.decode(errors="replace"))
                if not client_gone:
                    try:
                        self.wfile.write(line)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        client_gone = True  # 照樣讀完上游，帳才記得到
                s = line.strip()
                if s.startswith(b"data:") and s[5:].strip() not in (b"[DONE]", b""):
                    try:
                        obj = json.loads(s[5:])
                    except ValueError:
                        continue
                    for k in ("id", "provider", "model"):
                        if obj.get(k):
                            meta[k] = obj[k]
                    if obj.get("error"):
                        meta["stream_error"] = obj["error"]      # 內容開始之後才出現：沒辦法重試，照記
                    if obj.get("usage"):
                        last_obj = obj
            self.close_connection = True
            final = dict(meta, usage=(last_obj or {}).get("usage"), client_disconnected=client_gone)
            return self._finish(tag, model, body, sent, r.status, "".join(chunks), final, attempts, t0, stream)

        def _finish(self, tag, model, body, sent, status, resp_text, parsed, attempts, t0, stream):
            u = _usage_of((parsed or {}).get("usage") if isinstance(parsed, dict) else None)
            cost = u.pop("cost")
            led = {"ts": t0, "tag": tag, "model": model, "think": getattr(self, "_think", None), "host": host_id,
                   "upstream": getattr(self, "_up", None), "status": status, "stream": stream,
                   "generation_id": (parsed or {}).get("id") if isinstance(parsed, dict) else None,
                   "provider": (parsed or {}).get("provider") if isinstance(parsed, dict) else None,
                   "usage": u, "cost": cost, "latency_s": round(time.time() - t0, 3),
                   "attempts": len(attempts),
                   "stream_error": (parsed or {}).get("stream_error") if isinstance(parsed, dict) else None,
                   "retried_stream_errors": sum(1 for a in attempts if a.get("stream_error"))}
            io = {"ts": t0, "tag": tag, "model": model, "request_from_agent": body,
                  "request_sent": {k: v for k, v in sent.items() if k != "messages"} | {"messages": "<same as request_from_agent>"},
                  "status": status, "attempts": attempts, "response": resp_text}
            ledger.write(io, led)

    return H


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True, help="JSON: {models: {id: {provider: {...}}}, budget_usd}")
    ap.add_argument("--out", required=True, help="紀錄目錄（io.jsonl、ledger.jsonl、summary.json）")
    ap.add_argument("--key-file", default=os.path.expanduser("~/.config/vacant-eval/openrouter.key"),
                    help="OpenRouter 金鑰；設定檔有 upstreams（本機算力）時不讀")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=18900)
    a = ap.parse_args(argv)
    cfg = json.loads(Path(a.config).read_text())
    key = "" if cfg.get("upstreams") else Path(a.key_file).read_text().strip()
    ledger = Ledger(Path(a.out), float(cfg["budget_usd"]), key)
    srv = ThreadingHTTPServer((a.host, a.port), make_handler(cfg, ledger, key))
    print(f"orproxy on http://{a.host}:{a.port} -> {sorted(cfg.get('upstreams') or {}) or UPSTREAM}; out={a.out}; "
          f"spent so far ${ledger.spent:.6f} of ${ledger.budget}", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
