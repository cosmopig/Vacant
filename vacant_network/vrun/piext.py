"""這支在架構裡承重什麼：**pi 的產品版 extension——「裝一次、打開 pi、`/vacant on`」的那一支檔。**

`vacant install --agent pi` 之前的形狀是改寫 `~/.pi/agent/models.json`（把使用者每一個
provider 的 `baseUrl` 全部改道、再加一個 `vacant` provider），而那一格從來沒有被
`requests_seen` 證實過（`possess.CHANNEL_MEASURED["pi"] == ""`）。2026-09-22 人類的
要求是：

    pip install vacant-network
    vacant install            # 或裸打 vacant 讓它引導
    pi                        # 之後照舊；輸入框裡 /vacant on|off|status

pi 0.87.0 的 extension API（`docs/extensions.md`，2026-09-22 從原始碼讀的）讓這件事
**不必碰 `models.json`**：

  · `pi.registerProvider("vacant", {baseUrl, api:"openai-completions", apiKey, models})`
    —— provider 在 runtime 註冊，使用者自己的 provider **一個都不改道**。
  · `pi.setModel(model)` —— session 層的選擇，不改 `defaultProvider`。
  · `pi.registerCommand("vacant", …)` —— `/vacant on|off|status`。
  · 七個掛鉤事件 —— 與 2026-09-20 A 級那一跑用的**同一組**，經 `hookcli` 落 JSONL。

本模組只做一件事：把那支 extension **渲染成文字**（python 路徑、套件路徑、埠、
state 目錄、裝機當下抓到的模型清單都烤進去）。寫進 `~/.pi/agent/extensions/vacant.ts`
的是 `possess.wire_pi`（`write_tracked`，可逐位元還原）。

## 為什麼是 `.ts` 而內容是純 JS

pi 的 `isExtensionFile` 只認 `.ts`／`.js`（`chunk-4DKZACXI.js`，jiti 載入）。純 JS 是
合法 TS，而純 JS 才能用 `node --check` 驗語法（`tests/test_vrun_possess.py`）。

## 誠實邊界（改碼請保留）

1. **裝了 extension ≠ 被中介。** 唯一算數的證據仍是常駐 proxyd journal 的
   `requests_seen`；`vacant possess status` 的 `wired`／`proven` 兩欄不變。
2. **agent 刪得掉這支檔**（`DECISION_20260920_AGENT_HOOKS_MEASURED.md` §三）。刪掉的
   那一跑 canary 不會燒 ⇒ 收據自動降級。本檔不假裝這是保證；保證只在 kernel。
3. **`/vacant off` 是使用者的選擇，不是失效**——但那一段要留痕：extension 會寫一筆
   `vacant_off`（含切去哪個 provider）進掛鉤日誌，收據不替它說謊。
   反方向同理：用 Ctrl+P／`/model` 切**回** `vacant` 會寫一筆 `vacant_on`（`source`＝
   `cycle`／`set`／`restore`）。不變式是**每一次轉換（任一方向）恰好一筆**；
   2026-09-24 實測前只有切走那一邊有痕跡，切回來之後日誌一路說「off」而呼叫其實又經過
   Vacant。⚠ 這仍只是**掛鉤日誌的敘述**，不是中介的證據（邊界 1）。
4. **fail-closed 不用另外寫**：模型一旦指到 `vacant` provider，proxyd 沒起來就是
   connection refused，pi 不會自己換 provider。`session_start` 會探一次並通知，讓使用者
   分得出「Vacant 那一層壞了」與「模型壞了」。
5. **互動 session 不出裁決收據。** 閘門（驗收＋`ws_verdict`）仍然在 `pi -p` 經 PATH shim
   那一條；互動模式的閘門要掛在 `agent_before_settle`，那是另一份裁決（`decisions/notes/
   NOTE_20260922_PI_OPENCODE_SLASH_VACANT_PLAN.md` §3.3），本檔**沒有做**。
6. 掛鉤日誌**只落雜湊**（`hookcli` 邊界 1）；本檔不落 prompt、不落工具輸入原文。
7. **金鑰：借，不存。** `vacant` provider 的 `apiKey` 在 pi 行程裡、factory 那一刻，從
   `models.json` 裡 **baseUrl 等於 proxyd 上游**的那個 provider 抄它的 `apiKey` **設定字串**
   （字面值、`$VAR`／`${VAR}`、`!命令` 都原樣抄，交給 pi 自己解析；裸的 `MY_KEY`
   在 pi 是**字面值**，不是環境變數名）。所以 Authorization 帶的是
   使用者自己的金鑰，proxyd `sentinel=""` 原樣穿透、**永不持有**；本檔與 `possess` 的
   state 也**從不寫入金鑰**（烤進來的只有 provider id 與上游 url）。比對條件是 baseUrl
   相等——金鑰只送回它本來就要去的主機。找不到 ⇒ 送佔位 `sk-vacant-possess`，
   `session_start` 會講。金鑰在 `auth.json` 的內建 provider **不借**（`NEVER_TOUCH`）。
   ~~⚠ **沒量過**：pi 0.87.0 的 `registerProvider({apiKey})` 是否跟 `models.json` 走同一套
   解析（env 名／`!命令`）是從文件推的，**還沒有一跑真的用借來的金鑰打到要金鑰的上游**。~~
   ⇒ 2026-09-24 在 vacant-dev 用真 pi 0.87.0 量過：字面值、`$VAR`、`!命令` 三種借法都
   真的打到要金鑰的上游（解析與 `models.json` 同一套）。`${VAR}` 寫法沒有單獨量過借用。
   provider 的自訂 `headers`／`authHeader` 也沒有抄。
8. 上游是 sink（裝機時沒找到上游）⇒ 仍然切到 `vacant`（fail-closed，不偷偷直連），
   但 `session_start` 會用 error 等級講清楚「每一通都會被擋、怎麼修、`/vacant off` 回原模型」。
9. **模型清單也是借的，而且只有借的那份靠得住。** 裝機時的 `probe_models`、extension 的
   `refreshModels` 與 `proxyAlive` 都**不帶 Authorization**（金鑰是設定字串，只有 pi 會
   解析；本檔不自己跑 `!命令`）⇒ 上游要金鑰就一律 401（2026-09-24 實測），烤進來的清單
   是空的、`refreshModels` 也拿不到。所以 `vacant` provider 的模型次序是：
   **邊界 7 那個 provider 的 `models`**（只抄 id／name／contextWindow／maxTokens／
   reasoning／input；`cost` 歸零、`headers`／`authHeader` 不抄；`compat` 見邊界 10）→ 裝機時烤進來的
   → `DEFAULT_MODEL`。落到最後那一格時清單是**猜的**：上游沒有那個 id 就每一通 404
   （fail-closed，不會繞開），`session_start` 會講。`/vacant on` 先找使用者**現在用的那個
   id**（＝同一個模型、經過 Vacant），找不到才依 `VACANT_AGENT_MODEL`→`DEFAULT_MODEL`→
   第一個。⚠ 同 id 不保證同一個模型設定：借來的欄位以外（model 層 compat、自訂 headers）不一樣。
10. **compat（上游的方言）也借**：provider 層的 `compat` 物件蓋在預設值上。2026-09-24 接 Gemini
   的 OpenAI 相容端點實測：它回 400「Unknown name "store"」，使用者要寫 `supportsStore:false`；
   vacant provider 若不跟著寫，裝了 Vacant 就壞。model 層的 compat、`headers`、`authHeader` 仍不抄。
"""
from __future__ import annotations

