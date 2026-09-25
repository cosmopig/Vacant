"""server — **HTTP 收件口**：閉源 agent、SaaS 匯出、人工上傳都從這裡交件。

這支在架構裡承重什麼（報告 §06「真正的非程式落地缺口：雲端收件服務」、§11「只能交
文件／圖片的 SaaS」）：

報告審視 vacant-world-cloud 的 `/api/result` 時指出：回寫端**相信回傳者給的 verdict**，
接著把狀態設成 `done`；`matched || null` 把「檢查過而且不相符」與「沒評估」混在一起；
沒設 token 時有 `dev-token` 預設值。這支是同一件事的正確形狀：

- **提交者只能提交。** 請求裡的 `verdict`／`accepted`／`matched`／`status` 一律忽略，
  回應裡列在 `ignored_fields`——裁決只來自本機驗證器，由 verifier 金鑰簽。
- **生命週期明示**：已收到 → 驗證 → accept／reject／hold／escalate（`void` 另計）
  → 只有經過 `vacant release`（收件端重驗＋讀回）的版本才出現在公開路徑。
- **公開路徑只讀已放行的檔案**：`GET /published/<task>/<path>` 讀的是 `dir:` 目的端，
  不是隔離區；沒放行就是 404。只送收件端放行紀錄裡列著、而且此刻內容雜湊仍對得上的
  檔案；不跟隨符號連結。
- **沒有 token 就不啟動**（除非明講 `--insecure-no-token`，那是開發用）。

## 端點

    POST /v1/tasks/<task_id>/submissions   Authorization: Bearer <token>
         {"source": "...", "files": {"report.md": "<base64>", ...}}
         沒過 ⇒ 回應多 `feedback`（和 agent 回合結束收到的同一段：哪個檔哪一行、應該是多少）與 `issues`
         （結構化）。交來的只有檔案：**不追到步驟、不記任何人**；隱藏主張只說沒過。
    GET  /v1/tasks/<task_id>                Authorization: Bearer <token>
    GET  /published/<task_id>/<path>        公開，只有已放行的版本

## 誠實邊界

1. 共享 token 證明的是「持有這個 token 的人送來的」，不是「哪一個 agent」，更不是「品質」。
2. 放行（`vacant release`）刻意**不**在這個服務裡自動做：批准權屬於另一個角色。
3. 伺服器與提交者在同一台機器同一個帳號時，隔離區的不可竄改性見 `artifact.py` 誠實邊界 1。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import pathlib
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import flow
from .approval import check_lock
from .artifact import artifact_digest, safe_relpath
from .contract import load as load_contract
from .recipients import RECORD_NAME, DirRecipient, parse_destination

MAX_BODY = 60 * 1024 * 1024
IGNORED_SUBMITTER_FIELDS = ("verdict", "accepted", "matched", "status", "outcome", "decision")


class IntakeApp:
    def __init__(self, contracts: list[pathlib.Path], *, token: str | None,
                 sandbox: str = "auto"):
        self.token = token
        self.sandbox = sandbox
        self.contract_paths = {}
        for p in contracts:
            c = load_contract(p)
            self.contract_paths[c.task_id] = p
        self._lock = threading.Lock()

    def task(self, task_id: str) -> flow.Task | None:
        p = self.contract_paths.get(task_id)
        return flow.open_task(p) if p else None

    def authorized(self, header: str | None) -> bool:
        if self.token is None:
            return True
        if not header or not header.startswith("Bearer "):
            return False
        return hmac.compare_digest(header[7:].strip(), self.token)

    def submit(self, task_id: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        task = self.task(task_id)
        if task is None:
            return 404, {"error": f"unknown task {task_id}"}
        files = body.get("files")
        if not isinstance(files, dict) or not files:
            return 400, {"error": "files must be a non-empty object of path -> base64"}
        blobs: dict[str, bytes] = {}
        for rel, b64 in files.items():
            if safe_relpath(str(rel)) is None:
                return 400, {"error": f"unsafe path {rel!r}"}
            try:
                blobs[str(rel)] = base64.b64decode(str(b64), validate=True)
            except (ValueError, TypeError):
                return 400, {"error": f"{rel}: not valid base64"}
        ignored = [k for k in IGNORED_SUBMITTER_FIELDS if k in body]
        with self._lock:
            res = flow.submit_blobs(task, blobs, source=f"http:{str(body.get('source', ''))[:80]}",
                                    sandbox=self.sandbox)
        located = _locate(task, res, blobs)
        res = {k: v for k, v in res.items() if k != "results"} | {
            "results": [{"claim_id": r["claim_id"], "status": r["status"],
                         "detail": r["detail"][:500]} for r in res.get("results", [])],
            "ignored_fields": ignored,
            "published": False,
            "note": "the decision is made here; release is a separate, approved step"} | located
        return 200, res

    def status(self, task_id: str) -> tuple[int, dict[str, Any]]:
        task = self.task(task_id)
        if task is None:
            return 404, {"error": f"unknown task {task_id}"}
        st = flow.status(task)
        return 200, {k: st.get(k) for k in ("task_id", "state", "latest_outcome",
                                             "latest_artifact", "latest_reasons", "attempts",
                                             "decisions", "void", "released")}

    @staticmethod
    def _released_by_gate(task: flow.Task, rcp: DirRecipient, art: str) -> bool:
        try:
            return _released_by_gate_impl(task, rcp, art)
        except Exception:  # noqa: BLE001 — 查不清楚就不送
            return False

    def published(self, task_id: str, rel: str) -> tuple[int, bytes, str]:
        """只送**收件端寫過紀錄、而且內容對得上紀錄**的檔案。

        不跟隨連結：任務目錄本身、或路徑上任何一段是符號連結 ⇒ 404（先 resolve 再比對
        包含關係的話，一個指向別處的任務目錄連結會把別處的檔案當成已放行的送出去）。
        每次送出前重算雜湊，和放行紀錄（`files`）逐檔比對；並且**不信紀錄檔本身**
        （誰都寫得出來），而是確認簽過的帳本裡有一筆收件端的 `released`：同一個成果、
        目前被鎖的契約、同一個解析後的目的端、讀回成立、之後沒被撤回。
        """
        nf = (404, b"not found", "text/plain")
        task = self.task(task_id)
        if task is None:
            return nf
        dest = task.contract.release.get("destination") or ""
        try:
            rcp = parse_destination(dest, task.contract.base_dir)
        except Exception:  # noqa: BLE001
            return nf
        if not isinstance(rcp, DirRecipient):
            return 404, b"this task is not published over HTTP", "text/plain"
        norm = safe_relpath(rel)
        if norm is None or norm.startswith(".vacant") or norm == RECORD_NAME:
            return nf
        tdir = rcp.root / task_id
        cur = tdir
        for part in [""] + norm.split("/"):
            cur = cur / part if part else cur
            if cur.is_symlink():
                return nf
        recp = tdir / RECORD_NAME
        if not tdir.is_dir() or recp.is_symlink() or not recp.is_file():
            return nf
        try:
            record = json.loads(recp.read_text(encoding="utf-8"))
            files = {f["path"]: f for f in record.get("files", [])}
        except (ValueError, TypeError, KeyError, AttributeError):
            return nf
        art = str(record.get("artifact_sha256"))
        if record.get("task_id") != task_id or norm not in files \
                or artifact_digest(list(files.values())) != art \
                or not self._released_by_gate(task, rcp, art):
            return nf
        p = tdir / norm
        if not p.is_file():
            return nf
        data = p.read_bytes()
        if hashlib.sha256(data).hexdigest() != files[norm]["sha256"]:
            return nf
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        return 200, data, ctype


#: 交件超過這個大小就不定位（只回裁決與各主張的細節）：定位是給人看的方便，不可以讓遠端一次交件佔住一個核心
LOCATE_MAX_BYTES = 5 * 1024 * 1024
_CLIP = 200


def _locate(task: flow.Task, res: dict[str, Any], blobs: dict[str, bytes]) -> dict[str, Any]:
    """交件沒過時：和 agent 在回合結束收到的同一段「哪個檔哪一行、應該是多少」（`trace.blame.locate_results`
    ＋`feedback.render_agent`；KS-1 乾淨），外加一份結構化的清單。HTTP 交來的只有檔案、沒有任何一步 ⇒ **不追到步驟、
    不記任何人**（誠實邊界 1：token 證明不了是哪一個 agent）。隱藏主張只說「沒過」。壞掉 ⇒ 不影響裁決，照樣回應。

    定位看的是**收件口凍結、驗過的那一份**（隔離區的 manifest 攤開），不是交來的原始位元組：不在繳付物裡的檔、
    路徑寫法不同的檔都不會被拿來說事（2026-09-25 審查 http#3、#4、#5）。"""
    art = res.get("artifact_sha256")
    if res.get("outcome") in (None, "accept") or not res.get("results") or not art:
        return {}
    import tempfile
    try:
        from ..trace import blame as B
        from ..trace import feedback as F
        manifest = task.store.load_manifest(str(art))
        size = sum(int(f.get("size") or 0) for f in manifest.get("files") or [])
        if size > LOCATE_MAX_BYTES:
            return {"feedback_skipped": f"the submission is {size} bytes; locating stops at "
                                        f"{LOCATE_MAX_BYTES} (see results[].detail)"}
        hidden = {c.id for c in task.contract.claims if c.hidden}
        results = [dict(r, hidden=r.get("claim_id") in hidden) for r in res["results"]]
        with tempfile.TemporaryDirectory(prefix="vacant-http-") as td:
            root = task.store.materialize(manifest, pathlib.Path(td) / "a")
            found = B.locate_results(task.contract, results, root)
        text, _state = F.render_agent(
            found, results, reasons=res.get("reasons"),
            header=f"The intake's decision for this submission is {res.get('outcome')!r} "
                   f"(signed; the submitter cannot change it). The checks point here:",
            footer="Fix these and submit again; `results` has every check's own words.",
            more_hint="see `issues` and `results`")

        def clip(v: Any) -> Any:
            return v[:_CLIP] if isinstance(v, str) else v
        issues = [{"claim_id": b["claim"], "path": clip(b["location"].get("path")),
                   "line": b["location"].get("line"), "value": clip(b.get("value")),
                   "expected": clip(next((e.get("value") for e in b.get("expected") or []
                                          if e.get("value") is not None), None)),
                   "note": clip(b["location"].get("note"))}
                  for b in found if not b.get("hidden")][:50]
        return {"feedback": text, "issues": issues}
    except Exception as e:  # noqa: BLE001 — 定位壞掉不影響裁決
        return {"feedback_error": type(e).__name__}


