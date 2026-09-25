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

重試：上游 429／5xx／連線錯誤最多重試 4 次（2、4、8、16 秒退避），只在還沒送任何位元組
給 agent 之前重試；每一次嘗試都各記一筆。

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
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UPSTREAM = "https://openrouter.ai"
RETRY_WAITS = (2, 4, 8, 16)
RETRY_STATUS = {429, 500, 502, 503, 504}


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
            bucket["ok"] += int(rec.get("status") == 200)
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

    def write(self, io_rec: dict, led_rec: dict) -> None:
        with self._lock:
            with (self.out / "io.jsonl").open("a") as f:
                f.write(self._redact(json.dumps(io_rec, ensure_ascii=False)) + "\n")
            with (self.out / "ledger.jsonl").open("a") as f:
                f.write(json.dumps(led_rec) + "\n")
            self._add(led_rec)
            s = dict(self.summary, spent_usd=round(self.spent, 8), budget_usd=self.budget)
            (self.out / "summary.json").write_text(json.dumps(s, indent=1))


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

        def _split(self) -> tuple[str, str]:
            p = self.path
            if p.startswith("/t/"):
                rest = p[3:]
                tag, _, tail = rest.partition("/")
                return tag or "untagged", "/" + tail
            return "untagged", p

        def do_GET(self):  # /models 之類的唯讀查詢原樣轉送（不記帳）
            tag, path = self._split()
            if not path.startswith("/api/v1/models"):
                return self._send_json(404, {"error": "not proxied"})
            req = urllib.request.Request(UPSTREAM + path, headers={"Authorization": f"Bearer {key}"})
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
            tag, path = self._split()
            t0 = time.time()
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
                return self._send_json(402, {"error": "evaluation budget exhausted"})
            sent = dict(body)
            sent["provider"] = models[model]["provider"]
            sent["usage"] = {"include": True}
            stream = bool(sent.get("stream"))
            if stream:
                sent["stream_options"] = dict(sent.get("stream_options") or {}, include_usage=True)
            data = json.dumps(sent).encode()
            attempts = []
            for i in range(len(RETRY_WAITS) + 1):
                req = urllib.request.Request(UPSTREAM + "/api/v1/chat/completions", data=data, headers={
                    "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/cosmopig/vacant", "X-Title": "vacant-eval"})
                try:
                    r = urllib.request.urlopen(req, timeout=600)
                except urllib.error.HTTPError as e:
                    err = e.read().decode(errors="replace")
                    attempts.append({"status": e.code, "error": err[:2000], "t": round(time.time() - t0, 2)})
                    if e.code in RETRY_STATUS and i < len(RETRY_WAITS):
                        time.sleep(RETRY_WAITS[i])
                        continue
                    self._finish(tag, model, body, sent, e.code, err, None, attempts, t0, stream)
                    return self._send_json(e.code, {"error": err[:2000]})
                except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                    attempts.append({"status": None, "error": repr(e)[:500], "t": round(time.time() - t0, 2)})
                    if i < len(RETRY_WAITS):
                        time.sleep(RETRY_WAITS[i])
                        continue
                    self._finish(tag, model, body, sent, 502, repr(e), None, attempts, t0, stream)
                    return self._send_json(502, {"error": "upstream unreachable"})
                attempts.append({"status": r.status, "t": round(time.time() - t0, 2)})
                return self._relay(r, tag, model, body, sent, attempts, t0, stream)

        def _relay(self, r, tag, model, body, sent, attempts, t0, stream):
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
            for line in r:
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
                    if obj.get("usage"):
                        last_obj = obj
            self.close_connection = True
            final = dict(meta, usage=(last_obj or {}).get("usage"), client_disconnected=client_gone)
            return self._finish(tag, model, body, sent, r.status, "".join(chunks), final, attempts, t0, stream)

        def _finish(self, tag, model, body, sent, status, resp_text, parsed, attempts, t0, stream):
            u = _usage_of((parsed or {}).get("usage") if isinstance(parsed, dict) else None)
            cost = u.pop("cost")
            led = {"ts": t0, "tag": tag, "model": model, "status": status, "stream": stream,
                   "generation_id": (parsed or {}).get("id") if isinstance(parsed, dict) else None,
                   "provider": (parsed or {}).get("provider") if isinstance(parsed, dict) else None,
                   "usage": u, "cost": cost, "latency_s": round(time.time() - t0, 3),
                   "attempts": len(attempts)}
            io = {"ts": t0, "tag": tag, "model": model, "request_from_agent": body,
                  "request_sent": {k: v for k, v in sent.items() if k != "messages"} | {"messages": "<same as request_from_agent>"},
                  "status": status, "attempts": attempts, "response": resp_text}
            ledger.write(io, led)

    return H


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True, help="JSON: {models: {id: {provider: {...}}}, budget_usd}")
    ap.add_argument("--out", required=True, help="紀錄目錄（io.jsonl、ledger.jsonl、summary.json）")
    ap.add_argument("--key-file", default=os.path.expanduser("~/.config/vacant-eval/openrouter.key"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=18900)
    a = ap.parse_args(argv)
    cfg = json.loads(Path(a.config).read_text())
    key = Path(a.key_file).read_text().strip()
    ledger = Ledger(Path(a.out), float(cfg["budget_usd"]), key)
    srv = ThreadingHTTPServer((a.host, a.port), make_handler(cfg, ledger, key))
    print(f"orproxy on http://{a.host}:{a.port} -> {UPSTREAM}; out={a.out}; "
          f"spent so far ${ledger.spent:.6f} of ${ledger.budget}", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
