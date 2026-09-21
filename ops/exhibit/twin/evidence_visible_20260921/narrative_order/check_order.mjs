// 敘事順序表與收尾層的**可執行判準**。
//
// 為什麼要有這一支：這一條的產出是「文案」，而文案最容易出的錯是
// **兩份表漂開**（畫面上演的一句、表上寫的另一句）與**禁語溜進去**。
// 兩個都是讀 code 讀不出來的，要跑。
//
// 它做四件事：
//   1. `scenes/narrative_order.json` 裡每一個字串都掃禁語（兩句假話 ＋「信任」）。
//   2. 把 `scenes/seam_ending.js` 整支丟進 `vm` 沙箱**真的跑一次**（餵假的
//      director／arrivals／document／location），拿回它的純函數，
//      逐句跟表上的 `beats[n=18]` 比對 ⇒ 表漂開就會紅。
//   3. `pick()` 的四個分支各驗一次（冷、熱、twinseam 在講話、不在 s11）。
//   4. 接線用的 patch 還套得上（`git apply --check`）。
//
// 用法：node check_order.mjs        退出碼 0＝全過，1＝有紅
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { execFileSync } from "node:child_process";

const HM = "/Users/cosmopig/Documents/GitHub/vacant_hm";
const HERE = path.dirname(new URL(import.meta.url).pathname);
let fail = 0, pass = 0;
const check = (name, ok, note = "") => {
  if (ok) { pass++; console.log(`[OK    ] ${name}${note ? "  " + note : ""}`); }
  else { fail++; console.log(`[FAIL  ] ${name}  ${note}`); }
};

/* ── 1. 禁語 ─────────────────────────────────────────────────────── */
const ORDER_PATH = path.join(HM, "world3/scenes/narrative_order.json");
const order = JSON.parse(fs.readFileSync(ORDER_PATH, "utf8"));
// ⚠ **只掃會上螢幕的欄位。** 表裡的說明文字（`_`、`why_*`、`honest`、
//   `forbidden_lines`）**逐字引用**了那兩句禁語，也用到「不用『信任』」這種
//   後設說法——那是刻意的，讓下一個人看得到禁的是什麼。連它一起掃＝
//   把說明當成違規（第一版就是這樣紅的）。
//   會上螢幕的只有這幾個鍵：head／sub／badge／what（含 `was` 裡的舊版）。
const ON_SCREEN_KEYS = new Set(["head", "sub", "badge", "what"]);
const flat = [];
(function walk(v, p, key) {
  if (typeof v === "string") { if (ON_SCREEN_KEYS.has(key)) flat.push([p, v]); }
  else if (Array.isArray(v)) v.forEach((x, i) => walk(x, `${p}[${i}]`, key));
  else if (v && typeof v === "object") for (const k of Object.keys(v)) walk(v[k], `${p}.${k}`, k);
})(order, "$", null);
check("N0 掃得到東西（掃 0 個字串＝量具壞了，不是「沒有違規」）",
      flat.length >= 40, `${flat.length} 條會上螢幕的字串`);

const BANNED = [
  ["你可以隨時要求我們刪除", "撤回入口還沒做好，今天是假的"],
  ["每一通模型呼叫都經過 Vacant", "那是 A 級的句子；展場這批是 C 級"],
  ["信任", "CLAUDE.md 口徑 5：用「可究責 / 讓依賴有根據」"],
];
for (const [word, why] of BANNED) {
  const hits = flat.filter(([, s]) => s.includes(word));
  check(`N1 順序表裡沒有「${word}」（${why}）`, hits.length === 0,
        hits.map(([p]) => p).join("／"));
}
// 文案層的兩個檔也一起掃。
// ⚠ 註解裡的「不寫 X」是**刻意逐字引用**的，所以要先把註解真的拿掉。
//   第一版只濾「行首是 * 或 //」⇒ 區塊註解裡 `- ❌ 不寫「…」` 那種行活下來，
//   六條全紅、而且紅的是說明不是違規。**量具說謊的典型。**
function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, " ")      // 區塊註解整段拿掉
            .split("\n").filter((l) => !/^\s*\/\//.test(l)).join("\n");
}
for (const rel of ["world3/twinseam.js", "world3/scenes/seam_ending.js"]) {
  const code = stripComments(fs.readFileSync(path.join(HM, rel), "utf8"));
  // 先證明量得動：拿掉註解之後**還是要有碼**，否則「沒命中」只是掃了空字串。
  check(`N2a ${rel} 去註解之後還有碼可以掃`, code.length > 800, `${code.length} bytes`);
  for (const [word] of BANNED) {
    check(`N2 ${rel} 的非註解部分沒有「${word}」`, !code.includes(word),
          code.includes(word) ? "命中" : "");
  }
}

