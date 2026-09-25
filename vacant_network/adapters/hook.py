"""hook — `vacant hook <agent> <event>`：**四種原生掛鉤格式 → 一份政策 → 四種原生回應**。

這支在架構裡承重什麼（`adapters/__init__.py` 共通面 4）：

agent 在每一次工具呼叫前、每一回合結束、工作階段結束時執行這支，stdin 是 agent 原生的
JSON。這裡做三件事，而且**只有翻譯是各 agent 不同的**：

    原生 payload ──(normalize_<agent>)──→ HookEvent
    HookEvent ──(hookpolicy)──→ HookDecision
    HookDecision ──(render_<agent>)──→ 原生回應（stdout／退出碼）

| agent | 事件（原生） | 拒絕工具的方式 | 回合結束時要求繼續 |
|---|---|---|---|
| Claude Code | `PreToolUse`／`PostToolUse(Failure)`／`SubagentStop`／`Stop`／`SessionEnd` | stdout `hookSpecificOutput.permissionDecision="deny"` | stdout `{"decision":"block","reason":…}` |
| Codex | `PreToolUse`／`PostToolUse`／`SubagentStop`／`Stop`／`SessionEnd` | exit 2＋stderr 理由（2026-09-20 實測） | stdout `{"decision":"block","reason":…}` |
| OpenCode | 外掛轉送 `tool.execute.before/after`／`session.idle` | 外掛讀我們的 JSON 後 `throw` | 外掛把理由當下一則訊息送回 session |
| pi | extension 轉送 `tool_call`／`tool_result`／`agent_before_settle`／`session_shutdown` | extension 回 `{block:true, reason}` | extension 把理由當下一則訊息送回 |

OpenCode 與 pi 的外掛是我們自己寫的（`adapters/agents.py` 裡的原始碼），所以它們跟這支
之間用的是**我們的**格式：stdout 一行 `{"action": "allow|deny|continue", "reason": …}`。

## 快速路徑

這支在**每一次工具呼叫**前都會被執行。專案裡沒有契約 ⇒ 除了「不准碰 `$VACANT_HOME`」
這一條，什麼都不做、立刻放行；不載入收件口、不讀帳本。

## 誠實邊界（改碼請保留）

1. **任何例外都放行**（exit 0、沒有輸出），並把錯誤落到 `$VACANT_HOME/intake/hooks/errors.jsonl`。
   掛鉤壞掉弄死 agent 的代價，比少擋一次的代價大；而保證本來就不在這一層
   （`hookpolicy.py` 誠實邊界 1、2）。
2. 事件紀錄只落雜湊與工具名，不落指令原文或檔案內容（`vrun/hookcli.py` 誠實邊界 1 的同一條）；
   agent 用 CronCreate／ScheduleWakeup 排給自己的提示也只記雜湊（`intake/hooks/scheduled_*.json`，
   沒開追緝時分辨「這一則是不是人打的」用）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from typing import Any

from .hookpolicy import (NON_TERMINAL_END_REASONS, HookDecision, HookEvent, decide_pre_tool,
                         decide_stop, new_request, vacant_state_dir)

#: 原生事件名 → 正規化種類
EVENT_MAP: dict[str, dict[str, str]] = {
    "claude": {"PreToolUse": "pre_tool", "PostToolUse": "post_tool",
               "PostToolUseFailure": "post_tool", "Stop": "stop", "SubagentStop": "other",
               "SubagentStart": "other",
               "SessionEnd": "session_end", "SessionStart": "session_start",
               "UserPromptSubmit": "other"},
    "codex": {"PreToolUse": "pre_tool", "PostToolUse": "post_tool", "Stop": "stop",
              "SubagentStop": "other", "SubagentStart": "other",
              "SessionEnd": "session_end", "SessionStart": "session_start",
              "UserPromptSubmit": "other"},
    "opencode": {"pre_tool": "pre_tool", "post_tool": "post_tool", "stop": "stop",
                 "session_end": "session_end", "session_start": "session_start",
                 "prompt": "other"},
    "pi": {"pre_tool": "pre_tool", "post_tool": "post_tool", "stop": "stop",
           "session_end": "session_end", "session_start": "session_start",
           "subagent_stop": "other", "prompt": "other"},
}
AGENTS = tuple(EVENT_MAP)

_PATH_KEYS = ("file_path", "filePath", "path", "notebook_path", "target", "filename")


def _paths_from(inp: Any) -> list[str]:
    out: list[str] = []
    if isinstance(inp, dict):
        for k in _PATH_KEYS:
            v = inp.get(k)
            if isinstance(v, str) and v:
                out.append(v)
        for k in ("edits", "files", "changes"):
            v = inp.get(k)
            if isinstance(v, list):
                for x in v:
                    out += _paths_from(x)
        # 真實的 apply_patch 形狀：Codex 0.156.1 是 `{"command": <patch>}`
        # （codex-rs apply_patch.rs）、OpenCode 是 `{"patchText": <patch>}`（tool/registry.ts）。
        patch = inp.get("patch") or inp.get("patchText") or inp.get("input") or (
            inp.get("command") if _is_patch(inp.get("command")) else None)
        if isinstance(patch, str) and "*** " in patch:
            for line in patch.splitlines():
                for tag in ("*** Add File: ", "*** Update File: ", "*** Delete File: ",
                            "*** Move to: "):
                    if line.startswith(tag):
                        out.append(line[len(tag):].strip())
    return out


def _is_patch(v: Any) -> bool:
    return isinstance(v, str) and v.lstrip().startswith("*** Begin Patch")


def _command_from(inp: Any) -> str | None:
    if isinstance(inp, dict):
        c = inp.get("command") or inp.get("cmd")
        if _is_patch(c):
            return None                   # 那是檔案修補，不是 shell 指令（路徑另外抽）
        if isinstance(c, list):
            return " ".join(str(x) for x in c)
        if isinstance(c, str):
            return c
    return None


def normalize(agent: str, event: str, payload: dict[str, Any]) -> HookEvent:
    kind = EVENT_MAP.get(agent, {}).get(event) or EVENT_MAP.get(agent, {}).get(
        str(payload.get("hook_event_name", ""))) or "other"
    if agent in ("claude", "codex"):
        tool = payload.get("tool_name")
        inp = payload.get("tool_input") or {}
        sid = payload.get("session_id")
        cwd = payload.get("cwd") or os.getcwd()
        active = bool(payload.get("stop_hook_active"))
    else:  # opencode / pi：我們自己的外掛送的格式
        tool = payload.get("tool")
        inp = payload.get("input") or payload.get("args") or {}
        sid = payload.get("session_id")
        cwd = payload.get("cwd") or os.getcwd()
        active = bool(payload.get("stop_hook_active"))
    reason = payload.get("reason")
    return HookEvent(agent=agent, kind=kind, tool=str(tool) if tool else None,
                     command=_command_from(inp), paths=_paths_from(inp), cwd=str(cwd),
                     session_id=str(sid) if sid else None, stop_hook_active=active,
                     reason=str(reason) if reason else None)


def render(agent: str, ev: HookEvent, d: HookDecision) -> tuple[str, str, int]:
    """回 `(stdout, stderr, exit_code)`。"""
    if agent == "claude":
        if ev.kind == "pre_tool" and d.action == "deny":
            return json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": d.reason}}), "", 0
        if ev.kind == "stop" and d.action == "continue":
            return json.dumps({"decision": "block", "reason": d.reason}), "", 0
        if ev.kind == "stop" and d.record.get("user_message"):
            # 不再要求 agent 繼續，但問題還在 ⇒ 直接顯示給人（不進模型的上下文）
            return json.dumps({"systemMessage": d.record["user_message"]}), "", 0
        return "", "", 0
    if agent == "codex":
        if ev.kind == "pre_tool" and d.action == "deny":
            return "", d.reason, 2
        if ev.kind == "stop" and d.action == "continue":
            return json.dumps({"decision": "block", "reason": d.reason}), "", 0
        return "", "", 0
    out = {"action": d.action, "reason": d.reason}
    if ev.kind == "stop" and d.action != "continue" and d.record.get("user_message"):
        out["note"] = d.record["user_message"]   # pi／OpenCode 的橋接自己決定要不要顯示（有介面才顯示）
    return json.dumps(out), "", 0


def _log(name: str, rec: dict[str, Any]) -> None:
    try:
        p = vacant_state_dir() / "intake" / "hooks" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), **rec}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _spawn_submit(contract_path: Any, agent: str) -> int | None:
    import subprocess
    try:
        logf = vacant_state_dir() / "intake" / "hooks" / "submit.log"
        logf.parent.mkdir(parents=True, exist_ok=True)
        with open(logf, "ab") as out:
            p = subprocess.Popen(
                [sys.executable, "-m", "vacant_network", "submit", "--contract",
                 str(contract_path), "--source", f"{agent}:session_end", "--json"],
                stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True,
                env={**os.environ, "VACANT_HOOK_NO_SUBMIT": "1"})
        return p.pid
    except OSError as e:
        _log("errors.jsonl", {"agent": agent, "event": "session_end",
                              "error": f"could not start submit: {e}"})
        return None


def _spawn_finalize(contract: Any, agent: str, payload: dict[str, Any],
                    ev: HookEvent) -> int | None:
    """工作階段結束的追緝（`trace/finalize.py`）：背景跑，掛鉤立刻返回。沒開追緝就不跑。"""
    import subprocess
    try:
        from ..trace.capture import workspace_for
        if workspace_for(ev.cwd, contract) is None:
            return None
        logf = vacant_state_dir() / "intake" / "hooks" / "finalize.log"
        logf.parent.mkdir(parents=True, exist_ok=True)
        with open(logf, "ab") as out:
            p = subprocess.Popen(
                [sys.executable, "-m", "vacant_network.trace.finalize", str(contract.path), agent,
                 str(ev.session_id or "unknown"), str(payload.get("model") or "")],
                stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True)
        return p.pid
    except Exception as e:  # noqa: BLE001
        _log("errors.jsonl", {"agent": agent, "event": "session_end",
                              "error": f"could not start trace finalize: {e}"[:300]})
        return None


def _trace(agent: str, event: str, payload: dict[str, Any], ev: HookEvent, contract: Any,
           d: HookDecision) -> None:
    """可究責追緝的病歷（`trace/capture.py`）。壞掉只記錯、不影響裁決（誠實邊界 1）；
    記不到的那一段在下一步會變成缺口。"""
    try:
        from ..trace import capture
        capture.observe(agent, event, payload, cwd=ev.cwd, contract=contract, decision=d)
    except Exception as e:  # noqa: BLE001
        _log("errors.jsonl", {"agent": agent, "event": event,
                              "error": f"trace: {type(e).__name__}: {e}"[:500]})


def _remember_scheduled(agent: str, event: str, payload: dict[str, Any], ev: HookEvent) -> None:
    """agent 用 CronCreate／ScheduleWakeup 排給自己的提示：記在病歷之外（`capture.remember_scheduled`），
    沒開追緝的專案裡照樣認得出它觸發時的那一則不是人打的（2026-09-25 審查 C5）。失敗的呼叫不記。"""
    from ..trace import capture
    if ev.tool not in capture.SCHEDULER_TOOLS or event == "PostToolUseFailure" \
            or payload.get("is_error") or payload.get("error"):
        return
    try:
        capture.remember_scheduled(agent, payload)
    except Exception as e:  # noqa: BLE001 — 掛鉤不可以因為這個壞掉
        _log("errors.jsonl", {"agent": agent, "event": event,
                              "error": f"scheduled: {type(e).__name__}: {e}"[:500]})


def _person_prompt(agent: str, event: str, payload: dict[str, Any], cwd: str | None,
                   contract: Any) -> bool:
    """這則使用者訊息是人打的（不是背景子 agent 的結果、不是父 agent 給子 agent 的任務、不是 agent
    自己排的排程提示、不是別的行動者的話、不是 `vacant do` 交給 agent 的任務（含接在後面的回饋），
    也不是 Vacant 自己的回饋被當成使用者訊息送回來——那個再給新輪數就是一個不會停的迴圈）。
    分辨規則只有一份：`capture.classify_prompt`（病歷記的來源也是它；agent 排過的提示在病歷沒開時看
    `capture.scheduled_outside_trace`）。"""
    from ..trace import capture
    action = capture.ACTIONS.get(event) or capture.ACTIONS.get(
        str(payload.get("hook_event_name") or ""))
    text = str(payload.get("prompt") or "")
    if action != "prompt" or not text.strip():
        return False
    return capture.classify_prompt(agent, payload, text, cwd, contract)[0] == "user"


def _defer_for_subagents(contract: Any, ev: HookEvent) -> bool:
    try:
        from ..trace import capture, recorder, stopcheck
        ws = capture.workspace_for(ev.cwd, contract)
        if ws is None or not ev.session_id:
            return False
        rec = recorder.Recorder(ws)
        key = f"{ev.agent}:{ev.session_id}"
        if not rec.should_defer(key):
            return False
        # 上一次回合邊界的「過／不過」已經不是現況：不可以在工作階段結束時被當成這一跑的結果
        # （審查 defer#2：先 accept、之後自己刪掉報告、叫一個背景子 agent、延後、結束 ⇒ 曾經記成成功）
        stopcheck.forget_outcome(rec, key)
        return True
    except Exception:  # noqa: BLE001 — 看不出來就照常驗收
        return False


def _localize(contract: Any, res: dict[str, Any], ev: HookEvent,
              why: str | None) -> dict[str, Any] | None:
    from ..trace import recorder, stopcheck
    return stopcheck.localize(contract, res, cwd=ev.cwd, why_open=why,
                              session=f"{ev.agent}:{ev.session_id}",
                              scan_deadline_s=recorder.HOOK_SCAN_S)


def _zero_mode() -> str:
    try:
        from .mode import current_mode
        return current_mode()
    except Exception:  # noqa: BLE001 — 看不出來就當沒裝
        return "off"


def _zero_scope(cwd: str | None) -> Any:
    from ..trace import capture, zerostop
    ws = capture.workspace_for(cwd, None)
    return zerostop.scope(ws) if ws is not None else None


def _zero_stop(agent: str, payload: dict[str, Any], ev: HookEvent, mode: str) -> HookDecision:
    """沒有契約的 Stop：證據檢查（`trace/zerostop.py`）。任何錯誤都放行（誠實邊界 1）。"""
    from ..trace import zerostop
    action, reason, record = zerostop.stop(agent, ev.session_id, ev.cwd,
                                           zerostop.final_text_of(payload), mode=mode)
    z = record.get("zero") or {}
    if z.get("error"):
        _log("errors.jsonl", {"agent": agent, "event": "stop",
                              "error": f"zero-config check: {z['error']}"[:500]})
    return HookDecision(action if action in ("allow", "continue") else "allow", reason, record)


def handle(agent: str, event: str, payload: dict[str, Any]) -> tuple[str, str, int]:
    from ..intake import contract as C

    ev = normalize(agent, event, payload)
    cpath = C.find(ev.cwd) if ev.cwd else None
    contract = None
    if cpath is not None:
        try:
            contract = C.load(cpath)
        except C.ContractError as e:
            _log("errors.jsonl", {"agent": agent, "event": event,
                                  "error": f"contract invalid: {e}"[:500]})
    d = HookDecision("allow")
    # 零設定（沒有契約、人裝過 Vacant）：`adapters/mode.py`；有契約時一律走契約那條
    zero = _zero_mode() if contract is None else "off"
    if ev.kind == "stop":
        # 追緝之前先收掉這個工作階段裡等不到 post 的步驟，否則這一回合看不到它們（integration#5）
        _trace(agent, event, payload, ev, contract, d)
    if ev.kind == "pre_tool":
        d = decide_pre_tool(ev, contract)
    elif ev.kind == "stop" and (contract is not None or zero != "off") \
            and _defer_for_subagents(contract, ev):
        # 背景的子 agent 還在做（Claude 預設把子 agent 放到背景）：主 agent 的回合結束不是交件的時候，
        # 這時驗收只會叫它把子 agent 正在做的事重做一遍。等子 agent 回報之後的那一次回合結束再驗
        # （連續延後有上限；這個工作階段上一次的驗收結果作廢——之後的工作階段結束以新的驗收為準）
        d = HookDecision("allow", "", {"stop_check_deferred": "a delegated task is still running"})
    elif ev.kind == "stop" and contract is None and zero != "off" \
            and not os.environ.get("VACANT_HOOK_NO_STOP"):
        d = _zero_stop(agent, payload, ev, zero)
    elif ev.kind == "stop" and contract is not None and not os.environ.get("VACANT_HOOK_NO_STOP") \
            and os.environ.get("VACANT_FEEDBACK_MODE") != "none":
        from ..intake import flow
        generic = os.environ.get("VACANT_FEEDBACK_MODE") == "generic"   # 預註冊實驗的 RF 臂
        d = decide_stop(ev, contract, check_fn=flow.check,
                        localize=None if generic else
                        (lambda res, why: _localize(contract, res, ev, why)))
    elif ev.kind == "session_end" and contract is not None \
            and ev.reason in NON_TERMINAL_END_REASONS:
        d = HookDecision("allow", "", {"submit_skipped": f"reason={ev.reason} (not the end "
                                                         f"of the work)"})
    elif ev.kind == "session_end" and contract is not None \
            and contract.hooks.get("submit_on_end", True) \
            and not os.environ.get("VACANT_HOOK_NO_SUBMIT"):
        # ⚠ 不在掛鉤裡同步交件：Claude Code 的 SessionEnd 預設只給 1.5 秒
        #   （agent-claude 對照 §3.6），驗證器跑不完就被砍，那一次就不見了。
        #   改成分離的背景行程，掛鉤立刻返回；交件結果（含失敗）照樣進帳本。
        pid = _spawn_submit(contract.path, agent)
        d = HookDecision("allow", "", {"submit_scheduled": pid is not None, "pid": pid})
    if ev.kind != "stop":
        _trace(agent, event, payload, ev, contract, d)
    if (contract is not None or zero != "off") and ev.kind in ("pre_tool", "post_tool") \
            and d.action != "deny":
        _remember_scheduled(agent, event, payload, ev)
    if (contract is not None or zero != "off") and ev.kind == "other":
        try:
            if _person_prompt(agent, event, payload, ev.cwd, contract):
                # 人的一個新要求：回饋輪數重新算（零設定時的鍵＝專案根目錄）
                new_request(ev.session_id, contract if contract is not None
                            else _zero_scope(ev.cwd))
        except Exception as e:  # noqa: BLE001 — 掛鉤不可以因為這個壞掉
            _log("errors.jsonl", {"agent": agent, "event": event,
                                  "error": f"new_request: {type(e).__name__}: {e}"[:500]})
    if ev.kind == "session_end" and contract is not None and ev.reason not in \
            NON_TERMINAL_END_REASONS and not os.environ.get("VACANT_HOOK_NO_SUBMIT"):
        # 工作階段結束的追緝報告：和自動交件無關（`submit_on_end=false` 也要有；integration#6）
        d.record["trace_finalize"] = _spawn_finalize(contract, agent, payload, ev)
    rec = {"agent": agent, "event": event, "kind": ev.kind, "tool": ev.tool,
           "action": d.action, "contract": str(cpath) if cpath else None,
           "command_sha256": (hashlib.sha256(ev.command.encode()).hexdigest()
                              if ev.command else None),
           # 給人的訊息含繳付物裡的值：不進事件紀錄（誠實邊界 2），它在病歷目錄的報告裡
           **{k: v for k, v in d.record.items() if k != "user_message"}}
    _log("events.jsonl", rec)
    if contract is not None and (d.action != "allow" or ev.kind in ("stop", "session_end")):
        try:
            from ..intake.ledger import Ledger
            Ledger(contract.task_id).append("hook_event", {
                k: v for k, v in rec.items() if k != "contract"})
        except Exception as e:  # noqa: BLE001
            _log("errors.jsonl", {"agent": agent, "event": event, "error": str(e)[:500]})
    return render(agent, ev, d)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[0] not in AGENTS:
        print(f"usage: vacant hook <{'|'.join(AGENTS)}> <event>  (JSON payload on stdin)",
              file=sys.stderr)
        return 0
    agent, event = args[0], args[1]
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        out, err, code = handle(agent, event, payload)
    except Exception as e:  # noqa: BLE001 — 誠實邊界 1：掛鉤壞掉不可以弄死 agent
        _log("errors.jsonl", {"agent": agent, "event": event,
                              "error": f"{type(e).__name__}: {e}"[:500]})
        return 0
    if out:
        sys.stdout.write(out + "\n")
    if err:
        sys.stderr.write(err + "\n")
    return code



if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
