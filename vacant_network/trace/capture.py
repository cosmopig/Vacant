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
3. 一則使用者訊息是誰說的（`classify`）只看掛鉤送來的內容：人貼上一段形狀完全一樣的信封、一字不差地
   打出 agent 排過的提示（沒開追緝時比的是 `$VACANT_HOME/intake/hooks/scheduled_*.json` 裡的雜湊）、
   或在 agent 排過 `/loop` 記號的工作階段裡貼上帶著那一種標題行的一段，都會被當成不是人說的；
   agent 在殼層裡自己呼叫 `vacant hook` 偽造一則「人打的」，這裡看不出來（字串層的擋在 `hookpolicy`）。偽造的那一則最多成為**它自己那個工作階段**的任務訊息——
   `*`／`do:<run>` 這兩種工作階段鍵掛鉤記不出來（`reserved_session`）。
4. `vacant do` 開出來的工作階段靠環境變數 `VACANT_DO_RUN` 認（掛鉤行程從 agent 繼承）：agent 沒把環境傳給
   掛鉤行程 ⇒ `run.do` 記的那一筆任務訊息對它不算數（它自己的提示掛鉤記的那一則照樣算），重試提示整段記成
   人說的——接在後面、`run.do` 記過的回饋原文照樣在追緝時逐字拿掉（`blame.Trace.prompt_text`），改寫過的拿不掉。
   偽造掛鉤時自己帶上這個環境變數，也能把一個工作階段標成那一跑的（同第 3 條，這裡看不出來）。
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
_HOOK_WRAPPER_END = re.compile(r"</hook_prompt>\s*$")
#: Claude Code 2.1.281 的 binary 裡**別的行動者**的信封（別的工作階段、隊友、外面的事件）：
#: 標籤 → 那個信封一定帶的屬性。binary 組出來的形狀是 `<標籤 屬性="…" …>` 開頭、後面有 `</標籤>`
#: （teammate：`<teammate-message teammate_id="…"[ color=…][ summary=…]>\n…\n</teammate-message>`；
#: cross-session：`<cross-session-message from="…"[ from-name=…]…>\n…\n</cross-session-message>`；
#: 事件：`<event[ nonce=…] kind="…" at="…">…</event>`；`<wake reason="external-event" current-time="…">…</wake>`）。
#: 只認這個形狀、只認 Claude：人貼上的 `<event type="close" total="4321"/>` 不是信封（2026-09-25 審查 #10）
_ENVELOPE_ATTR = {"teammate-message": "teammate_id", "cross-session-message": "from",
                  "event": "kind", "wake": "reason"}
_ENVELOPE_OPEN = re.compile(r'<(teammate-message|cross-session-message|event|wake)'
                            r'((?:[ \t]+[A-Za-z][A-Za-z0-9_-]*="[^"\n]*")+)[ \t]*>')
#: binary 在信封前面有時加一行（只加在這幾種信封前面）：別的工作階段的訊息前的說明、
#: 一批事件前的 `<system>authentic event nonces for this delivery: …</system>`
_ENVELOPE_LEADS = {"Another Claude session sent a message": ("teammate-message",
                                                            "cross-session-message"),
                   "A peer session sent a message": ("teammate-message", "cross-session-message"),
                   "<system>authentic event nonces for this delivery: ": ("event",)}
#: agent 自己排的提示（到時候以一則使用者訊息回來，掛鉤的內容和人打的一模一樣）
SCHEDULER_TOOLS = frozenset({"CronCreate", "ScheduleWakeup"})
#: `/loop` 的排程提示是一個記號，Claude Code 在觸發時換成一段固定開頭的指示（binary 2.1.281：
#: 自動循環第一次是「# Autonomous loop check」的前言＋`---`＋tick，之後只有 tick；loop.md 那一種是
#: 「# /loop tick — …」起頭）。記號 → 觸發時那一則裡的標題行（整行相等／這個開頭）
_LOOP_AUTONOMOUS = ("# Autonomous loop check", "# Autonomous loop tick",
                    "# Autonomous loop tick (dynamic pacing)")
