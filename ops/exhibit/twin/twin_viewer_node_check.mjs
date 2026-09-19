// 把 examples/twin_viewer.html 裡「真的那兩段 JS」抽出來，對頁內的真資料跑一次。
//
// 為什麼還要這一支：pytest 那邊測的是「我以為 JS 在做什麼」（Python 鏡像），
// 這一支測的是「JS 實際在做什麼」。而且它不需要任何外部答案就能自證：
//   1. 每一筆的 prev_hash 就是前一筆的 hash（檔案自己帶著答案）；
//   2. 每一個 Ed25519 簽章是 Python 那端用 canonical_bytes 簽出來的，
//      JS 這邊少一個位元組就會全部驗不過；
//   3. 交付物的樹雜湊是頁面自己從檔案內容算的，要等於鏈上簽過的 ws_end_sha256。
//
// 用法（要有 node ≥ 18）：
//   node ops/exhibit/twin/twin_viewer_node_check.mjs
import fs from "node:fs";
import path from "node:path";
import url from "node:url";
import vm from "node:vm";

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
const viewer = path.join(REPO, "examples/twin_viewer.html");

let fail = 0;
const check = (name, ok, extra = "") => {
  console.log(`[${ok ? "OK    " : "BROKEN"}] ${name}${extra ? "  " + extra : ""}`);
  if (!ok) fail++;
};

const html = fs.readFileSync(viewer, "utf8");
function slice(beginMark, endMark) {
  const i = html.indexOf(beginMark), j = html.indexOf(endMark);
  if (i < 0 || j < 0) { console.error(`找不到 ${beginMark} / ${endMark}`); process.exit(2); }
  return html.slice(i, j + endMark.length);
}
const canonSrc = slice("/* === CANON-BEGIN ===", "/* === CANON-END === */");
const logicSrc = slice("/* === LOGIC-BEGIN ===", "/* === LOGIC-END === */");

const ctx = {
  TextEncoder, JSON, Math, Number, Array, Object, String, Uint8Array, Uint32Array,
  DataView, Error, parseInt, Map, Set, Promise, setTimeout, crypto, console,
  URLSearchParams,
};
vm.createContext(ctx);
vm.runInContext(
  canonSrc + "\n" + logicSrc
  + "\n;globalThis.__api={entryHash,signedBytes,canonicalString,canonicalBytes,hexToBytes,"
  + "bytesToHex,sha256Bytes,lineHasOnlySafeIntegers,ZERO64,cmpCodePoint,parseBook,"
  + "verifyChain,revalidateAt,treeRoot,checkDelivery,verdictFromChain,summaryMismatch,"
  + "consentAudit,vacantIdFromPubHex,laneSummary,hashTarget};", ctx);
const api = ctx.__api;
console.log(`抽出 CANON ${canonSrc.length} ＋ LOGIC ${logicSrc.length} 字元`);

function block(id) {
  const re = new RegExp(`<script[^>]*id="${id}"[^>]*>\\n([\\s\\S]*?)\\n</script>`);
  const m = html.match(re);
  if (!m) { console.error(`頁面裡找不到 id=${id}`); process.exit(2); }
  return JSON.parse(m[1]);
}
const PACK = block("twin-pack");
const ASSETS = block("twin-assets");

const results = [];
for (const c of PACK.cells) {
  const entries = api.parseBook(c.chain);
  results.push({ c, entries, res: await api.verifyChain(entries, c.pub.pub_hex) });
}

// N1 —— 每一條鏈逐筆對得上
{
  const bad = results.filter((r) => !r.res.ok);
  check("N1 每一格的鏈逐筆對得上",
        bad.length === 0 && results.length > 0,
        `${results.length} 條、共 ${results.reduce((a, r) => a + r.res.n, 0)} 筆`);
}

// N2 —— 簽章真的被驗過（node ≥ 18 有 Ed25519），而且全過
{
  const checked = results.every((r) => r.res.sigChecked);
  const nSig = results.reduce((a, r) => a + r.res.nSigOk, 0);
  const nAll = results.reduce((a, r) => a + r.res.n, 0);
  check("N2 Ed25519 逐筆驗過", checked && nSig === nAll, `${nSig}/${nAll}`);
}

