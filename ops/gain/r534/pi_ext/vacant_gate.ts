/*
 * 這支在架構裡承重什麼：R534 的「可究責層裝在別人的 agent harness 上」的接線。
 *
 * Vacant 的核心是三件事，這支負責把它們接到 pi 的掛鉤上——**但一件判斷都不自己做**：
 *
 *   (1) 跑客戶的可執行驗收測試當交付閘門
 *         -> on("agent_settled") 時問 sidecar 的 `settled`，由 Python 跑
 *            ops/gain/r530/acceptance.run_suite(suite="visible")
 *   (2) 沒過就重抽／重改，仍沒過就拒絕交付
 *         -> sidecar 回 action："feedback" 就 pi.sendUserMessage() 貼回同一段
 *            session（重改）、"stop" 就 ctx.shutdown()（重抽由 driver 重置工作區
 *            重開一份，或直接拒交）
 *   (3) 每一步簽進 Ed25519 hash chain 收據
 *         -> 由 sidecar 呼叫 vacant_network/logbook.py。私鑰只在 driver 行程的記憶體裡，
 *            不落盤（RECORD_SPEC §7）
 *
 * **為什麼判斷不寫在這裡**：沙箱、DENY 正則、驗收判準、預算判準在 Python 各只有
 * 一份。在 TS 再寫一份就是第二把會漂的尺，而且漂掉那天沒有人會發現，
 * 因為兩份各自都「看起來對」。所以這支只做四件事：接線、斷言、落盤、轉交。
 *
 * 四格（A1/A2/B1/B2）共用**同一支擴充、同一段 system prompt、同一個工具、
 * 同一份預算上限**。唯一的兩個差異：
 *   · `arm`："vacant" 進閘門、"plain" 宣告完成就收（sidecar 那一側分岔）
 *   · `reasoning_effort`：由 models.json 的 samplingParams 決定，
 *     本支只**斷言**它在 wire 上是不是預期的樣子，不偷偷補、不偷偷拿掉。
 *
 * ⚠ 紅線：hidden tests 的路徑不出現在本檔，也不出現在任何送回模型的字串裡。
 *   回饋只轉發 sidecar 對**可見**驗收的渲染。
 *
 * ⚠ 誠實邊界（改碼請保留）：本支 records、asserts and gates，不 proves。
 *   它證明「宣告完成之後可見驗收先跑了一次、沒過就沒出貨」，不證明模型沒有別的
 *   路徑繞過 harness，也不證明可見驗收涵蓋真需求（單邊保證）。
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
import { connect } from "node:net";
import { Type } from "typebox";

type Cfg = {
  sock: string;
  cell: string;
  arm: "vacant" | "plain";
  policy: "revise" | "resample";
  task_id: string;
  attempt: number;
  model: string;
  provider: string;
  system_prompt: string;
  run_bash_description: string;
  expect_reasoning_effort_none: boolean;
  tool_timeout_s: number;
  tool_timeout_max_s: number;
  ext_log: string;
};

const CFG: Cfg = JSON.parse(
  readFileSync(process.env.R534_CONFIG as string, "utf8"),
) as Cfg;

function sha256(s: string): string {
  return createHash("sha256").update(s, "utf8").digest("hex");
}

/** 擴充自己那一份逐字紀錄。**同步寫**：行程被砍也不會掉最後幾筆（鐵律 3）。 */
function jot(rec: Record<string, unknown>): void {
  mkdirSync(dirname(CFG.ext_log), { recursive: true });
  appendFileSync(
    CFG.ext_log,
    JSON.stringify({ ts_ms: Date.now(), cell: CFG.cell, task_id: CFG.task_id, attempt: CFG.attempt, ...rec }) + "\n",
    "utf8",
  );
}

