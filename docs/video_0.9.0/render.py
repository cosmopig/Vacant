import sys, json, subprocess, asyncio
from playwright.async_api import async_playwright
# usage: render.py W H out.mp4|stills  [fps] [t1,t2,...]
W,H,out=int(sys.argv[1]),int(sys.argv[2]),sys.argv[3]
fps=int(sys.argv[4]) if len(sys.argv)>4 else 30
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/opt/pw-browsers/chromium',args=['--font-render-hinting=none','--disable-lcd-text'])
        pg=await b.new_page(viewport={'width':W,'height':H},device_scale_factor=1)
        await pg.goto(f'http://127.0.0.1:8765/film.html?w={W}&h={H}')
        await pg.evaluate('window.ready')
        audit={}
        if out=='stills':
            ts=[float(x) for x in sys.argv[5].split(',')]
            for t in ts:
                bad=await pg.evaluate(f'window.frame({t},{int(t*fps)})')
                if bad: audit[t]=bad
                await pg.screenshot(path=f'stills/{W}x{H}_{t:05.2f}.png')
        else:
            n=60*fps
            ff=subprocess.Popen(['ffmpeg','-y','-v','error','-f','image2pipe','-framerate',str(fps),'-i','-','-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p','-tune','film',out],stdin=subprocess.PIPE)
            for f in range(n):
                t=f/fps
                bad=await pg.evaluate(f'window.frame({t},{f})')
                if bad: audit[f]=bad
                ff.stdin.write(await pg.screenshot(type='png'))
                if f%300==0: print(f,flush=True)
            ff.stdin.close(); ff.wait()
        json.dump(audit,open(f'audit_{W}x{H}.json','w'),ensure_ascii=False)
        print('audit frames with overflow:',len(audit))
        await b.close()
asyncio.run(main())
