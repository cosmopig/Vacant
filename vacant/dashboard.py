"""dashboard — localhost 單頁觀測台（12 §4.3；承重「讓信任基建可被人眼即時稽核」）。

信任是「之間那條線」上的東西：路由給誰、誰審過、稽核過沒、有沒有被 slash——
這些都在 ledger 事件流裡。本檔把事件流開一扇窗給人看，讓「可究責」不只是 JSON，
而是能盯著看的活面板（信用曲線、路由流、SLASH 紅色跳出、on/off 對照）。

⚠️ 誠實邊界：本檔只是「觀測」，不是「信任來源」。面板好看不代表系統可信；
真正的可信性來自 ledger 的簽章鏈與 chain_ok，面板若與 ledger 不符，以 ledger 為準。
面板一律顯示 flags（PROBATION／INSUFFICIENT_DATA）與 chain_ok 的真實面，不美化。

紀律：純 stdlib（http.server / json / time），無任何外部依賴、無 CDN、無框架。
不 import ecosystem（避免循環）；名冊與計分板由建構時注入的 callable 取得。
"""

from __future__ import annotations

import hashlib
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

_POLL_S = 0.5  # SSE 輪詢新行的節奏

_LEDGER_GENESIS = "0" * 64  # ledger head 滾動雜湊的創世值


def ledger_head(ledger_path: Path) -> tuple[int, str]:
    """重算 ledger 的 (事件數, 滾動 head 雜湊)——/api/snapshot 的唯一真相來源。

    head = sha256(head_prev + 該行原文) 逐行滾動（創世 64 個 '0'）：與 logbook
    的 hash-chain 同構，任何一行被竄改/重排/刪除都會改變 head。這是「面板快照
    可被事後對帳」的錨：快照時刻的 ledger_seq 與 head 落盤後，事後重算不符
    即知 ledger 動過——**面板不是信任來源，以 ledger 為準**（本檔 docstring）。
    """
    head = _LEDGER_GENESIS
    seq = 0
    if ledger_path.exists():
        with ledger_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                head = hashlib.sha256((head + line).encode("utf-8")).hexdigest()
                seq += 1
    return seq, head


def build_snapshot(ledger_path: Path, roster_fn: Callable[[], Any],
                   scoreboard_fn: Callable[[], Any]) -> dict[str, Any]:
    """GET /api/snapshot 的 payload（17 §P0-3）：{roster, scoreboard, ts_ms,
    ledger_seq, ledger_head_hash}。給外部監看一個可對帳的唯讀切面。"""
    seq, head = ledger_head(ledger_path)
    return {
        "roster": roster_fn(),
        "scoreboard": scoreboard_fn(),
        "ts_ms": time.time_ns() // 1_000_000,
        "ledger_seq": seq,
        "ledger_head_hash": head,
    }


# --- 內嵌單頁（無框架 / 無 CDN；居民卡片＋信用曲線＋路由流＋SLASH＋on/off）------
_PAGE = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vacant — 信任觀測台</title>
<style>
  :root { color-scheme: light dark; --bg:#0f1115; --panel:#171a21; --ink:#e6e8ee;
          --muted:#9aa1b0; --line:#262b36; --ok:#3ecf8e; --warn:#f0b429; --bad:#ff5470;
          --accent:#6ea8fe; }
  * { box-sizing: border-box; }
  body { margin:0; font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
         background:var(--bg); color:var(--ink); }
  header { padding:16px 20px; border-bottom:1px solid var(--line);
           display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }
  header h1 { font-size:16px; margin:0; }
  #status { color:var(--muted); font-size:12px; }
  .wrap { display:grid; grid-template-columns:1fr 1fr; gap:16px; padding:16px 20px; }
  @media (max-width:820px){ .wrap{ grid-template-columns:1fr; } }
  section { background:var(--panel); border:1px solid var(--line); border-radius:10px;
            padding:14px; min-width:0; }
  section h2 { font-size:12px; letter-spacing:.06em; text-transform:uppercase;
               color:var(--muted); margin:0 0 10px; }
  .cards { display:flex; flex-direction:column; gap:8px; }
  .card { border:1px solid var(--line); border-radius:8px; padding:10px 12px;
          display:flex; justify-content:space-between; gap:10px; align-items:center; }
  .card .who { font-weight:600; }
  .card .meta { color:var(--muted); font-size:12px; }
  .pill { font-size:11px; padding:1px 7px; border-radius:999px; border:1px solid var(--line); }
  .pill.ok { color:var(--ok); border-color:var(--ok); }
  .pill.bad { color:var(--bad); border-color:var(--bad); }
  .pill.warn { color:var(--warn); border-color:var(--warn); }
  #routes { list-style:none; margin:0; padding:0; max-height:260px; overflow:auto;
            font-variant-numeric:tabular-nums; }
  #routes li { padding:5px 0; border-bottom:1px solid var(--line); font-size:13px;
               display:flex; gap:8px; }
  #routes .t { color:var(--muted); }
  .sb { display:flex; gap:20px; }
  .sb .col { flex:1; }
  .sb .big { font-size:26px; font-weight:700; font-variant-numeric:tabular-nums; }
  .sb .lbl { color:var(--muted); font-size:12px; }
  #delta { font-size:13px; margin-top:8px; }
  canvas { width:100%; height:120px; display:block; background:#0c0e13;
           border:1px solid var(--line); border-radius:8px; }
  #slash { position:fixed; right:16px; bottom:16px; display:flex; flex-direction:column;
           gap:8px; z-index:9; }
  .flash { background:var(--bad); color:#12060a; font-weight:700; padding:10px 14px;
           border-radius:8px; box-shadow:0 6px 24px rgba(255,84,112,.4);
           animation:pop .35s ease; }
  @keyframes pop { from{ transform:scale(.85); opacity:0 } to{ transform:scale(1); opacity:1 } }
