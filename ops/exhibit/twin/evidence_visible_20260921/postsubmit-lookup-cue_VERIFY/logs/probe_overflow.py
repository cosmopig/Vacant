# -*- coding: utf-8 -*-
"""p5／p6 溢出量：head（改動前）vs nostage（只有 MARK）vs live（MARK+STAGE）。
   量的是 .inner 超出視窗多少 px，以及頁面能不能捲（section 是 overflow 隱藏就捲不到）。"""
import base64, io, os, re, subprocess, sys
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:18764"
OUT="/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/shots_overflow"
os.makedirs(OUT, exist_ok=True)
REPO="/Users/cosmopig/Documents/GitHub/vacant-world-cloud"
LIVE=open(REPO+"/public/index.html",encoding="utf-8").read()
HEAD=subprocess.run(["git","-C",REPO,"show","HEAD:public/index.html"],capture_output=True,text=True,check=True).stdout
def strip_stage(h):
    h=re.sub(r"/\* STAGE-CSS-V1 BEGIN.*?/\* STAGE-CSS-V1 END \*/","",h,flags=re.S)
    h=re.sub(r"/\* STAGE-JS-V1 BEGIN.*?/\* STAGE-JS-V1 END \*/","function setStage(n){}\nfunction triggerLookUp(){return Promise.resolve();}\n",h,flags=re.S)
    h=re.sub(r'<div class="stagebar" id="stagebar">.*?</div>\s*</div>',"</div>",h,flags=re.S,count=1)
    h=re.sub(r'<div class="lookup" id="lookup">.*?</div>\n',"",h,flags=re.S)
    return h
VAR={"head":HEAD,"nostage":strip_stage(LIVE),"live":LIVE}
im=Image.new("RGB",(540,700),(46,38,30)); d=ImageDraw.Draw(im)
d.ellipse((150,180,390,470),fill=(198,142,96)); d.ellipse((205,90,335,215),fill=(214,163,116))
b=io.BytesIO(); im.save(b,"PNG"); CARD="data:image/png;base64,"+base64.b64encode(b.getvalue()).decode()
FAKE="00000000-1111-2222-3333-444444444444"
for vname,body in VAR.items():
    for w,h,dev in [(375,667,"SE"),(390,844,"i13")]:
        with sync_playwright() as pw:
            br=pw.chromium.launch(); ctx=br.new_context(viewport={"width":w,"height":h},device_scale_factor=2,is_mobile=True,has_touch=True,locale="zh-TW")
            pg=ctx.new_page()
            pg.route(re.compile(r"^http://127\.0\.0\.1:18764/(index\.html)?(\?.*)?$"),
                     lambda r: r.fulfill(status=200,content_type="text/html; charset=utf-8",body=body))
            for step in (5,6):
                pg.goto(f"{BASE}/?step={step}&id={FAKE}", wait_until="networkidle")
                if step==6:
                    pg.evaluate("(c)=>{document.getElementById('cardImg').src=c;document.getElementById('codeOut').textContent='4UR7-Q5T6';}",CARD)
                pg.wait_for_timeout(700)
                m=pg.evaluate("""() => {
                  const sec=document.querySelector('section.on'), inner=sec.querySelector('.inner');
                  const r=inner.getBoundingClientRect();
                  const cs=getComputedStyle(sec);
                  return {cutTop:Math.max(0,Math.round(-r.top)),
                          cutBottom:Math.max(0,Math.round(r.bottom-innerHeight)),
                          secOverflow:cs.overflow,
                          pageScrollable:document.documentElement.scrollHeight>innerHeight+2,
                          h2:(sec.querySelector('h2')||{}).textContent||null,
                          h2top:sec.querySelector('h2')?Math.round(sec.querySelector('h2').getBoundingClientRect().top):null};
                }""")
                print(f"{vname:8s} {dev:5s} p{step}: 上切 {m['cutTop']:4d}px 下切 {m['cutBottom']:4d}px "
                      f"捲得動={m['pageScrollable']} section.overflow={m['secOverflow']} "
                      f"標題「{m['h2']}」top={m['h2top']}")
                pg.screenshot(path=f"{OUT}/{vname}_{dev}_p{step}.png")
            br.close()