/** sidecar 呼叫：一個連線一個請求一個回應。沙箱指令可能跑到 300 秒，所以不設短 timeout。 */
function ask(req: Record<string, unknown>): Promise<any> {
  return new Promise((resolve, reject) => {
    const sock = connect(CFG.sock);
    let buf = "";
    let done = false;
    const finish = (fn: (v: any) => void, v: any) => {
      if (done) return;
      done = true;
      try { sock.destroy(); } catch { /* 已經關了就算了 */ }
      fn(v);
    };
    sock.setTimeout(3_600_000);
    sock.on("connect", () => { sock.write(JSON.stringify(req) + "\n"); });
    sock.on("data", (chunk) => {
      buf += chunk.toString("utf8");
      const nl = buf.indexOf("\n");
      if (nl >= 0) {
        try { finish(resolve, JSON.parse(buf.slice(0, nl))); }
        catch (err) { finish(reject, err); }
      }
    });
    sock.on("error", (err) => finish(reject, err));
    sock.on("timeout", () => finish(reject, new Error("sidecar timeout")));
    sock.on("close", () => {
      if (!done) finish(reject, new Error("sidecar closed without a reply"));
    });
  });
}

/** 落盤 ＋ 通知 sidecar（不等回應：落盤那一份已經是證據）。 */
function emit(rec: Record<string, unknown>): void {
  jot(rec);
  ask({ op: "event", record: rec }).catch((err) => {
    jot({ kind: "sidecar_event_failed", error: String(err), of: rec.kind });
  });
}

