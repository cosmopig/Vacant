import { chromium } from "playwright";
const BASE = "http://localhost:3311";
const browser = await chromium.launch();

const IOS_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const AND_UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36";

for (const [tag, ua] of [["ios", IOS_UA], ["android", AND_UA]]) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
    isMobile: true, hasTouch: true, userAgent: ua, locale: "zh-TW" });
  const page = await ctx.newPage();
  await page.goto(BASE + "/?step=3&debug=applink", { waitUntil: "networkidle" });
  await page.waitForTimeout(300);
  const lines = await page.evaluate(() => document.getElementById("applinkDebug").textContent);
  console.log("== " + tag + " ==\n" + lines + "\n");
  await page.screenshot({ path: "/tmp/claude-501/shots_final/ai-path/03c_applink_" + tag + ".png" });
  await ctx.close();
}
await browser.close();
