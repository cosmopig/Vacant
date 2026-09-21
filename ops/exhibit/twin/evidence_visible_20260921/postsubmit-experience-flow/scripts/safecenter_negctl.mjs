// PANEL-SAFE-CENTER-V1 的負控制：用注入的 CSS 把 safe center 蓋掉、退回純 center，
// 跟修好之後的畫面對照，證明「有差別」。同一個 id、同一組資料，只差這一行 CSS。
import { chromium } from "playwright";
const BASE = "http://localhost:3311";
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
  isMobile: true, hasTouch: true, locale: "zh-TW" });
const page = await ctx.newPage();

// AFTER（現況＝已修）
await page.goto(BASE + "/?step=6&id=demo-negctl-0001", { waitUntil: "networkidle" });
await page.waitForTimeout(350);
await page.screenshot({ path: "/tmp/claude-501/shots_final/fix-verify/AFTER_safecenter_p6_390x844.png" });

// BEFORE（負控制：注入 CSS 蓋掉 safe，退回純 center，模擬修之前的行為）
await page.addStyleTag({ content: ".panel{justify-content:center !important}" });
await page.waitForTimeout(150);
await page.screenshot({ path: "/tmp/claude-501/shots_final/fix-verify/BEFORE_negctl_forced_center_p6_390x844.png" });

await ctx.close();
await browser.close();
console.log("done");
