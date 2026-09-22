# -*- coding: utf-8 -*-
"""邊界：/api/result 只回 verdict、沒有 card_png（world3 判決先到、圖還沒出）。
   server 會把 status 設成 done。手機端這時會怎樣？"""
import json, os, sys, time, urllib.request
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:18764"; TOKEN="verify-token"
OUT="/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/shots_edge"
os.makedirs(OUT, exist_ok=True)
def api(p, payload=None, method="GET"):
    req=urllib.request.Request(BASE+p, data=json.dumps(payload).encode() if payload is not None else None,
        method=method, headers={"Content-Type":"application/json","X-Venue-Token":TOKEN})
    return json.loads(urllib.request.urlopen(req).read().decode())
with sync_playwright() as pw:
    br=pw.chromium.launch(); ctx=br.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True,locale="zh-TW")
    pg=ctx.new_page()
    pg.on("pageerror", lambda e: print("  [PAGEERROR]", e))
    pg.goto(BASE+"/", wait_until="networkidle")
    pg.click("#startBtn"); pg.wait_for_timeout(400); pg.click("#refuseBtn")
    pg.wait_for_function("document.getElementById('p5').classList.contains('on')", timeout=20000)
    sid=pg.evaluate("localStorage.getItem('vacant_id')")
    print("claim", api("/api/claim", {"ids":[sid]}, "POST"))
    print("result(no card)", api("/api/result", {"id":sid,"verdict":"accepted"}, "POST"))
    print("server says", api("/api/status/"+sid))
    pg.wait_for_timeout(9000)
    print("page  =", pg.evaluate("[0,1,2,3,4,5,6,7].filter(i=>document.getElementById('p'+i)&&document.getElementById('p'+i).classList.contains('on')).map(i=>'p'+i)"))
    print("stage =", pg.evaluate("[0,1,2].map(i=>document.getElementById('stage'+i).className)"))
    print("stage 文字 =", pg.evaluate("[0,1,2].map(i=>document.getElementById('stage'+i).innerText)"))
    print("lookup 閃過嗎 =", pg.evaluate("document.getElementById('lookup').classList.contains('on')"))
    pg.screenshot(path=os.path.join(OUT,"edge_done_without_card.png"))
    # 再等一輪，確認不是只是慢
    pg.wait_for_timeout(9000)
    print("再等 9s 後 page =", pg.evaluate("[0,1,2,3,4,5,6,7].filter(i=>document.getElementById('p'+i)&&document.getElementById('p'+i).classList.contains('on')).map(i=>'p'+i)"))
    br.close()
