"""零設定的回合結束：agent 說做完 → 證據檢查（子行程、有時限）→ 退回或放行 → 交件說明。

這支在架構裡承重什麼：產品原則「裝一次、照常用，成果比沒裝好」（CLAUDE.md〈產品原則〉；
`decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md` §二、§四、§五）。沒有契約的專案，
`adapters/hook.handle` 在 Stop 走這裡，不走 `hookpolicy.decide_stop`（那條要契約）。

1. **病歷先驗**：只驗上次驗過之後新增的那一段（`Recorder.verify_since`）。驗不過 ⇒ 舊鏈改名留著、
   從新的一段開始，這一次**不退回**，交件說明講一次。
2. **證據檢查**（`trace/evidence.py`）在子行程裡跑，時限 `CHECK_TIMEOUT_S`；超時或任何錯誤 ⇒ 放行，
   錯誤記在掛鉤的錯誤紀錄，畫面最多一行 `DID_NOT_RUN`。
3. **退回的回合數**：人的一個要求之內最多 `ZERO_MAX_ROUNDS` 回合；「點名的檔沒打開」只退回
   `UNREAD_MAX_ROUNDS` 回合。人打新要求重新算（`hookpolicy.new_request`，鍵＝`scope(ws)`）；
   掛鉤沒收到人的提示時，看到回合起點變了也重新算。
4. **解決看現況**：每一次都在現在的工作區與紀錄上重跑，發現不在了就是解決了。值還在原位、那一行標了
   假設 ⇒ 記成「揭露了、沒修」，不算修好。
5. **只剩最後一回合**（v3，agent 的系統提示寫了回合上限、擴充數到只剩 1 回合）：只退回「要求的檔不存在」——
   一回合裡只來得及把檔寫出來；其他發現照樣寫進交件說明。沒有寫明上限時行為和字句都和之前一樣。
6. **還沒說做完就結束**（v3，`ended`）：回合上限、Esc、關掉——交件前檢查沒跑到的那一跑也寫一份交件說明給人
   （哪個要求的檔不在、提醒過幾次），不送任何東西給模型。
7. **交件說明**寫在 `$VACANT_HOME/trace/projects/<專案>/delivery.{md,json}`：不寫進工作區、不送給模型。
   畫面上最多 6 行（Claude `systemMessage`、pi 有介面時的 `ui.notify`）；這一回合沒有寫出任何檔 ⇒ 不顯示。

誠實邊界：
1. 退回只根據紀錄：紀錄裡看不到的讀取（殼層指令執行中讀的檔）會讓「沒打開」「找不到出處」偏向多報，
   所以只在高確定度的四類上退回（`evidence.py` 誠實邊界 1–3）。退回不是說答案錯了。
2. 子行程超時會被砍掉；那一次什麼都沒查（不是「查過沒問題」），交件說明寫的是「沒跑」。
3. 驗病歷的記號存在病歷旁邊、沒有簽章，只省時間不是證據（`Recorder.verify_since`）。
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
import re
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any

from . import capture
from .recorder import Recorder

ZERO_MAX_ROUNDS = 2
UNREAD_MAX_ROUNDS = 1
CHECK_TIMEOUT_S = 330
STATE_FILE = "zero_state.json"
NOTE_MAX_LINES = 6
DID_NOT_RUN = "Vacant check did not run (error recorded)."
NOTE_FOOTER = "This note lists what the record shows; it does not say whether the answer is right."


def scope(ws: str | pathlib.Path) -> SimpleNamespace:
    """回饋輪數的鍵（`hookpolicy._rounds_file` 讀 `.path`）：沒有契約時用專案根目錄。"""
    return SimpleNamespace(path=f"ws:{pathlib.Path(ws).resolve()}")


# ── state ────────────────────────────────────────────────────────────
def _load_state(rec: Recorder) -> dict[str, Any]:
    try:
        st = json.loads((rec.dir / STATE_FILE).read_text(encoding="utf-8"))
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(rec: Recorder, st: dict[str, Any]) -> None:
    from ..atomic import atomic_write_text
    rec.dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(rec.dir / STATE_FILE, json.dumps(st, ensure_ascii=False))


def _rounds_used(session_id: str | None, zc: Any) -> int:
    from ..adapters.hookpolicy import _rounds_file
    try:
        return int(json.loads(_rounds_file(session_id, zc).read_text()).get("n", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0


# ── the child process ────────────────────────────────────────────────
def check(req: dict[str, Any]) -> dict[str, Any]:
    """子行程裡跑的那一段：驗病歷（增量）→ 證據檢查。只讀病歷與工作區，只寫病歷目錄裡的狀態。"""
    from .evidence import evidence_for
    rec = Recorder(req["ws"])
    if not rec.chain_path.is_file():
        return {"ran": False, "why": "no record for this project yet"}
    st = _load_state(rec)
    ok, why, mark = rec.verify_since(st.get("verified"))
    if not ok:
        moved = rec.set_aside(why)
        st["verified"] = None
        st.setdefault("set_aside", []).append({"at": time.time(), "why": why, "file": moved,
                                               "told": False})
        _save_state(rec, st)
        return {"ran": False, "broken": why, "set_aside": moved}
    st["verified"] = mark
    _save_state(rec, st)
    today = _dt.date.fromisoformat(req["today"]) if req.get("today") else None
    res = evidence_for(rec, platform=req["platform"], session=req["session"],
                       final_text=req.get("final_text"), today=today)
    return {"ran": True, "result": res}


def _run_child(req: dict[str, Any]) -> dict[str, Any]:
    p = subprocess.run([sys.executable, "-m", "vacant_network.trace.zerostop", "check"],
                       input=json.dumps(req), capture_output=True, text=True,
                       timeout=CHECK_TIMEOUT_S, start_new_session=True)
    if p.returncode != 0:
        raise RuntimeError(f"check exited {p.returncode}: {p.stderr.strip()[-400:]}")
    lines = [x for x in p.stdout.splitlines() if x.strip()]
    if not lines:
        raise RuntimeError("check printed nothing")
    return json.loads(lines[-1])


# ── the decision ─────────────────────────────────────────────────────
def _compact(f: dict[str, Any]) -> dict[str, Any]:
    return {k: f.get(k) for k in ("finding_id", "kind", "path", "line", "value", "sub", "step",
                                  "quote", "cmd", "asked") if f.get(k) is not None}


def stop(agent: str, session_id: str | None, cwd: str | None, final_text: str | None, *,
         mode: str, runner: Any = None, turns_left: int | None = None,
         budget: int | None = None) -> tuple[str, str, dict[str, Any]]:
    """回 `(action, reason, record)`；`action` 只會是 `allow` 或 `continue`。
    任何錯誤 ⇒ `allow`（失敗一律放行），`record["user_message"]` 最多一行。"""
    ws = capture.workspace_for(cwd, None)
    if ws is None:
        return "allow", "", {}
    rec = Recorder(ws)
    if not rec.chain_path.is_file():
        return "allow", "", {"zero": {"ran": False, "why": "nothing recorded"}}
    session = str(session_id or "unknown")
    req = {"ws": str(ws), "platform": agent, "session": session,
           "final_text": (final_text or "")[:20000] or None}
    try:
        out = (runner or _run_child)(req)
    except subprocess.TimeoutExpired:
        return "allow", "", {"zero": {"ran": False, "error": f"timed out after {CHECK_TIMEOUT_S} s"},
                             "user_message": DID_NOT_RUN}
    except Exception as e:  # noqa: BLE001 — 失敗一律放行
        return "allow", "", {"zero": {"ran": False, "error": f"{type(e).__name__}: {e}"[:400]},
                             "user_message": DID_NOT_RUN}
    try:
        return _decide(rec, agent, session_id, session, out, mode, turns_left=turns_left,
                       budget=budget)
    except Exception as e:  # noqa: BLE001
        return "allow", "", {"zero": {"ran": False, "error": f"{type(e).__name__}: {e}"[:400]},
                             "user_message": DID_NOT_RUN}


def _decide(rec: Recorder, agent: str, session_id: str | None, session: str,
            out: dict[str, Any], mode: str, *, turns_left: int | None = None,
            budget: int | None = None) -> tuple[str, str, dict[str, Any]]:
    from ..adapters.hookpolicy import _bump_round, _rounds_file
    from . import review
    from .stopcheck import _actor_tokens
    zc = scope(rec.workspace)
    key = f"{agent}:{session}"
    st = _load_state(rec)
    if not out.get("ran"):
        if out.get("broken"):
            note = _write_note(rec, key, None, st.get("sessions", {}).get(key) or {}, mode,
                               broken=out)
            _told(rec)
            return "allow", "", {"zero": {"ran": False, "broken": out.get("broken")},
                                 "user_message": note}
        return "allow", "", {"zero": {"ran": False, "why": out.get("why")}}
    res = out["result"]
    sess = dict((st.get("sessions") or {}).get(key) or {})
    if sess.get("request") != res.get("window_start"):
        # 新的要求（掛鉤沒收到人的提示時也認得出來）：之前的回合與開著的發現不帶過來
        sess = {"request": res.get("window_start"), "rounds": [], "open": []}
        _rounds_file(session_id, zc).unlink(missing_ok=True)
    used = _rounds_used(session_id, zc)
    findings = res.get("findings") or []
    pushable = [f for f in findings if f["kind"] != "unread" or used < UNREAD_MAX_ROUNDS]
    last_turn = turns_left is not None and turns_left <= 1
    if last_turn:   # 只剩一回合：只來得及把要求的檔寫出來（其他的照樣進說明）
        pushable = [f for f in pushable if f["kind"] == "missing_output"]
    now_ids = {f["finding_id"] for f in findings}
    was_open = [f for r in sess.get("rounds") or [] for f in r.get("findings") or []]
    resolved = sorted({f["finding_id"] for f in was_open} - now_ids)
    event: dict[str, Any] = {"mode": mode, "session": key, "window_start": res.get("window_start"),
                             "deliverables": res.get("deliverables"),
                             "findings": [_compact(f) for f in findings][:30],
                             "resolved": resolved}
    if mode == "evidence" and pushable and used < ZERO_MAX_ROUNDS:
        n = _bump_round(session_id, zc)
        text, withheld = review.render(pushable, actor_tokens=_actor_tokens(rec),
                                       previous_open=set(sess.get("open") or []),
                                       budget_note=review.turns_left_note(turns_left, budget)
                                       if last_turn else "")
        sess.setdefault("rounds", []).append({"round": n, "findings":
                                              [_compact(f) for f in pushable]})
        sess["open"] = sorted(f["finding_id"] for f in pushable)
        _put_session(rec, key, sess)
        event.update(action="continue", round=n, sent=[f["finding_id"] for f in pushable],
                     withheld=withheld, **({"turns_left": turns_left, "budget": budget}
                                           if last_turn else {}))
        rec.append("review", event)
        _write_note(rec, key, res, sess, mode, in_progress=True)
        return "continue", text, {"zero": {"ran": True, "round": n, "sent": len(pushable),
                                           "withheld": withheld}}
    if not findings:
        _rounds_file(session_id, zc).unlink(missing_ok=True)
    sess["open"] = []
    _put_session(rec, key, sess)
    # 還在的都寫進說明（含回合用完之後才不再退回的「沒打開」）；觀察模式另外列
    left = findings if mode == "evidence" else []
    event.update(action="allow", rounds_used=used, left_open=[f["finding_id"] for f in left])
    rec.append("review", event)
    note = _write_note(rec, key, res, sess, mode, left_open=left, rounds_used=used)
    record: dict[str, Any] = {"zero": {"ran": True, "rounds_used": used,
                                       "left_open": len(left)}}
    if note and res.get("deliverables"):
        record["user_message"] = note
    return "allow", "", record


def _put_session(rec: Recorder, key: str, sess: dict[str, Any]) -> None:
    st = _load_state(rec)
    st.setdefault("sessions", {})[key] = sess
    _save_state(rec, st)


def _told(rec: Recorder) -> None:
    st = _load_state(rec)
    for x in st.get("set_aside") or []:
        x["told"] = True
    _save_state(rec, st)


# ── the delivery note ────────────────────────────────────────────────
def _value_state(rec: Recorder, f: dict[str, Any]) -> str:
    """一個曾經退回的「沒有出處的值」現在怎樣了：changed／disclosed／confirmed。"""
    from .evidence import ASSUMPTION_WORDS, EXEMPT_HEADINGS
    try:
        lines = (rec.workspace / str(f.get("path"))).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return "changed"
    val = str(f.get("value") or "")
    under: set[int] = set()          # `Unverified`／`Assumptions` 這類標題底下的行
    level: int | None = None
    for i, ln in enumerate(lines, 1):
        h = re.match(r"^\s{0,3}(#{1,6})\s", ln)
        if h:
            if level is not None and len(h.group(1)) <= level:
                level = None
            if EXEMPT_HEADINGS.match(ln):
                level = len(h.group(1))
        if level is not None:
            under.add(i)
    hits = [i for i, ln in enumerate(lines, 1) if val and val in ln]
    if not hits:
        return "changed"
    if any(i in under or ASSUMPTION_WORDS.search(lines[i - 1]) for i in hits):
        return "disclosed"
    return "confirmed"


def _say(f: dict[str, Any]) -> str:
    k = f.get("kind")
    if k == "unsourced":
        where = f"{f.get('path')} line {f.get('line')}" if f.get("line") else str(f.get("path"))
        return f'{where}: "{f.get("value")}" had no source in the record'
    if k == "unread":
        return f"{f.get('path')} (named in the request) had not been opened"
    if k == "missing_output":
        return f"{f.get('path')} (asked for in the request) did not exist"
    if k == "test_claim":
        return f'the final message said "{f.get("quote")}" without a matching test run'
    if k == "failed_step":
        return f"step {f.get('step')} ({f.get('cmd')}) had failed"
    return str(k)


def _write_note(rec: Recorder, key: str, res: dict[str, Any] | None, sess: dict[str, Any],
                mode: str, *, in_progress: bool = False, left_open: list[dict[str, Any]] | None = None,
                rounds_used: int = 0, broken: dict[str, Any] | None = None,
                after_end: str | None = None) -> str:
    """寫 delivery.md／.json；回畫面上的短訊息（最多 `NOTE_MAX_LINES` 行）。
    `after_end`：這一跑已經結束、檢查是事後補跑的（v3.2）——那一句放在最前面，還在的發現寫成「事後查到、沒有退回」。"""
    md = rec.dir / "delivery.md"
    stamp = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    out = ["# Vacant delivery note", "", f"Project: {rec.workspace}", f"Session: {key}",
           f"Turn ended: {stamp}" + (" (sent back for another pass)" if in_progress else ""), ""]
    if after_end:
        out += ["## Checked after the run ended", "", f"- {after_end}", ""]
    screen: list[str] = [after_end] if after_end else []
    data: dict[str, Any] = {"project": str(rec.workspace), "session": key, "at": stamp,
                            "mode": mode, "in_progress": in_progress,
                            **({"checked_after_end": True} if after_end else {})}
    if broken:
        why = str(broken.get("broken"))
        out += ["## Not checked", "",
                f"- The record of this project did not verify ({why}). It was set aside as "
                f"{broken.get('set_aside')} and a new one was started. This turn was not reviewed.",
                "", NOTE_FOOTER, ""]
        data["broken"] = broken
        _write(md, "\n".join(out), data)
        return (f"Vacant: the record of this project did not verify and was set aside; this turn "
                f"was not reviewed. Note: {md}")
    assert res is not None
    v = res.get("values") or {}
    delivs = res.get("deliverables") or []
    named = res.get("materials_named") or []
    observed = set(res.get("observed") or [])
    opened = [x for x in named if x in observed]
    not_opened = [x for x in named if x not in observed]
    out += ["## What was checked", ""]
    out.append("- Files written in this turn: " + (", ".join(delivs[:20]) if delivs else "none"))
    checked = int(v.get("checked") or 0)
    if checked:
        out.append(f"- Values in the lines written this turn: {checked} checked — "
                   f"{v.get('traced', 0)} found in what the task read or ran, "
                   f"{v.get('derived', 0)} computable from tables it read, "
                   f"{v.get('exempt', 0)} given in the request, dated today, or marked as "
                   f"assumptions, {v.get('not_typed', 0)} written by a script it ran")
    if named:
        out.append(f"- Files named in the request: {len(named)} — opened: "
                   f"{', '.join(opened) or 'none'}" +
                   (f"; not opened: {', '.join(not_opened)}" if not_opened else ""))
    in_dirs = res.get("materials_in_dirs") or []
    dir_opened = [x for x in in_dirs if x in observed]
    if in_dirs:
        out.append(f"- Files in the folders named in the request: {len(in_dirs)} — opened: "
                   f"{', '.join(dir_opened[:20]) or 'none'}")
    out.append("- Final message: " + ("checked for test and build claims"
                                      if res.get("final_text_seen") else "not available"))
    fixed: list[str] = []
    disclosed: list[str] = []
    now = {f["finding_id"] for f in res.get("findings") or []}
    for r in sess.get("rounds") or []:
        for f in r.get("findings") or []:
            if f["finding_id"] in now:
                continue
            if f.get("kind") == "unsourced":
                s = _value_state(rec, f)
                if s == "disclosed":
                    disclosed.append(f"round {r['round']}: {_say(f)}; it is still there, marked "
                                     f"as an assumption")
                    continue
                how = ("the value was changed" if s == "changed"
                       else "the value was checked against what was read")
            elif f.get("kind") == "unread":
                how = "it was opened afterwards"
            elif f.get("kind") == "missing_output":
                how = "it was written afterwards"
            else:
                how = "the record now matches"
            fixed.append(f"round {r['round']}: {_say(f)}; {how}")
    if fixed:
        out += ["", "## Redone before delivery", ""] + [f"- {x}" for x in fixed]
    unverified: list[str] = []
    for x in (v.get("not_traced_note_only") or [])[:20]:
        unverified.append(f"{x}: not found in the record (the request named no data, so it was "
                          f"not sent back)")
    unread_dir = res.get("unread_dir") or []
    if unread_dir:
        unverified.append("Given files never opened: " + ", ".join(unread_dir[:20]))
    unverified += disclosed
    for f in left_open or []:
        unverified.append(f"Found after the run ended (not sent back): {_say(f)}" if after_end
                          else f"Still open after {rounds_used} round(s): {_say(f)}")
    if mode == "observe":
        for f in res.get("findings") or []:
            unverified.append(f"Observed (not sent back, observe mode): {_say(f)}")
    if unverified:
        out += ["", "## Not verified", ""] + [f"- {x}" for x in unverified]
    st = _load_state(rec)
    untold = [x for x in st.get("set_aside") or [] if not x.get("told")]
    if untold:
        out += ["", f"Earlier record set aside because it did not verify: {untold[-1].get('file')} "
                    f"({untold[-1].get('why')})"]
    out += ["", NOTE_FOOTER, ""]
    data.update(checked=v, deliverables=delivs, named=named, opened=opened,
                not_opened=not_opened, in_dirs=in_dirs, dir_opened=dir_opened,
                fixed=fixed, unverified=unverified,
                findings=res.get("findings") or [])
    _write(md, "\n".join(out), data)
    if untold:
        _told(rec)
    if in_progress:
        return ""
    given, given_opened = len(named) + len(in_dirs), len(opened) + len(dir_opened)
    screen.append(f"Vacant checked this turn: {checked} value(s)" +
                  (f", {given_opened}/{given} given file(s) opened" if given else "") + ".")
    if fixed:
        screen.append(f"Redone before delivery: {len(fixed)} point(s).")
    n_unv = len(v.get("not_traced_note_only") or []) + len(disclosed)
    if n_unv or unread_dir:
        parts = []
        if n_unv:
            parts.append(f"{n_unv} value(s) without a source in the record")
        if unread_dir:
            parts.append(f"{len(unread_dir)} given file(s) not opened")
        screen.append("Not verified: " + "; ".join(parts) + ".")
    if left_open:
        screen.append(f"Found after the run ended: {len(left_open)} point(s)." if after_end
                      else f"Still open after {rounds_used} round(s): {len(left_open)} point(s).")
    screen.append(f"Note: {md}")
    return "\n".join(screen[:NOTE_MAX_LINES])


def _write(md: pathlib.Path, text: str, data: dict[str, Any]) -> None:
    from ..atomic import atomic_write_text
    md.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(md, text)
    atomic_write_text(md.with_suffix(".json"), json.dumps(data, ensure_ascii=False, indent=1,
                                                          default=str))


# ── ended before the agent said it was done (v3) ────────────────────
def ended(agent: str, session_id: str | None, cwd: str | None, *, mode: str,
          turn: Any = None, budget: Any = None, final_answer: bool = False,
          final_text: str | None = None, runner: Any = None) -> dict[str, Any]:
    """這一跑被中止（pi 回報：回合上限或人按 Esc）、而且這個要求最後沒有一次放行的交件前檢查：
    寫交件說明給人（只寫檔：工作階段結束時已經沒有畫面可以顯示）。不送任何東西給模型。任何錯誤都不擋。
    最後一次檢查是「退回」（只剩一回合時退回缺檔、接著被上限切斷）也寫（v3.1）。
    `final_answer`：最後一回合是最終答案（agent 說了做完），只是檢查沒跑到——這裡補跑同一個檢查，
    結果照一般的交件說明寫給人，**不說**「還沒說做完」（v3.2；2026-09-26 審查：正式批次 C2 的 7 份說明裡 2 份是這種）。"""
    from .budget import missing_outputs
    from .evidence import Evidence
    ws = capture.workspace_for(cwd, None)
    if ws is None:
        return {}
    rec = Recorder(ws)
    if not rec.chain_path.is_file():
        return {}
    session = str(session_id or "unknown")
    key = f"{agent}:{session}"
    ev = Evidence(rec, platform=agent, session=session)
    start, texts, steps = ev.window()
    if not steps:
        return {"ended": {"why": "no steps in this request"}}
    evs = [e for e in rec.events() if e.get("session") == key and int(e.get("seq") or 0) > start]
    reviews = [e for e in evs if e.get("type") == "review"]
    if any(e.get("type") == "ended" for e in evs) or (reviews and reviews[-1].get("action") != "continue"):
        return {"ended": {"why": "the delivery check let it through (or the note exists)"}}
    nudges = [e for e in evs if e.get("type") == "nudge"]
    asked = ev.requested_outputs(texts)
    _s2, missing = missing_outputs(rec, agent, session)
    miss = {rel for rel, _ in missing}
    try:
        turn_i, budget_i = int(turn), int(budget)
        at_cap = turn_i >= budget_i
    except (TypeError, ValueError):
        turn_i = budget_i = None  # type: ignore[assignment]
        at_cap = False
    if final_answer:
        done = _check_after_end(rec, agent, session_id, session, key, start, mode, final_text,
                                turn_i, budget_i, at_cap, nudges, sorted(miss), runner)
        if done is not None:
            return done
    head = ("The agent said it was done, but the delivery check did not run."
            if final_answer else
            "Ended before the agent said it was done" +
            (f", after the stated {budget_i} model turns" if at_cap else "") +
            ("; the last delivery check had sent it back." if reviews else "; no delivery check ran."))
    lines = [head]
    turns = [str(e.get("turn")) for e in nudges]
    reminded = ("" if not turns else f" A budget reminder was sent after turn {turns[0]}." if len(turns) == 1
                else f" Budget reminders were sent after turns {', '.join(turns)}.")
    for rel, raw in asked:
        lines.append(f"{raw}: " + ("does not exist." if rel in miss else
                                   "exists; its content was not checked.") + reminded)
    stamp = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    md = rec.dir / "delivery.md"
    out = ["# Vacant delivery note", "", f"Project: {rec.workspace}", f"Session: {key}",
           f"Ended: {stamp}", "", "## Stopped before delivery", "", *[f"- {x}" for x in lines],
           "", NOTE_FOOTER, ""]
    data = {"project": str(rec.workspace), "session": key, "at": stamp, "mode": mode,
            "ended_before_delivery": True, "turn": turn_i, "budget": budget_i,
            "requested": [r for r, _ in asked], "missing": sorted(miss),
            "nudged_turns": [e.get("turn") for e in nudges]}
    _write(md, "\n".join(out), data)
    rec.append("ended", {"session": key, "window_start": start, "turn": turn_i, "budget": budget_i,
                         "missing": sorted(miss), "nudges": len(nudges),
                         **({"final_answer": True, "checked": False} if final_answer else {})})
    screen = [head] + lines[1:3] + [f"Note: {md}"]
    return {"ended": {"missing": len(miss), "nudges": len(nudges)},
            "user_message": "\n".join(screen[:NOTE_MAX_LINES])}


def _check_after_end(rec: Recorder, agent: str, session_id: str | None, session: str, key: str,
                     start: int, mode: str, final_text: str | None, turn: int | None,
                     budget: int | None, at_cap: bool, nudges: list[dict[str, Any]],
                     missing: list[str], runner: Any) -> dict[str, Any] | None:
    """agent 說了做完、這一跑已經結束：補跑交件前檢查（同一個檢查、同一個子行程與時限），只寫給人。
    檢查跑不起來 ⇒ None（呼叫端寫「說了做完、檢查沒跑」的短說明）。"""
    req = {"ws": str(rec.workspace), "platform": agent, "session": session,
           "final_text": (final_text or "")[:20000] or None}
    try:
        out = (runner or _run_child)(req)
    except Exception as e:  # noqa: BLE001 — 失敗一律不擋
        rec.append("ended", {"session": key, "window_start": start, "turn": turn, "budget": budget,
                             "final_answer": True, "checked": False,
                             "error": f"{type(e).__name__}: {e}"[:300]})
        return None
    if not out.get("ran"):
        return None
    res = out["result"]
    st = _load_state(rec)
    sess = dict((st.get("sessions") or {}).get(key) or {})
    if sess.get("request") != res.get("window_start"):
        sess = {"request": res.get("window_start"), "rounds": [], "open": []}
    findings = res.get("findings") or []
    said = ("The agent said it was done on the last of the stated "
            f"{budget} model turns; the run stopped there, before the delivery check could send "
            "anything back." if at_cap and budget else
            "The agent said it was done, and the run was stopped before the delivery check could "
            "send anything back.")
    said += " The check ran afterwards, for you only (nothing was sent to the agent)."
    note = _write_note(rec, key, res, sess, mode, left_open=findings if mode == "evidence" else [],
                       rounds_used=_rounds_used(session_id, scope(rec.workspace)), after_end=said)
    rec.append("ended", {"session": key, "window_start": start, "turn": turn, "budget": budget,
                         "missing": missing, "nudges": len(nudges), "final_answer": True,
                         "checked": True, "findings": [_compact(f) for f in findings][:30]})
    return {"ended": {"final_answer": True, "checked": True, "findings": len(findings),
                      "nudges": len(nudges)},
            "user_message": note}


def final_text_of(payload: dict[str, Any]) -> str | None:
    """agent 這一回合最後的訊息：pi 的擴充送 `final_text`；Claude Code 與 Codex 的 Stop 送
    `last_assistant_message`（2026-09-25 查過兩者的掛鉤結構）。拿不到 ⇒ None（測試說法就不查）。"""
    for k in ("final_text", "last_assistant_message"):
        t = payload.get(k)
        if isinstance(t, str) and t.strip():
            return t
    return None


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["check"]:
        print("usage: python -m vacant_network.trace.zerostop check  (JSON request on stdin)",
              file=sys.stderr)
        return 2
    req = json.loads(sys.stdin.read() or "{}")
    print(json.dumps(check(req), ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
