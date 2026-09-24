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
4. **fail-closed 不用另外寫**：模型一旦指到 `vacant` provider，proxyd 沒起來就是
   connection refused，pi 不會自己換 provider。`session_start` 會探一次並通知，讓使用者
   分得出「Vacant 那一層壞了」與「模型壞了」。
5. **互動 session 不出裁決收據。** 閘門（驗收＋`ws_verdict`）仍然在 `pi -p` 經 PATH shim
   那一條；互動模式的閘門要掛在 `agent_before_settle`，那是另一份裁決（`decisions/notes/
   NOTE_20260922_PI_OPENCODE_SLASH_VACANT_PLAN.md` §3.3），本檔**沒有做**。
6. 掛鉤日誌**只落雜湊**（`hookcli` 邊界 1）；本檔不落 prompt、不落工具輸入原文。
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

function modelDef(id) {
  return { id, name: id, reasoning: false, input: ["text"],
           cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
           contextWindow: 131072, maxTokens: 16384 };
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

// ── 狀態：這個 session 有沒有開、開之前用的是哪個模型 ────────────────────────
let enabled = true;
let previous = null;   // {provider, id} —— /vacant off 切回去用
// /vacant off 自己已經寫過一筆 vacant_off；它接著呼叫 pi.setModel(previous) 會觸發
// model_select，那一筆不可以再寫第二次（不變式：每一次切離 vacant 恰好一筆痕跡）。
let offInProgress = false;

function pickVacantModel(ctx) {
  const reg = ctx && ctx.modelRegistry;
  if (!reg) return null;
  const want = process.env.VACANT_AGENT_MODEL || DEFAULT_MODEL;
  const ids = [want, ...BAKED_MODELS];
  for (const id of ids) {
    try { const m = reg.find(PROVIDER, id); if (m) return m; } catch (e) { /* 下一個 */ }
  }
  try {
    const all = typeof reg.getAll === "function" ? reg.getAll() : [];
    for (const m of all) if (m && m.provider === PROVIDER) return m;
  } catch (e) { /* 沒有 */ }
  return null;
}

async function switchOn(pi, ctx, why) {
  const cur = ctx && ctx.model;
  if (cur && cur.provider === PROVIDER) return true;
  const target = pickVacantModel(ctx);
  if (!target) {
    notify(ctx, "Vacant：找不到 provider「" + PROVIDER + "」的模型 ⇒ 沒有切換。**這個 session 沒經過 Vacant。**", "error");
    fire("vacant_on_failed", { reason: "no_model" });
    return false;
  }
  previous = cur ? { provider: cur.provider, id: cur.id } : previous;
  const ok = await pi.setModel(target);
  if (!ok) {
    notify(ctx, "Vacant：pi.setModel 回 false（provider 沒有 auth？）⇒ 沒有切換。**這個 session 沒經過 Vacant。**", "error");
    fire("vacant_on_failed", { reason: "setModel_false" });
    return false;
  }
  fire("vacant_on", { source: why, model: target.provider + "/" + target.id });
  return true;
}

export default function (pi) {
  // ── 通道：runtime 註冊 provider，**不動使用者的 models.json** ──────────────
  pi.registerProvider(PROVIDER, {
    name: "Vacant（常駐 proxyd :" + PORT + "）",
    baseUrl: BASE,
    apiKey: "sk-vacant-possess",      // 佔位；proxyd sentinel="" ⇒ Authorization 原樣穿透
    api: "openai-completions",
    compat: { supportsDeveloperRole: false, supportsReasoningEffort: false },
    models: (BAKED_MODELS.length ? BAKED_MODELS : [DEFAULT_MODEL]).map(modelDef),
    // 上游目錄變了就重抓；這一通同時是一次會進 journal 的 canary。
    // ⚠ **永遠不回空清單、也不 throw**：proxyd 起來了但上游是 sink／掛了時，
    //   /v1/models 會回 502（常常不是 JSON）或 JSON 錯誤體。若照回 `[]`（或拋錯讓 pi
    //   自己決定），pi 可能拿它蓋掉 provider 的模型清單 ⇒ 烤進去的模型消失、
    //   pickVacantModel 找不到 ⇒ `/vacant on`／session_start 報「沒有模型」而**沒有切過去**，
    //   使用者就安靜地停在原 provider 上。那不是 fail-closed，是 fail-open。
    //   pi 0.87.0 對 refreshModels 拋錯時保留舊清單還是清空，NOTE_20260922 沒有讀到
    //   ⇒ 不賭它：非 2xx／例外／空清單一律回烤進去的那份。模型仍指到 vacant，
    //   上游壞掉就在連線那一刻失敗（誠實邊界 4），而不是在選模型那一刻繞開。
    async refreshModels({ signal }) {
      const baked = () => (BAKED_MODELS.length ? BAKED_MODELS : [DEFAULT_MODEL]).map(modelDef);
      try {
        const r = await fetch(BASE + "/models?vacant_canary=refresh-" + runId, { signal });
        if (!r || !r.ok) return baked();
        const body = await r.json();
        const data = Array.isArray(body && body.data) ? body.data : [];
        const out = data.filter((m) => m && typeof m.id === "string").map((m) => modelDef(m.id));
        return out.length ? out : baked();
      } catch (e) {
        return baked();
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
      const sub = String(args || "").trim().split(/\s+/)[0] || "status";
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
    await switchOn(pi, ctx, "session_start");
  });
  pi.on("before_agent_start", () => { fire("user_prompt_submit", { source: "pi-extension" }); });
  pi.on("tool_call", (event) => {
    fire("pre_tool_use", { tool_name: event && event.toolName, tool_input: (event && event.input) || {} });
  });
  pi.on("tool_result", (event) => { fire("tool_result", { tool_name: event && event.toolName }); });
  pi.on("before_provider_request", () => { fire("before_provider_request", {}); });
  pi.on("model_select", (event) => {
    // 使用者用 /model 切走 ＝ 這一段不經過 Vacant。**留痕，不擋。**
    // /vacant off 切回去時那一筆已經由指令寫過 ⇒ 這裡跳過，不重複。
    const m = event && event.model;
    if (m && m.provider !== PROVIDER && !offInProgress) {
      fire("vacant_off", { from: PROVIDER, to: m.provider + "/" + m.id, source: (event && event.source) || "model_select" });
    }
  });
  pi.on("agent_end", () => { fire("stop", {}); });
  pi.on("session_shutdown", () => { fire("session_end", {}); });
}
"""


def render(*, port: int, state_dir: str, python: str | None = None,
           package_path: str = "", models: list[str] | None = None,
           default_model: str | None = None) -> str:
    """把 extension 渲染成文字。**純函式**：不讀環境、不碰檔案。"""
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
    }


def probe_models(port: int, timeout: float = 5.0) -> list[str]:
    """裝機當下透過 proxyd 問一次 `/v1/models`，拿到就烤進 extension。

    拿不到（上游是 sink、沒開）⇒ 回空清單，**不是錯**：extension 會退回
    `DEFAULT_MODEL`／`VACANT_AGENT_MODEL`，並靠 `refreshModels` 之後再抓。
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
