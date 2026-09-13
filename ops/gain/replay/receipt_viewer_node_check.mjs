// 把 examples/receipt_viewer.html 裡「真的那一份 JS」抽出來跑一次。
//
// 為什麼還要這一支（`receipt_viewer_crosscheck.py` 已經有 Python 鏡像）：
// 鏡像測的是「我以為 JS 在做什麼」，這一支測的是「JS 實際在做什麼」。兩者都要。
// 而且它不需要任何外部答案就能自證位元組佈局正確——
//   1. 每一筆的 prev_hash 就是前一筆的 hash（檔案自己帶著答案）；
//   2. 482 個 Ed25519 簽章是 Python 那端用 canonical_bytes 簽出來的，
//      JS 這邊只要少一個位元組就會全部驗不過。
//
// 用法（要有 node ≥ 18；沒有 node 就跑 Python 那一支，不影響展場）：
//   node ops/gain/replay/receipt_viewer_node_check.mjs
//   node ops/gain/replay/receipt_viewer_node_check.mjs runs/g_r447_conform_lcb2 CONFORM
import fs from "node:fs";
import path from "node:path";
import url from "node:url";
import vm from "node:vm";

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
const runDir = path.resolve(REPO, process.argv[2] || "runs/g_r445_conform_mbpp_ext");
const arm = process.argv[3] || "CONFORM";
const viewer = path.join(REPO, "examples/receipt_viewer.html");

let fail = 0;
const check = (name, ok, extra = "") => {
  console.log(`[${ok ? "OK    " : "BROKEN"}] ${name}${extra ? "  " + extra : ""}`);
  if (!ok) fail++;
};

// --- 抽出頁內的 CANON 區段，原封不動在 vm 裡跑 ---------------------------
const html = fs.readFileSync(viewer, "utf8");
const B = "/* === CANON-BEGIN ===", E = "/* === CANON-END === */";
const i = html.indexOf(B), j = html.indexOf(E);
if (i < 0 || j < 0) { console.error("找不到 CANON-BEGIN／CANON-END 標記"); process.exit(2); }
const src = html.slice(i, j + E.length);
const ctx = { TextEncoder, JSON, Math, Number, Array, Object, String, Uint8Array, Uint32Array,
              DataView, Error, parseInt };
vm.createContext(ctx);
vm.runInContext(src + "\n;globalThis.__api={entryHash,signedBytes,canonicalString,canonicalBytes,"
  + "hexToBytes,bytesToHex,sha256Bytes,lineHasOnlySafeIntegers,cmpCodePoint,ZERO64};", ctx);
const api = ctx.__api;
console.log(`抽出 CANON 區段 ${src.length} 字元；run=${path.relative(REPO, runDir)} arm=${arm}`);

// --- 讀鏈 -----------------------------------------------------------------
const lines = fs.readFileSync(path.join(runDir, `receipts_${arm}.ndjson`), "utf8")
  .split("\n").filter((l) => l.trim());
const entries = lines.map((l) => JSON.parse(l));
const pub = JSON.parse(fs.readFileSync(path.join(runDir, `receipts_${arm}.pub.json`), "utf8"));
const hashes = entries.map((e) => api.entryHash(e));

