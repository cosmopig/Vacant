"""statusboard — `vacant dashboard`：裝完 Vacant 之後，在本機看它每一個狀態的單頁儀表板。

這支在架構裡承重什麼：產品原則（CLAUDE.md「產品原則」，人類 2026-09-25）——使用者做的事只有
「安裝」＋「打開他本來就用的 agent」。Vacant 在背後記每一步、在 agent 說做完時查一次、把該重做的
退回；這些結果原本散在 `$VACANT_HOME` 底下的好幾個檔（install.json、掛鉤紀錄、每個專案的簽章鏈、
交件說明、任務帳本），要看得一個一個打開。這一頁把它們收在一起，**零設定**：不用給路徑、
不用 token、不用設任何外部端點。

四塊，每一塊都直接讀既有的那一份，不另存一份「儀表板的資料」：

  1. 安裝 — `adapters.mode.current_mode()`、`adapters.cli.status()`（四個 agent 的掛鉤還在不在、
     有沒有被改過）；
  2. 掛鉤活動 — `$VACANT_HOME/intake/hooks/events.jsonl`／`errors.jsonl` 的尾巴；
  3. 專案 — `trace/projects/*/state.json` ＋ 每個專案的簽章鏈（`Recorder.events()`）＋
     最後一次交件前檢查的 `delivery.{json,md}`；
  4. 任務 — `intake.ledger.report()`（只有契約／`vacant do` 才有）。

⚠ 誠實邊界：
  * 這一頁**只讀**：不寫 `$VACANT_HOME` 底下任何檔、不建金鑰、不建目錄（`tests/test_statusboard.py`
    逐位元比對前後的目錄樹）。面板與磁碟不符時以磁碟為準；簽章鏈有沒有被動過，以
    `vacant trace verify` 為準——這裡顯示的「鏈驗證」就是呼叫同一個 `Recorder.verify()`。
  * 交件說明每個專案**只留最後一次**（`zerostop._write`）；歷次退回從鏈上的 `review` 事件數。
  * 只綁 127.0.0.1，而且只回 Host 是本機的請求（擋 DNS rebinding）：頁面上有專案路徑與
    繳付物裡的值，不該讓別的網頁讀到。
  * 口徑：顯示的是「每一步有沒有根據」的檢查結果，**不是**「答案對不對」（CLAUDE.md 零設定口徑）。

紀律：純 stdlib，無外部依賴、無 CDN、無框架（同 `dashboard.py`）。
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .intake.statepaths import state_dir

DEFAULT_PORT = 7790
TAIL_BYTES = 256 * 1024          # 掛鉤紀錄只讀尾巴：長期安裝下它會一直長
HOOK_TAIL = 40
STEP_TAIL = 60
REVIEW_TAIL = 30
_KEY_RE = re.compile(r"^[0-9a-f]{16}$")


# ── 讀檔（一律容錯：一個壞檔不可以讓整頁消失）───────────────────────────────
def _read_json(p: pathlib.Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _tail_jsonl(p: pathlib.Path, n: int) -> tuple[list[dict[str, Any]], bool]:
    """最後 n 行（只讀檔尾 TAIL_BYTES）。回 (列, 是否截斷了前面)。"""
    try:
        size = p.stat().st_size
        with p.open("rb") as f:
            if size > TAIL_BYTES:
                f.seek(size - TAIL_BYTES)
            data = f.read()
    except OSError:
        return [], False
    cut = size > TAIL_BYTES
    lines = data.split(b"\n")
    if cut:
        lines = lines[1:]  # 第一行多半被切半
    out: list[dict[str, Any]] = []
    for raw in lines:
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out[-n:], cut


def _mtime_ms(p: pathlib.Path) -> int | None:
    try:
        return int(p.stat().st_mtime * 1000)
    except OSError:
        return None


# ── 1. 安裝 ─────────────────────────────────────────────────────────────
def install_status() -> dict[str, Any]:
    from .adapters import install as INS
    from .adapters.mode import budget_reminder_on, current_mode

    manifest = INS.state_root() / "install.json"
    raw = _read_json(manifest) if manifest.is_file() else None
    try:
        from .adapters.cli import status as agent_status
        agents = agent_status()
        agents_error = None
    except Exception as e:  # noqa: BLE001 — 壞掉就講，不要整頁 500
        agents, agents_error = {}, f"{type(e).__name__}: {e}"[:300]
    rows = []
    for name, s in agents.items():
        states = [c.get("state") for c in s.get("config", [])]
        if not s.get("installed"):
            health = "not_installed"
        elif states and all(x == "present" for x in states):
            health = "ok"
        else:
            health = "drift"  # 掛鉤被拿掉或被改過：Vacant 在這個 agent 上可能沒在作用
        meta = ((raw or {}).get("agents") or {}).get(name) or {}
        rows.append({"name": name, "binary": s.get("binary"), "installed": bool(s.get("installed")),
                     "health": health, "config": s.get("config", []),
                     "installed_at": meta.get("installed_at")})
    return {
        "version": __version__,
        "vacant_home": str(state_dir()),
        "manifest": str(manifest),
        "manifest_found": manifest.is_file(),
        "manifest_readable": raw is not None if manifest.is_file() else None,
        "mode": current_mode(),
        "mode_env_override": bool(os.environ.get("VACANT_MODE") or os.environ.get("VACANT_TRACE") == "0"),
        "budget_reminder": budget_reminder_on(),
        "agents": rows,
        "agents_error": agents_error,
    }


# ── 2. 掛鉤活動 ──────────────────────────────────────────────────────────
_HOOK_KEEP = ("ts", "agent", "event", "kind", "tool", "action", "zero_ran", "why", "error")


def hook_activity(n: int = HOOK_TAIL) -> dict[str, Any]:
    d = state_dir() / "intake" / "hooks"
    events, ev_cut = _tail_jsonl(d / "events.jsonl", n)
    errors, er_cut = _tail_jsonl(d / "errors.jsonl", 10)
    slim = []
    for r in events:
        row = {k: r.get(k) for k in _HOOK_KEEP if r.get(k) is not None}
        z = r.get("zero")
        if isinstance(z, dict):
            row["zero"] = {k: z[k] for k in ("ran", "round", "sent", "rounds_used", "left_open", "why")
                           if k in z}
        slim.append(row)
    return {"events": slim, "events_truncated": ev_cut,
            "last_event_ms": _mtime_ms(d / "events.jsonl"),
            "errors": [{k: r.get(k) for k in ("ts", "agent", "event", "error")} for r in errors],
            "errors_truncated": er_cut}


# ── 3. 專案 ─────────────────────────────────────────────────────────────
class _EventCache:
    """`Recorder.events()` 每次都從頭讀整條鏈；面板每幾秒輪詢一次，依 (mtime, size) 快取。"""

    def __init__(self) -> None:
        self._c: dict[str, tuple[tuple[int, int], list[dict[str, Any]]]] = {}

    def get(self, rec: Any) -> list[dict[str, Any]]:
        try:
            st = rec.chain_path.stat()
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            return []
        hit = self._c.get(str(rec.dir))
        if hit and hit[0] == sig:
            return hit[1]
        try:
            evs = rec.events()
        except Exception:  # noqa: BLE001 — 鏈壞了：列表上照實標，不 500
            evs = []
        self._c[str(rec.dir)] = (sig, evs)
        return evs


_EVENTS = _EventCache()


def _projects_dir() -> pathlib.Path:
    from .trace.recorder import trace_home
    return trace_home() / "projects"


def _recorder(key: str) -> Any | None:
    from .trace.recorder import Recorder, project_key
    if not _KEY_RE.match(key):
        return None
    st = _read_json(_projects_dir() / key / "state.json")
    if not isinstance(st, dict) or not st.get("workspace"):
        return None
    rec = Recorder(st["workspace"])
    if project_key(rec.workspace) != key:  # state.json 指到別處：不跟著走
        return None
    return rec


def _session_of(e: dict[str, Any]) -> str | None:
    if e.get("session"):
        return str(e["session"])
    a = e.get("actor") or {}
    if a.get("platform") and a.get("session"):
        return f"{a['platform']}:{a['session']}"
    return None


def _delivery_summary(d: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(d, dict):
        return None
    findings = d.get("findings") or []
    return {"at": d.get("at"), "session": d.get("session"), "mode": d.get("mode"),
            "in_progress": bool(d.get("in_progress")),
            "ended_before_delivery": bool(d.get("ended_before_delivery")),
            "broken": bool(d.get("broken")),
            "n_fixed": len(d.get("fixed") or []), "n_unverified": len(d.get("unverified") or []),
            "n_findings": len(findings) if isinstance(findings, list) else 0,
            "n_deliverables": len(d.get("deliverables") or [])}


def project_summary(key: str) -> dict[str, Any] | None:
    rec = _recorder(key)
    if rec is None:
        return None
    st = _read_json(rec.state_path) or {}
    sessions = st.get("sessions") or {}
    evs = _EVENTS.get(rec)
    reviews = [e for e in evs if e.get("type") == "review"]
    flags = [e for e in evs if e.get("type") == "flag"]
    dismissed = {str(e["dismisses"]) for e in flags if e.get("dismisses")}
    open_flags = [e for e in flags if e.get("flag_id") and not e.get("dismisses")
                  and str(e["flag_id"]) not in dismissed]
    last_ms = max((e.get("ts_ms") or 0 for e in evs), default=0) or _mtime_ms(rec.state_path)
    return {
        "key": key,
        "workspace": str(rec.workspace),
        "workspace_exists": rec.workspace.is_dir(),
        "n_sessions": len(sessions),
        "n_open_sessions": sum(1 for s in sessions.values() if isinstance(s, dict) and not s.get("closed")),
        "n_steps": int(st.get("n_steps") or sum(1 for e in evs if e.get("type") == "step")),
        "n_gaps": sum(1 for e in evs if e.get("type") == "unrecorded_change"),
        "n_checks": len(reviews),
        "n_sent_back": sum(1 for e in reviews if e.get("action") == "continue"),
        "n_ended_early": sum(1 for e in evs if e.get("type") == "ended"),
        "n_open_flags": len(open_flags),  # 簽章是否來自 owner 在明細頁用 open_flags() 判
        "scan_disabled": bool(st.get("scan_disabled")),
        "scan_disabled_reason": st.get("scan_disabled"),   # 為什麼被關（救回：`vacant trace rescan`）
        "last_activity_ms": last_ms,
        "delivery": _delivery_summary(_read_json(rec.dir / "delivery.json")),
    }


def list_projects() -> list[dict[str, Any]]:
    d = _projects_dir()
    out = []
    for p in sorted(d.glob("*/state.json")) if d.is_dir() else []:
        s = project_summary(p.parent.name)
        if s is not None:
            out.append(s)
    out.sort(key=lambda s: s.get("last_activity_ms") or 0, reverse=True)
    return out


def _say(f: dict[str, Any]) -> str:
    from .trace.zerostop import _say as say
    try:
        return say(f)
    except Exception:  # noqa: BLE001
        return str(f.get("kind"))


def _step_row(e: dict[str, Any]) -> dict[str, Any]:
    a = e.get("actor") or {}
    who = a.get("platform") or "?"
    if a.get("agent"):
        who += f" › {a.get('agent_type') or 'subagent'}"
    writes = [w.get("path") for w in (e.get("writes") or []) if isinstance(w, dict)]
    return {"seq": e.get("seq"), "ts_ms": e.get("ts_ms"), "n": e.get("n"), "who": who,
            "session": a.get("session"), "tool": e.get("tool"),
            "writes": writes[:8], "n_writes": len(writes),
            "error": bool(e.get("error")), "denied": bool(e.get("denied")),
            "writes_unknown": bool(e.get("writes_unknown"))}


def project_detail(key: str) -> dict[str, Any] | None:
    from .trace.cli import open_flags

    rec = _recorder(key)
    if rec is None:
        return None
    summary = project_summary(key) or {}
    evs = _EVENTS.get(rec)
    try:
        chain_ok, chain_why = rec.verify()
    except Exception as exc:  # noqa: BLE001
        chain_ok, chain_why = False, f"{type(exc).__name__}: {exc}"[:300]
    try:
        flags = [{"flag_id": f.get("flag_id"), "location": f.get("location"), "note": f.get("note")}
                 for f in open_flags(rec)]
    except Exception:  # noqa: BLE001
        flags = []
    checks = []
    for e in evs:
        t = e.get("type")
        if t == "review":
            checks.append({"type": "review", "ts_ms": e.get("ts_ms"), "session": e.get("session"),
                           "action": e.get("action"), "round": e.get("round"),
                           "rounds_used": e.get("rounds_used"), "mode": e.get("mode"),
                           "findings": [_say(f) for f in (e.get("findings") or [])][:12],
                           "n_findings": len(e.get("findings") or []),
                           "n_resolved": len(e.get("resolved") or []),
                           "left_open": len(e.get("left_open") or [])})
        elif t == "ended":
            checks.append({"type": "ended", "ts_ms": e.get("ts_ms"), "session": e.get("session"),
                           "turn": e.get("turn"), "budget": e.get("budget"),
                           "checked": e.get("checked"), "final_answer": e.get("final_answer"),
                           "missing": (e.get("missing") or [])[:8],
                           "findings": [_say(f) for f in (e.get("findings") or [])][:12]})
    st = _read_json(rec.state_path) or {}
    sessions = []
    for sk, s in (st.get("sessions") or {}).items():
        if not isinstance(s, dict):
            continue
        sessions.append({"session": sk, "first_seen": s.get("first_seen"),
                         "closed": bool(s.get("closed")), "model": s.get("model"),
                         "n_steps": sum(1 for e in evs if e.get("type") == "step"
                                        and _session_of(e) == sk)})
    sessions.sort(key=lambda s: s.get("first_seen") or 0, reverse=True)
    try:
        note = (rec.dir / "delivery.md").read_text(encoding="utf-8")
    except OSError:
        note = None
    steps = [_step_row(e) for e in evs if e.get("type") == "step"]
    return {**summary,
            "chain_ok": chain_ok, "chain_note": chain_why,
            "sessions": sessions,
            "steps": steps[-STEP_TAIL:], "n_steps_shown": min(len(steps), STEP_TAIL),
            "checks": checks[-REVIEW_TAIL:],
            "gaps": [{"seq": e.get("seq"), "ts_ms": e.get("ts_ms"),
                      "paths": [c.get("path") for c in (e.get("changes") or []) if isinstance(c, dict)][:8]}
                     for e in evs if e.get("type") == "unrecorded_change"][-10:],
            "flags": flags,
            "delivery_md": note}


# ── 4. 任務帳本 ──────────────────────────────────────────────────────────
def tasks() -> dict[str, Any]:
    from .intake.ledger import ledger_dir, report
    if not ledger_dir().is_dir():
        return {"n_tasks": 0, "tasks": [], "by_state": {}}
    try:
        r = report()
    except Exception as e:  # noqa: BLE001
        return {"n_tasks": 0, "tasks": [], "by_state": {}, "error": f"{type(e).__name__}: {e}"[:300]}
    keep = ("task_id", "state", "attempts", "decisions", "void", "latest_outcome", "destination_live")
    return {"n_tasks": r.get("n_tasks", 0), "by_state": {k: v for k, v in (r.get("by_state") or {}).items() if v},
            "tasks": [{k: t.get(k) for k in keep} for t in r.get("tasks", [])][-50:],
            "note": r.get("note")}


def overview() -> dict[str, Any]:
    return {"generated_ms": int(time.time() * 1000), "install": install_status(),
            "hooks": hook_activity(), "projects": list_projects(), "tasks": tasks()}


# ── HTTP ────────────────────────────────────────────────────────────────
#: `GET /api` 的索引：只列**真的存在**的端點。
#: （2026-10-24 dogfood：裸 404 沒法看；舊 backlog 指過的 `/api/snapshot` 是舊
#: dashboard.py 的端點、本面板沒有——不指向不存在的端點。）
_API_INDEX = {
    "endpoints": {
        "/": "HTML 儀表板（總覽＋專案詳情）",
        "/api/overview": "總覽 JSON（projects[].key 供 /api/project/<key> 用）",
        "/api/project/<key>": "單個專案詳情 JSON（chain/flags/帳本…）",
    },
    "note": "read-only；數字是讀取時刻的快照——live session 持續寫鏈，前後讀取不同是正常的",
}


class _Handler(BaseHTTPRequestHandler):
    server_version = "vacant-dashboard"

    def log_message(self, *_a: Any) -> None:
        pass

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if ctype.startswith("text/html"):
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'; "
                             "style-src 'unsafe-inline'; connect-src 'self'; img-src data:")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, status: int = 200) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
        return name in ("127.0.0.1", "localhost", "[::1]")

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._json({"error": "only served to localhost"}, 403)
            return
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                self._send(200, _PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/overview":
                self._json(overview())
            elif path in ("/api", "/api/"):
                self._json(_API_INDEX)
            elif path.startswith("/api/project/"):
                d = project_detail(path[len("/api/project/"):])
                if d is None:
                    self._json({"error": "no such project"}, 404)
                else:
                    self._json(d)
            elif path.startswith("/api/"):
                self._json({"error": "not found", "endpoints": _API_INDEX["endpoints"]}, 404)
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001 — 面板不該因為一個壞檔掛掉
            self._json({"error": f"{type(e).__name__}: {e}"[:300]}, 500)

    def do_POST(self) -> None:  # noqa: N802
        self._json({"error": "read-only"}, 405)

    do_PUT = do_DELETE = do_PATCH = do_POST


def make_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """只綁 127.0.0.1。port=0 ⇒ 系統挑（測試用）。"""
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    srv.daemon_threads = True
    return srv


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    import webbrowser

    ap = argparse.ArgumentParser(prog="vacant dashboard",
                                 description="在本機看 Vacant 的每一個狀態（只讀；只開在 127.0.0.1）")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"埠（預設 {DEFAULT_PORT}）")
    ap.add_argument("--open", action="store_true", help="啟動後用瀏覽器打開")
    ap.add_argument("--json", action="store_true", help="不起伺服器，印一次總覽 JSON 就結束")
    args = ap.parse_args(argv)
    if args.json:
        print(json.dumps(overview(), ensure_ascii=False, indent=2, default=str))
        return 0
    try:
        srv = make_server(args.port)
    except OSError as e:
        print(f"[vacant] cannot listen on 127.0.0.1:{args.port} ({e}); "
              f"try another: vacant dashboard --port <port>", file=sys.stderr)
        return 2
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    print(f"[vacant] dashboard → {url}   (read-only, this machine only; Ctrl-C to stop)")
    if args.open:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


# ── 單頁 ─────────────────────────────────────────────────────────────────
_PAGE = r"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vacant 儀表板</title>
<style>
:root{--bg:#f6f7f9;--panel:#fff;--ink:#16181d;--muted:#5d6472;--line:#e3e6eb;
  --ok:#1f8a5b;--warn:#a86a00;--bad:#c2334d;--accent:#2f6fd6;--chip:#eef1f5;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1115;--panel:#171a21;
  --ink:#e6e8ee;--muted:#9aa1b0;--line:#262b36;--ok:#3ecf8e;--warn:#f0b429;--bad:#ff5470;
  --accent:#6ea8fe;--chip:#20242e;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 system-ui,-apple-system,"Segoe UI","Noto Sans TC",sans-serif}
header{padding:16px 20px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
header h1{font-size:17px;margin:0}
.muted{color:var(--muted)} .small{font-size:12px}
main{max-width:1100px;margin:0 auto;padding:16px}
section{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px;min-width:0}
h2{font-size:15px;margin:0 0 10px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{background:var(--chip);border-radius:8px;padding:10px 12px}
.kpi .v{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}
.kpi .l{font-size:12px;color:var(--muted)}
.chip{display:inline-block;padding:1px 8px;border-radius:999px;background:var(--chip);font-size:12px;white-space:nowrap}
.ok{color:var(--ok)} .warn{color:var(--warn)} .bad{color:var(--bad)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--muted);font-size:12px}
.scroll{overflow-x:auto}
.nw{word-break:normal;white-space:nowrap}
tr.click{cursor:pointer} tr.click:hover{background:var(--chip)}
code,.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;word-break:break-all}
pre{white-space:pre-wrap;word-break:break-word;background:var(--chip);padding:10px;border-radius:8px;font-size:12px;max-height:360px;overflow:auto}
button{font:inherit;background:var(--chip);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:3px 10px;cursor:pointer}
.empty{color:var(--muted);padding:6px 0}
ul.f{margin:4px 0 0 18px;padding:0}
</style></head><body>
<header><h1>Vacant 儀表板</h1><span id="hdr" class="muted small"></span>
<span class="muted small" style="margin-left:auto">只讀 · 只在本機 · 每 3 秒更新 · 數字是讀取時刻的快照</span></header>
<main>
<section id="sec-install"><h2>安裝</h2><div id="install" class="empty">讀取中…</div></section>
<section id="sec-projects"><h2>專案（agent 在這些資料夾裡做事時，Vacant 有記錄）</h2><div id="projects" class="empty">讀取中…</div></section>
<section id="sec-detail" hidden><h2 id="dtitle">專案明細</h2><div id="detail"></div></section>
<section id="sec-hooks"><h2>最近的掛鉤活動</h2><div id="hooks" class="empty">讀取中…</div></section>
<section id="sec-tasks"><h2>任務帳本（有契約或用 <code>vacant do</code> 時才有）</h2><div id="tasks" class="empty">讀取中…</div></section>
<p class="muted small">這一頁顯示的是 Vacant 對「每一步有沒有根據」的檢查，不判斷答案對錯。面板與磁碟不符時以磁碟為準；
簽章鏈以 <code>vacant trace verify</code> 為準。</p>
</main>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ago=ms=>{if(!ms)return'—';const s=(Date.now()-ms)/1000;if(s<60)return Math.max(0,Math.round(s))+' 秒前';
  if(s<3600)return Math.round(s/60)+' 分鐘前';if(s<86400)return Math.round(s/3600)+' 小時前';return Math.round(s/86400)+' 天前'};
const tsS=t=>t?ago(t*1000):'—';
const MODE={evidence:['開啟（交件前檢查）','ok'],observe:['只記錄、不退回','warn'],off:['關閉','bad']};
const HEALTH={ok:['掛鉤正常','ok'],drift:['掛鉤被移除或改過','bad'],not_installed:['沒裝','muted']};
const ACT={allow:'放行',continue:'退回',deny:'擋下',block:'擋下',ask:'問人'};
const STATE={present:'在',missing:'不見了',modified:'被改過',unreadable:'讀不到'};
let SEL=null;
function kpi(v,l,cls){return `<div class="kpi"><div class="v ${cls||''}">${esc(v)}</div><div class="l">${esc(l)}</div></div>`}
function renderInstall(i){
  const m=MODE[i.mode]||[i.mode,''];
  const inst=i.agents.filter(a=>a.installed), bad=inst.filter(a=>a.health!=='ok');
  let h=`<div class="grid">${kpi(m[0],'Vacant 模式'+(i.mode_env_override?'（環境變數覆寫）':''),m[1])}
   ${kpi(inst.length+' / '+i.agents.length,'已接上的 agent', inst.length?'':'warn')}
   ${kpi(!inst.length?'—':bad.length?bad.length+' 個有問題':'都正常','掛鉤狀態', !inst.length?'warn':bad.length?'bad':'ok')}
   ${kpi('v'+i.version,'版本')}</div>`;
  if(!i.manifest_found) h+=`<p class="warn">還沒安裝：執行 <code>vacant install</code>，然後照常打開你用的 agent。</p>`;
  else if(i.manifest_readable===false) h+=`<p class="bad">install.json 讀不到（<code>${esc(i.manifest)}</code>）。</p>`;
  if(i.agents_error) h+=`<p class="bad">讀 agent 狀態失敗：${esc(i.agents_error)}</p>`;
  h+=`<div class="scroll"><table><tr><th>agent</th><th>找到程式</th><th>狀態</th><th>設定檔</th><th>安裝時間</th></tr>`;
  for(const a of i.agents){const hh=HEALTH[a.health]||[a.health,''];
    h+=`<tr><td><b>${esc(a.name)}</b></td><td>${a.binary?'<span class="ok">是</span>':'<span class="muted">否</span>'}</td>
    <td class="${hh[1]}">${esc(hh[0])}</td><td>${a.config.map(c=>`<div class="mono">${esc(c.path)} <span class="chip ${c.state==='present'?'ok':'bad'}">${esc(STATE[c.state]||c.state)}</span></div>`).join('')||'<span class="muted">—</span>'}</td>
    <td class="small muted">${esc(a.installed_at||'—')}</td></tr>`}
  h+=`</table></div><p class="muted small">狀態目錄：<code>${esc(i.vacant_home)}</code>${i.budget_reminder?' · 回合預算提醒：開':''}</p>`;
  $('install').className='';$('install').innerHTML=h;
}
function deliv(d){
  if(!d)return'<span class="muted">還沒檢查過</span>';
  if(d.broken)return'<span class="bad">紀錄壞掉、已擱到旁邊</span>';
  if(d.ended_before_delivery)return'<span class="warn">沒說做完就結束</span>';
  if(d.in_progress)return'<span class="warn">退回重做中</span>';
  const p=[];if(d.n_fixed)p.push(`改好 ${d.n_fixed}`);if(d.n_unverified)p.push(`未驗證 ${d.n_unverified}`);
  const head=d.n_findings?'交件（有 '+d.n_findings+' 項沒解決）':d.n_fixed?'交件（退回後改好）':'交件，沒找到問題';
  return `<span class="${d.n_findings?'warn':'ok'}">${head}</span>${p.length?' <span class="muted small">'+p.join(' · ')+'</span>':''}`;
}
function renderProjects(ps){
  if(!ps.length){$('projects').className='empty';$('projects').innerHTML='還沒有紀錄。裝好之後在一個專案資料夾（git repo）裡照常用 agent，這裡就會出現。';return}
  let h=`<div class="scroll"><table><tr><th>專案</th><th>工作階段</th><th>步驟</th><th>檢查／退回</th><th>最後一次交件前檢查</th><th>最後活動</th></tr>`;
  for(const p of ps){h+=`<tr class="click" data-k="${esc(p.key)}"><td><b>${esc(p.workspace.split(/[\\/]/).filter(Boolean).pop()||p.workspace)}</b><div class="mono small muted">${esc(p.workspace)}</div>${p.workspace_exists?'':'<span class="chip muted">資料夾已不在</span>'}${p.n_open_flags?` <span class="chip bad">人的標記 ${p.n_open_flags}</span>`:''}${p.n_gaps?` <span class="chip warn">沒記到的改動 ${p.n_gaps}</span>`:''}</td>
   <td>${p.n_sessions}${p.n_open_sessions?` <span class="muted small">（進行中 ${p.n_open_sessions}）</span>`:''}</td>
   <td>${p.n_steps}</td><td>${p.n_checks} / <span class="${p.n_sent_back?'warn':''}">${p.n_sent_back}</span></td>
   <td>${deliv(p.delivery)}</td><td class="small muted">${ago(p.last_activity_ms)}</td></tr>`}
  h+='</table></div><p class="muted small">點一列看明細。</p>';
  $('projects').className='';$('projects').innerHTML=h;
  for(const tr of $('projects').querySelectorAll('tr.click')) tr.onclick=()=>openProject(tr.dataset.k);
}
function renderHooks(hk){
  const ev=hk.events.slice().reverse();
  let h='';
  if(hk.errors.length) h+=`<p class="bad small">掛鉤錯誤 ${hk.errors.length} 筆（最近：${esc(hk.errors[hk.errors.length-1].error||'')}）</p>`;
  if(!ev.length){h+='<div class="empty">還沒有掛鉤被觸發。</div>';$('hooks').className='';$('hooks').innerHTML=h;return}
  h+=`<div class="scroll"><table><tr><th>時間</th><th>agent</th><th>事件</th><th>工具</th><th>結果</th></tr>`;
  for(const e of ev){let r=ACT[e.action]||e.action||'';const z=e.zero;
    if(z&&z.ran===false)r+=` <span class="muted small">沒檢查（${esc(z.why||'')}）</span>`;
    else if(z&&z.sent!=null)r+=` <span class="warn small">第 ${esc(z.round)} 輪</span>`;
    else if(z&&z.ran)r+=` <span class="ok small">檢查過</span>`;
    h+=`<tr><td class="small muted">${tsS(e.ts)}</td><td>${esc(e.agent)}</td><td>${esc(e.event)}</td><td class="mono nw">${esc(e.tool||'')}</td><td class="${e.action==='continue'?'warn':''}">${r}</td></tr>`}
  h+='</table></div>';
  $('hooks').className='';$('hooks').innerHTML=h;
}
function renderTasks(t){
  if(t.error){$('tasks').innerHTML=`<p class="bad">${esc(t.error)}</p>`;return}
  if(!t.n_tasks){$('tasks').className='empty';$('tasks').innerHTML='沒有任務（零設定的日常使用不會產生任務）。';return}
  let h=`<p>${Object.entries(t.by_state).map(([k,v])=>`<span class="chip">${esc(k)} ${v}</span>`).join(' ')} <span class="muted small">共 ${t.n_tasks}</span></p>
  <div class="scroll"><table><tr><th>任務</th><th>狀態</th><th>嘗試</th><th>作廢</th><th>最後結果</th></tr>`;
  for(const r of t.tasks.slice().reverse())h+=`<tr><td class="mono">${esc(r.task_id)}</td><td>${esc(r.state)}</td><td>${esc(r.attempts)}</td><td>${esc(r.void)}</td><td>${esc(r.latest_outcome??'')}</td></tr>`;
  $('tasks').className='';$('tasks').innerHTML=h+'</table></div>';
}
async function openProject(k){SEL=k;$('sec-detail').hidden=false;await refreshDetail();$('sec-detail').scrollIntoView({behavior:'smooth'})}
async function refreshDetail(){
  if(!SEL)return;
  let d;try{const r=await fetch('/api/project/'+SEL);d=await r.json();if(!r.ok)throw new Error(d.error)}catch(e){$('detail').innerHTML=`<p class="bad">${esc(e.message)}</p>`;return}
  $('dtitle').textContent='專案明細';
  let h=`<p class="mono">${esc(d.workspace)}</p><p>簽章鏈：${d.chain_ok?'<span class="ok">驗證通過</span>':`<span class="bad">沒通過</span> <span class="small muted">${esc(d.chain_note)}</span>`}
   <button style="float:right" onclick="SEL=null;document.getElementById('sec-detail').hidden=true">關閉</button></p>`;
  if(d.flags.length){h+='<h2>人的標記（還沒撤銷）</h2><ul class="f">'+d.flags.map(f=>`<li>${esc((f.location||{}).path||'')} ${esc(f.note||'')}</li>`).join('')+'</ul>'}
  h+='<h2>交件前檢查（歷次）</h2>';
  if(!d.checks.length)h+='<div class="empty">還沒有檢查。agent 說做完的時候才會檢查。</div>';
  else{h+='<div class="scroll"><table><tr><th>時間</th><th>工作階段</th><th>結果</th><th>內容</th></tr>';
   for(const c of d.checks.slice().reverse()){let res,cls;
    if(c.type==='ended'){res=c.checked?'結束後補查':'沒說做完就結束';cls='warn'}
    else if(c.action==='continue'){res='退回（第 '+(c.round??'?')+' 輪）';cls='warn'}
    else{res=c.left_open?'放行（'+c.left_open+' 項寫進交件說明）':'放行';cls=c.left_open?'warn':'ok'}
    h+=`<tr><td class="small muted">${ago(c.ts_ms)}</td><td class="mono">${esc(c.session||'')}</td><td class="${cls}">${res}</td>
     <td>${c.findings&&c.findings.length?'<ul class="f">'+c.findings.map(x=>`<li>${esc(x)}</li>`).join('')+'</ul>':'<span class="muted">—</span>'}${c.missing&&c.missing.length?'<div class="small">缺：'+c.missing.map(esc).join(', ')+'</div>':''}</td></tr>`}
   h+='</table></div>'}
  if(d.delivery_md)h+=`<h2>最後一次的交件說明</h2><pre>${esc(d.delivery_md)}</pre>`;
  h+=`<h2>工作階段</h2>`+(d.sessions.length?'<div class="scroll"><table><tr><th>工作階段</th><th>步驟</th><th>狀態</th><th>開始</th></tr>'+d.sessions.map(s=>`<tr><td class="mono">${esc(s.session)}</td><td>${s.n_steps}</td><td>${s.closed?'結束':'<span class="ok">進行中</span>'}</td><td class="small muted">${tsS(s.first_seen)}</td></tr>`).join('')+'</table></div>':'<div class="empty">—</div>');
  h+=`<h2>最近的步驟 <span class="muted small">（最後 ${d.n_steps_shown} 步，共 ${d.n_steps}）</span></h2>`;
  if(!d.steps.length)h+='<div class="empty">—</div>';
  else{h+='<div class="scroll"><table><tr><th>#</th><th>時間</th><th>誰</th><th>工具</th><th>寫了</th></tr>';
   for(const s of d.steps.slice().reverse())h+=`<tr><td>${esc(s.n??s.seq)}</td><td class="small muted">${ago(s.ts_ms)}</td><td>${esc(s.who)}</td><td class="mono nw">${esc(s.tool)}${s.error?' <span class="chip bad">失敗</span>':''}${s.denied?' <span class="chip warn">被拒</span>':''}</td><td class="mono">${s.writes.map(esc).join('<br>')}${s.n_writes>s.writes.length?' …':''}${s.writes_unknown?'<span class="muted">（不確定）</span>':''}</td></tr>`;
   h+='</table></div>'}
  if(d.gaps.length)h+='<h2>沒被任何一步解釋的改動</h2><p class="muted small">這是紀錄的缺口，不歸給任何人。</p><ul class="f">'+d.gaps.map(g=>`<li class="mono">${g.paths.map(esc).join(', ')||'—'} <span class="muted">${ago(g.ts_ms)}</span></li>`).join('')+'</ul>';
  $('detail').innerHTML=h;
}
async function tick(){
  try{const r=await fetch('/api/overview');const o=await r.json();
   $('hdr').textContent='v'+o.install.version+' · 更新於 '+new Date(o.generated_ms).toLocaleTimeString();
   renderInstall(o.install);renderProjects(o.projects);renderHooks(o.hooks);renderTasks(o.tasks);
   if(SEL)refreshDetail();
  }catch(e){$('hdr').textContent='連不到（vacant dashboard 還在跑嗎？）'}
}
tick();setInterval(()=>{if(!document.hidden)tick()},3000);
</script></body></html>
"""
