"""這支在架構裡承重什麼：**掛鉤契約的那一端**——框架呼叫它，它留下證據。

`DECISION_20260920_COMPLETE_MEDIATION.md` §二把工作切成兩半：

    kernel（enclosure）給「**有沒有**」——保證，不依賴廠商。
    hook  （本檔）  給「**是什麼、為什麼**」——語意與閘門，依賴廠商。

本檔是後者的**唯一落地點**：五個 agent 的掛鉤設定各寫各的，但它們**都
呼叫同一支命令**，寫進**同一份 JSONL**，用**同一個契約版本**。多一個 agent
只要多一份設定檔，不要多一份解析器。

## 契約（`vacant-hook/1`）

環境變數（由 `gateshim`／enclosure 的 runner 設好）：

    VACANT_HOOK_LOG    事件 JSONL 落在哪（**沒有這一個就什麼都不做**）
    VACANT_RUN_ID      這一跑的 id（對帳時用來過濾）
    VACANT_HOOK_AGENT  哪個 agent（收據的 `framework_hook.agent`）
    VACANT_RUN_PROXY   canary 那一通要打去哪（沒有就只寫事件、不打）

每一行一個事件：

    {"contract":"vacant-hook/1","run_id":…,"agent":…,"event":…,
     "ts":…,"pid":…,"tool":…,"command_sha256":…,"payload_sha256":…}

## canary：**級別由探針決定**（裁決 §三-1）

`session_start` 事件會多做兩件事，這兩件就是 A 級的兩個探針：

  1. 多寫一筆 `event="canary"` ⇒ 收據的 `framework_hook.canary_fired`
     **讀的是這一行**，不是「我們有沒有寫過設定檔」。
  2. 對 `$VACANT_RUN_PROXY/v1/models?vacant_canary=<run_id>` 打一通
     ⇒ 那一通**一定**會出現在中繼的 journal 裡 ⇒ **實證 proxy 真的在跑**，
     而不是「設定檔裡寫了 proxy」。

⚠ 第 2 條是被實測逼出來的：Codex 的 `network_proxy` 關著的時候 allowlist
  **設了、不報錯、也不執行**（官方文件逐字承認那是設計不是 bug）。
  ⇒ **收據不可以只檢查設定檔寫了什麼。**

## 誠實邊界（改碼請保留）

1. **本檔不落 payload 原文，只落雜湊。** 框架丟進 stdin 的 JSON 可能含
   prompt 全文、檔案內容、甚至憑證。落雜湊 ⇒ 對得起來、又不會把使用者的
   東西寫到一個他沒預期的檔案裡。`tool` 與 `command_sha256` 是例外：
   **指令的雜湊**是閘門唯一需要的東西，指令原文一樣不落。
2. **本檔預設不擋任何東西**（`exit 0`）。它是**紀錄端**不是閘門端。
   閘門（`deny`）是 P1 的事，而且 §二 已經寫明：**保證不可以建立在 hook 上**
   （`--bare` 一個旗標就 skip hooks、Codex 的 `trusted_hash` 改一個空白就
   fail-silent）。本檔存在的理由是「是什麼」，不是「有沒有」。
3. **掛鉤自己壞掉不可以弄死 agent。** 任何例外都吞掉並回 0；
   寫不進日誌的後果是**收據降級**（`canary_fired=False`），那正確——
   量不到就是量不到，不是假裝量到了。
4. **`canary_fired=True` 只證明這一次燒了**，不證明下一次還在（邊界 4，
   `vacant_network/vrun/attest.py`）。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

from .attest import CANARY_QUERY_KEY, CONTRACT_VERSION

#: canary 那一通的逾時。短——它卡住就等於掛鉤卡住 agent。
CANARY_TIMEOUT_S = 5.0


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _log_path() -> pathlib.Path | None:
    p = os.environ.get("VACANT_HOOK_LOG")
    return pathlib.Path(p) if p else None


def emit(event: str, **fields) -> bool:
    """寫一筆事件。回 `True` ＝寫進去了。**寫不進去不 raise**（邊界 3）。"""
    p = _log_path()
    if p is None:
        return False
    rec = {"contract": CONTRACT_VERSION,
           "run_id": os.environ.get("VACANT_RUN_ID"),
           "agent": os.environ.get("VACANT_HOOK_AGENT"),
           "event": event, "ts": time.time(), "pid": os.getpid(), **fields}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())    # 被砍也要留得住（鐵律 3）
        return True
    except OSError:
        return False


def fire_relay_canary() -> dict:
    """對中繼打一通**一定會進 journal** 的請求。回一份結果（不 raise）。

    path 用 `/v1/models`（在 `wireproxy.MODEL_PATHS` 名單上 ⇒ `path_policy=model`
    的門會放行），query 帶 `vacant_canary=<run_id>` ⇒ 對帳時認得出它是 canary
    而不是 agent 真的在叫模型。
    """
    base = (os.environ.get("VACANT_RUN_PROXY") or "").rstrip("/")
    run_id = os.environ.get("VACANT_RUN_ID") or "norunid"
    out: dict = {"attempted": bool(base), "url": None, "status": None,
                 "error": None}
    if not base:
        out["error"] = "沒有 $VACANT_RUN_PROXY ⇒ 沒打（沒量到，不是「打了失敗」）"
        return out
    url = f"{base}/v1/models?{CANARY_QUERY_KEY}={run_id}"
    out["url"] = url
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"vacant-canary/{CONTRACT_VERSION}")
        with urllib.request.urlopen(req, timeout=CANARY_TIMEOUT_S) as r:
            out["status"] = r.status
            r.read(4096)
    except urllib.error.HTTPError as e:
        # ⚠ 4xx／5xx **也算打到了**：那一通照樣進 journal（門的 403、
        #   fail-closed sink 的 502 都是）。canary 要的是「有沒有經過中繼」，
        #   不是「上游高不高興」。
        out["status"] = e.code
    except Exception as e:                                   # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def handle(event: str, stdin_bytes: bytes = b"") -> int:
    """框架呼叫的入口。**永遠回 0**（邊界 3）。"""
    payload: dict = {}
    if stdin_bytes:
        try:
            loaded = json.loads(stdin_bytes.decode("utf-8", "replace"))
            payload = loaded if isinstance(loaded, dict) else {}
        except ValueError:
            payload = {}
    fields: dict = {"payload_sha256": _sha256(stdin_bytes) if stdin_bytes
                    else None}
    # ⚠ 只落「是哪一個工具、指令的雜湊」，**不落指令原文**（邊界 1）
    tool = (payload.get("tool_name") or payload.get("tool")
            or (payload.get("tool_input") or {}).get("name"))
    if isinstance(tool, str):
        fields["tool"] = tool
    cmd = ((payload.get("tool_input") or {}).get("command")
           or payload.get("command"))
    if isinstance(cmd, str):
        fields["command_sha256"] = _sha256(cmd.encode("utf-8"))
        fields["command_bytes"] = len(cmd.encode("utf-8"))
    emit(event, **fields)
    if event == "session_start":
        # ⚠ **順序是規格不是風格**：`canary` 這一行要寫在那一通打出去**之前**。
        #   對帳的判準是「一通呼叫之前有沒有一個還沒被消耗掉的回合開端」，
        #   先打再寫的話 canary 自己那一通會變成 `unexplained`——
        #   2026-09-20 實測過這個假陽性。
        emit("canary",
             note=("這一行就是 `framework_hook.canary_fired` 的唯一依據——"
                   "讀的是掛鉤自己寫的，不是「我們裝過了」"))
        canary = fire_relay_canary()
        # 結果另外一行：它**不是**回合開端（不會再引起一通），
        # 所以不可以跟上面那一行合併。
        emit("canary_result", relay_canary=canary)
    return 0


# ── 安裝：每個 agent 一份設定，**都指向本檔** ──────────────────────────
#
#   ⚠ 這幾支寫的是 **per-run 的設定目錄**（`gateshim.exec_inner` 那一份），
#     不是使用者常駐的那一份。理由跟 `exec_inner` 一樣：那一跑要指向
#     這一跑自己的東西，而且**跑完就跟著 per-run 目錄一起消失**。
#   ⚠ 裝了**不等於**會燒。會不會燒由 `attest.probe_framework_hook` 讀日誌決定。

#: 本檔可以自己裝掛鉤的 agent。**不在這份名單上的＝這條線還沒開採**，
#: 收據上會是 `canary_fired=null`（沒量到），不是 `false`。
INSTALLERS = ("claude", "opencode")


def hook_command() -> list[str]:
    """框架要執行的那一串。用 `sys.executable -m` ⇒ 不依賴 PATH 上有 `vacant`。"""
    return [sys.executable, "-m", "vacant_network.vrun.hookcli"]


def _hook_env(hook_log: str, agent: str, run_id: str,
              proxy: str | None) -> dict[str, str]:
    env = {"VACANT_HOOK_LOG": str(hook_log),
           "VACANT_RUN_ID": run_id, "VACANT_HOOK_AGENT": agent}
    if proxy:
        env["VACANT_RUN_PROXY"] = proxy
    return env


def install_claude(cfg_dir: pathlib.Path, *, hook_log: str, run_id: str,
                   proxy: str | None) -> dict:
    """Claude Code：`<CLAUDE_CONFIG_DIR>/settings.json` 的 `hooks` 區塊。

    ⚠ `DECISION_20260920_AGENT_HOOKS_MEASURED.md` 量到：這份設定是 `$HOME`
      底下的普通檔，**agent 自己的寫檔工具刪得掉**（實測 `d.pop('hooks')`
      之後零觸發）。所以它是「語意」不是「保證」——而它被刪掉的那一跑，
      canary 不會燒 ⇒ 收據**自動降級**，這正是要的行為。
    """
    cmd = " ".join(hook_command())
    def _h(ev: str) -> dict:
        return {"hooks": [{"type": "command", "command": f"{cmd} {ev}"}]}
    doc = {"hooks": {
        "SessionStart": [_h("session_start")],
        "UserPromptSubmit": [_h("user_prompt_submit")],
        "PreToolUse": [{"matcher": "*", **_h("pre_tool_use")}],
        "PostToolUse": [{"matcher": "*", **_h("post_tool_use")}],
        "Stop": [_h("stop")],
        "SessionEnd": [_h("session_end")],
    }}
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "settings.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"agent": "claude", "target": str(cfg_dir / "settings.json"),
            "env": _hook_env(hook_log, "claude", run_id, proxy),
            "events": sorted(doc["hooks"])}


#: OpenCode plugin 的本體。**純 JS、零依賴**——它只是把事件轉給本檔。
_OPENCODE_PLUGIN = """\
// Vacant 掛鉤契約 vacant-hook/1 —— 只紀錄，不擋（見 hookcli.py 誠實邊界 2）。
// 它把 OpenCode 的事件轉成一次 `python -m vacant_network.vrun.hookcli <event>`。
import { spawnSync } from "node:child_process";

