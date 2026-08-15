#!/usr/bin/env python3
"""產生外網可看的進度頁。

給人在手機上看的：現在在做什麼、每一輪做了什麼、有沒有留下 commit。
刻意把「有沒有 commit」放在最顯眼的位置——那是唯一能證明一輪真的做了事的東西，
其他欄位都是自述。
"""
import html
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path.home() / "vacant"
LOGS = ROOT / "logs"
OUT = ROOT / "public" / "index.html"
REPOS = ["Vacant", "vacant_hm", "vacant-docs-web"]


def sh(cmd, cwd=None):
    try:
        return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True,
                              text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def read(p, default=""):
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return default


def iterations():
    """每一輪的摘要：編號、時間、大小、有沒有留下東西。"""
    out = []
    for f in sorted(LOGS.glob("iter-*.log"), reverse=True)[:40]:
        m = re.search(r"iter-(\d+)", f.name)
        st = f.stat()
        out.append({
            "n": int(m.group(1)) if m else 0,
            "when": time.strftime("%m-%d %H:%M", time.localtime(st.st_mtime)),
            "size": st.st_size,
            "tail": read(f)[-1400:],
        })
    return out


def commits():
    rows = []
    for r in REPOS:
        d = ROOT / r
        if not (d / ".git").exists():
            continue
        raw = sh('git log -8 --pretty=format:"%h\x1f%ad\x1f%s" --date=format:"%m-%d %H:%M"', cwd=d)
        for line in raw.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 3:
                rows.append((r, *parts))
    rows.sort(key=lambda x: x[2], reverse=True)
    return rows[:20]


def unpushed():
    out = []
    for r in REPOS:
        d = ROOT / r
        if not (d / ".git").exists():
            continue
        n = sh("git rev-list --count @{u}..HEAD 2>/dev/null", cwd=d) or "0"
        br = sh("git branch --show-current", cwd=d)
        if n.isdigit() and int(n) > 0:
            out.append((r, br, int(n)))
    return out


def running():
    return bool(sh("pgrep -f 'loop.sh' | head -1"))


def md_light(text, limit=6000):
    """極簡 markdown：標題、粗體、程式碼、清單。不引入相依。"""
    t = html.escape(text[:limit])
    t = re.sub(r"^### (.+)$", r"<h4>\1</h4>", t, flags=re.M)
    t = re.sub(r"^## (.+)$", r"<h3>\1</h3>", t, flags=re.M)
    t = re.sub(r"^# (.+)$", r"<h2>\1</h2>", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"^- (.+)$", r"• \1", t, flags=re.M)
    return t