LOOP_SENTINELS: dict[str, tuple[tuple[str, ...], str | None]] = {
    "<<autonomous-loop>>": (_LOOP_AUTONOMOUS, None),
    "<<autonomous-loop-dynamic>>": (_LOOP_AUTONOMOUS, None),
    "<<loop.md>>": ((), "# /loop tick — "),
    "<<loop.md-dynamic>>": ((), "# /loop tick — "),
}
#: Claude Code 的 UserPromptSubmit `source`（binary 裡的欄位說明；目前還不送）——只有這兩種是人
_PERSON_SOURCES = frozenset({"user", "sdk"})
#: `vacant do` 那一跑的 id：`adapters/run.do` 設在 agent 的環境裡，掛鉤行程從 agent 繼承
DO_RUN_ENV = "VACANT_DO_RUN"


def reserved_session(session: str) -> bool:
    """只有 Vacant 自己記的提示用得到的工作階段鍵：`*`＝這個工作區裡的任何工作階段（舊病歷裡 `vacant do`
    的記法）、`do:<run>`＝那一跑開出來的工作階段。掛鉤送來的 `session_id` 不可以是這兩種
    （2026-09-25 審查 C1：偽造一則 `session_id="*"` 的「人打的」就成了每個工作階段的任務訊息）。"""
    return session == "*" or session.startswith("do:")


def _session(v: Any) -> str:
    s = str(v or "unknown")
    return "hook:" + s if reserved_session(s) else s


def _unwrap(text: str) -> str:
    """去掉 Codex 的 `<hook_prompt …>` 包裝與前後空白（比對「是不是同一段文字」用）。"""
    t = _HOOK_WRAPPER.sub("", text, count=1)
    return _HOOK_WRAPPER_END.sub("", t).strip()


def _claude_envelope(t: str) -> str | None:
    """`t` 是 Claude Code 送進來的別的行動者的信封 ⇒ 標籤名；不是 ⇒ None。
    要：（可有可無的那一行說明）＋開頭標籤帶著那個信封一定有的屬性＋後面有對應的結束標籤。"""
    allowed: tuple[str, ...] | None = None
    first, nl, rest = t.partition("\n")
    for lead, tags in _ENVELOPE_LEADS.items():
        if nl and first.startswith(lead):
            t, allowed = rest.lstrip("\n"), tags
            break
    m = _ENVELOPE_OPEN.match(t)
    if m is None:
        return None
    tag = m.group(1)
    if allowed is not None and tag not in allowed:
        return None
    if not re.search(r'(?:^|[ \t])' + re.escape(_ENVELOPE_ATTR[tag]) + r'="', m.group(2)):
        return None
    return tag if f"</{tag}>" in t[m.end():] else None


def prompt_source(agent: str, payload: dict[str, Any], text: str) -> tuple[str, str | None]:
    """這則「使用者訊息」其實是誰說的（2026-09-24 審查 blame#5、integration#0）：
    Claude 把背景子 agent 的結果以 `<task-notification>` 送回；Codex 子 agent 的
    UserPromptSubmit 是父 agent 給它的任務說明；Vacant 自己的回饋（2026-09-25）；
    Claude 送進來的別的行動者的話（隊友、別的工作階段、外面的事件）＝`other_actor`：
    不是人的新要求，但**是**值的來源——agent 抄了隊友給的數字，不是 agent 自己的錯（2026-09-25 審查 C0）。
    只認 Claude 的真形狀（審查 #10）；另外三個 agent 沒有這些信封，長得像的一則照樣是人打的。
    ⚠ 人打的訊息裡剛好貼了回饋的開頭，也會被當成 Vacant 的回饋（不當來源、不重新算輪數）；
    人貼上一段形狀完全一樣的信封（有那個屬性、有結束標籤），也會被當成別的行動者的話。
    ⚠ `<wake>` 裡由人觸發的那一則（綁定的討論串裡人的話）也記成別的行動者的話：是來源，但不重新算輪數。"""
    t = _HOOK_WRAPPER.sub("", text).lstrip()
    from .feedback import FEEDBACK_HEADER, FLAG_HEADER
    if t.startswith((FEEDBACK_HEADER, FLAG_HEADER)):
        # Vacant 自己的回饋被當成使用者訊息送回來（OpenCode 的外掛用 `session.prompt` 送）：不是人說的，
        # 也不是任何值的來源（裡面引了繳付物的錯值與應有的值；當成「任務說的」就等於替 agent 洗掉錯）。
        # 只認**開頭**：人打的一則裡引了一段回饋，仍然是人說的（2026-09-25 審查 loop#3）
        return "vacant_feedback", None
    if agent == "claude" and _claude_envelope(t) is not None:
        return "other_actor", None       # 別的工作階段／隊友／事件送進來的話，不是人打的
    if t.startswith("<task-notification>"):
        m = _TASK_NOTE.search(t)
        return "subagent_result", (m.group(1).strip() if m else None)
    parent = payload.get("parent_session_id")
    if payload.get("agent_id") or (parent and parent != payload.get("session_id")):
        return "parent_agent", None
    return "user", None


