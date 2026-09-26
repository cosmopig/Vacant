// 電視的 `pickCastFor`（vacant_hm/world3/index.html）與後端 `polaroid.pick_cast_for` 逐一相等嗎。
//
// 為什麼要真的跑前端那一段 JS，而不是在 Python 裡再寫一份「我以為它在做什麼」：
// 這條線要保證的是**電視、拍立得、手機三處一定同一張臉**。對照的另一邊必須是
// 電視**實際在跑的那幾行**，不然兩邊一起錯也會綠。
//
// 做法：從頁面裡把 `const COLOR_ANCHOR = …` 到 `function pickCastFor(card){…}` 的結尾
// 原樣切出來，放進 vm，餵同一份 cast40 manifest，對 Python 那邊產的對照表逐列比。
//
// 用法：
//   node ops/exhibit/twin/cast_parity_node_check.mjs <world3/index.html> <frontend manifest.json> \
//        <parity.json（polaroid.py parity-table 產的）>
// 退出碼：0 ＝ 逐一相等；1 ＝ 有不相等；2 ＝ 切不出那一段（頁面改版了，要人看）。
import fs from "node:fs";
import vm from "node:vm";

const [, , pagePath, manifestPath, tablePath] = process.argv;
if (!pagePath || !manifestPath || !tablePath) {
  console.error("用法：node cast_parity_node_check.mjs <index.html> <manifest.json> <parity.json>");
  process.exit(2);
}
const html = fs.readFileSync(pagePath, "utf8");
const start = html.indexOf("const COLOR_ANCHOR");
const fnAt = html.indexOf("function pickCastFor(", start);
if (start < 0 || fnAt < 0) {
  console.error("頁面裡找不到 COLOR_ANCHOR／pickCastFor");
  process.exit(2);
}
// 從 pickCastFor 的第一個 { 開始數括號，找到它自己的結尾（不靠縮排或空行猜）。
let i = html.indexOf("{", fnAt), depth = 0, end = -1;
for (; i < html.length; i++) {
  const ch = html[i];
  if (ch === "{") depth++;
  else if (ch === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
}
if (end < 0) { console.error("pickCastFor 的括號沒有收尾"); process.exit(2); }
const src = html.slice(start, end);

const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
// 電視那一側 CAST 是 Image 物件、`_id` 是 cNN；這裡只需要 `_id`。
const CAST = Object.keys(manifest).map((id) => ({ _id: id }));
const ctx = { manifest, CAST };
vm.createContext(ctx);
vm.runInContext(src + "\n;globalThis.__pick = pickCastFor;", ctx);

const table = JSON.parse(fs.readFileSync(tablePath, "utf8"));
let mismatches = 0, first = null;
const seen = new Set();
for (const row of table.rows) {
  const fe = ctx.__pick(row.card || {})._id;
  seen.add(fe);
  if (fe !== row.cast_id) {
    mismatches++;
    if (!first) first = { card: row.card, frontend: fe, backend: row.cast_id };
  }
}
const out = {
  page: pagePath, extracted_chars: src.length, tie: table.tie,
  n: table.rows.length, mismatches, first_mismatch: first,
  distinct_cast_ids: seen.size, manifest_entries: CAST.length,
};
console.log(JSON.stringify(out));
process.exit(mismatches === 0 ? 0 : 1);