const PY = %(py)s;
const ARGS = %(args)s;

function fire(event, payload) {
  try {
    spawnSync(PY, [...ARGS, event], {
      input: JSON.stringify(payload || {}),
      timeout: 10000, stdio: ["pipe", "ignore", "ignore"],
    });
  } catch (e) { /* 掛鉤壞掉不可以弄死 agent（誠實邊界 3） */ }
}

export const VacantHook = async () => {
  fire("session_start", { source: "opencode-plugin" });
  return {
    "tool.execute.before": async (input, output) => {
      fire("pre_tool_use", { tool_name: input && input.tool,
                             tool_input: output && output.args });
    },
    "tool.execute.after": async (input) => {
      fire("post_tool_use", { tool_name: input && input.tool });
    },
  };
};
export default VacantHook;
"""


def install_opencode(cfg_dir: pathlib.Path, *, hook_log: str, run_id: str,
                     proxy: str | None) -> dict:
    """OpenCode：`<OPENCODE_CONFIG_DIR>/plugin/vacant.js`。

    ⚠ `session_start` 是在 plugin **被載入時**燒的（OpenCode 的 plugin 沒有
      一個叫 SessionStart 的事件）。那仍然滿足 canary 的要求：**plugin 真的
      被載入了**才會有那一行；設定檔寫了但沒載入 ⇒ 沒有那一行 ⇒ 降級。
    """
    d = cfg_dir / "plugin"
    d.mkdir(parents=True, exist_ok=True)
    cmd = hook_command()
    (d / "vacant.js").write_text(
        _OPENCODE_PLUGIN % {"py": json.dumps(cmd[0]),
                            "args": json.dumps(cmd[1:])}, encoding="utf-8")
    return {"agent": "opencode", "target": str(d / "vacant.js"),
            "env": _hook_env(hook_log, "opencode", run_id, proxy),
            "events": ["session_start", "pre_tool_use", "post_tool_use"]}


def install(agent: str, cfg_dir: pathlib.Path, *, hook_log: str, run_id: str,
            proxy: str | None = None) -> dict | None:
    """裝這個 agent 的掛鉤。**回 `None` ＝這個 agent 還沒開採**（不是失敗）。

    ⚠ 回一份非 `None` 的報告**不代表掛鉤會燒**。那一句只有
      `attest.probe_framework_hook` 讀完日誌才說得出來（裁決 §三-1）。
    """
    fn = {"claude": install_claude, "opencode": install_opencode}.get(agent)
    if fn is None:
        return None
    try:
        return fn(cfg_dir, hook_log=hook_log, run_id=run_id, proxy=proxy)
    except OSError as e:
        return {"agent": agent, "target": None, "error": f"{type(e).__name__}: {e}",
                "env": _hook_env(hook_log, agent, run_id, proxy), "events": []}


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if not a:
        print("用法：hookcli <event>（由 agent 框架的掛鉤呼叫）", file=sys.stderr)
        return 0                # ⚠ 連用法錯誤都回 0：不可以弄死 agent
    data = b""
    try:
        if not sys.stdin.isatty():
            data = sys.stdin.buffer.read()
    except Exception:                                        # noqa: BLE001
        data = b""
    try:
        return handle(a[0], data)
    except Exception:                                        # noqa: BLE001
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