</style></head>
<body>
<header>
  <h1>Vacant · 信任觀測台</h1>
  <span id="trust"></span>
  <span id="status">連線中…</span>
</header>
<div class="wrap">
  <section><h2>居民</h2><div id="cards" class="cards"></div></section>
  <section><h2>信用曲線（REVIEW weight 累計）</h2><canvas id="spark" width="600" height="120"></canvas></section>
  <section><h2>路由流（最近 ROUTE）</h2><ul id="routes"></ul></section>
  <section><h2>計分板 on / off</h2>
    <div class="sb">
      <div class="col"><div class="lbl">trust ON pass率</div><div id="on" class="big">–</div></div>
      <div class="col"><div class="lbl">trust OFF pass率</div><div id="off" class="big">–</div></div>
    </div>
    <div id="delta" class="lbl"></div>
  </section>
</div>
<div id="slash"></div>
<script>
const $ = s => document.querySelector(s);
function pct(o){ return o && o.n ? (100*o.pass/o.n).toFixed(0)+'%' : '–'; }

async function refresh(){
  try {
    const [r, s] = await Promise.all([
      fetch('/api/roster').then(x=>x.json()),
      fetch('/api/scoreboard').then(x=>x.json())
    ]);
    renderRoster(r);
    $('#on').textContent = pct(s.on); $('#off').textContent = pct(s.off);
    $('#delta').textContent = (s.paired_delta==null) ? '配對差：資料不足'
      : '配對差 Δ = ' + s.paired_delta + '（on − off，正值＝信任層有增益）';
  } catch(e){ /* 面板容錯：抓不到就下輪再抓 */ }
}
function renderRoster(rows){
  const box = $('#cards'); box.innerHTML='';
  rows.forEach(r=>{
    const flags = (r.flags||[]).map(f=>`<span class="pill warn">${f}</span>`).join(' ');
    const chain = r.chain_ok ? '<span class="pill ok">chain ok</span>'
                             : '<span class="pill bad">chain ✗</span>';
    const el = document.createElement('div'); el.className='card';
    el.innerHTML = `<div><div class="who">${r.name} <span class="meta">·${r.tier}</span></div>
      <div class="meta">信用 ${r.credit} · ${r.n_obs} obs · 交付 ${r.deliveries}</div></div>
      <div style="text-align:right">${chain} ${flags}</div>`;
    box.appendChild(el);
  });
}

// 信用曲線：把每筆 REVIEW 的 weight 依序累計成一條 sparkline
const series = [];
function drawSpark(){
  const c = $('#spark'), ctx = c.getContext('2d');
  const W=c.width, H=c.height; ctx.clearRect(0,0,W,H);
  if(series.length<2){ return; }
  const mn=Math.min(...series), mx=Math.max(...series), rng=(mx-mn)||1;
  ctx.strokeStyle='#6ea8fe'; ctx.lineWidth=2; ctx.beginPath();
  series.forEach((v,i)=>{
    const x = i/(series.length-1)*(W-8)+4;
    const y = H-6 - (v-mn)/rng*(H-14);
    i? ctx.lineTo(x,y) : ctx.moveTo(x,y);
  });
  ctx.stroke();
}

