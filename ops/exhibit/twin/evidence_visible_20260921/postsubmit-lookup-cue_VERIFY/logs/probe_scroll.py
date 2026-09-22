# -*- coding: utf-8 -*-
"""被切掉的那一塊，觀眾捲得到嗎？section overflow:auto — 真的能捲就只是小問題。"""
import os, re
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:18764"; FAKE="00000000-1111-2222-3333-444444444444"
OUT="/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/shots_overflow"
with sync_playwright() as pw:
    br=pw.chromium.launch(); ctx=br.new_context(viewport={"width":375,"height":667},device_scale_factor=2,is_mobile=True,has_touch=True,locale="zh-TW")
    pg=ctx.new_page()
    for step in (5,6):
        pg.goto(f"{BASE}/?step={step}&id={FAKE}", wait_until="networkidle"); pg.wait_for_timeout(500)
        before=pg.evaluate("""() => {const s=document.querySelector('section.on');
            return {id:s.id, scrollTop:s.scrollTop, scrollH:s.scrollHeight, clientH:s.clientHeight,
                    h2top:Math.round(s.querySelector('h2').getBoundingClientRect().top)};}""")
        pg.evaluate("""() => {const s=document.querySelector('section.on'); s.scrollTop = 9999;}""")
        pg.wait_for_timeout(300)
        after=pg.evaluate("""() => {const s=document.querySelector('section.on');
            return {scrollTop:s.scrollTop, h2top:Math.round(s.querySelector('h2').getBoundingClientRect().top)};}""")
        # 也試整頁捲（觀眾手指其實是捲 body）
        pg.mouse.wheel(0, 600); pg.wait_for_timeout(300)
        wheel=pg.evaluate("""() => {const s=document.querySelector('section.on');
            return {docTop:Math.round(scrollY), secTop:s.scrollTop,
                    h2top:Math.round(s.querySelector('h2').getBoundingClientRect().top)};}""")
        print(f"p{step} before={before}")
        print(f"     scrollTop=9999 -> {after}")
        print(f"     wheel 600     -> {wheel}")
        pg.screenshot(path=f"{OUT}/scrolltest_SE_p{step}.png")
    br.close()
