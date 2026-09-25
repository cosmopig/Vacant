"""capture — **四個 agent 的原生掛鉤 → 病歷**：誰（行動者）、哪一步（步驟 id）、輸出、逐字稿。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §三、§4.8 K1/K6/K12）：

`adapters/hook.py` 每收到一個掛鉤事件就叫 `observe()`。這裡只做翻譯，記錄本身在 `recorder.py`：

| 平台 | 步驟 id | 行動者（子 agent） | 模型 | 失敗 |
|---|---|---|---|---|
| Claude Code | `tool_use_id` | `agent_id`／`agent_type`（只在子 agent 裡出現） | 掛鉤沒有；工作階段結束時從逐字稿補（`claimed`） | `PostToolUseFailure.error` |
| Codex | `tool_use_id`（＝Responses `call_id`） | `agent_id`／`agent_type`；`session_id` 是根工作階段 | 掛鉤帶**要求的** slug（`claimed`） | 沒有失敗事件（apply_patch 失敗不發 PostToolUse ⇒ `post_missing`） |
| OpenCode | 外掛送 `callID` | 子 session（外掛以 `session.created.parentID` 記下） | — | `output` 內容 |
| pi | 外掛送 `toolCallId` | pi 沒有內建子 agent | 外掛送 `ctx.model.id`（`claimed`） | `isError` |

量測底稿：`ops/accountability/capture/`（[RUN]＝真 binary＋假模型實跑）。

**什麼時候記**：專案有契約（`vacant.toml`）⇒ 記在契約所在的專案根；否則只在
`VACANT_TRACE=1` 時記在 `cwd`。`VACANT_TRACE=0` 一律不記。家目錄與 `/` 不記（一掃就是整台機器）。

## 誠實邊界（改碼請保留）

1. 這支在掛鉤行程裡跑，**任何例外都由呼叫端吞掉並記錯**（`hook.py` 誠實邊界 1）——
   記不到的那一段，下一次 `pre` 會把改動記成缺口，而不是讓 agent 停擺。
2. 逐字稿是 agent 自己寫的檔（Claude 在 `~/.claude/projects/`、Codex 的 rollout）：
   工作階段結束時把它**封存**（雜湊＋內容進版本庫＋簽進鏈），之後的竄改可察覺；
   封存之前的竄改看不出來。從逐字稿讀出的模型 id 一律標 `claimed`。
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import re
import time
from typing import Any

from . import recorder as R

#: 原生事件名 → 這支認得的動作（沒列的不記）
ACTIONS = {
    "UserPromptSubmit": "prompt", "prompt": "prompt",
    "PreToolUse": "pre", "PostToolUse": "post", "PostToolUseFailure": "post",
    "SubagentStop": "subagent_stop", "SubagentStart": "subagent_start",
    "Stop": "stop", "SessionEnd": "session_end",
    "pre_tool": "pre", "post_tool": "post", "stop": "stop", "session_end": "session_end",
    "subagent_stop": "subagent_stop",
}
MAX_TRANSCRIPT = 64 * 1024 * 1024


def workspace_for(cwd: str | None, contract: Any = None) -> pathlib.Path | None:
    flag = os.environ.get("VACANT_TRACE", "").strip()
    if flag == "0":
        return None
    if contract is not None:
        ws = pathlib.Path(contract.base_dir).resolve()
    elif flag != "1" or not cwd:
        return None
    else:
        ws = pathlib.Path(cwd).resolve()
    return ws if _traceable(ws) else None


def _traceable(ws: pathlib.Path) -> bool:
    """`/`、家目錄或它的上層（一掃就是整台機器）、Vacant 自己的狀態目錄（或它的上下層）都不追
    （2026-09-24 審查 recorder#11：原本只比「相等」，契約放在家目錄就把整個家目錄掃進去）。"""
    from ..intake.statepaths import state_dir, work_dir
    home = pathlib.Path.home().resolve()
    if ws == pathlib.Path(ws.anchor) or ws == home or ws in home.parents:
        return False
    sd = state_dir().resolve()
    if ws == sd or sd in ws.parents or ws in sd.parents:
        return False
    # `vacant do` 的工作區都在工作區根底下：根本身和它的上層不追，根底下的每一個工作區照追
    # （把整個根當成狀態目錄曾經讓 `vacant do` 一步都沒記——R536 的追緝回饋少了「第幾步」）
    wd = work_dir().resolve()
    if ws == wd or ws in wd.parents:
        return False
    return True