// N3 —— vacant_id 由公鑰當場重算得到
{
  const bad = results.filter((r) => api.vacantIdFromPubHex(r.c.pub.pub_hex) !== r.c.pub.vacant_id);
  check("N3 vacant_id ＝ multibase(multihash(公鑰))", bad.length === 0,
        `${results.length - bad.length}/${results.length}`);
}

// N4 —— 交付物樹雜湊重算後等於鏈上簽過的 ws_end_sha256
{
  let ok = 0, n = 0;
  for (const r of results) {
    const d = api.checkDelivery(r.c.delivery);
    if (!d.recomputable) continue;
    n++;
    const fromChain = api.verdictFromChain(r.entries);
    if (d.rootOk && fromChain && d.rootComputed === fromChain.ws_end_sha256) ok++;
  }
  check("N4 交付物樹雜湊 ＝ 鏈上的 ws_end_sha256", n > 0 && ok === n, `${ok}/${n}`);
}

// N5 —— 摘要與鏈上那一筆逐欄相同（不同就代表有一邊在說謊）
{
  const bad = results.filter((r) =>
    api.summaryMismatch(r.c, api.verdictFromChain(r.entries)).length > 0);
  check("N5 摘要與鏈上 ws_verdict 逐欄相同", bad.length === 0,
        bad.length ? bad.map((r) => r.c.cell_id).join(",") : "");
}

// N6 —— 竄改會咬人：翻掉 accepted ⇒ 那一筆簽章對不上、下一筆接不上
{
  const r = results.find((x) => x.entries.some((e) => e.type === "ws_verdict"));
  const entries = JSON.parse(JSON.stringify(r.entries));
  const res = await api.verifyChain(entries, r.c.pub.pub_hex);
  let idx = -1;
  for (let i = 0; i < entries.length; i++) if (entries[i].type === "ws_verdict") idx = i;
  const before = res.hashes[idx];
  entries[idx].payload.accepted = !(entries[idx].payload.accepted === true);
  const after = await api.revalidateAt(res, entries, r.c.pub.pub_hex, idx);
  check("N6 翻掉 accepted ⇒ hash 變、簽章對不上",
        after.hashes[idx] !== before && after.sigOk[idx] === false && !after.ok,
        `${r.c.cell_id} 第 ${idx + 1} 筆`);
}

// N7 —— 兩種結局都在（一個永遠拒交的閘門跟沒有閘門一樣沒用）
{
  const acc = results.filter((r) => api.verdictFromChain(r.entries).accepted === true).length;
  const ref = results.length - acc;
  check("N7 交付格與拒交格都有", acc > 0 && ref > 0, `交付 ${acc}／拒交 ${ref}`);
}

// N8 —— 同意鏈：驗得過、狀態算得出來、而且原文與 nonce 不在鏈上
{
  const cn = PACK.consent;
  const entries = api.parseBook(cn.chain);
  const res = await api.verifyChain(entries, cn.pub.pub_hex);
  const audit = api.consentAudit(entries, res.hashes);
  const erased = audit.subjects.filter((s) => s.state === "erased").length;
  check("N8 同意鏈驗得過且有人被刪除",
        res.ok && audit.problems.length === 0 && erased > 0,
        `${entries.length} 筆、已刪除 ${erased} 位`);

  const blob = JSON.stringify(entries);
  const leak = (PACK.residents || []).flatMap((r) =>
    Object.values(r.persona).flat()).filter((v) => blob.indexOf(v) >= 0);
  check("N8b 鏈上沒有 persona 原文", leak.length === 0,
        leak.length ? leak.join(",") : "四類欄位的值一個都沒出現在鏈上");
}

// N9 —— 拿掉刪除那一筆 ⇒ 狀態回到「撤回了但沒刪」
{
  const cn = PACK.consent;
  const entries = api.parseBook(cn.chain).filter((e) => e.type !== "PERSONA_ERASED");
  const res = await api.verifyChain(entries, cn.pub.pub_hex);
  const audit = api.consentAudit(entries, res.hashes);
  const pending = audit.subjects.filter((s) => s.state === "withdrawn").length;
  check("N9 拿掉刪除 ⇒ 看得見一個沒做完的義務", pending > 0, `${pending} 位`);
}