const routes = $('#routes');
function onEvent(ev){
  let d; try { d = JSON.parse(ev.data); } catch(_) { return; }
  if(d.type==='ROUTE'){
    const li=document.createElement('li');
    const t = new Date(d.ts_ms||Date.now()).toLocaleTimeString();
    li.innerHTML = `<span class="t">${t}</span><span>→ ${d.to} <span class="meta">(${d.mode}·${d.tier})</span></span>`;
    routes.insertBefore(li, routes.firstChild);
    while(routes.children.length>40) routes.removeChild(routes.lastChild);
  } else if(d.type==='REVIEW'){
    let acc = series.length ? series[series.length-1] : 0;
    acc += (typeof d.weight==='number' ? d.weight : 0);
    series.push(acc); if(series.length>400) series.shift();
    drawSpark();
    refresh();
  } else if(d.type==='SLASH'){
    const f=document.createElement('div'); f.className='flash';
    f.textContent='⚡ SLASH · '+(d.target||'?')+' — '+(d.reason||'');
    $('#slash').appendChild(f);
    setTimeout(()=>f.remove(), 6000);
    refresh();
  } else if(d.type==='DELIVERED' || d.type==='HUMAN_REPORT' || d.type==='WIPE'){
    refresh();
  }
}

const es = new EventSource('/events');
es.onopen = ()=>{ $('#status').textContent='● 已連線 (SSE)'; };
es.onerror = ()=>{ $('#status').textContent='○ 連線中斷，重試中…'; };
es.onmessage = onEvent;
refresh();
</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    # server 上掛的注入點：由 make_dashboard 設定
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a: Any) -> None:  # 靜音，避免污染 stdout（測試/常駐皆然）
        pass

    # -- 便利：拿到 make_dashboard 注入的依賴 --------------------------------
    @property
    def _ctx(self) -> "_Ctx":
        return self.server._vacant_ctx  # type: ignore[attr-defined]

    def _send_json(self, obj: Any) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib 介面命名)
        path = self.path.split("?", 1)[0]
        try:
            if path == "/":
                self._send_html(_PAGE)
            elif path == "/api/roster":
                self._send_json(self._ctx.roster_fn())
            elif path == "/api/scoreboard":
                self._send_json(self._ctx.scoreboard_fn())
            elif path == "/api/snapshot":
                self._send_json(build_snapshot(
                    self._ctx.ledger_path, self._ctx.roster_fn, self._ctx.scoreboard_fn))
            elif path == "/events":
                self._stream_events()
            else:
                self.send_error(404, "not found")
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客戶端斷線（SSE 常見）——安靜收工

    # -- SSE：先重放既有行，再輪詢新行 --------------------------------------
    def _stream_events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(b": connected\n\n")
        self.wfile.flush()

        ledger: Path = self._ctx.ledger_path
        pos = 0
        srv = self.server
        idle = 0
        while getattr(srv, "_vacant_running", True):
            if ledger.exists():
                with ledger.open("r", encoding="utf-8") as f:
                    f.seek(pos)
                    for line in f:
                        line = line.rstrip("\n")
                        if not line:
                            continue
                        # 一律走預設 message 事件；type 由 body JSON 內帶（前端解析）
                        self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                    new_pos = f.tell()
                if new_pos != pos:
                    idle = 0
                pos = new_pos
                self.wfile.flush()
            # 無新事件時定期送 SSE 註解 keepalive：讓斷線的客戶端在下一次寫入
            # 觸發 BrokenPipe → 執行緒收工（否則 handler 對死連線永遠空轉）。
            idle += 1
            if idle * _POLL_S >= 10.0:
                idle = 0
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
            time.sleep(_POLL_S)


class _Ctx:
    """注入給 handler 的執行脈絡（避免用全域）。"""

    def __init__(self, ledger_path: Path, roster_fn: Callable[[], Any],
                 scoreboard_fn: Callable[[], Any]) -> None:
        self.ledger_path = ledger_path
        self.roster_fn = roster_fn
        self.scoreboard_fn = scoreboard_fn


def make_dashboard(
    root: Path,
    roster_fn: Callable[[], Any],
    scoreboard_fn: Callable[[], Any],
    port: int = 7777,
) -> ThreadingHTTPServer:
    """組出 dashboard server（呼叫端自行 serve_forever / shutdown）。

    root：生態根（讀 root/ledger/events.jsonl 當 SSE 源）。
    roster_fn / scoreboard_fn：注入的取數 callable（不 import ecosystem，斷循環）。
    port=0 → 隨機埠（測試用；真埠見 server.server_address[1]）。
    """
    ledger_path = Path(root) / "ledger" / "events.jsonl"
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    server.daemon_threads = True  # shutdown 時不被掛住的 SSE 執行緒卡死
    server._vacant_ctx = _Ctx(ledger_path, roster_fn, scoreboard_fn)  # type: ignore[attr-defined]
    server._vacant_running = True  # type: ignore[attr-defined]

    # 包住 shutdown：先掀旗讓 SSE 迴圈自然收工，再走原本流程
    _orig_shutdown = server.shutdown

    def _shutdown() -> None:
        server._vacant_running = False  # type: ignore[attr-defined]
        _orig_shutdown()

    server.shutdown = _shutdown  # type: ignore[assignment]
    return server