_TASK_NOTE = re.compile(r"<tool-use-id>([^<]+)</tool-use-id>")
#: Codex 把掛鉤送回的文字包在 `<hook_prompt …>` 裡
_HOOK_WRAPPER = re.compile(r"^\s*</?hook_prompt\b[^>]*>")
#: 不是人打的使用者訊息（Claude Code 2.1.281 的 binary 裡的信封；2026-09-25 審查 loop#5）
_MACHINE_ENVELOPES = ("<cross-session-message", "<teammate-message", "<event ", "<wake")
#: agent 自己排的提示（到時候以一則使用者訊息回來，掛鉤的內容和人打的一模一樣）
SCHEDULER_TOOLS = frozenset({"CronCreate", "ScheduleWakeup"})
#: Claude Code 的 UserPromptSubmit `source`（binary 裡的欄位說明；目前還不送）——只有這兩種是人
_PERSON_SOURCES = frozenset({"user", "sdk"})


def prompt_source(agent: str, payload: dict[str, Any], text: str) -> tuple[str, str | None]:
    """這則「使用者訊息」其實是誰說的（2026-09-24 審查 blame#5、integration#0）：
    Claude 把背景子 agent 的結果以 `<task-notification>` 送回；Codex 子 agent 的
    UserPromptSubmit 是父 agent 給它的任務說明；Vacant 自己的回饋（2026-09-25）。
    ⚠ 人打的訊息裡剛好貼了回饋的開頭，也會被當成 Vacant 的回饋（不當來源、不重新算輪數）。"""
    t = _HOOK_WRAPPER.sub("", text).lstrip()
    from .feedback import FEEDBACK_HEADER, FLAG_HEADER
    if t.startswith((FEEDBACK_HEADER, FLAG_HEADER)):
        # Vacant 自己的回饋被當成使用者訊息送回來（OpenCode 的外掛用 `session.prompt` 送）：不是人說的，
        # 也不是任何值的來源（裡面引了繳付物的錯值與應有的值；當成「任務說的」就等於替 agent 洗掉錯）。
        # 只認**開頭**：人打的一則裡引了一段回饋，仍然是人說的（2026-09-25 審查 loop#3）
        return "vacant_feedback", None
    if t.startswith(_MACHINE_ENVELOPES):
        return "machine", None           # 別的工作階段／隊友／事件送進來的訊息，不是人打的
    if t.startswith("<task-notification>"):
        m = _TASK_NOTE.search(t)
        return "subagent_result", (m.group(1).strip() if m else None)
    parent = payload.get("parent_session_id")
    if payload.get("agent_id") or (parent and parent != payload.get("session_id")):
        return "parent_agent", None
    return "user", None


def classify_prompt(agent: str, payload: dict[str, Any], text: str, cwd: str | None,
                    contract: Any = None) -> tuple[str, str | None]:
    """`prompt_source` 再加上要看病歷才分得出來的：agent 自己排的提示（CronCreate／ScheduleWakeup 在這個
    工作階段裡記過同一段文字）、平台送的 `source` 說不是人。病歷記的來源與「人的新要求重新算輪數」都用這一份
    （2026-09-25 審查 loop#5：真的 Claude Code 在排程觸發時送的 UserPromptSubmit 和人打的一模一樣）。"""
    src, tid = prompt_source(agent, payload, text)
    if src != "user":
        return src, tid
    declared = payload.get("source")
    if isinstance(declared, str) and declared and declared not in _PERSON_SOURCES:
        return "machine", None
    ws = workspace_for(cwd, contract)
    if ws is None:
        return src, tid
    sid = str(payload.get("session_id") or "")
    body = text.strip()
    for e in R.Recorder(ws).events():
        if e.get("type") != "step" or e.get("tool") not in SCHEDULER_TOOLS:
            continue
        if sid and str((e.get("actor") or {}).get("session") or "") != sid:
            continue
        try:
            inp = json.loads(R.Recorder(ws).blobs.get(e["input_blob"]).decode("utf-8", "replace"))
        except (OSError, ValueError, KeyError, TypeError):
            continue
        sched = str((inp or {}).get("prompt") or "").strip() if isinstance(inp, dict) else ""
        if sched and (sched == body or sched in body):
            return "scheduled_by_agent", str(e.get("step") or "") or None
    return src, tid