def build():
    state = read(ROOT / "STATE.md", "（還沒有 STATE.md——第一輪還沒跑完）")
    prog = read(ROOT / "PROGRESS.md", "（還沒有 PROGRESS.md）")
    its = iterations()
    cms = commits()
    unp = unpushed()
    live = running()
    stopped = (ROOT / "STOP").exists()
    up = sh("uptime -p") or ""
    disk = sh("df -h / | tail -1 | awk '{print $4\" 可用 / \"$5\" 已用\"}'")
    loop_tail = read(LOGS / "loop.log")[-3000:]

    if stopped:
        status, scls = "已停止（STOP 檔存在）", "bad"
    elif live:
        status, scls = "運作中", "good"
    else:
        status, scls = "沒有在跑", "bad"

    it_html = "".join(
        f'<details><summary><b>第 {i["n"]} 輪</b>'
        f'<span class="dim"> · {i["when"]} · {i["size"]//1024}KB</span></summary>'
        f'<pre>{html.escape(i["tail"])}</pre></details>'
        for i in its) or '<p class="dim">還沒有任何一輪。</p>'

    cm_html = "".join(
        f'<tr><td><code>{html.escape(h)}</code></td><td class="dim">{html.escape(d)}</td>'
        f'<td class="dim">{html.escape(r)}</td><td>{html.escape(s)}</td></tr>'
        for r, h, d, s in cms) or '<tr><td colspan="4" class="dim">沒有 commit</td></tr>'

    warn = ""
    if unp:
        items = "、".join(f"{r}（{b}）{n} 筆" for r, b, n in unp)
        warn = (f'<div class="warn"><b>有未推送的 commit：</b>{html.escape(items)}'
                f'<br><span class="dim">沒推上去的東西，稽核端看不到——等於沒做。</span></div>')

    doc = f"""<!doctype html>
<html lang="zh-Hant"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>Vacant 執行端 · user1-2</title>
<style>
:root{{--bg:#0f1216;--panel:#161a20;--ink:#dee3e9;--ink2:#aab2bc;--dim:#7d8691;
--rule:#272d36;--good:#5fa87c;--bad:#cf7466;--warn:#c0a04a;
--mono:ui-monospace,"DejaVu Sans Mono",Menlo,Consolas,monospace;
--sans:-apple-system,"Noto Sans CJK TC","PingFang TC",system-ui,sans-serif}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
font-size:15px;line-height:1.7}}
.wrap{{max-width:60rem;margin:0 auto;padding:1.6rem 1rem 5rem}}
h1{{font-size:1.5rem;margin:0 0 .3rem;font-weight:600}}
h2{{font-size:1.15rem;margin:2.4rem 0 .8rem;font-weight:600;
border-bottom:1px solid var(--rule);padding-bottom:.4rem}}
h3{{font-size:1rem;margin:1.2rem 0 .4rem}}
h4{{font-size:.92rem;margin:1rem 0 .3rem;color:var(--ink2)}}
.dim{{color:var(--dim)}}
.bar{{display:flex;gap:.7rem;flex-wrap:wrap;align-items:center;
font-family:var(--mono);font-size:.8rem;color:var(--dim);margin-bottom:1.6rem}}
.pill{{padding:.16rem .6rem;border:1px solid var(--rule);border-radius:99px}}
.good{{color:var(--good);border-color:var(--good)}}
.bad{{color:var(--bad);border-color:var(--bad)}}
.card{{background:var(--panel);border:1px solid var(--rule);
padding:1rem 1.15rem;margin-bottom:1rem;border-radius:3px}}
.warn{{background:#241f14;border:1px solid var(--warn);color:#e6d9a8;
padding:.8rem 1rem;margin-bottom:1rem;border-radius:3px;font-size:.9rem}}
pre{{background:#0b0e12;border:1px solid var(--rule);padding:.8rem;
overflow-x:auto;font-family:var(--mono);font-size:.76rem;line-height:1.55;
white-space:pre-wrap;word-break:break-word;margin:.5rem 0 0}}
code{{font-family:var(--mono);font-size:.85em;background:#0b0e12;
padding:.1em .35em;border-radius:2px}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
td{{padding:.35rem .5rem;border-bottom:1px solid var(--rule);vertical-align:top}}
td:nth-child(1){{white-space:nowrap}}
td:nth-child(2),td:nth-child(3){{white-space:nowrap;font-size:.8rem}}
details{{border-bottom:1px solid var(--rule);padding:.5rem 0}}
summary{{cursor:pointer;font-size:.9rem}}
summary::marker{{color:var(--dim)}}
footer{{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--rule);
font-family:var(--mono);font-size:.72rem;color:var(--dim);line-height:1.9}}
</style></head><body><div class="wrap">

<h1>Vacant 執行端</h1>
<div class="bar">
  <span class="pill {scls}">{html.escape(status)}</span>
  <span class="pill">共 {len(its)} 輪</span>
  <span class="pill">user1-2</span>
  <span>{html.escape(up)}</span>
  <span>{html.escape(disk)}</span>
  <span>更新於 {time.strftime('%m-%d %H:%M:%S')}</span>
</div>

{warn}

<h2>現在在做什麼</h2>
<div class="card">{md_light(state)}</div>

<h2>進度大綱</h2>
<div class="card">{md_light(prog)}</div>

<h2>留下的東西</h2>
<p class="dim" style="font-size:.85rem;margin:0 0 .6rem">
這一欄是唯一能證明某一輪真的做了事的東西——其餘全部是自述。</p>
<table><tbody>{cm_html}</tbody></table>

<h2>每一輪</h2>
{it_html}

<h2>迴圈日誌</h2>
<pre>{html.escape(loop_tail)}</pre>

<footer>
每 60 秒自動重新整理。頁面由 <code>bin/progress.py</code> 在每一輪結束後產生。<br>
停止迴圈：<code>touch ~/vacant/STOP</code>（當輪跑完才停，不要用 kill）。
</footer>

</div></body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"進度頁已更新 {OUT}（{len(doc)//1024}KB，{len(its)} 輪，{len(cms)} 筆 commit）")


if __name__ == "__main__":
    build()
