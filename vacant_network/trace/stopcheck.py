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
                 required=True, hidden=False)
        out.append(b)
    return out


def localize(contract: Any, res: dict[str, Any], *, cwd: str | None,
             why_open: str | None = None, sandbox: str = "auto",
             workspace: pathlib.Path | None = None) -> dict[str, Any] | None:
    ws = workspace or capture.workspace_for(cwd, contract)
    if ws is None:
        return None
    rec = Recorder(ws)
    if not rec.chain_path.is_file():
        return None
    rec.checkpoint("check")
    results = res.get("results") or []
    hidden = {c.id for c in contract.claims if c.hidden}
    for r in results:
        r.setdefault("hidden", r.get("claim_id") in hidden)
    blames = blame_results(rec, contract, results, ws, sandbox=sandbox)
    blames += _flag_blames(rec, contract)
    st_path = rec.dir / "feedback_state.json"
    try:
        previous = json.loads(st_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    text, state = F.render_agent(blames, results, previous=previous,
                                 reasons=res.get("reasons"))
    prev_open = set((previous.get("open") or {}))
    for b in blames:
        fid = F.finding_id(b)
        if fid in prev_open:
            continue
        rec.append("finding", {"finding_id": fid, "status": "open", **{
            k: b.get(k) for k in ("claim", "location", "value", "state", "fault_class",
                                  "confidence", "layer", "step", "source", "candidates",
                                  "rerun", "note")}})
    for fid in sorted(prev_open - set(state["open"])):
        rec.append("finding", {"finding_id": fid, "status": "resolved"})
    # 後果（只有事實層進信譽；輸入錯記來源；缺口記整合覆蓋率）——也簽進病歷（K6）
    book = A.ActorBook()
    for ev in A.consequences(book, blames, contract=contract, workspace=rec.workspace,
                             finding_id=F.finding_id, platform=rec.last_platform()):
        rec.append("consequence", ev)
    state["outcome"] = res.get("outcome")
    st_path.write_text(json.dumps(state), encoding="utf-8")
    report = F.render_report(blames, results, outcome=res.get("outcome"),
                             coverage=_coverage(rec), why_open=why_open,
                             contract_task=getattr(contract, "task_id", None))
    rec_line = A.recommendation_line(book, A.family_of(contract))
    if rec_line:
        report += f"\n## Routing (advice for you, never shown to the agent)\n\n{rec_line}\n"
    rp = rec.dir / "report.md"
    rp.write_text(report, encoding="utf-8")
    (rec.dir / "report.json").write_text(json.dumps(
        {"outcome": res.get("outcome"), "blames": blames, "results": results},
        ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return {"text": text, "blames": blames, "report": str(rp),
            "summary": F.human_summary(blames, results, pathlib.Path(rp), why_open=why_open)}
