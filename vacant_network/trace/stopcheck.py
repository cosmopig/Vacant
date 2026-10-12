"""stopcheck — **回合結束的那一刻**：驗 → 定位 → 追緝 → 事實回饋 → 報告。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §三「回合結束」）：

`adapters/hookpolicy.decide_stop` 驗完契約後叫 `localize()`。這裡把不過的主張交給
`blame.py`，把結論簽進病歷（`finding` 事件：新出現的、已解決的），把給 agent 的回饋換成
**有位置、有來源、沒有行動者**的版本，並把給人的未解問題清單寫到病歷目錄。

沒有病歷（這個專案沒開追緝、或還沒有任何步驟）⇒ 回 None，`decide_stop` 用原本的泛用回饋。

## 誠實邊界（改碼請保留）

1. 追緝在 Stop 的時間預算裡跑（Claude／Codex 600 秒）；重跑 `python_checks`／`command` 類
   主張可能要幾秒一次。追緝本身壞掉 ⇒ 回 None（泛用回饋照樣送），錯誤記在掛鉤的錯誤紀錄。
2. 報告寫在 `$VACANT_HOME/trace/projects/<專案>/`，**不寫進工作區**（寫進去會變成繳付物的一部分，
   也會被下一步記成改動）。
3. 截短偵測（`verify_anchored`）只到**最後一次錨點**為止：錨點在回合邊界寫進任務帳本，之後才加的
   病歷尾巴被截掉，只剩沒簽章的 `head.json` 對得出來。任務帳本自己也可能整條被換掉——那一層靠收件端
   保存的帳本鏈頭（`intake/ledger.py` 誠實邊界 1）。沒有契約／帳本 ⇒ 說「沒有對」，不當成對過了。
   回合邊界發現病歷驗不過時**不再錨定**，改在帳本簽一筆 `trace_broken`；之後 `vacant trace verify`
   一直回報壞掉（不會因為下一個回合又多寫幾步就「好了」）。要重新開始只能換一個乾淨的病歷目錄。
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

from . import actors as A
from . import capture
from . import feedback as F
from .blame import blame_results
from .recorder import Recorder


def _coverage(rec: Recorder) -> dict[str, Any]:
    steps = gaps = post_missing = 0
    for e in rec.events():
        if e["type"] == "step":
            steps += 1
            post_missing += 1 if e.get("post_missing") else 0
        elif e["type"] == "unrecorded_change":
            gaps += 1
    return {"steps": steps, "gaps": gaps, "post_missing": post_missing}


def _flag_blames(rec: Recorder, contract: Any) -> list[dict[str, Any]]:
    """人標記過、還沒撤銷、而且那個值**還在**那個位置的：和不過的主張一起回饋給 agent。"""
    from . import locate as L
    from .blame import Trace, blame_location
    from .cli import open_flags
    out = []
    trace = None
    for f in open_flags(rec):
        loc = L.Location.from_json(f.get("location") or {})
        p = rec.workspace / loc.path
        try:
            txt = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if loc.value and not L.contains(txt, loc.value):
            continue                                     # 已經改掉了 ⇒ 這個標記解決了
        trace = trace or Trace(rec)
        b = blame_location(trace, loc, contract=contract)
        b.update(claim=f"flag:{f['flag_id']}", detail=f.get("note") or "flagged by the task owner",
                 required=True, hidden=False, finding_id=str(f["flag_id"]))
        out.append(b)
    return out


def forget_outcome(rec: Recorder, session: str) -> None:
    """這個工作階段上一次回合邊界的檢查結果作廢（延後驗收時：現況不是那個結果）。"""
    p = rec.dir / "feedback_state.json"
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    outs = dict(state.get("outcomes") or {})
    ads = dict(state.get("adoptions") or {})
    popped = outs.pop(session, None) is not None
    if session in ads:
        ads.pop(session)
        popped = True
    if popped:
        state["outcomes"] = outs
        state["adoptions"] = ads
        p.write_text(json.dumps(state), encoding="utf-8")


def localize(contract: Any, res: dict[str, Any], *, cwd: str | None,
             why_open: str | None = None, sandbox: str = "auto",
             workspace: pathlib.Path | None = None,
             session: str | None = None,
             scan_deadline_s: float | None = None) -> dict[str, Any] | None:
    ws = workspace or capture.workspace_for(cwd, contract)
    if ws is None:
        return None
    rec = Recorder(ws)
    rec.scan_deadline_s = scan_deadline_s      # 在掛鉤裡（Stop）：和其他掛鉤同一個掃描時限
    if not rec.chain_path.is_file():
        return None
    rec.checkpoint("check")
    verified, why_not = verify_anchored(rec, contract)
    results = res.get("results") or []
    hidden = {c.id for c in contract.claims if c.hidden}
    for r in results:
        r.setdefault("hidden", r.get("claim_id") in hidden)
    scope = rec.dir.name                         # 專案鍵：結論的 id 不跨專案撞在一起
    blames = blame_results(rec, contract, results, ws, sandbox=sandbox)
    blames += _flag_blames(rec, contract)
    for b in blames:
        b.setdefault("finding_id", F.finding_id(b, scope=scope))
        b["source_hidden"] = _hidden_source(contract, b)
    st_path = rec.dir / "feedback_state.json"
    try:
        previous = json.loads(st_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    text, state = F.render_agent(blames, results, previous=previous,
                                 reasons=res.get("reasons"), extra_tokens=_actor_tokens(rec))
    seen = set(previous.get("seen") or [])
    last_status: dict[str, str] = {}
    for e in rec.events():
        if e["type"] == "finding" and e.get("finding_id"):
            last_status[str(e["finding_id"])] = str(e.get("status"))
    # 已經以「開著」記在鏈上的（例如 `vacant flag` 當下記的）不再記一次
    seen |= {k for k, v in last_status.items() if v == "open"}
    now = {str(b["finding_id"]) for b in blames}
    for b in blames:
        if b["finding_id"] in seen:
            continue
        rec.append("finding", {"finding_id": b["finding_id"], "status": "open", **{
            k: b.get(k) for k in ("claim", "location", "value", "state", "fault_class",
                                  "confidence", "layer", "step", "source", "candidates",
                                  "rerun", "note", "correct_value_seen")}})
    for fid in sorted(seen - now):
        rec.append("finding", {"finding_id": fid, "status": "resolved"})
    state["seen"] = sorted(now)
    # 後果（只有事實層進信譽；輸入錯記來源；缺口記整合覆蓋率）——也簽進病歷（K6）。
    # 病歷自己驗不過（被改過、被截短）⇒ 一筆後果都不記（2026-09-24 審查 recorder#5）
    book = A.ActorBook()
    if verified:
        for ev in A.consequences(book, blames, contract=contract, workspace=rec.workspace,
                                 finding_id=lambda b: str(b["finding_id"]),
                                 platform=rec.last_platform()):
            rec.append("consequence", ev)
    outcomes = dict(previous.get("outcomes") or {})
    adoptions = dict(previous.get("adoptions") or {})
    if session:
        outcomes[session] = res.get("outcome")
        # 工作階段結束時記 adoption 用（`capture._outcome`）：hold／escalate ⇒ None＝不記
        adoptions[session] = A.adoption_of(res)
    state["outcomes"] = outcomes
    state["adoptions"] = adoptions
    state["outcome"] = res.get("outcome")
    st_path.write_text(json.dumps(state), encoding="utf-8")
    # 只有驗得過才更新錨點。驗不過還照樣錨定＝下一個普通回合就把截短「合法化」
    # （2026-09-25 審查 consequences blocker）：改成在帳本裡簽一筆「病歷壞了」，之後每次驗證都看得到。
    if verified:
        _anchor(rec, contract)
    else:
        _record_break(rec, contract, why_not)
    report = F.render_report(blames, results, outcome=res.get("outcome"),
                             coverage=_coverage(rec), why_open=why_open,
                             contract_task=getattr(contract, "task_id", None))
    if not verified:
        report += (f"\n⚠ The trace does not verify ({why_not}); no consequence was recorded "
                   f"from this check.\n")
    rec_line = A.recommendation_line(book, A.family_of(contract))
    if rec_line:
        report += f"\n## Routing (advice for you, never shown to the agent)\n\n{rec_line}\n"
    rp = rec.dir / "report.md"
    rp.write_text(report, encoding="utf-8")
    (rec.dir / "report.json").write_text(json.dumps(
        {"outcome": res.get("outcome"), "blames": blames, "results": results,
         "trace_verified": verified},
        ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return {"text": text, "blames": blames, "report": str(rp), "trace_verified": verified,
            "summary": F.human_summary(blames, results, pathlib.Path(rp), why_open=why_open)}


def _anchor(rec: Recorder, contract: Any) -> None:
    """病歷的鏈頭＋筆數寫進收件端**簽過的**帳本：之後從尾巴截短病歷，對得出來（K3）。
    讀回來對的是 `ledger_anchor`／`verify_anchored`（`vacant trace verify`、下一次回合邊界）。"""
    try:
        head = json.loads((rec.dir / "head.json").read_text(encoding="utf-8"))
        from ..intake.ledger import Ledger
        Ledger(contract.task_id).append("trace_head", {"project": rec.dir.name,
                                                       "seq": head.get("seq"),
                                                       "hash": head.get("hash")})
    except Exception:  # noqa: BLE001 — 錨定失敗不影響追緝；報告照寫
        pass


def _record_break(rec: Recorder, contract: Any, why: str) -> None:
    """病歷驗不過：在收件端簽過的帳本裡記一筆 `trace_broken`（同一個鏈頭只記一次）。
    之後 `ledger_anchor` 看到它就一直回報壞掉——截短不會因為之後又多寫了幾步而消失。"""
    if contract is None or not getattr(contract, "task_id", None):
        return
    try:
        head = json.loads((rec.dir / "head.json").read_text(encoding="utf-8"))
        from ..intake.ledger import Ledger
        led = Ledger(contract.task_id)
        if led.path.is_file() and any(
                e.get("type") == "trace_broken" and e.get("project") == rec.dir.name
                and e.get("seq") == head.get("seq") and e.get("hash") == head.get("hash")
                for e in led.events()):
            return
        led.append("trace_broken", {"project": rec.dir.name, "seq": head.get("seq"),
                                    "hash": head.get("hash"), "why": str(why)[:500]})
    except Exception:  # noqa: BLE001 — 記不下來不影響追緝；報告照寫
        pass


def ledger_anchor(rec: Recorder, contract: Any,
                  trust: Any = None) -> tuple[dict[str, Any] | None, str | None, str]:
    """讀回 `_anchor` 寫進去的東西：這個專案在任務帳本裡**最後一個** `trace_head`。

    回 `(錨點, 壞掉的理由, 說明)`：
    - 沒有契約／沒有帳本檔／帳本裡沒有這個專案的錨點 ⇒ `(None, None, "沒有對")`——**沒對過，不是對過了**
    - 帳本自己驗不過（被改、簽章者不在清單上）⇒ `(None, 理由, …)`：拿不出可信的錨點，照壞掉算
    """
    if contract is None or not getattr(contract, "task_id", None):
        return None, None, "not checked against a task ledger (no task contract)"
    try:
        from ..intake import keys as _keys
        from ..intake.ledger import Ledger, LedgerError
        led = Ledger(contract.task_id)
        if not led.path.is_file():
            return None, None, "not checked against a task ledger (the task has no ledger yet)"
        ok, why = led.verify(trust or _keys.Trust.load())
        if not ok:
            return None, f"the task ledger that anchors this trace does not verify ({why})", ""
        heads = [e for e in led.events()
                 if e.get("type") == "trace_head" and e.get("project") == rec.dir.name]
    except (LedgerError, OSError, ValueError) as e:
        return None, f"the task ledger that anchors this trace is unreadable ({e})", ""
    breaks = [e for e in led.events()
              if e.get("type") == "trace_broken" and e.get("project") == rec.dir.name]
    if breaks:
        b = breaks[0]
        return None, (f"the task ledger recorded that this trace stopped verifying at entry "
                      f"{b.get('seq')} ({b.get('why')})"), ""
    if not heads:
        return None, None, ("not checked against a task ledger (it has no trace head for this "
                            "project yet)")
    h = heads[-1]
    return ({"seq": h.get("seq"), "hash": h.get("hash")}, None,
            f"matches the task ledger's anchor at entry {h.get('seq')}")


def verify_anchored(rec: Recorder, contract: Any, trust: Any = None) -> tuple[bool, str]:
    """`Recorder.verify` ＋ 收件端帳本的錨點（`vacant trace verify` 與回合邊界都用這一支）。
    沒有帳本可對 ⇒ 照 `Recorder.verify` 的結果，說明裡寫出「沒有對」；不當成失敗。"""
    anchor, broken, note = ledger_anchor(rec, contract, trust)
    if broken:
        return False, broken
    ok, why = rec.verify(trust, anchor=anchor)
    return ok, (f"{why}; {note}" if ok and note else why)


def _hidden_source(contract: Any, b: dict[str, Any]) -> bool:
    """這個結論的來源是不是只給隱藏主張用的輸入（講出來就洩漏隱藏驗收；agent_text#1）。"""
    src = b.get("source") or {}
    name = src.get("name")
    if not name:
        return False
    used_visible = any(not c.hidden and name in json.dumps(c.params) for c in contract.claims)
    used_hidden = any(c.hidden and name in json.dumps(c.params) for c in contract.claims)
    return used_hidden and not used_visible