def _loop_fire_of(sentinel: str, body: str) -> bool:
    """`body` 是 `/loop` 記號 `sentinel` 觸發時 Claude Code 換上的那一段：有一**整行**就是那一種的標題
    （第一次觸發前面多一段前言；標題寫在一行的中間不算）。"""
    heads, prefix = LOOP_SENTINELS[sentinel]
    for line in body.split("\n"):
        line = line.rstrip()
        if line in heads or (prefix is not None and line.startswith(prefix)):
            return True
    return False


def _scheduled_matches(sched: str, body: str) -> bool:
    """排程時寫下的提示 `sched` 觸發時是不是就是 `body`：**相等**（去掉包裝與前後空白），不是「包含」——
    人的一則較長的訊息裡剛好有排程的那句話，仍然是人的（2026-09-25 審查 #6）。`/loop` 的記號在觸發時被換成
    固定開頭的指示（審查 #7）：記號只認它自己那一種的標題行。"""
    s = _unwrap(sched)
    if not s:
        return False
    if s in LOOP_SENTINELS:
        return _loop_fire_of(s, body)
    return s == body


def classify(agent: str, payload: dict[str, Any], text: str, cwd: str | None,
             contract: Any = None) -> tuple[str, str | None, str]:
    """`classify_prompt` 的完整版：多回一段**要記進病歷的文字**（`vacant do` 的重試提示只記任務那一段）。"""
    src, tid = prompt_source(agent, payload, text)
    if src != "user":
        return src, tid, text
    declared = payload.get("source")
    if isinstance(declared, str) and declared and declared not in _PERSON_SOURCES:
        return "machine", None, text
    body = _unwrap(text)
    sid = str(payload.get("session_id") or "")
    if scheduled_outside_trace(agent, sid, body):
        return "scheduled_by_agent", None, text
    ws = workspace_for(cwd, contract)
    if ws is None:
        return src, tid, text
    rec = R.Recorder(ws)
    events = rec.events()
    session = actor_of(agent, payload).session
    for e in events:
        if e.get("type") != "step" or e.get("tool") not in SCHEDULER_TOOLS or e.get("denied") \
                or e.get("error"):
            continue                     # 被擋下、失敗的排程不會觸發
        if sid and str((e.get("actor") or {}).get("session") or "") != session:
            continue
        try:
            inp = json.loads(rec.blobs.get(e["input_blob"]).decode("utf-8", "replace"))
        except (OSError, ValueError, KeyError, TypeError):
            continue
        sched = str((inp or {}).get("prompt") or "") if isinstance(inp, dict) else ""
        if _scheduled_matches(sched, body):
            return "scheduled_by_agent", str(e.get("step") or "") or None, text
    bodies = [body]
    if agent == "opencode":
        bodies.append(opencode_run_unquote(body))
    task = _vacant_do_task(rec, events, bodies)
    if task is not None:
        return "vacant do", None, task
    return src, tid, text