export default function (pi: ExtensionAPI) {
  let stopped = false;          // 已經收到 stop，之後的 settled 一律不動作
  let voided = false;           // 不變量破了 ⇒ 這一格作廢
  let callsUsed = 0;
  let toolCalls = 0;
  let completionTokens = 0;
  let promptTokens = 0;
  let reasoningTokens = 0;
  let lastPromptTokens = 0;

  /** 不變量破了：**立刻停**，不要偷偷修好繼續跑（零容忍）。 */
  function voidCell(reason: string, detail: Record<string, unknown>, ctx: any): void {
    if (voided) return;
    voided = true;
    stopped = true;
    emit({ kind: "harness_void", reason, ...detail });
    try { ctx.abort?.(); } catch { /* 沒有正在跑的 turn 就沒事 */ }
    try { ctx.shutdown?.(); } catch { /* 同上 */ }
  }

  // ── 1. 握手：起點樹雜湊對不上就收掉（起點不對，後面全白跑）──────────
  pi.on("session_start", async (event, ctx) => {
    const resp = await ask({
      op: "hello", cwd: ctx.cwd, mode: ctx.mode, reason: (event as any).reason,
      pid: process.pid,
    }).catch((err) => ({ ok: false, error: String(err) }));
    jot({ kind: "session_start", mode: ctx.mode, cwd: ctx.cwd, hello: resp });
    if (!resp || resp.ok !== true) {
      voidCell("hello_failed", { hello: resp }, ctx);
      return;
    }
    pi.setActiveTools(["run_bash"]);
    jot({ kind: "active_tools", tools: pi.getActiveTools() });
  });

  // ── 2. 唯一的工具。執行**不在這裡**：丟給 sidecar 的沙箱 ──────────────
  pi.registerTool({
    name: "run_bash",
    label: "run_bash",
    description: CFG.run_bash_description,
    parameters: Type.Object({
      command: Type.String({ description: "The shell command to run." }),
      timeout_s: Type.Optional(
        Type.Number({ description: "Seconds to allow the command to run." }),
      ),
    }),
    async execute(_toolCallId: string, params: any) {
      toolCalls += 1;
      const command = String(params?.command ?? "");
      const timeout_s = Number(params?.timeout_s ?? CFG.tool_timeout_s);
      const resp = await ask({ op: "exec", command, timeout_s });
      if (!resp || resp.ok !== true) {
        // 沙箱起不來＝基建故障，不是候選的錯。讓它以 isError 回給模型，
        // 同時 sidecar 那一側已經把 infra_void 記下來了。
        jot({ kind: "tool_infra_error", command, resp });
        throw new Error(`sandbox unavailable: ${JSON.stringify(resp)}`);
      }
      jot({ kind: "tool_done", command, blocked: !!resp.blocked, rc: resp.rc ?? null, deny_tag: resp.deny_tag ?? null });
      return { content: [{ type: "text", text: String(resp.text ?? "") }] };
    },
  } as any);

  // ── 3. system prompt：**整段取代**成凍結字串（四格逐位元相同）────────
  //
  // 用取代而不是檢查：pi 會把 AGENTS.md／SYSTEM.md／skills／tool snippets
  // 串進去，那些東西隨機器狀態改變 ⇒ 用檢查的，四格會在不同時間以不同方式紅。
  // 工具說明不會因此消失——pi 走 native tool-calling，schema 在 payload.tools。
  pi.on("before_agent_start", async (event) => {
    jot({
      kind: "before_agent_start",
      prompt_sha256: sha256(String((event as any).prompt ?? "")),
      pi_system_prompt_sha256: sha256(String((event as any).systemPrompt ?? "")),
      frozen_system_prompt_sha256: sha256(CFG.system_prompt),
    });
    return { systemPrompt: CFG.system_prompt };
  });

  // ── 4. header 蓋章：wire.jsonl 的歸屬不必只靠「哪個埠」──────────────
  pi.on("before_provider_headers", (event) => {
    const h = (event as any).headers as Record<string, string | null>;
    h["x-r534-cell"] = CFG.cell;
    h["x-r534-arm"] = CFG.arm;
    h["x-r534-task"] = CFG.task_id;
    h["x-r534-attempt"] = String(CFG.attempt);
  });

  // ── 5. wire 斷言：**這是唯一看得到真正要送出去的 payload 的地方** ──────
  //
  // 同步 handler：回傳 undefined ⇒ payload 不變。**不補、不改、不修**——
  // 這裡的工作是「說出 wire 上是什麼」，不是把它弄成該有的樣子。
  pi.on("before_provider_request", (event, ctx) => {
    const payload = (event as any).payload ?? {};
    const keys = Object.keys(payload).sort();
    const hasEffort = Object.prototype.hasOwnProperty.call(payload, "reasoning_effort");
    const effort = hasEffort ? payload.reasoning_effort : "<absent>";
    const sysMsg = Array.isArray(payload.messages)
      ? payload.messages.find((m: any) => m?.role === "system" || m?.role === "developer")
      : undefined;
    const sysText = typeof sysMsg?.content === "string"
      ? sysMsg.content
      : JSON.stringify(sysMsg?.content ?? null);
    const rec = {
      kind: "provider_request",
      keys,
      model: payload.model ?? null,
      reasoning_effort: effort,
      stream: payload.stream ?? null,
      stream_options: payload.stream_options ?? null,
      temperature: payload.temperature ?? null,
      max_completion_tokens: payload.max_completion_tokens ?? null,
      messages_n: Array.isArray(payload.messages) ? payload.messages.length : null,
      system_role: sysMsg?.role ?? null,
      system_prompt_sha256: sysText ? sha256(sysText) : null,
      tools_schema_sha256: sha256(JSON.stringify(payload.tools ?? null)),
    };
    emit(rec);

    // 零容忍：旗標與宣告的不一樣 ⇒ 這一格作廢，不要繼續產生看起來正常的資料。
    const wantNone = CFG.expect_reasoning_effort_none;
    const ok = wantNone ? effort === "none" : !hasEffort;
    if (!ok) {
      voidCell("reasoning_effort_mismatch",
        { want_none: wantNone, got: effort, keys }, ctx);
      return undefined;
    }
    if (payload.model !== CFG.model) {
      voidCell("model_mismatch", { want: CFG.model, got: payload.model ?? null }, ctx);
      return undefined;
    }
    if (sysText && sha256(sysText) !== sha256(CFG.system_prompt)) {
      voidCell("system_prompt_mismatch",
        { want_sha256: sha256(CFG.system_prompt), got_sha256: sha256(sysText) }, ctx);
      return undefined;
    }
    return undefined;
  });

  pi.on("after_provider_response", (event) => {
    jot({ kind: "provider_response_head", status: (event as any).status ?? null,
          headers: (event as any).headers ?? null });
  });

  // ── 6. 自動壓縮：取消 ────────────────────────────────────────────────
  //
  // 自動壓縮會把「脈絡用光」這個**真實行為**變成看不見的東西。
  // 我們要的是它撞成 budget_context，而不是被悄悄縮掉繼續跑。
  pi.on("session_before_compact", async (event) => {
    emit({ kind: "compaction_cancelled", reason: (event as any).reason ?? null });
    return { cancel: true };
  });

  // ── 7. 訊息全文 ＋ 預算 ──────────────────────────────────────────────
  pi.on("message_end", async (event) => {
    const msg = (event as any).message;
    await ask({ op: "message", message: msg }).catch((err) => {
      jot({ kind: "sidecar_message_failed", error: String(err) });
    });
  });

  pi.on("turn_end", async (event, ctx) => {
    callsUsed += 1;
    const msg = (event as any).message ?? {};
    const usage = msg.usage ?? {};
    completionTokens += Number(usage.output ?? 0);
    promptTokens += Number(usage.input ?? 0);
    reasoningTokens += Number(usage.reasoning ?? 0);
    lastPromptTokens = Number(usage.input ?? 0);
    const resp = await ask({
      op: "turn_end", usage,
      // pi 連不上 provider 時會自己重試三次然後**安靜地**以空訊息結束
      // （stopReason "error"）⇒ 不回報這一格，一整批會長出看起來正常的空白資料。
      assistant_stop_reason: msg.stopReason ?? null,
      error_message: msg.errorMessage ?? null,
      calls_used: callsUsed, tool_calls: toolCalls,
      completion_tokens: completionTokens, prompt_tokens: promptTokens,
      reasoning_tokens: reasoningTokens, last_prompt_tokens: lastPromptTokens,
    }).catch((err) => ({ ok: false, error: String(err) }));
    jot({ kind: "turn_end", usage, calls_used: callsUsed, tool_calls: toolCalls, budget: resp });
    if (resp && resp.stop_reason) {
      stopped = true;
      jot({ kind: "budget_stop", stop_reason: resp.stop_reason });
      try { ctx.abort?.(); } catch { /* 沒有正在跑的 turn */ }
      try { ctx.shutdown?.(); } catch { /* rpc 模式會等到 idle */ }
    }
  });

  pi.on("tool_execution_end", async (event) => {
    jot({
      kind: "tool_execution_end",
      tool: (event as any).toolName,
      tool_call_id: (event as any).toolCallId,
      is_error: (event as any).isError ?? null,
      result: (event as any).result ?? null,
    });
  });

  // ── 8. 閘門本體：**四格唯一的分岔點** ────────────────────────────────
  //
  // `agent_settled` 的語意就是「沒有待處理的自動重試、壓縮或排隊訊息了」，
  // 也就是 R530 那句「回覆裡沒有 bash 圍欄」＝宣告完成。
  // `agent_end` 還可能自動重試，所以不能掛在那裡。
  pi.on("agent_settled", async (_event, ctx) => {
    if (stopped || voided) {
      jot({ kind: "settled_ignored", stopped, voided });
      return;
    }
    const resp = await ask({ op: "settled" }).catch((err) => ({ ok: false, error: String(err) }));
    jot({ kind: "settled", resp });
    if (!resp || resp.ok !== true) {
      voidCell("settled_failed", { resp }, ctx);
      return;
    }
    if (resp.action === "nudge" || resp.action === "feedback") {
      pi.sendUserMessage(String(resp.message), { deliverAs: "followUp" });
      jot({ kind: "sent_back", action: resp.action,
            message_sha256: sha256(String(resp.message)),
            message: String(resp.message) });
      return;
    }
    stopped = true;
    jot({ kind: "stop", stop_reason: resp.stop_reason, accepted: resp.accepted,
          final: resp.final });
    try { ctx.shutdown?.(); } catch (err) { jot({ kind: "shutdown_error", error: String(err) }); }
  });

  // ── 9. 收官：簽 ws_verdict ──────────────────────────────────────────
  pi.on("session_shutdown", async (event) => {
    const resp = await ask({ op: "final", reason: (event as any).reason ?? null })
      .catch((err) => ({ ok: false, error: String(err) }));
    jot({ kind: "session_shutdown", reason: (event as any).reason ?? null,
          final: resp, calls_used: callsUsed, tool_calls: toolCalls });
  });
}
