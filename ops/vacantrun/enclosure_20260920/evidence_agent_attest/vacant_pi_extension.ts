// Vacant 掛鉤契約 vacant-hook/1 —— pi 0.85.1（extensions/ 底下自動載入）。
// 只紀錄，不擋（見 hookcli.py 誠實邊界 2）。**唯一的例外**是
// VACANT_PI_MUTATE_TOOL_INPUT：那是「掛鉤改不改得動工具輸入」那一格的探針，
// 預設整段不執行。
import { spawnSync } from "node:child_process";
import { appendFileSync } from "node:fs";

const PY = "/usr/bin/python3";
const ARGS = ["-m", "vacant_network.vrun.hookcli"];

function fire(event, payload) {
  try {
    spawnSync(PY, [...ARGS, event], {
      input: JSON.stringify(payload || {}),
      timeout: 20000, stdio: ["pipe", "ignore", "ignore"],
    });
  } catch (e) { /* 掛鉤壞掉不可以弄死 agent（誠實邊界 3） */ }
}

// 診斷線：**跟契約日誌分開**。契約只落雜湊（誠實邊界 1），這一條落的是
// 欄位名、長度這種不含使用者內容的東西，而且只有 VACANT_PI_DIAG 有值才寫。
function diag(rec) {
  try {
    const p = process.env.VACANT_PI_DIAG;
    if (!p) return;
    rec.ts = Date.now() / 1000;
    appendFileSync(p, JSON.stringify(rec) + "\n");
  } catch (e) { /* 同上 */ }
}

// 工具輸入改寫探針。規格 JSON：{"tool":"<可選>","from":"<子字串>","to":"<替換>"}
// ⚠ 預設不開。開了才改，而且**改了什麼一定落一筆 diag**——
//   「hook 能改工具輸入」這句話的證據是**落盤的那個檔**，不是這一筆紀錄，
//   但沒有這一筆就分不出「改了」與「agent 本來就那樣叫」。
function mutateInput(event) {
  let spec = null;
  try { spec = JSON.parse(process.env.VACANT_PI_MUTATE_TOOL_INPUT || ""); }
  catch (e) { return; }
  if (!spec || !spec.from) return;
  if (spec.tool && spec.tool !== (event && event.toolName)) return;
  const changed = [];
  const input = (event && event.input) || {};
  for (const k of Object.keys(input)) {
    const v = input[k];
    if (typeof v === "string" && v.indexOf(spec.from) >= 0) {
      input[k] = v.split(spec.from).join(spec.to === undefined ? "" : spec.to);
      changed.push(k);
    }
  }
  diag({ kind: "tool_input_mutated", tool: event && event.toolName,
         fields: changed, from: spec.from, to: spec.to });
}

export default function (pi) {
  // ── 回合開端（對到 attest.TURN_OPENING_EVENTS 的那三個）──────────────
  pi.on("session_start", () => { fire("session_start", { source: "pi-extension" }); });
  pi.on("before_agent_start", () => { fire("user_prompt_submit", { source: "pi-extension" }); });
  pi.on("tool_result", (event) => { fire("tool_result", { tool_name: event && event.toolName }); });

  // ── 非回合開端：紀錄用 ───────────────────────────────────────────────
  pi.on("tool_call", (event) => {
    // 先落「模型要求的是什麼」，**再**改。順序反過來的話紀錄裡只剩改完的樣子。
    fire("pre_tool_use", { tool_name: event && event.toolName,
                           tool_input: (event && event.input) || {} });
    diag({ kind: "tool_call", tool: event && event.toolName,
           input_keys: Object.keys((event && event.input) || {}) });
    mutateInput(event);
  });
  pi.on("before_provider_request", (event) => {
    let n = null;
    try { n = JSON.stringify((event && event.payload) || {}).length; } catch (e) { n = null; }
    diag({ kind: "before_provider_request", payload_chars: n });
    fire("before_provider_request", {});
  });
  pi.on("agent_end", () => { fire("stop", {}); });
  pi.on("session_shutdown", () => { fire("session_end", {}); });
}