def opencode_run_unquote(body: str) -> str:
    """`opencode run` 把含空白的引數包成 `"…"`、裡面的 `"` 換成 `\\"` 再交給 session（opencode 1.x 的
    `run`：`args.map(a => a.includes(" ") ? '"' + a.replace(/"/g, '\\\\"') + '"' : a).join(" ")`）⇒
    外掛的 `chat.message` 看到的是包過的那一段。還原；不是這個形狀就原樣回傳。"""
    if len(body) > 1 and body[0] == body[-1] == '"':
        return body[1:-1].replace('\\"', '"')
    return body


def classify_prompt(agent: str, payload: dict[str, Any], text: str, cwd: str | None,
                    contract: Any = None) -> tuple[str, str | None]:
    """`prompt_source` 再加上要看病歷才分得出來的：agent 自己排的提示（CronCreate／ScheduleWakeup 在這個
    工作階段裡記過同一段文字，或 `/loop` 的記號；病歷沒開時看 `scheduled_outside_trace`）、平台送的 `source`
    說不是人、`vacant do` 交給 agent 的任務（重試時後面接著 Vacant 的回饋）。病歷記的來源與「人的新要求重新算
    輪數」都用這一份（2026-09-25 審查 loop#5：真的 Claude Code 在排程觸發時送的 UserPromptSubmit 和人打的一模一樣）。"""
    src, tid, _text = classify(agent, payload, text, cwd, contract)
    return src, tid


def _vacant_do_task(rec: R.Recorder, events: list[dict[str, Any]],
                    bodies: list[str]) -> str | None:
    """這一則是 `vacant do` 交給 agent 的提示 ⇒ 任務那一段（`run.do` 記的原文）；不是 ⇒ None。

    `run.do` 的重試提示＝任務 P＋`\\n\\n`＋Vacant 的回饋。agent 自己的提示掛鉤把它整段當成一則使用者訊息送來，
    整段記成「人說的」，回饋裡引的錯值就變成「任務自己說的」——agent 再寫一次同一個錯值，追緝就替它洗掉了
    （2026-09-25 審查 #0/#1/#5/#13/#23）。只認**這一跑**（`VACANT_DO_RUN`）記過的 P，後面只接得了這一跑記過的
    回饋原文、或以回饋開頭起頭的一段。"""
    run = os.environ.get(DO_RUN_ENV, "").strip()
    if not run:
        return None
    scope = f"do:{run}"
    tasks: list[str] = []
    fbs: set[str] = set()
    for e in events:
        if e.get("type") != "prompt" or str(e.get("session")) != scope:
            continue
        try:
            txt = rec.blobs.get(e["text_blob"]).decode("utf-8", "replace")
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if e.get("source") == "vacant do":
            tasks.append(txt)
        elif e.get("source") == "vacant_feedback":
            fbs.add(txt.strip())
    from .feedback import FEEDBACK_HEADER, FLAG_HEADER
    for body in bodies:
        for task in tasks:
            p = task.strip()
            if not p or not body.startswith(p):
                continue
            rest = body[len(p):]
            if not rest.strip():
                return task
            if not rest.startswith("\n"):
                continue
            rest = rest.strip()
            if rest in fbs or rest.startswith((FEEDBACK_HEADER, FLAG_HEADER)):
                return task
    return None


# ── agent 自己排的提示：病歷沒開也要記得（2026-09-25 審查 C5）──────────────────
# 輪數上限在沒開追緝的專案裡照樣有效；那裡看不到 CronCreate／ScheduleWakeup 那一步，agent 排給自己的
# 提示就又能把輪數歸零。這裡只記雜湊（`hook.py` 誠實邊界 2），每個工作階段一個小檔。
MAX_SCHEDULED = 256


def _scheduled_file(agent: str, session_id: str) -> pathlib.Path:
    from ..intake.statepaths import state_dir
    sid = re.sub(r"[^A-Za-z0-9._-]", "_", f"{agent}_{session_id or 'nosession'}")[:160]
    return state_dir() / "intake" / "hooks" / f"scheduled_{sid}.json"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_scheduled(p: pathlib.Path) -> list[str]:
    try:
        have = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(x) for x in have] if isinstance(have, list) else []


