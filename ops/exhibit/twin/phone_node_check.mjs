// 把 `ops/exhibit/twin/phone.html` 裡 PHONE-BEGIN → PHONE-END 那一段抽出來，
// 對**真的一份 `/state`** 跑一次。
//
// 為什麼要這一支：手機那一頁上每一行字都是一個宣告。pytest 測得到伺服器吐什麼，
// 測不到手機把它翻成哪一句話。這一段刻意寫成純函數就是為了讓它可以被這樣執行。
//
// 用法（要有 node ≥ 18）：
//   python3 ops/exhibit/twin/serve_twin.py --port 8899 --dwell 9999 &
//   node ops/exhibit/twin/phone_node_check.mjs [http://127.0.0.1:8899]
// 不給網址就用內建的一份手搓 state（離線也跑得過，但那一份標著 SYNTH）。
import fs from "node:fs";
import path from "node:path";
import url from "node:url";
import vm from "node:vm";

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const PHONE = path.join(HERE, "phone.html");
const BASE = process.argv[2] || null;

let fail = 0;
const check = (name, ok, extra = "") => {
  console.log(`[${ok ? "OK    " : "BROKEN"}] ${name}${extra ? "  " + extra : ""}`);
  if (!ok) fail++;
};

const html = fs.readFileSync(PHONE, "utf8");
const i = html.indexOf("/* === PHONE-BEGIN ===");
const j = html.indexOf("/* === PHONE-END === */");
if (i < 0 || j < 0) { console.error("找不到 PHONE-BEGIN／PHONE-END"); process.exit(2); }
const ctx = { JSON, Math, Object, Array, String, console };
vm.createContext(ctx);
vm.runInContext(html.slice(i, j)
  + "\n;globalThis.__api={cellLine,nextText,evidenceText,EV_TEXT};", ctx);
const api = ctx.__api;

let state, live = false;
if (BASE) {
  try {
    state = await (await fetch(BASE.replace(/\/$/, "") + "/state")).json();
    live = true;
  } catch (e) { console.error(`連不上 ${BASE}：${e}`); }
}
if (!state) {
  // SYNTH：手搓的一份，形狀與 `/state` 相同。**它測的是措辭，不是資料。**
  state = { next_in_s: 12.4, cells: [
    { cell_id: "SYNTH__a__held", side: "held", exit_code: 20, evidence: "L-none" },
    { cell_id: "SYNTH__a__pc", side: "pc", exit_code: 0, evidence: "L-real" },
    { cell_id: "SYNTH__b__held", side: "held", exit_code: 3, evidence: "L-none" },
  ] };
}
console.log(`資料來源：${live ? BASE + "/state（真的）" : "內建 SYNTH"}，`
  + `${state.cells.length} 格\n`);

// P1 —— 結果只從 exit_code 讀，**不從 side 猜**
{
  const bySide = state.cells.map((c) => api.cellLine(c));
  const heldTags = new Set(state.cells.filter((c) => c.side === "held")
    .map((c) => api.cellLine(c).tag));
  const wrong = state.cells.filter((c) => {
    const want = c.exit_code === 0 ? "交付" : c.exit_code === 20 ? "擋下" : "沒收尾";
    return api.cellLine(c).tag !== want;
  });
  check("P1 每一格的結果只從 exit_code 讀（不從「扣住／寫明」反推）",
        wrong.length === 0, `${bySide.length} 格，held 那一邊的標籤：${[...heldTags].join("／")}`);
  // 反面（SYNTH）：一格「扣住卻交付」的格子要印「交付」，不准印「擋下」
  const odd = api.cellLine({ cell_id: "SYNTH", side: "held", exit_code: 0 });
  check("P1b SYNTH 扣住卻交付 ⇒ 照實印「交付」", odd.tag === "交付" && odd.side === "介面扣住",
        `${odd.side} → ${odd.tag}`);
}

// P2 —— 沒收尾的格子有自己的字（不准混進「擋下」）
{
  const v = api.cellLine({ cell_id: "SYNTH", side: "pc", exit_code: 3 });
  check("P2 exit_code 不是 0／20 ⇒「沒收尾」，不准講成「擋下」",
        v.tag === "沒收尾", v.tag);
}

// P3 —— 證據等級的措辭：L-none 不准講成「正在發生」
{
  const t = ["L-real", "L-fake", "L-none", "L-unknown", "", null]
    .map((l) => api.evidenceText(l));
  check("P3 L-none 的措辭是「這一格沒有模型參與」，沒有一個等級被講成「正在發生」",
        api.evidenceText("L-none") === "這一格沒有模型參與"
        && t.every((x) => !String(x).includes("正在發生"))
        && api.evidenceText(null) === "—",
        t.slice(0, 4).join("／"));
}

// P4 —— 「沒人按的話」那一行
{
  check("P4 倒數那一行讀得出來，沒有就印「—」",
        /秒後自己換下一格/.test(api.nextText(state))
        && api.nextText(null) === "—" && api.nextText({}) === "—",
        api.nextText(state));
}

// P5 —— 整頁掃：口徑紅線與離線紅線
{
  check("P5 手機頁不用「信任」這個詞（展場口徑：可究責性／讓依賴有根據）",
        !html.includes("信任"), "");
  const ext = [...html.matchAll(/(?:src|href)\s*=\s*"([^"]+)"/g)]
    .map((m) => m[1]).filter((u) => /^(https?:)?\/\//.test(u));
  check("P5b 零外部資源（展場沒有網路）", ext.length === 0, ext.join("、") || "0 個");
  check("P5c charset 有加", html.includes('<meta charset="utf-8">'), "");
  // 翻位元那一顆**不准預告某一格的結果**。
  //
  // ⚠ 這條界線要畫在對的地方：「翻掉一個被簽章覆蓋的欄位，hash 會變、簽章會
  //   對不上」是**機制的性質**（而且是這個展件要教的那件事），講它是對的。
  //   不准講的是「**這一格**的簽章對不上」——那是一個具體計算的結果，
  //   而這一頁一次都沒有算過。所以：靜態說明可以講機制，
  //   **導播分頁與任何 JS 產生的字串不准出現結果宣告**。
  const pd = html.slice(html.indexOf('<section id="pane-d">'),
                        html.indexOf('<section id="pane-a"'));
  const js = html.slice(html.indexOf("/* === PHONE-END === */"));
  const claim = /簽章對不上|驗證通過|已驗證|驗過了/;
  check("P5d 導播分頁與 JS 都不宣告任何一格的驗證結果（靜態說明講機制可以）",
        !claim.test(pd) && !claim.test(js)
        && /這台機器沒有驗|你自己/.test(html), "");
}

console.log(fail ? `\n${fail} 項 BROKEN` : "\n全部通過");
process.exit(fail ? 1 : 0);
