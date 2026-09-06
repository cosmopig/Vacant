// 把 examples/receipt_viewer_multiparty.html 裡「真的那兩段 JS」抽出來，對真資料跑一次。
//
// 為什麼還要這一支：pytest 那邊的 Python 鏡像測的是「我以為 JS 在做什麼」，
// 這一支測的是「JS 實際在做什麼」。而且它不需要任何外部答案就能自證：
//   1. 每一筆的 prev_hash 就是前一筆的 hash（檔案自己帶著答案）；
//   2. 5579 個 Ed25519 簽章是 Python 那端用 canonical_bytes 簽出來的，
//      JS 這邊少一個位元組就會全部驗不過；
//   3. 頁面自己算出來的裁決／指名／出貨，要逐格等於歸檔的分析輸出。
//
// 用法（要有 node ≥ 18；沒有 node 就跑 pytest 那一組，不影響展場）：
//   node ops/gain/replay/multiparty_viewer_node_check.mjs
import fs from "node:fs";
import path from "node:path";
import url from "node:url";
import vm from "node:vm";

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
const R454 = path.join(REPO, "ops/gain/replay/r454");
const viewer = path.join(REPO, "examples/receipt_viewer_multiparty.html");

let fail = 0;
const check = (name, ok, extra = "") => {
  console.log(`[${ok ? "OK    " : "BROKEN"}] ${name}${extra ? "  " + extra : ""}`);
  if (!ok) fail++;
};

// --- 抽出頁內的 CANON ＋ LOGIC 區段，原封不動在 vm 裡跑 -------------------
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
};
vm.createContext(ctx);
vm.runInContext(
  canonSrc + "\n" + logicSrc
  + "\n;globalThis.__api={entryHash,signedBytes,canonicalString,hexToBytes,bytesToHex,"
  + "sha256Bytes,lineHasOnlySafeIntegers,ZERO64,KEYS,cellKey,vacantIdFromPubHex,parseBook,"
  + "verifyChain,verifyAttestation,formVerdict,buildCells,attachVerification,shipFor};", ctx);
const api = ctx.__api;
console.log(`抽出 CANON ${canonSrc.length} ＋ LOGIC ${logicSrc.length} 字元`);

// --- 讀頁內內嵌的資料（不是讀磁碟：驗的是「這一頁裡的那一份」）-----------
function block(id) {
  const re = new RegExp(`<script[^>]*id="${id}"[^>]*>\\n([\\s\\S]*?)\\n</script>`);
  const m = html.match(re);
  if (!m) { console.error(`頁面裡找不到 id=${id}`); process.exit(2); }
  return m[1];
}
const KEYS = api.KEYS;
const entries = {}, pubs = {};
for (const k of KEYS) {
  entries[k] = api.parseBook(block(`book-${k}`));
  pubs[k] = JSON.parse(block(`pub-${k}`));
}
const candMap = JSON.parse(block("cand-map"));
const gauge = JSON.parse(block("gauge"));
const receipt = JSON.parse(block("exhibition-receipt"));
const ref = JSON.parse(block("single-key-ref"));
const QUORUM = receipt.verdict.quorum;

