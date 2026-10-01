/*
 * 這支在架構裡承重什麼：數位分身（pi）**唯一**拿得到的三個工具。
 *
 * 裁決：decisions/DECISION_20260924_TWIN_AGENT_RUN.md §三。
 * 契約：plans/CONTRACT_PROCESS_20260928.md §A（步驟事件，2026-09-28）。
 *
 * 特質文字（TRAITS.md）來自觀眾——那是**觀眾可控的輸入**，也就是提示注入的入口。
 * 所以 pi 以 `--no-builtin-tools --tools ws_list,ws_read,ws_write` 啟動：
 * 內建的 bash／read／write／edit／grep／find／ls 一個都不開，只剩這裡的三個。
 *
 * ⚠ 為什麼不用內建的 read／write：它們**吃絕對路徑**，不限在工作區。
 *
 * 三個工具共同的規則（`confine()`）：
 *   · 只收**相對路徑**（絕對路徑直接拒絕）；
 *   · 解析後必須落在工作區（啟動時的 cwd，也就是 launcher 給的拋棄式工作區）之內；
 *   · 沿途任何一段是 symlink 就拒絕（不讓一條連結把「房間裡」接到房間外）；
 *   · 讀／寫單檔上限 64 KiB；
 *   · 寫入不准落在 `地上/` 底下（W3b：世界的實物，唯讀）。
 * 沒有任何一個工具會開網路連線。
 *
 * ## 步驟紀錄（`logStep`，2026-09-28）
 *
 * 每次三個工具**被呼叫**（不管成功或被 `confine()` 擋下）就往
 * `$VACANT_TWIN_STEP_LOG` 指到的檔追加一行 `{ts_ms,seq,tool,path,bytes,ok}`。
 * 那個路徑由 `twin_agent.sh` 從它自己的 `$RUN_DIR`（工作區外）算出來再 export
 * 給這個行程——**單一行程、沒有跨執行緒的環境變數競態**（Python 那一側是
 * ThreadPoolExecutor 平行跑好幾位分身，`os.environ` 不安全；bash 腳本一支一個
 * 行程沒有這個問題）。這一行**含檔名**：檔名只活在這個記錄檔（run-dir 裡，
 * 撤回時整個刪掉），電視那一側的事件流不帶檔名（`sidecar.py` 轉出
 * `twin_step` 時只留 `path_kind` 三類＋`ws_list` 的 `other`）。
 * `VACANT_TWIN_STEP_LOG` 沒設 ⇒ `logStep` 是空操作（舊行為不變，測試與
 * 沒接上這條線的呼叫端都不受影響）。
 * ⚠ 記步驟失敗（例如檔案系統滿了）**不准**改變工具本身的回傳值——這是旁註，
 *   不是驗收的一部分（同 `sidecar.py` 誠實邊界 2 的精神）。
 *
 * ⚠ 誠實邊界（改碼請保留）：
 *   1. 這是**我們寫的 TypeScript 判準**，不是作業系統的權限。pi（node）行程本身
 *      仍然有完整的檔案系統與網路權限；收住的是「模型能請 pi 做什麼」。
 *   2. 判準有可執行的 probe（ops/exhibit/twin/probe_pi_tools.py）：越界三條要被擋、
 *      正控制要寫得進去、負控制（預設工具）要真的執行得了 bash。
 *   3. pi 改版要重跑 probe。
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import {
  existsSync, lstatSync, mkdirSync, readdirSync, readFileSync, realpathSync,
  statSync, writeFileSync,
} from "node:fs";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";

const MAX_BYTES = 64 * 1024;

/** 工作區根。**啟動時就定下來**，之後 cwd 被誰改掉都不影響。 */
const ROOT = realpathSync(process.cwd());

/** 步驟記錄檔（工作區外）。沒設就是空字串 ⇒ `logStep` 全部是空操作。 */
const STEP_LOG = process.env.VACANT_TWIN_STEP_LOG || "";
let STEP_SEQ = 0;

/**
 * 記一步（每次工具被呼叫，不管成功或被擋）。**不丟例外**：記步驟這件事
 * 本身失敗不准影響工具的回傳值（誠實邊界，見檔頭）。
 */
function logStep(tool: string, path: string | null, bytes: number | null, ok: boolean): void {
  if (!STEP_LOG) return;
  STEP_SEQ += 1;
  const row = { ts_ms: Date.now(), seq: STEP_SEQ, tool, path, bytes, ok };
  try {
    mkdirSync(dirname(STEP_LOG), { recursive: true });
    writeFileSync(STEP_LOG, JSON.stringify(row) + "\n", { encoding: "utf8", flag: "a" });
  } catch {
    // 見檔頭誠實邊界：記不到步驟不影響工具本身。
  }
}