def remember_scheduled(agent: str, payload: dict[str, Any]) -> bool:
    """CronCreate／ScheduleWakeup 的掛鉤事件：記下它排的提示（雜湊）。回傳有沒有記。"""
    from ..atomic import atomic_write_text, file_lock
    tool, inp = _tool_and_input(agent, payload)
    if tool not in SCHEDULER_TOOLS or not isinstance(inp, dict):
        return False
    text = _unwrap(str(inp.get("prompt") or ""))
    if not text:
        return False
    p = _scheduled_file(agent, str(payload.get("session_id") or ""))
    h = _sha(text)
    with file_lock(p.with_name(p.name + ".lock")):
        have = _read_scheduled(p)
        if h not in have:
            atomic_write_text(p, json.dumps((have + [h])[-MAX_SCHEDULED:]))
    return True


def scheduled_outside_trace(agent: str, session_id: str, body: str) -> bool:
    """這個工作階段裡 agent 排過的提示（`remember_scheduled` 記的）觸發時就是 `body`（和病歷裡的比法一樣：
    相等；`/loop` 的記號認它自己那一種的標題行）。"""
    have = set(_read_scheduled(_scheduled_file(agent, session_id)))
    if not have or not body:
        return False
    if _sha(body) in have:
        return True
    return any(_sha(s) in have and _loop_fire_of(s, body) for s in LOOP_SENTINELS)


def actor_of(agent: str, payload: dict[str, Any]) -> R.Actor:
    sid = _session(payload.get("session_id"))
    if agent in ("claude", "codex"):
        return R.Actor(agent, sid, agent=_s(payload.get("agent_id")),
                       agent_type=_s(payload.get("agent_type")),
                       model=_s(payload.get("model")))
    if agent == "opencode":
        parent = _s(payload.get("parent_session_id"))
        if parent:          # 子 session ＝ 子 agent；工作階段鍵用根 session
            return R.Actor(agent, _session(payload.get("root_session_id") or parent),
                           agent=sid, agent_type=_s(payload.get("agent")) or "subagent",
                           model=_s(payload.get("model")))
        return R.Actor(agent, sid, model=_s(payload.get("model")))
    parent = _s(payload.get("parent_session_id"))
    if agent == "pi" and parent and _session(parent) != sid:
        # 另一個 pi 行程，從父 agent 的行程開出來（Vacant 的 pi 擴充帶過來的標記）：子 agent；
        # 工作階段鍵用最上層那個 session。代理人類型由 `link_child` 從叫它的那個呼叫補上
        return R.Actor(agent, _session(parent), agent=sid, agent_type="subagent",
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
    run = os.environ.get(DO_RUN_ENV, "").strip()
    if run:
        # `vacant do` 開出來的工作階段：那一跑的任務訊息（`do:<run>`）只對這些工作階段算數
        rec.tag_do_run(actor, run)
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
            # `vacant do` 的重試提示只記任務那一段（接在後面的回饋不是任何值的來源）
            src, tid, keep = classify(agent, payload, str(text), cwd, contract)
            out = rec.prompt(keep, session=actor.session, source=src, tool_use_id=tid,
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
    這個工作階段沒有檢查過（沒有契約、沒有 Stop）⇒ 不記。"""
    if contract is None or os.environ.get("VACANT_HOOK_NO_SUBMIT"):
        # `vacant do` 自己在行程結束後記這一跑（只記一次；2026-09-24 審查 consequences#1）
        return
    try:
        st = json.loads((rec.dir / "feedback_state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    # 只用**這個**工作階段自己的檢查結果；沒檢查過的工作階段不記（審查 consequences#2）
    mine = (st.get("outcomes") or {}).get(f"{actor.platform}:{actor.session}")
    if not mine:
        return
    st = {"outcome": mine}
    from . import actors as A
    model = actor.model or rec.session_info(actor.platform, actor.session).get("model")
    main = {"platform": actor.platform, "session": actor.session, "model": model}
    if A.record_outcome(A.ActorBook(), session_key=f"{actor.platform}:{actor.session}",
                        actor=main, accepted=st["outcome"] == "accept", contract=contract,
                        workspace=rec.workspace):
        rec.append("consequence", {"kind": "outcome", "accepted": st["outcome"] == "accept",
                                   "session": actor.session})


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