// M1 SHA-256 自我校驗（已知向量）
const h = (s) => api.bytesToHex(api.sha256Bytes(new TextEncoder().encode(s)));
check("M1 SHA-256 已知向量",
  h("") === "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  && h("abc") === "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");

// M2 三條完整的鏈：逐筆重算 hash、串接、Ed25519（總共 5579 筆）
const chain = {};
let nAll = 0, nSig = 0, nProblem = 0;
for (const k of KEYS) {
  chain[k] = await api.verifyChain(entries[k], pubs[k].pub_hex, null);
  nAll += chain[k].n; nSig += chain[k].nSigOk; nProblem += chain[k].problems.length;
}
check("M2 三條鏈從創世驗到鏈頭，簽章全數通過、串接零斷點",
  nProblem === 0 && nSig === nAll,
  `${nSig}/${nAll} 筆；${KEYS.map((k) => `${k}=${chain[k].n}`).join(" ")}；問題 ${nProblem}`);
check("M2b 頁面重算的鏈頭 ＝ 公鑰檔裡宣稱的 book_head",
  KEYS.every((k) => chain[k].head === pubs[k].book_head),
  KEYS.map((k) => `${k}:${chain[k].head.slice(0, 12)}…`).join(" "));

// M3 vacant_id ＝ 公鑰的多重雜湊（頁面自己重算）
check("M3 vacant_id 由公鑰重算得到",
  KEYS.every((k) => api.vacantIdFromPubHex(pubs[k].pub_hex) === pubs[k].vacant_id));

// M4 切格：對照表與鏈相符
const built = api.buildCells(entries, candMap, gauge, QUORUM);
api.attachVerification(built.cells, chain);
check("M4 「第幾份」對照表與三條鏈對得上（K1／K2 另外對本頁自己算的位置）",
  built.mapProblems.length === 0, built.mapProblems.slice(0, 3).join("；"));
check("M4b 格數與題數", built.cells.size === 1840 && built.tasks.length === 368,
  `${built.cells.size} 格 / ${built.tasks.length} 題`);

// M5 逐格裁決 vs 歸檔的 r454_naming_table.tsv（1840 列）
const tsv = fs.readFileSync(path.join(R454, "r454_naming_table.tsv"), "utf8")
  .trim().split("\n").map((l) => l.split("\t"));
const col = {};
tsv[0].forEach((name, i) => { col[name] = i; });
let nRow = 0, nBad = 0, firstBad = "";
for (const row of tsv.slice(1)) {
  const tid = row[col.task_id], c = Number(row[col.cand]);
  const v = api.formVerdict(built.cells.get(api.cellKey(tid, c)), null);
  const gotV = v.visible_ok === null ? "None" : (v.visible_ok ? "True" : "False");
  const gotD = v.dissenters.length ? v.dissenters.join(",") : "-";
  const gotE = v.equivocators.length ? v.equivocators.join(",") : "-";
  const ok = gotV === row[col.verdict] && gotD === row[col.dissenters]
    && gotE === row[col.equivocators] && v.n_admitted === Number(row[col.n_admitted]);
  nRow++;
  if (!ok) { nBad++; if (!firstBad) firstBad = `${tid}#${c} 得到 ${gotV}/${gotD}/${gotE}`; }
}
check("M5 逐格裁決＋指名＝歸檔的 naming table", nBad === 0, `${nRow - nBad}/${nRow} 列  ${firstBad}`);

// M6 出貨 vs 歸檔的分析輸出
let nShip = 0, nShipBad = 0;
for (const tid of built.tasks) {
  const s = api.shipFor(built.cells, built.taskCands, tid);
  const r = ref.tasks[tid];
  const idx = (r.analysis_shipped_index === null || r.analysis_shipped_index === undefined)
    ? null : r.analysis_shipped_index;
  nShip++;
  if (s.shipped_index !== idx || s.shipped_sha256 !== (r.analysis_shipped_sha256 || null)) nShipBad++;
}
check("M6 出貨決定＝歸檔的分析輸出", nShipBad === 0, `${nShip - nShipBad}/${nShip} 題`);

// M7 展出的那一格 ＝ 歸檔收據 r454_exhibition_receipt.json
const EX = api.cellKey(receipt.task_id, receipt.candidate_index);
const v0 = api.formVerdict(built.cells.get(EX), null);
const votesOk = KEYS.every((k) => {
  const rec = v0.admitted[k];
  const w = receipt.votes[k];
  return rec && rec.entry.payload.visible_ok === w.visible_ok
    && String(rec.entry.payload.first_failing_test) === String(w.first_failing_test)
    && rec.hash === w.entry_hash;
});
check("M7 展出那一格的三票、卡在第幾條、entry hash ＝ 歸檔收據", votesOk);
check("M7b 展出那一格的裁決與指名 ＝ 歸檔收據",
  v0.visible_ok === receipt.verdict.visible_ok
  && v0.dissenters.join(",") === receipt.named.dissenters.join(",")
  && v0.n_admitted === receipt.verdict.n_admitted
  && v0.quorum === receipt.verdict.quorum,
  `被指名 ${v0.dissenters.join(",") || "（無）"}；法定人數 ${v0.quorum}/${KEYS.length}`);
const ship0 = api.shipFor(built.cells, built.taskCands, receipt.task_id);
check("M7c 這一題出貨的那一份 ＝ 歸檔收據，且與 r446 單執行器逐位相同",
  ship0.shipped_index === receipt.what_shipped_for_this_task.shipped_index
  && ship0.shipped_sha256 === receipt.what_shipped_for_this_task.shipped_sha256
  && ship0.shipped_sha256 === ref.tasks[receipt.task_id].r446_runtime_sha256,
  `第 ${ship0.shipped_index} 份 ${String(ship0.shipped_sha256).slice(0, 12)}…`);
check("M7d 被指名那把金鑰的鏈本身驗得過（鏈驗得過 ≠ 話是真的）",
  v0.dissenters.length === 1 && chain[v0.dissenters[0]].problems.length === 0
  && chain[v0.dissenters[0]].nSigOk === chain[v0.dissenters[0]].n,
  `${v0.dissenters[0]} 鏈頭 ${chain[v0.dissenters[0]].head.slice(0, 16)}…`);

// M8 竄改（a）：翻掉 K3 這一票 ⇒ 簽章掛、下一筆接不上、這一票不進計票
{
  const tampered = api.parseBook(block("book-K3"));
  const cell = built.cells.get(EX);
  const idx = cell.recs.K3[0].idx;
  const before = api.entryHash(tampered[idx]);
  tampered[idx].payload.visible_ok = !tampered[idx].payload.visible_ok;
  const after = api.entryHash(tampered[idx]);
  const ch = await api.verifyChain(tampered, pubs.K3.pub_hex, null);
  const sigBroke = ch.sigOk[idx] === false;
  const linkBroke = tampered[idx + 1].prev_hash !== after;
  const built2 = api.buildCells({ K1: entries.K1, K2: entries.K2, K3: tampered },
                                candMap, gauge, QUORUM);
  api.attachVerification(built2.cells, { K1: chain.K1, K2: chain.K2, K3: ch });
  const v = api.formVerdict(built2.cells.get(EX), null);
  const why = v.rejected.filter((r) => r[0] === "K3").map((r) => r[1]);
  check("M8 竄改（a）翻掉 K3 這一票：hash 變、簽章掛、下一筆接不上、這一票被判不採信",
    before !== after && sigBroke && linkBroke && why[0] === "bad_signature"
    && v.n_admitted === 2 && v.dissenters.length === 0 && v.visible_ok === false,
    `不採信理由=${why.join(",")}；採信 ${v.n_admitted} 票；被指名 ${v.dissenters.join(",") || "（無）"}`);
}

// M9 竄改（b）：拿掉 K2 這一票 ⇒ 1 比 1 平手、未決、不指名（R454 §三-3）
{
  const v = api.formVerdict(built.cells.get(EX), { dropped: { key: "K2" } });
  check("M9 竄改（b）少一票誠實的：1 比 1 平手 ⇒ 未決、不指名",
    v.n_admitted === 2 && v.n_pass === 1 && v.n_fail === 1
    && v.visible_ok === null && v.dissenters.length === 0
    && chain.K2.problems.length === 0,
    `採信 ${v.n_admitted} 票（${v.n_pass} 比 ${v.n_fail}）；K2 的鏈仍然驗得過`);
}

// M10 竄改（c）：換掉 K3 的機器字串 ⇒ 什麼都不會變（平台字串不在任何簽章裡）
{
  const label = pubs.K3.platform;
  const inSigned = entries.K3.some((e) => api.canonicalString(e.payload).indexOf(label) >= 0);
  const pub2 = JSON.parse(block("pub-K3"));
  pub2.platform = "Windows-11-AMD64（示範用的假字串）";
  const ch = await api.verifyChain(entries.K3, pub2.pub_hex, null);
  check("M10 竄改（c）換掉平台字串：它不在任何被簽的 payload 裡，鏈照樣驗得過",
    !inSigned && ch.problems.length === 0 && ch.nSigOk === ch.n
    && api.vacantIdFromPubHex(pub2.pub_hex) === pub2.vacant_id,
    `原字串「${label}」`);
  // 反面：executor_id 有進簽章，改掉它就會掛。
  const tampered = api.parseBook(block("book-K3"));
  tampered[0].payload.executor_id = "K9";
  const ch2 = await api.verifyChain(tampered, pubs.K3.pub_hex, null);
  check("M10b 反面對照：executor_id 有進簽章，改掉它就掛",
    ch2.sigOk[0] === false && ch2.problems.length > 0);
}

// M11 非 BMP 鍵的正規化（N5b 的同一組 fixture，頁面的 canonicalString 本體）
{
  const obj = { "\u{1F331}": 2, "�": 1, "Ａ": 3, "a": 4, " ": 5 };
  const want = '{" ":5,"a":4,"Ａ":3,"�":1,"\u{1F331}":2}';
  check("M11 跨平面鍵：canonicalString 本體逐位元組＝vacant/canonical.py 的排序",
    api.canonicalString(obj) === want, api.canonicalString(obj));
}

console.log(`總判定：${fail === 0 ? "OK" : "BROKEN"}（${fail} 項不合格）`);
process.exit(fail === 0 ? 0 : 1);