/* ── 2. 在沙箱裡真的把收尾層跑起來 ───────────────────────────────── */
const endSrc = fs.readFileSync(path.join(HM, "world3/scenes/seam_ending.js"), "utf8");
function mount(search) {
  const attrs = {};
  const win = {};
  const sandbox = {
    console: { info() {}, warn() {}, error() {} },
    location: { search },
    document: { documentElement: {
      setAttribute(k, v) { attrs[k] = v; },
      removeAttribute(k) { delete attrs[k]; },
    } },
    URLSearchParams,
    director: { mode: "ambient", titleOv: null, update(dt) { this.__dt = dt; } },
    arrivals: { update(dt) { this.__dt = dt; } },
    sceneId: "s11",
  };
  sandbox.window = win;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(endSrc, sandbox, { filename: "seam_ending.js" });
  return { api: win.__seamEnding, sandbox, attrs, win };
}

const { api, sandbox, win } = mount("");
check("N3 收尾層在沙箱裡掛得起來（不依賴 canvas／影片／網路）", !!api);

// 掛兩次要被自己擋下來
const dbl = (() => {
  try {
    vm.runInContext(endSrc, sandbox, { filename: "seam_ending.js#2" });
    return true;
  } catch (e) { return "throw:" + e.message; }
})();
check("N4 重複掛不會包兩層 director.update（<script> 插兩次的防呆）",
      dbl === true && win.__seamEnding === api);

/* ── 3. 文案逐句跟表上比對（表漂開就紅）──────────────────────────── */
const beat18 = (order.beats || []).find((b) => b.n === 18);
check("N5 表上有幕 18", !!beat18);
if (beat18 && api) {
  const one = api.T.loop(1), many = api.T.loop(3);
  check("N6 幕 18（一位）的大標跟表上逐字一致",
        beat18.head.split("　／　")[0].trim() === one.head, `碼=${one.head}`);
  check("N7 幕 18（一位）的副標跟表上逐字一致",
        beat18.sub.split("　／　")[0].trim() === one.sub, `碼=${one.sub}`);
  check("N8 幕 18（多位）的大標跟表上逐字一致",
        beat18.head.split("　／　")[1].trim() === many.head, `碼=${many.head}`);
  check("N9 幕 18（多位）的副標把數字填進去",
        many.sub === beat18.sub.split("　／　")[1].trim().replace("{N}", "3"),
        `碼=${many.sub}`);
  // 「一位」不准報數字——「走進來的 1 位」讀起來像統計，不像指著剛剛那個人。
  check("N10 一位的時候不報數字", !/\d/.test(one.sub) && !/\d/.test(one.head), one.sub);
}

