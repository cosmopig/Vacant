from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:18764"; FAKE="00000000-1111-2222-3333-444444444444"
M="""(sel)=>{const c=document.querySelector(sel);if(!c)return null;const g=c.getContext('2d');
 const d=g.getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i]>8)n++;return n;}"""
for trial in range(3):
    with sync_playwright() as pw:
        br=pw.chromium.launch()   # 全新瀏覽器＝冷快取
        ctx=br.new_context(viewport={"width":375,"height":667},device_scale_factor=2,is_mobile=True,has_touch=True)
        pg=ctx.new_page()
        pg.goto(f"{BASE}/?step=5&id={FAKE}")     # 不等 networkidle
        for t in (0, 300, 900, 2000):
            if t: pg.wait_for_timeout(t if t==300 else t-300 if t==900 else 1100)
            print(f"  trial{trial} t≈{t}ms mark5={pg.evaluate(M,'#mark5 .markglyph')} "
                  f"mark6={pg.evaluate(M,'#mark6 .markglyph')}")
        br.close()
