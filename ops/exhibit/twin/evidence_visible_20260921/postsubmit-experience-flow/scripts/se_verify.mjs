// 驗證 PANEL-SAFE-CENTER-V1 修掉了 VERIFY 抓到的 iPhone SE 375x667 標題被切問題。
import { chromium } from "playwright";
const BASE = "http://localhost:3311";
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 375, height: 667 }, deviceScaleFactor: 2,
  isMobile: true, hasTouch: true, locale: "zh-TW" });
const page = await ctx.newPage();
await page.goto(BASE + "/?step=5&id=demo-se-check-0001", { waitUntil: "networkidle" });
await page.waitForTimeout(400);
await page.screenshot({ path: "/tmp/claude-501/shots_final/se375x667_AFTER_fix_p5.png" });
await page.goto(BASE + "/?step=6&id=demo-se-check-0001", { waitUntil: "networkidle" });
await page.waitForTimeout(400);
await page.screenshot({ path: "/tmp/claude-501/shots_final/se375x667_AFTER_fix_p6.png" });
await ctx.close();
await browser.close();
console.log("done");