import json
import sys

#: 我們註冊進 pi 的 provider id。**要看得出是誰接的**——狀態列會顯示 `(vacant) <model>`。
PROVIDER_ID = "vacant"

#: 裝機時抓不到上游模型清單的時候烤進去的那一個（與 `possess`／`gateshim` 同一個預設）。
DEFAULT_MODEL = "gemma-4-12b-it-qat"

#: extension 檔名（相對 `~/.pi/agent/`）。
EXTENSION_REL = ".pi/agent/extensions/vacant.ts"

#: 本檔渲染出來的 extension 第一行要有這個標記——`status`／測試用它認「這支是我們寫的」。
MARK = "// vacant-possess-extension/1"

_TEMPLATE = r"""%(mark)s
// 由 vacant_network/vrun/piext.py 渲染；`vacant uninstall` 會逐位元還原／刪掉本檔。
// ⚠ 這支檔在 $HOME 底下，agent 自己刪得掉（實測）。刪掉的那一跑 canary 不會燒，
//   收據自動降級——本檔不是保證，保證只在 kernel（enclosure）。
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";

const PY = %(py)s;
const HOOK_ARGS = %(hook_args)s;
const PYPATH = %(pypath)s;
const STATE = %(state)s;
const PORT = %(port)s;
const PROVIDER = %(provider)s;
const BAKED_MODELS = %(models)s;
const DEFAULT_MODEL = %(default_model)s;
const UPSTREAM = %(upstream)s;        // proxyd 轉去的地方（裝機時決定；只有 url，沒有金鑰）
const UPSTREAM_IS_SINK = %(upstream_is_sink)s;
const KEY_FROM = %(key_from)s;        // 裝機時算出的「金鑰向哪個 provider 借」（只是提示，runtime 仍比對 baseUrl）
const PI_AGENT_DIR = %(pi_agent_dir)s;
const PROXY = %(proxy)s;          // 字面值（不是算出來的）：status／測試要在檔案裡直接看得到端點
const BASE = PROXY + "/v1";

// ── 掛鉤契約 vacant-hook/1：每個事件 spawn 一次 hookcli，落 JSONL ─────────────
const runId = randomUUID();
const hookLog = join(STATE, "hooks", "pi_" + runId + ".jsonl");

function hookEnv() {
  const env = Object.assign({}, process.env);
  env.VACANT_HOOK_LOG = hookLog;
  env.VACANT_RUN_ID = runId;
  env.VACANT_HOOK_AGENT = "pi";
  env.VACANT_RUN_PROXY = PROXY;
  env.PYTHONPATH = PYPATH + (process.env.PYTHONPATH ? ":" + process.env.PYTHONPATH : "");
  return env;
}

function fire(event, payload) {
  try {
    mkdirSync(join(STATE, "hooks"), { recursive: true });
    spawnSync(PY, [...HOOK_ARGS, event], {
      input: JSON.stringify(payload || {}),
      timeout: 20000, stdio: ["pipe", "ignore", "ignore"], env: hookEnv(),
    });
  } catch (e) { /* 掛鉤壞掉不可以弄死 agent（hookcli 誠實邊界 3） */ }
}

function notify(ctx, text, level) {
  try { if (ctx && ctx.hasUI && ctx.ui) ctx.ui.notify(text, level || "info"); }
  catch (e) { /* print 模式沒有 UI */ }
}

// src ＝ 使用者 models.json 裡那個 provider 的 model 條目（借來的；可缺）。
// 只抄 name／reasoning／input／contextWindow／maxTokens；cost 不抄（我們不替別人記帳）、
// headers／authHeader 不抄（誠實邊界 7、9）；compat 另外在 provider 層借（邊界 10）。
function modelDef(id, src) {
  const s = src && typeof src === "object" ? src : {};
  const pos = (v, d) => (typeof v === "number" && isFinite(v) && v > 0 ? v : d);
  const input = Array.isArray(s.input) ? s.input.filter((x) => typeof x === "string" && x) : [];
  return { id,
           name: typeof s.name === "string" && s.name ? s.name : id,
           reasoning: typeof s.reasoning === "boolean" ? s.reasoning : false,
           input: input.length ? input : ["text"],
           cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
           contextWindow: pos(s.contextWindow, 131072),
           maxTokens: pos(s.maxTokens, 16384) };
}

// models.json 的 `models` 陣列 → modelDef 清單（條目可以是物件或裸 id 字串；重複 id 只留第一個）
function modelDefsFrom(list) {
  const out = [], seen = new Set();
  for (const m of Array.isArray(list) ? list : []) {
    const id = typeof m === "string" ? m : (m && typeof m.id === "string" ? m.id : "");
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(modelDef(id, typeof m === "object" ? m : null));
  }
  return out;
}

async function proxyAlive(signal) {
  try {
    const r = await fetch(BASE + "/models?vacant_canary=status-" + runId, { signal });
    return { listening: true, status: r.status };
  } catch (e) {
    return { listening: false, status: null, error: String(e && e.message || e) };
  }
}

function heartbeat() {
  try {
    const p = join(STATE, "proxyd", "heartbeat");
    if (!existsSync(p)) return null;
    return JSON.parse(readFileSync(p, "utf-8"));
  } catch (e) { return null; }
}

function hookLines() {
  try { return existsSync(hookLog) ? readFileSync(hookLog, "utf-8").split("\n").filter(Boolean).length : 0; }
  catch (e) { return 0; }
}

// ── 借：使用者自己那個 provider 的 apiKey 設定字串＋模型清單（誠實邊界 7、9）───
//   只借 baseUrl 等於 UPSTREAM 的；抄的是**設定字串**，解析交給 pi。不寫任何檔。
//   models.json 只在 factory 那一刻讀一次。
function normUrl(u) { return String(u || "").trim().replace(/\/+$/, ""); }
function upstreamProviders() {
  if (!UPSTREAM || UPSTREAM_IS_SINK) return [];
  try {
    const dir = process.env.PI_CODING_AGENT_DIR || PI_AGENT_DIR;
    if (!dir) return [];             // 不知道 pi 設定在哪 ⇒ 不借（絕不讀 cwd 的 models.json）
    const doc = JSON.parse(readFileSync(join(dir, "models.json"), "utf-8"));
    const provs = (doc && doc.providers) || {};
    const ids = Object.keys(provs).filter((id) => id !== PROVIDER && id !== "vacantproxy");
    ids.sort((a, b) => (b === KEY_FROM) - (a === KEY_FROM));
    return ids.map((id) => ({ id, p: provs[id] || {} }))
      .filter((x) => normUrl(x.p.baseUrl) === normUrl(UPSTREAM));
  } catch (e) { return []; /* 讀不到 models.json ⇒ 不借 */ }
}
const MATCHED = upstreamProviders();
function borrowKey() {
  for (const { id, p } of MATCHED) {
    if (typeof p.apiKey === "string" && p.apiKey) return { provider: id, apiKey: p.apiKey };
  }
  return null;
}
const BORROWED = borrowKey();
// 模型清單：先看借金鑰的那一個 provider，再看其他 baseUrl 相同的（同一台主機，同一份目錄）。
function borrowModels() {
  const first = BORROWED ? MATCHED.filter((x) => x.id === BORROWED.provider) : [];
  for (const { id, p } of first.concat(MATCHED.filter((x) => !BORROWED || x.id !== BORROWED.provider))) {
    if (modelDefsFrom(p.models).length) return { provider: id, raw: p.models };
  }
  return null;
}
const BORROWED_MODELS = borrowModels();
// ⚠ 要金鑰的上游對「不帶 Authorization 的探測」一律 401 ⇒ 裝機時 BAKED_MODELS 是空的、
//   refreshModels 也拿不到 ⇒ 若只剩 DEFAULT_MODEL，那是**猜的**，上游多半沒有這個 id（每一通 404）。
//   所以次序是：借來的清單 → 裝機時烤進來的 → DEFAULT_MODEL（誠實邊界 9）。
// compat：**上游的方言**。vacant provider 轉去的是同一個上游，就得講同一種方言
// （2026-09-24 接 Gemini 實測：它不認得 `store` 欄位，使用者自己要寫 `supportsStore:false`，
//  vacant provider 不跟著寫就 400）。預設值不變，使用者那個 provider 寫了什麼就蓋過去。
// 只抄 provider 層的 `compat`（物件）；model 層的 compat、headers、authHeader 仍不抄（誠實邊界 10）。
function borrowCompat() {
  const out = { supportsDeveloperRole: false, supportsReasoningEffort: false };
  const first = BORROWED ? MATCHED.filter((x) => x.id === BORROWED.provider) : [];
  for (const { p } of first.concat(MATCHED.filter((x) => !BORROWED || x.id !== BORROWED.provider))) {
    const c = p && p.compat;
    if (c && typeof c === "object" && !Array.isArray(c)) return Object.assign(out, c);
  }
  return out;
}
const MODEL_SOURCE = BORROWED_MODELS ? "borrowed" : (BAKED_MODELS.length ? "baked" : "default");
function baseModels() {                // 每次回新物件（pi 可能改它拿到的陣列）
  if (BORROWED_MODELS) return modelDefsFrom(BORROWED_MODELS.raw);
  return (BAKED_MODELS.length ? BAKED_MODELS : [DEFAULT_MODEL]).map((id) => modelDef(id));
}
function modelSourceText() {
  if (MODEL_SOURCE === "borrowed") return "借自 models.json 的「" + BORROWED_MODELS.provider + "」";
  if (MODEL_SOURCE === "baked") return "裝機時經 proxyd 問到的";
  return "**猜的**（只有 " + DEFAULT_MODEL + "；上游沒有這個 id 就每一通 404）";
}

// ── 狀態：這個 session 有沒有開、開之前用的是哪個模型 ────────────────────────
let enabled = true;
let previous = null;   // {provider, id} —— /vacant off 切回去用
// 不變式：**每一次轉換（任一方向）恰好一筆痕跡**。
// /vacant off 自己已經寫過一筆 vacant_off；它接著呼叫 pi.setModel(previous) 會觸發
// model_select（實測：extension 的 await pi.setModel 會在 await 之內同步觸發），那一筆不可以再寫。
let offInProgress = false;
// 反方向同理：switchOn 自己會寫 vacant_on；它的 pi.setModel(target) 觸發的 model_select 不再寫。
let onInProgress = false;
// 我們最後知道的「現在在不在 vacant 上」（true／false／null＝不知道）。
// model_select 帶 previousModel 時以它為準；沒帶才用這個判斷是不是一次轉換。
let onVacantNow = null;

function pickVacantModel(ctx) {
  const reg = ctx && ctx.modelRegistry;
  if (!reg) return null;
  const cur = ctx && ctx.model;
  // 「/vacant on」＝**同一個模型，經過 Vacant**：先找使用者現在用的那個 id，
  // 再 VACANT_AGENT_MODEL、DEFAULT_MODEL，最後才是 vacant provider 的第一個。
  const ids = [];
  if (cur && typeof cur.id === "string" && cur.id) ids.push(cur.id);
  if (process.env.VACANT_AGENT_MODEL) ids.push(process.env.VACANT_AGENT_MODEL);
  ids.push(DEFAULT_MODEL);
  for (const id of ids) {
    try { const m = reg.find(PROVIDER, id); if (m) return m; } catch (e) { /* 下一個 */ }
  }
  try {
    const all = typeof reg.getAll === "function" ? reg.getAll() : [];
    for (const m of all) if (m && m.provider === PROVIDER) return m;
  } catch (e) { /* 沒有 */ }
  for (const d of baseModels()) {       // registry 沒有 getAll 時的最後一招
    try { const m = reg.find(PROVIDER, d.id); if (m) return m; } catch (e) { /* 下一個 */ }
  }
  return null;
}

async function switchOn(pi, ctx, why) {
  const cur = ctx && ctx.model;
  if (cur && cur.provider === PROVIDER) { onVacantNow = true; return true; }
  const target = pickVacantModel(ctx);
  if (!target) {
    notify(ctx, "Vacant：找不到 provider「" + PROVIDER + "」的模型 ⇒ 沒有切換。**這個 session 沒經過 Vacant。**", "error");
    fire("vacant_on_failed", { reason: "no_model" });
    return false;
  }
  previous = cur ? { provider: cur.provider, id: cur.id } : previous;
  let ok = false;
  onInProgress = true;
  try { ok = await pi.setModel(target); } finally { onInProgress = false; }
  if (!ok) {
    notify(ctx, "Vacant：pi.setModel 回 false（provider 沒有 auth？）⇒ 沒有切換。**這個 session 沒經過 Vacant。**", "error");
    fire("vacant_on_failed", { reason: "setModel_false" });
    return false;
  }
  onVacantNow = true;
  fire("vacant_on", { source: why, model: target.provider + "/" + target.id });
  return true;
}

export default function (pi) {
  // ── 通道：runtime 註冊 provider，**不動使用者的 models.json** ──────────────
  pi.registerProvider(PROVIDER, {
    name: "Vacant（常駐 proxyd :" + PORT + "）",
    baseUrl: BASE,
    // 使用者自己的金鑰設定字串（借來的）或佔位；proxyd sentinel="" ⇒ Authorization 原樣穿透
    apiKey: BORROWED ? BORROWED.apiKey : "sk-vacant-possess",
    api: "openai-completions",
    // 預設 ＋ 使用者那個 provider 自己的 compat（誠實邊界 10）
    compat: borrowCompat(),
    // 借來的清單 → 裝機時烤進來的 → DEFAULT_MODEL（誠實邊界 9）
    models: baseModels(),
    // 上游目錄變了就重抓；這一通同時是一次會進 journal 的 canary。
    // ⚠ **永遠不回空清單、也不 throw**：proxyd 起來了但上游是 sink／掛了時，
    //   /v1/models 會回 502（常常不是 JSON）或 JSON 錯誤體。若照回 `[]`（或拋錯讓 pi
    //   自己決定），pi 可能拿它蓋掉 provider 的模型清單 ⇒ 烤進去的模型消失、
    //   pickVacantModel 找不到 ⇒ `/vacant on`／session_start 報「沒有模型」而**沒有切過去**，
    //   使用者就安靜地停在原 provider 上。那不是 fail-closed，是 fail-open。
    //   pi 0.87.0 對 refreshModels 拋錯時保留舊清單還是清空，NOTE_20260922 沒有讀到
    //   ⇒ 不賭它：非 2xx／例外／空清單一律回 baseModels()（與註冊時同一份）。模型仍指到
    //   vacant，上游壞掉就在連線那一刻失敗（誠實邊界 4），而不是在選模型那一刻繞開。
    // ⚠ 這一通**不帶 Authorization**（金鑰是設定字串，只有 pi 會解析）⇒ 要金鑰的上游
    //   在這裡永遠 401，清單只能靠借的（2026-09-24 vacant-dev 實測）。
    // 上游 2xx 且有清單（不要金鑰的本機上游）時：
    //   · 有借來的清單 ⇒ **聯集，借來的在前、原樣保留**。理由：使用者設定的 contextWindow／
    //     maxTokens／reasoning 才是「同一個模型」——只照上游 id 重建會把它們重設成預設值，
    //     那正是 LCB 兩臂對照第一版整批作廢的干擾（contextWindow 262144 vs 131072）。
    //     也**不刪**上游沒列的借來 id：有些伺服器只列已載入的模型，刪了會把使用者
    //     正在用的模型從 session 底下抽走。上游多列的 id 補在後面（它們真的在那台主機上）。
    //   · 沒有借來的清單 ⇒ 上游的活清單取代裝機時的快照（兩者本來就是同一個來源）。
    async refreshModels({ signal }) {
      const base = baseModels();
      try {
        const r = await fetch(BASE + "/models?vacant_canary=refresh-" + runId, { signal });
        if (!r || !r.ok) return base;
        const body = await r.json();
        const data = Array.isArray(body && body.data) ? body.data : [];
        const live = modelDefsFrom(data.filter((m) => m && typeof m.id === "string").map((m) => m.id));
        if (!live.length) return base;
        if (!BORROWED_MODELS) return live;
        const have = new Set(base.map((m) => m.id));
        return base.concat(live.filter((m) => !have.has(m.id)));
      } catch (e) {
        return base;
      }
    },
  });

  // ── /vacant on | off | status ────────────────────────────────────────────
  pi.registerCommand("vacant", {
    description: "Vacant：on（切到中介）／off（切回原模型，留痕）／status（proxyd、通數、掛鉤日誌）",
    getArgumentCompletions: (prefix) => {
      const items = ["on", "off", "status"].filter((x) => x.startsWith(prefix || ""))
        .map((x) => ({ value: x, label: x }));
      return items.length ? items : null;
    },
    handler: async (args, ctx) => {
      // 只有空白與 "status" 是 status；**其他字一律不當 status 跑**（實測 `/vacant statusReply…`
      // 曾印出 status——打錯字不可以看起來像成功）。
      const sub = String(args || "").trim().split(/\s+/)[0] || "status";
      if (sub !== "on" && sub !== "off" && sub !== "status") {
        notify(ctx, "用法：/vacant on | off | status（收到「" + sub.slice(0, 40) + "」，什麼都沒做）", "warning");
        return;
      }
      if (sub === "on") {
        enabled = true;
        if (await switchOn(pi, ctx, "command")) {
          notify(ctx, "Vacant 開：模型呼叫經 " + PROXY + "（provider「" + PROVIDER + "」）", "info");
        }
        return;
      }
      if (sub === "off") {
        enabled = false;
        const cur = ctx && ctx.model;
        const to = previous;
        fire("vacant_off", { from: cur ? cur.provider + "/" + cur.id : null,
                             to: to ? to.provider + "/" + to.id : null });
        if (to && ctx && ctx.modelRegistry) {
          let m = null;
          try { m = ctx.modelRegistry.find(to.provider, to.id); } catch (e) { m = null; }
          let switched = false;
          if (m) {
            offInProgress = true;
            try { switched = await pi.setModel(m); } finally { offInProgress = false; }
          }
          if (switched) {
            onVacantNow = false;
            notify(ctx, "Vacant 關：切回 " + to.provider + "/" + to.id + "。⚠ 這一段不經過 Vacant，掛鉤日誌記了一筆 vacant_off。", "warning");
            return;
          }
        }
        notify(ctx, "Vacant 關：沒有可切回的先前模型，用 /model 自己選。⚠ 之後的呼叫不經過 Vacant，日誌記了一筆 vacant_off。", "warning");
        return;
      }
      // status
      const alive = await proxyAlive(ctx && ctx.signal);
      const hb = heartbeat();
      const cur = ctx && ctx.model;
      const onVacant = !!(cur && cur.provider === PROVIDER);
      const lines = [
        "Vacant status（這個 session）",
        "  模型      " + (cur ? cur.provider + "/" + cur.id : "－") + (onVacant ? "  ✓ 經過 Vacant" : "  **✗ 不經過 Vacant**"),
        "  proxyd    " + PROXY + "  在聽：" + (alive.listening ? "是（/v1/models → " + alive.status + "）" : "**否**（" + (alive.error || "") + "）"),
        "  通數      " + (hb ? "requests_seen=" + hb.requests_seen + "（機器層級的總量，不是這個 session 的）" : "－ 沒有 heartbeat"),
        "  模型清單  " + modelSourceText(),
        "  掛鉤日誌  " + hookLog + "（" + hookLines() + " 筆）",
        "  ⚠ 互動 session 不出裁決收據；閘門在 `pi -p` 經 shim 那一條。",
      ];
      notify(ctx, lines.join("\n"), onVacant && alive.listening ? "info" : "warning");
    },
  });

  // ── 掛鉤七事件（與 2026-09-20 A 級那一跑同一組）＋ 預設開 ───────────────────
  pi.on("session_start", async (event, ctx) => {
    fire("session_start", { source: "pi-extension", reason: event && event.reason });
    if (!enabled) return;
    const alive = await proxyAlive(ctx && ctx.signal);
    if (!alive.listening) {
      notify(ctx, "Vacant：常駐 proxyd " + PROXY + " **沒在聽**。模型仍會指到它 ⇒ 會 connection refused（fail-closed，不會偷偷直連）。看 `vacant possess status`。", "error");
    }
    if (UPSTREAM_IS_SINK) {
      notify(ctx, "Vacant：裝機時沒找到你的模型端點 ⇒ proxyd **沒有真上游**，每一通模型呼叫都會被擋（502，fail-closed，不會偷偷直連）。修法：`vacant uninstall` 後 `vacant install --agent pi --upstream openai=<你的端點>`；暫時要用原模型打 /vacant off。", "error");
    } else {
      if (!BORROWED) {
        notify(ctx, "Vacant：models.json 裡沒有 baseUrl 等於 " + UPSTREAM + " 的 provider ⇒ 送的是佔位金鑰；上游要金鑰就會 401。", "warning");
      }
      if (MODEL_SOURCE === "default") {
        notify(ctx, "Vacant：provider「" + PROVIDER + "」的模型清單是猜的（只有 " + DEFAULT_MODEL + "）——models.json 裡 baseUrl 等於 " + UPSTREAM + " 的 provider 沒有 `models`，裝機時不帶金鑰的探測也沒拿到清單。你的上游沒有這個 id 就每一通 404；修法：在那個 provider 的 `models` 列出你用的模型。", "warning");
      }
    }
    await switchOn(pi, ctx, "session_start");
  });
  pi.on("before_agent_start", () => { fire("user_prompt_submit", { source: "pi-extension" }); });
  pi.on("tool_call", (event) => {
    fire("pre_tool_use", { tool_name: event && event.toolName, tool_input: (event && event.input) || {} });
  });
  pi.on("tool_result", (event) => { fire("tool_result", { tool_name: event && event.toolName }); });
  pi.on("before_provider_request", () => { fire("before_provider_request", {}); });
  pi.on("model_select", (event) => {
    // 使用者用 /model／Ctrl+P 切換（event.source＝"set"／"cycle"／"restore"）。**留痕，不擋。**
    // 不變式：每一次轉換（任一方向）恰好一筆——
    //   · 切離 vacant ⇒ vacant_off；/vacant off 自己寫過（offInProgress）⇒ 跳過。
    //   · 切回 vacant ⇒ vacant_on；switchOn 自己會寫（onInProgress）⇒ 跳過。
    //     少了這條，Ctrl+P 切走再切回來，日誌會一路說「off」而呼叫其實又經過 Vacant 了（實測）。
    //   · vacant↔vacant（換 vacant 底下的模型）、別家↔別家 不是轉換 ⇒ 不寫。
    const m = event && event.model;
    if (!m) return;
    const prev = event.previousModel;
    const wasVacant = prev && prev.provider ? prev.provider === PROVIDER : onVacantNow;   // null＝不知道 ⇒ 當成轉換
    const source = event.source || "model_select";
    const toVacant = m.provider === PROVIDER;
    onVacantNow = toVacant;
    if (toVacant) {
      if (onInProgress || wasVacant === true) return;
      if (prev && prev.provider) previous = { provider: prev.provider, id: prev.id };   // /vacant off 切回它
      fire("vacant_on", { source, model: m.provider + "/" + m.id,
                          from: prev && prev.provider ? prev.provider + "/" + prev.id : null });
    } else {
      if (offInProgress || wasVacant === false) return;
      fire("vacant_off", { from: PROVIDER, to: m.provider + "/" + m.id, source });
    }
  });
  pi.on("agent_end", () => { fire("stop", {}); });
  pi.on("session_shutdown", () => { fire("session_end", {}); });
}
"""