/* ── 3b. 幕 7′（等待中）的文案也跟表上比對 ───────────────────────── */
const beat7 = (order.beats || []).find((b) => b.n === 7);
check("N5b 表上有幕 7′", !!beat7 && beat7.state === "new");
if (beat7 && api) {
  const w1 = api.T.waiting("鉛筆屑", 1), w3 = api.T.waiting("鉛筆屑", 3);
  check("N5c 幕 7′ 的大標跟表上逐字一致", beat7.head === w1.head, `碼=${w1.head}`);
  check("N5c2 幕 7′ 的兩句副標跟表上逐字一致",
        beat7.sub.replace("（剛好一位）", "").replace("{記號}", "鉛筆屑") === w1.sub
        && beat7.sub_many.replace("（兩位以上）", "").replace("{N}", "3") === w3.sub,
        `碼1=${w1.sub}｜碼3=${w3.sub}`);
  // 🔴 這一條是被**實截**逼出來的回歸：名字取 waiting[0]、數字取全部 ⇒
  //    大標說「風鈴串前面還有 1 位」，右下角陶牌同一畫面說「1 風鈴串 接下來就是他」。
  check("N5d 剛好一位的時候指名，而且**不講位置**（他就是第一位）",
        w1.sub.includes("鉛筆屑") && !/前面|第 ?\d+ ?位|還有/.test(w1.sub), w1.sub);
  check("N5e 兩位以上**不指名**（指名了就會跟陶牌的序號打架），只報總數",
        !w3.sub.includes("鉛筆屑") && /排著 3 位/.test(w3.sub), w3.sub);
  check("N5e2 兩位以上也不對單一個人講位置",
        !/前面還有/.test(w3.sub), w3.sub);
  check("N5f 拿不到代號也不會印出 null／undefined",
        !/null|undefined/.test(api.T.waiting(null, 1).sub),
        api.T.waiting(null, 1).sub);
  check("N5g 幕 7′ 不用第二人稱（大螢幕前站著的不只投卡的人）",
        !/你/.test(w1.sub + w3.sub + w1.head), w1.sub);
}

/* ── 4. pick() 的分支（優先序：等待 > 收尾 > 冷）─────────────────── */
if (api) {
  const d0 = { titleOv: null };
  check("N11 冷（沒人在等、也沒人走過）⇒ 不說話，「這 N 格會一直重播」留著",
        api.pick(d0, "s11", 0, 0, null) === null);
  check("N12 熱（有人走過）＋ 場景是 s11 ⇒ 說幕 18",
        api.pick(d0, "s11", 1, 0, null)?.head === "他還在");
  check("N12b 有人在等 ⇒ 說幕 7′（等待比收尾急）",
        api.pick(d0, "s11", 3, 2, "鉛筆屑")?.head === "先看別人的");
  check("N13 不在 s11（正在演別人的故事）⇒ 不搶大標",
        api.pick(d0, "s07", 3, 2, "鉛筆屑") === null);
  check("N14 twinseam 正在講話（幕 5／6／17）⇒ 讓位，不疊字",
        api.pick({ titleOv: { __seam: true } }, "s11", 3, 2, "x") === null);
  check("N15 beatTitle 之類別人的覆寫 ⇒ 也讓位",
        api.pick({ titleOv: { head: "x" } }, "s11", 3, 0, null) === null);
  check("N16 自己上一幀貼的可以續貼（不會自己把自己擋掉）",
        api.pick({ titleOv: { __seamEnd: true } }, "s11", 3, 0, null) !== null);
  check("N16b ?arrive=0（抵達層關掉、waiting 恆空）⇒ 幕 7′ 自動安靜",
        api.pick(d0, "s11", 0, 0, null) === null);
}

/* ── 5. 負控制：?seamend=0 整層不掛 ─────────────────────────────── */
{
  const off = mount("?seamend=0");
  check("N17 負控制 ?seamend=0 ⇒ 整層不掛（window.__seamEnding 不存在）",
        off.api === undefined);
  check("N18 負控制之下 director.update 沒有被包起來",
        off.sandbox.director.update.toString().includes("__dt"));
}

/* ── 6. 接線用的 patch 還套得上 ─────────────────────────────────── */
{
  const p = path.join(HERE, "wire_in.patch");
  let out = "";
  let ok = false;
  try {
    execFileSync("git", ["apply", "--check", p], { cwd: HM, stdio: ["ignore", "pipe", "pipe"] });
    ok = true;
  } catch (e) { out = String(e.stderr || e.message).slice(0, 200); }
  check("N19 接線 patch 對現在的 index.html 還套得上（套不上＝別人改到 </body> 附近了）",
        ok, out);
}

console.log(`\n${fail === 0 ? "全部通過" : "有紅"}（${pass} 過 / ${fail} 紅）`);
process.exit(fail === 0 ? 0 : 1);