def actor_of(agent: str, payload: dict[str, Any]) -> R.Actor:
    sid = str(payload.get("session_id") or "unknown")
    if agent in ("claude", "codex"):
        return R.Actor(agent, sid, agent=_s(payload.get("agent_id")),
                       agent_type=_s(payload.get("agent_type")),
                       model=_s(payload.get("model")))
    if agent == "opencode":
        parent = _s(payload.get("parent_session_id"))
        if parent:          # 子 session ＝ 子 agent；工作階段鍵用根 session
            return R.Actor(agent, str(payload.get("root_session_id") or parent),
                           agent=sid, agent_type=_s(payload.get("agent")) or "subagent",
                           model=_s(payload.get("model")))
        return R.Actor(agent, sid, model=_s(payload.get("model")))
    parent = _s(payload.get("parent_session_id"))
    if agent == "pi" and parent and parent != sid:
        # 另一個 pi 行程，從父 agent 的行程開出來（Vacant 的 pi 擴充帶過來的標記）：子 agent；
        # 工作階段鍵用最上層那個 session。代理人類型由 `link_child` 從叫它的那個呼叫補上
        return R.Actor(agent, parent, agent=sid, agent_type="subagent",
                       model=_s(payload.get("model")))
    return R.Actor(agent, sid, model=_s(payload.get("model")))


def _s(v: Any) -> str | None:
    return str(v) if v not in (None, "") else None


def step_id(agent: str, payload: dict[str, Any], tool: str | None, tool_input: Any) -> str:
    for k in ("tool_use_id", "call_id", "callID", "toolCallId"):
        v = payload.get(k)
        if v:
            return str(v)
    # 沒有平台給的 id：同一個工具＋同一份輸入在 pre 與 post 算出同一個 id（重複呼叫會撞在一起，
    # 那兩步就合成一步——比錯配成別人的步驟好）
    raw = json.dumps([payload.get("session_id"), payload.get("agent_id"), tool, tool_input],
                     sort_keys=True, ensure_ascii=False, default=str)
    return "h:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def _tool_and_input(agent: str, payload: dict[str, Any]) -> tuple[str, Any]:
    if agent in ("claude", "codex"):
        return str(payload.get("tool_name") or "?"), payload.get("tool_input") or {}
    return (str(payload.get("tool") or "?"),
            payload.get("input") or payload.get("args") or {})


def _output_and_error(agent: str, event: str, payload: dict[str, Any]) -> tuple[Any, str | None]:
    if agent == "claude":
        if event == "PostToolUseFailure":
            return None, str(payload.get("error") or "tool failed")
        return payload.get("tool_response"), None
    if agent == "codex":
        return payload.get("tool_response"), None
    out = payload.get("output")
    err = payload.get("error")
    if payload.get("is_error") and not err:
        err = "tool reported an error"
    return out, (str(err) if err else None)


def observe(agent: str, event: str, payload: dict[str, Any], *, cwd: str | None,
            contract: Any = None, decision: Any = None) -> dict[str, Any] | None:
    """把一個掛鉤事件記進病歷。回傳記下的東西（沒記回 None）。"""
    action = ACTIONS.get(event) or ACTIONS.get(str(payload.get("hook_event_name") or ""))
    if action is None:
        return None
    ws = workspace_for(cwd, contract)
    if ws is None:
        return None
    rec = R.Recorder(ws)
    rec.scan_deadline_s = R.HOOK_SCAN_S      # 在掛鉤裡：掃描有時限（第一次看改到背景）
    actor = actor_of(agent, payload)
    link: dict[str, Any] = {}
    if agent == "pi" and actor.agent:
        task = str(payload.get("prompt")) if action == "prompt" and payload.get("prompt") else None
        link = rec.link_child(actor, _s(payload.get("parent_agent_id")), task)
        if link.get("agent_type"):
            actor = dataclasses.replace(actor, agent_type=str(link["agent_type"]))
    t0 = time.perf_counter()
    out: Any = None
    if action in ("pre", "post"):
        tool, tool_input = _tool_and_input(agent, payload)
        step = step_id(agent, payload, tool, tool_input)
        if action == "pre" and decision is not None and getattr(decision, "action", "") == "deny":
            out = rec.denied(step, actor, tool, tool_input, getattr(decision, "reason", ""))
        elif action == "pre":
            out = rec.pre(step, actor, tool, tool_input)
        else:
            output, error = _output_and_error(agent, event, payload)
            out = rec.post(step, actor, tool, tool_input, output, error=error)
    elif action == "prompt":
        text = payload.get("prompt")
        if text:
            src, tid = classify_prompt(agent, payload, str(text), cwd, contract)
            out = rec.prompt(str(text), session=actor.session, source=src, tool_use_id=tid,
                             agent=actor.agent if src == "parent_agent" else None,
                             spawned_by=link.get("spawned_by"))
    elif action == "stop":
        out = rec.settle(actor, "turn_end")      # 已經在裁決之前收過一次（hook.handle）；冪等
    elif action == "subagent_start":
        out = rec.subagent_state(actor, running=True)
    elif action == "subagent_stop":
        rec.subagent_state(actor, running=False)
        path = payload.get("agent_transcript_path")
        out = seal_transcript(rec, actor, agent, path, role="subagent") if path else None
    elif action == "session_end":
        tp = payload.get("transcript_path")
        if tp:
            seal_transcript(rec, actor, agent, tp, role="session")
        reason = _s(payload.get("reason"))
        out = rec.close(actor, reason)
        from ..adapters.hookpolicy import NON_TERMINAL_END_REASONS
        if reason not in NON_TERMINAL_END_REASONS:
            _outcome(rec, actor, contract)
    _perf(rec, agent, event, time.perf_counter() - t0)
    return out if isinstance(out, dict) else {"n": len(out)} if isinstance(out, list) else None