// N10 —— 證據等級：requests_seen === 0 的格一定是 L-none（fail-closed）
{
  const bad = PACK.cells.filter((c) => c.requests_seen === 0 && c.evidence !== "L-none");
  check("N10 requests_seen=0 ⇒ L-none（宣告蓋不過資料）", bad.length === 0,
        `${PACK.cells.length} 格，等級分佈 ${JSON.stringify(PACK.evidence_counts)}`);
}

// N11 —— canonical 比較器真的被接上去用（N5b 那個瞎尺洞的同一條）
{
  const a = api.canonicalString({ "\u{1f600}": 1, z: 2 });
  const b = api.canonicalString({ z: 2, "\u{1f600}": 1 });
  // code point 排序：'z'(0x7a) < U+1F600 ⇒ z 在前
  check("N11 canonical 依 code point 排鍵（非 BMP 鍵也對）",
        a === b && a.indexOf('"z"') < a.indexOf("\u{1f600}"), a);
}

// N12 —— 素材是內嵌的 data URI，而且居民用得到的那幾張都在
{
  const names = Object.keys(ASSETS);
  const allData = names.every((n) => ASSETS[n].startsWith("data:image/png;base64,"));
  const need = (PACK.residents || []).map((r) => `${r.body}_portrait`);
  const missing = need.filter((n) => !ASSETS[n]);
  check("N12 素材內嵌且居民都有像", allData && missing.length === 0,
        `${names.length} 張；缺 ${missing.length}`);
}

// N13 —— 反事實那一臂**真的跑過**，而且沒有被畫成一個裁決
//
//  展場的主視覺是「同題關掉這層會怎樣」。2026-09-19 以前那一臂一次都沒跑過，
//  電視卻照樣印「也擋下」——替一個沒發生的反事實作證。這一條守兩件事：
//  (a) 頁面裡的 OFF 臂有真通數（requests_seen > 0）；
//  (b) 它**沒有收據、accepted 是 null**——沒有這一層就是沒有這一層。
{
  const offs = PACK.cells.map((c) => c.off).filter((o) => o && o.ran);
  const live = offs.filter((o) => !o.infra_void);
  const noCalls = live.filter((o) => !(o.requests_seen > 0));
  const faking = live.filter((o) => o.accepted !== null || o.has_receipt);
  check("N13 反事實那一臂真的跑過，且沒有裁決也沒有收據",
        offs.length === PACK.cells.length && live.length > 0 &&
        noCalls.length === 0 && faking.length === 0,
        `${offs.length}/${PACK.cells.length} 格有 OFF；零通數 ${noCalls.length}；` +
        `被畫成有裁決／有收據 ${faking.length}`);
}

// N14 —— 事後稽核不准被當成當場的判定
//
//  OFF 那份交付過不過，`vacant run --vacant 0` 答不出來（它當場沒量）。
//  那個數字是**事後**用同一把尺補量的，所以它必須自己帶著三個旗標。
//  少一個，頁面遲早會把它印成「OFF 也被擋下」。
{
  const pas = PACK.cells.map((c) => c.off && c.off.postaudit).filter(Boolean);
  const bad = pas.filter((p) => p.when !== "after_the_run" ||
                                p.is_verdict !== false || p.signed !== false);
  check("N14 事後稽核自己說它是事後的、非裁決、未簽章",
        pas.length > 0 && bad.length === 0, `${pas.length} 筆，違規 ${bad.length}`);
}

// N15 —— `#cell=<id>` 指得到每一格（C4：手機從電視那一格點過來）
{
  const ids = PACK.cells.map((c) => c.cell_id);
  const ok = ids.every((id) => api.hashTarget(`#cell=${id}`).cell === id);
  const t = api.hashTarget("#cell=" + ids[0] + "&tamper=1");
  const none = api.hashTarget("");
  check("N15 #cell= 指得到每一格、tamper 旗標讀得出、沒給就是 null",
        ok && t.tamper === true && t.cell === ids[0]
        && none.cell === null && none.tamper === false,
        `${ids.length} 格`);}

console.log(fail ? `\n${fail} 項 BROKEN` : "\n全部通過");
process.exit(fail ? 1 : 0);