// N1 SHA-256 自我校驗（空字串與 "abc" 的已知向量）
const h = (s) => api.bytesToHex(api.sha256Bytes(new TextEncoder().encode(s)));
check("N1 SHA-256 已知向量",
  h("") === "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  && h("abc") === "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");

// N2 檔案自己帶著答案：prev_hash 串接、創世 sentinel、stream_id、seq
let linkOk = entries[0].prev_hash === api.ZERO64 && entries[0].stream_id === api.ZERO64;
for (let k = 1; k < entries.length; k++) {
  if (entries[k].prev_hash !== hashes[k - 1]) linkOk = false;
  if (entries[k].stream_id !== hashes[0]) linkOk = false;
  if (entries[k].seq !== k + 1) linkOk = false;
}
check("N2 prev_hash／stream_id／seq 與 JS 重算的 hash 一致", linkOk,
  `${entries.length} 筆，head=${hashes[hashes.length - 1].slice(0, 12)}…`);

// N3 Ed25519：簽章是 Python canonical_bytes 簽的，JS 少一個位元組就會全掛
const key = await crypto.subtle.importKey("raw", api.hexToBytes(pub.pub_hex),
  { name: "Ed25519" }, false, ["verify"]);
let sigOk = 0;
for (const e of entries) {
  if (await crypto.subtle.verify({ name: "Ed25519" }, key, api.hexToBytes(e.sig),
                                 api.signedBytes(e))) sigOk++;
}
check("N3 Ed25519 全數通過（＝JS 的位元組佈局與 vacant/logbook.py 相同）",
  sigOk === entries.length, `${sigOk}/${entries.length}`);

// N4 竄改斷言：乾淨路徑通過不算數。
// 挑的是頁面〔竄改示範〕會挑的**同一筆**（`tamperTarget` 的規則：候選取中位，
// 且不能是最後一筆——最後一筆沒有下一筆的 prev_hash 可以互相對照，
// 沒有 Ed25519 的瀏覽器就只剩半個示範）。`receipt_viewer_crosscheck.py` 的 C5
// 用同一條規則，三邊指到同一筆才算對得起來。
const cand = [];
entries.forEach((e, k) => {
  if (k < entries.length - 1 && e.type === "conform_attempt"
      && e.payload && e.payload.visible_ok === true) cand.push(k);
});
const idx = cand.length ? cand[Math.floor(cand.length / 2)] : 0;
check("N4a 竄改示範挑的那一筆不是創世也不是最後一筆", idx > 0 && idx < entries.length - 1,
  `idx=${idx}（第 ${idx + 1} 筆，共 ${entries.length} 筆）`);
const tam = JSON.parse(lines[idx]);
tam.payload.visible_ok = !tam.payload.visible_ok;
const stillOk = await crypto.subtle.verify({ name: "Ed25519" }, key,
  api.hexToBytes(tam.sig), api.signedBytes(tam));
check("N4b 竄改第 " + (idx + 1) + " 筆：簽章失效、hash 改變、下一筆 prev_hash 接不上",
  !stillOk && api.entryHash(tam) !== hashes[idx] && entries[idx + 1].prev_hash !== api.entryHash(tam),
  `${hashes[idx].slice(0, 12)}… → ${api.entryHash(tam).slice(0, 12)}…`);

// N5 正規化的細節：鍵排序照 code point、控制字元與非 ASCII 的跳脫規則
check("N5a 鍵排序照 code point（比較器本身，孤立單元測試）",
  api.cmpCodePoint("\u{1F331}", "Ａ") > 0);

// N5b「blind ruler」的補丁：N5a 只測 cmpCodePoint 這個比較器本身，從沒斷言
// canonicalString 真的把它接上去用；N5c 原本唯一的形狀 fixture 也全是 ASCII
// 鍵。曾經把頁面第 849 行的 `Object.keys(v).sort(cmpCodePoint)` 改成
// `Object.keys(v).sort()`（吃 JS 預設、以 UTF-16 code unit 比大小的排序），
// N5a／N5c 照樣 OK，crosscheck／render check 三邊也全線，只因為沒有任何一組
// fixture 的「鍵」跨過 BMP／非 BMP 邊界。這裡直接餵 canonicalString 本體
// （不是比較器）一組鍵從第一個字元就跨邊界的物件，逐位元組比對
// vacant/canonical.py 真正簽章用的那個函式。期望值取得方式：
//   .venv/bin/python -c "from vacant.canonical import canonical_bytes; \
//     print(canonical_bytes({'\U0001F331':2,'�':1,'Ａ':3,'a':4,' ':5}).hex())"
// 同一組鍵也放進了 receipt_viewer_crosscheck.py 的 CANON_FIXTURES，三邊比對
// 同一份期望值。
const NON_BMP_FIXTURE = {};
NON_BMP_FIXTURE["\u{1F331}"] = 2;  // 🌱 U+1F331（非 BMP，UTF-16 代理對）
NON_BMP_FIXTURE["�"] = 1;     // U+FFFD REPLACEMENT CHARACTER
NON_BMP_FIXTURE["Ａ"] = 3;     // Ａ U+FF21（全形拉丁大寫 A）
NON_BMP_FIXTURE["a"] = 4;
NON_BMP_FIXTURE[" "] = 5;
const NON_BMP_EXPECTED_HEX =
  "7b2220223a352c2261223a342c22efbca1223a332c22efbfbd223a312c22f09f8cb1223a327d";
const nonBmpHex = api.bytesToHex(api.canonicalBytes(NON_BMP_FIXTURE));
check("N5b 跨平面鍵：canonicalString 本體（非孤立比較器）逐位元組＝vacant/canonical.py",
  nonBmpHex === NON_BMP_EXPECTED_HEX,
  `算出=${nonBmpHex}  期望=${NON_BMP_EXPECTED_HEX}`);

check("N5c canonical 形狀",
  api.canonicalString({ b: 1, a: [true, null, "中\n文"] }) === '{"a":[true,null,"中\\n文"],"b":1}',
  api.canonicalString({ b: 1, a: [true, null, "中\n文"] }));
check("N5d 控制字元用小寫 \\u00xx",
  api.canonicalString({ k: "\u001f" }) === '{"k":"\\u001f"}');

// N6 浮點數守門員
check("N6 守門員：小數／指數／超大整數一律回 false",
  lines.every((l) => api.lineHasOnlySafeIntegers(l))
  && !api.lineHasOnlySafeIntegers('{"a":1.5}')
  && !api.lineHasOnlySafeIntegers('{"a":1e7}')
  && !api.lineHasOnlySafeIntegers('{"a":12345678901234567}')
  && api.lineHasOnlySafeIntegers('{"a":"1.5e7"}'));

console.log(fail === 0 ? "總判定：OK" : `總判定：BROKEN（${fail} 項）`);
process.exit(fail === 0 ? 0 : 1);