function confine(p: unknown): string {
  if (typeof p !== "string" || p.trim() === "") {
    throw new Error("path 必須是非空字串（相對於你的房間）");
  }
  if (isAbsolute(p)) {
    throw new Error("只准相對路徑：你只碰得到自己的房間");
  }
  const abs = resolve(ROOT, p);
  const rel = relative(ROOT, abs);
  if (rel === "" || rel === ".." || rel.startsWith(".." + sep) || isAbsolute(rel)) {
    throw new Error("這個路徑跑出你的房間了");
  }
  // 沿途每一段都不准是 symlink（包含最後一段）。
  let cur = ROOT;
  for (const part of rel.split(sep)) {
    cur = resolve(cur, part);
    if (existsSync(cur) && lstatSync(cur).isSymbolicLink()) {
      throw new Error("不准走 symlink");
    }
  }
  return abs;
}

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "ws_list",
    label: "ws_list",
    description: "List the files in your room (the current folder). Only your room is visible.",
    parameters: Type.Object({}),
    async execute() {
      try {
        const out: string[] = [];
        const walk = (dir: string, depth: number) => {
          if (depth > 3) return;
          for (const name of readdirSync(dir).sort()) {
            const full = resolve(dir, name);
            const st = lstatSync(full);
            const rel = relative(ROOT, full);
            if (st.isSymbolicLink()) continue;
            if (st.isDirectory()) { out.push(rel + "/"); walk(full, depth + 1); }
            else out.push(`${rel} (${st.size} bytes)`);
          }
        };
        walk(ROOT, 0);
        logStep("ws_list", null, null, true);
        return { content: [{ type: "text", text: out.join("\n") || "(empty)" }] };
      } catch (e) {
        logStep("ws_list", null, null, false);
        throw e;
      }
    },
  } as any);

  pi.registerTool({
    name: "ws_read",
    label: "ws_read",
    description: "Read a text file in your room. `path` is relative to your room.",
    parameters: Type.Object({
      path: Type.String({ description: "Relative path inside your room, e.g. TRAITS.md" }),
    }),
    async execute(_id: string, params: any) {
      const rawPath = typeof params?.path === "string" ? params.path : null;
      try {
        const abs = confine(params?.path);
        const st = statSync(abs);
        if (!st.isFile()) throw new Error("那不是一個檔案");
        if (st.size > MAX_BYTES) throw new Error(`檔案太大（上限 ${MAX_BYTES} bytes）`);
        const text = readFileSync(abs, "utf8");
        logStep("ws_read", relative(ROOT, abs), Buffer.byteLength(text, "utf8"), true);
        return { content: [{ type: "text", text }] };
      } catch (e) {
        logStep("ws_read", rawPath, null, false);
        throw e;
      }
    },
  } as any);

  pi.registerTool({
    name: "ws_write",
    label: "ws_write",
    description:
      "Write (create or overwrite) a text file in your room. `path` is relative to your room.",
    parameters: Type.Object({
      path: Type.String({ description: "Relative path inside your room, e.g. PLAN.md" }),
      content: Type.String({ description: "The full text content of the file" }),
    }),
    async execute(_id: string, params: any) {
      const rawPath = typeof params?.path === "string" ? params.path : null;
      try {
        const abs = confine(params?.path);
        // W3b：地上/ 是世界的實物（唯讀）。檔案權限只擋得住既有的檔、擋不住新建，所以在這裡擋整個資料夾。
        const relw = relative(ROOT, abs);
        if (relw === "地上" || relw.startsWith("地上" + sep)) {
          throw new Error("地上的東西是唯讀的：你寫不進地上/");
        }
        const text = String(params?.content ?? "");
        if (Buffer.byteLength(text, "utf8") > MAX_BYTES) {
          throw new Error(`內容太大（上限 ${MAX_BYTES} bytes）`);
        }
        const parent = dirname(abs);
        mkdirSync(parent, { recursive: true });
        // mkdir 之後再檢一次：父目錄沿途不可以被換成 symlink。
        confine(relative(ROOT, abs));
        writeFileSync(abs, text, "utf8");
        logStep("ws_write", relative(ROOT, abs), Buffer.byteLength(text, "utf8"), true);
        return { content: [{ type: "text", text: `wrote ${relative(ROOT, abs)}` }] };
      } catch (e) {
        logStep("ws_write", rawPath, null, false);
        throw e;
      }
    },
  } as any);
}