def render(*, port: int, state_dir: str, python: str | None = None,
           package_path: str = "", models: list[str] | None = None,
           default_model: str | None = None, upstream: str = "",
           upstream_is_sink: bool = False, key_from: str = "",
           pi_agent_dir: str = "") -> str:
    """把 extension 渲染成文字。**純函式**：不讀環境、不碰檔案。

    ⚠ 參數裡**沒有金鑰**，也不准加：金鑰在 pi 行程裡借（誠實邊界 7）。
    """
    py = python or sys.executable
    return _TEMPLATE % {
        "mark": MARK,
        "py": json.dumps(py),
        "hook_args": json.dumps(["-m", "vacant_network.vrun.hookcli"]),
        "pypath": json.dumps(package_path),
        "state": json.dumps(state_dir),
        "port": json.dumps(int(port)),
        "proxy": json.dumps(f"http://127.0.0.1:{int(port)}"),
        "provider": json.dumps(PROVIDER_ID),
        "models": json.dumps(list(models or []), ensure_ascii=False),
        "default_model": json.dumps(default_model or DEFAULT_MODEL),
        "upstream": json.dumps(upstream or ""),
        "upstream_is_sink": json.dumps(bool(upstream_is_sink)),
        "key_from": json.dumps(key_from or ""),
        "pi_agent_dir": json.dumps(pi_agent_dir or ""),
    }


def probe_models(port: int, timeout: float = 5.0) -> list[str]:
    """裝機當下透過 proxyd 問一次 `/v1/models`，拿到就烤進 extension。

    拿不到（上游是 sink、沒開）⇒ 回空清單，**不是錯**：extension 會退回
    `DEFAULT_MODEL`／`VACANT_AGENT_MODEL`，並靠 `refreshModels` 之後再抓。
    ⚠ 本探測**不帶 Authorization** ⇒ 上游要金鑰就 401 ⇒ 也回空清單（2026-09-24 實測）。
    那時靠的是 extension 在 pi 行程裡借 `models.json` 同一個 provider 的 `models`
    （誠實邊界 9），不是這裡。
    """
    import urllib.request
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{int(port)}/v1/models?vacant_canary=install",
                timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:                                        # noqa: BLE001
        return []
    data = body.get("data") if isinstance(body, dict) else None
    out: list[str] = []
    for m in data or []:
        mid = m.get("id") if isinstance(m, dict) else None
        if isinstance(mid, str) and mid and mid not in out:
            out.append(mid)
    return out