def _released_by_gate_impl(task: flow.Task, rcp: DirRecipient, art: str) -> bool:
    """目的端上的紀錄檔誰都寫得出來（同一個帳號、專案裡的 `dir:published`）——
    所以**不信它**，只信簽過的帳本：這個成果在**目前被鎖的契約**下，由收件端放行到這個
    解析後的目的端、讀回成立，而且之後沒有被撤回。"""
    ok, _why = task.ledger.verify(task.trust)
    if not ok or check_lock(flow._lock_for(task), trust=task.trust, task_id=task.task_id,
                            contract_sha256=task.contract.sha256):
        return False
    if task.task_id in (rcp._state().get("withdrawn") or []):
        return False
    live: tuple[str, str] | None = None
    for ev in task.ledger.events():
        if ev.get("canonical_destination") != rcp.canonical:
            continue
        if ev["type"] == "released" and ev.get("readback_ok"):
            live = (str(ev.get("artifact_sha256")), str(ev.get("contract_sha256")))
        elif ev["type"] == "withdrawn" and not ev.get("noop"):
            live = None
    return live == (art, task.contract.sha256)


def make_handler(app: IntakeApp):
    class H(BaseHTTPRequestHandler):
        server_version = "vacant-intake/1"

        def log_message(self, fmt, *a):  # noqa: D401 — 安靜；帳本才是紀錄
            return

        def _json(self, code: int, obj: dict[str, Any]) -> None:
            data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):  # noqa: N802
            m = re.fullmatch(r"/v1/tasks/([A-Za-z0-9._-]+)/submissions", self.path)
            if not m:
                return self._json(404, {"error": "not found"})
            if not app.authorized(self.headers.get("Authorization")):
                return self._json(401, {"error": "missing or wrong bearer token"})
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return self._json(413, {"error": f"body must be 1..{MAX_BODY} bytes"})
            try:
                body = json.loads(self.rfile.read(n).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._json(400, {"error": "body is not JSON"})
            if not isinstance(body, dict):
                return self._json(400, {"error": "body must be a JSON object"})
            code, obj = app.submit(m.group(1), body)
            return self._json(code, obj)

        def do_GET(self):  # noqa: N802
            m = re.fullmatch(r"/v1/tasks/([A-Za-z0-9._-]+)", self.path)
            if m:
                if not app.authorized(self.headers.get("Authorization")):
                    return self._json(401, {"error": "missing or wrong bearer token"})
                code, obj = app.status(m.group(1))
                return self._json(code, obj)
            m = re.fullmatch(r"/published/([A-Za-z0-9._-]+)/(.+)", self.path)
            if m:
                code, data, ctype = app.published(m.group(1), m.group(2))
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return None
            return self._json(404, {"error": "not found"})

    return H


def serve(*, contracts: list[pathlib.Path], host: str, port: int,
          token_file: str | None, insecure_no_token: bool, sandbox: str = "auto") -> int:
    token = None
    if token_file:
        token = pathlib.Path(token_file).read_text(encoding="utf-8").strip() or None
    if token is None and not insecure_no_token:
        print("vacant intake: refusing to start without a submitter token "
              "(--token-file). Use --insecure-no-token only for local development.",
              file=sys.stderr)
        return 2
    app = IntakeApp(contracts, token=token, sandbox=sandbox)
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"vacant intake: serving {sorted(app.contract_paths)} on http://{host}:{port} "
          f"(token {'required' if token else 'NOT required — development only'})",
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