def _outcome(rec: R.Recorder, actor: R.Actor, contract: Any) -> None:
    """工作階段結束：最後一次回合邊界的檢查結果記成主 agent 這一跑的結果（信譽 adoption 維）。
    這個工作階段沒有檢查過（沒有契約、沒有 Stop）⇒ 不記。

    回合邊界的檢查是 `flow.check`（暫存帳本、空的簽章者清單）：**看不到人工審查**。所以只有
    `accept`／有必要主張 FAIL 的 `reject` 進 adoption；hold／escalate 照記一筆（帶 `outcome`）
    但不算（`actors.adoption_of`；架構文件 §10 第 16 列）。"""
    if contract is None or os.environ.get("VACANT_HOOK_NO_SUBMIT"):
        # `vacant do` 自己在行程結束後記這一跑（只記一次；2026-09-24 審查 consequences#1）
        return
    try:
        st = json.loads((rec.dir / "feedback_state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    # 只用**這個**工作階段自己的檢查結果；沒檢查過的工作階段不記（審查 consequences#2）
    skey = f"{actor.platform}:{actor.session}"
    mine = (st.get("outcomes") or {}).get(skey)
    if not mine:
        return
    from . import actors as A
    ads = st.get("adoptions") or {}
    # 舊版狀態檔沒有 `adoptions`：只憑裁決字串判（hold／escalate ⇒ 不記）
    adoption = ads[skey] if skey in ads else A.adoption_of({"outcome": mine})
    model = actor.model or rec.session_info(actor.platform, actor.session).get("model")
    main = {"platform": actor.platform, "session": actor.session, "model": model}
    A.record_run(rec, session_key=skey, actor=main, outcome=mine, adoption=adoption,
                 contract=contract, session=actor.session)


def _perf(rec: R.Recorder, agent: str, event: str, secs: float) -> None:
    """掛鉤花了多久（未簽章的量測紀錄；端到端證據拿它算 p95）。"""
    try:
        p = rec.dir / "perf.jsonl"
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "agent": agent, "event": event,
                                "ms": round(secs * 1000, 2)}) + "\n")
    except OSError:
        pass


# ── 逐字稿 ────────────────────────────────────────────────────────────

def models_from_transcript(agent: str, data: bytes) -> dict[str, str]:
    """步驟 id → 逐字稿**自稱**的模型。Claude：assistant 訊息的 `message.model` 與其中的
    `tool_use.id`；Codex rollout：最近一個 `turn_context.model` 與 `function_call.call_id`。"""
    out: dict[str, str] = {}
    current = None
    for line in data.decode("utf-8", "replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        if agent == "claude" and d.get("type") == "assistant":
            msg = d.get("message") or {}
            model = msg.get("model")
            for c in msg.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("id") and model:
                    out[str(c["id"])] = str(model)
        elif agent == "codex":
            raw_pl = d.get("payload")
            pl: dict[str, Any] = raw_pl if isinstance(raw_pl, dict) else {}
            if d.get("type") == "turn_context" and pl.get("model"):
                current = str(pl["model"])
            if d.get("type") == "response_item" and current:
                cid = pl.get("call_id")
                if cid and pl.get("type") in ("function_call", "custom_tool_call",
                                               "local_shell_call"):
                    out[str(cid)] = current
    return out


def seal_transcript(rec: R.Recorder, actor: R.Actor, agent: str, path: Any, *,
                    role: str) -> dict[str, Any] | None:
    p = pathlib.Path(str(path)).expanduser()
    try:
        size = p.stat().st_size
        if size > MAX_TRANSCRIPT:
            data = None
        else:
            data = p.read_bytes()
    except OSError as e:
        with rec._lock():
            return rec._append("coverage", {"actor": actor.to_json(), "role": role,
                                            "missing": "transcript", "path": str(p),
                                            "error": str(e)[:200]})
    payload: dict[str, Any] = {"actor": actor.to_json(), "role": role, "path": str(p),
                               "size": size, "observed_by": "agent_claim"}
    if data is not None:
        payload["sha256"] = rec.blobs.put_bytes(data)
        models = models_from_transcript(agent, data)
        payload["models_claimed"] = models
    with rec._lock():
        return rec._append("transcript", payload)