def _actor_tokens(rec: Recorder) -> set[str]:
    """病歷裡**所有**行動者的識別（不只這一次結論裡的；agent_text#4）：子 agent id、agent 類型、
    模型 id，以及子 agent **定義檔的雜湊**（信譽 stream `<平台>:def:<名字>:<sha>` 裡那個 sha；
    設計文件 §10 第 10 列）——它和 agent 類型一樣指得出「是哪一個行動者」。

    **刻意不收平台名**（`claude`／`codex`／`opencode`／`pi`）：`feedback_ks1_clean` 是子字串比對，
    平台名會撞到回饋正當要引用的檔名與路徑（`CLAUDE.md`、`.codex/config.toml`、`.opencode/…`），
    收了之後指向這些檔的回饋整行被換成「細節略去」（`feedback._clean_lines`），agent 就看不到位置。平台名本身也不指向某一個行動者（同一平台上每個 agent 都是它）。"""
    out: set[str] = set()
    defs: dict[tuple[str, str], str] = {}
    for e in rec.events():
        st = e.get("step")
        a = e.get("actor") or (st.get("actor") if isinstance(st, dict) else None) or {}
        if isinstance(a, dict):
            for k in ("agent", "agent_type", "model"):
                if a.get(k):
                    out.add(str(a[k]))
            if a.get("agent_type"):
                dk = (str(a.get("platform") or "?"), str(a["agent_type"]))
                if dk not in defs:
                    defs[dk] = A.definition_of(dict(a), rec.workspace)
        # 已經記下的後果帶著信譽鍵：定義檔之後被改了，舊的雜湊也照樣算識別
        key = e.get("key") if e.get("type") == "consequence" else None
        if isinstance(key, list) and key:
            defs.setdefault(("key", str(key[0])), str(key[0]))
    for stream in defs.values():
        parts = stream.split(":")
        if len(parts) >= 4 and parts[1] == "def" and parts[-1] != "None":
            out.add(parts[-1])
    return out
