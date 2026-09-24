"""feedback — **讓問題被提出來，而不是被淹沒**：給 agent 的事實回饋、給人的未解問題清單。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §4.4、§4.7；
LOOP §二-3；人類 2026-09-24：「就算有問題最後也要提出問題，而不是被上下文淹沒」）：

兩個讀者，兩種文字，**不混**：

| | 給 agent（回合邊界的回饋） | 給人（報告） |
|---|---|---|
| 內容 | 哪條沒過、**哪個檔哪一行寫了什麼**、應該是多少／從哪裡來、這個值第一次出現在第幾步 | 同上，再加：**誰**（行動者）、證據等級、重跑結果、缺口、覆蓋率 |
| 行動者 | **沒有**（KS-1：後果只走非文字通道；§4.7） | 有 |
| 措辭 | 只有事實與位置；沒有「你」、沒有責任或懲罰字眼（`feedback_ks1_clean` 可執行） | 同樣不用「信任」；等級一定標出來 |
| 長度 | ≤ `MAX_LINES` 行；「這次新增／還沒解決／已解決」差異 | 全部 |

回饋輪數用完、只剩 agent 改不動的（等人工審查、證據不齊）、或主張過了但有提示性問題時，
**問題不會就這樣消失**：它們留在報告裡，Claude Code 另外以 `systemMessage` 直接顯示給人，
`vacant do` 在結果裡印出來，`vacant trace report` 隨時可以再看。

## 誠實邊界（改碼請保留）

1. 「第一次出現在第幾步」是**工作區歷史的事實**，不是指控；那一步是誰做的只寫在給人的報告裡。
2. 隱藏主張只說「沒過（細節由委託者保留）」——位置與值都不給，和收件口同一條規則。
3. 回饋是否真的被模型讀到，要量（R535：寫檔 1/46）；OpenCode `run` 沒有回合邊界通道。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time
from typing import Any

from ..memory import assert_ks1_clean

MAX_LINES = 14
FEEDBACK_HEADER = ("The task contract's checks do not pass yet "
                   "(this is feedback from `vacant check`, not a final decision):")
FLAG_HEADER = ("The task contract's checks pass, but the task owner marked these places in "
               "the deliverable as wrong:")
FOOTER = "Run `vacant check` to re-check before finishing."


def finding_id(b: dict[str, Any], scope: str = "") -> str:
    """結論的穩定 id。`scope`＝專案鍵：兩個專案裡「同一條主張、同一個值」是兩件事
    （2026-09-24 審查 consequences#0：沒有 scope 時撤銷一個會撤到別的專案去）。"""
    if b.get("finding_id"):
        return str(b["finding_id"])
    loc = b.get("location") or {}
    raw = json.dumps([scope, b.get("claim"), loc.get("path"), loc.get("line"),
                      loc.get("value") or loc.get("note")], ensure_ascii=False)
    return "f_" + hashlib.sha256(raw.encode()).hexdigest()[:10]


class KS1FeedbackError(ValueError):
    pass


def feedback_ks1_clean(text: str, actor_tokens: set[str]) -> str:
    """`memory.assert_ks1_clean`（凍結的禁止片語）＋**任何行動者識別都不可以出現**
    （子 agent id、agent 類型、模型 id）。不擴充凍結的 `KS1_FORBIDDEN`。"""
    assert_ks1_clean(text)
    low = text.lower()
    for tok in actor_tokens:
        if tok and len(tok) >= 4 and tok.lower() in low:
            raise KS1FeedbackError(f"actor identifier {tok!r} in agent-facing text")
    return text


def actor_tokens(blames: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for b in blames:
        for s in [b.get("step")] + list(b.get("candidates") or []) + \
                [c for c in b.get("chain") or [] if isinstance(c, dict)]:
            a = (s or {}).get("actor") or {}
            for k in ("agent", "agent_type", "model"):
                if a.get(k):
                    out.add(str(a[k]))
    return out


def _clip(s: Any, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def _where(loc: dict[str, Any]) -> str:
    w = str(loc.get("path"))
    if loc.get("line"):
        w += f":{loc['line']}"
    return w


def agent_lines(b: dict[str, Any]) -> list[str]:
    """一條追緝結論 → 給 agent 的一到三行（只有事實；沒有行動者）。隱藏主張不經過這裡。"""
    cid = b.get("claim") or "flag"
    loc = b.get("location") or {}
    if loc.get("kind") == "missing":
        head = f"- {cid}: FAIL — {loc.get('path')}: {_clip(loc.get('note') or b.get('detail'), 160)}"
    else:
        val = b.get("value") or loc.get("value")
        head = f"- {cid}: FAIL — {_where(loc)} says {_clip(json.dumps(val, ensure_ascii=False), 80)}"
    out = [head]
    exp = [e for e in b.get("expected") or [] if e.get("value") is not None]
    if exp:
        e = exp[0]
        out.append(f"  expected {e['value']} ({_clip(e.get('note') or e.get('path'), 80)})")
    elif b.get("detail") and loc.get("kind") != "missing":
        out.append(f"  check says: {_clip(b['detail'], 160)}")
    src = b.get("source") or {}
    shown = b.get("fault_class") == "input" and src.get("observed", True) \
        and not b.get("source_hidden")
    if shown and src.get("kind") == "input":
        out.append(f"  the same value is in {src.get('path')}"
                   + (f" line {src['line']}" if src.get("line") else "")
                   + " (the given input); if the input is wrong, say so in the answer")
    elif shown and src.get("kind") == "file":
        # 繳付物本來就寫著這個值（不是給定的輸入）：照實說，不叫 agent 去「說明輸入有錯」
        out.append(f"  this value was already in {src.get('path')}"
                   + (f" line {src['line']}" if src.get("line") else "")
                   + " before the first recorded step")
    elif shown and src.get("kind") == "instructions":
        out.append(f"  the same value is in the instruction file {src.get('path')}")
    elif shown and src.get("kind") == "prompt":
        out.append("  the same value is in the task's own message")
    elif shown and src.get("kind") == "url":
        out.append(f"  the same value came from {src.get('ref')}")
    elif b.get("step") and b.get("fault_class") == "agent":
        st = b["step"]
        first = next((c for c in b.get("chain") or [] if c.get("step")), None)
        if first and first.get("step") != st.get("step"):
            out.append(f"  it was copied from step {st.get('n')} ({st.get('tool')}); "
                       f"step {first.get('n')} wrote it into {loc.get('path')}")
        else:
            out.append(f"  this value first appeared at step {st.get('n')} ({st.get('tool')})")
    return out


def _clean_lines(lines: list[str], tokens: set[str], cid: str) -> list[str]:
    """逐行過 KS-1＋行動者防呆：髒的那幾行換成一句中性的話，**不是**整則回饋作廢
    （2026-09-24 審查 agent_text#2：一行髒掉曾讓人標記、報告、結論全部消失）。"""
    out = []
    for ln in lines:
        try:
            feedback_ks1_clean(ln, tokens)
            out.append(ln)
        except (KS1FeedbackError, Exception):  # noqa: BLE001 — KS1Violation 也在內
            out.append(f"  (a detail of {cid} was left out)")
    return out


def render_agent(blames: list[dict[str, Any]], results: list[dict[str, Any]],
                 *, previous: dict[str, Any] | None = None,
                 reasons: list[str] | None = None,
                 extra_tokens: set[str] | None = None) -> tuple[str, dict[str, Any]]:
    """回 `(文字, 狀態)`；狀態存起來當下一次的 `previous`（「這次新增／已解決」）。

    隱藏主張：**一條主張一行**「沒過（細節由委託者保留）」，不論它有幾個位置；不標「還沒解決」、
    不算進「已解決」的數字——那些都會洩漏位置與個數（審查 agent_text#0）。"""
    previous = previous or {}
    tokens = actor_tokens(blames) | set(extra_tokens or ())
    blamed_claims = {b.get("claim") for b in blames}
    ids_now: dict[str, str] = {}
    body: list[str] = []
    hidden_done: set[str] = set()
    for b in blames:
        if not b.get("required", True):
            continue
        cid = str(b.get("claim") or "flag")
        if b.get("hidden"):
            if cid not in hidden_done:
                hidden_done.add(cid)
                body.append(f"- {cid}: FAIL (details withheld by the task owner)")
            continue
        fid = finding_id(b)
        ids_now[fid] = cid
        lines = agent_lines(b)
        if previous.get("open") and fid in previous["open"]:
            lines[0] += "  (still open)"
        body += _clean_lines(lines, tokens, cid)
    for r in results:
        if r.get("status") == "PASS" or not r.get("required", True) \
                or r.get("claim_id") in blamed_claims:
            continue
        line = f"- {r['claim_id']}: {r['status']}" + \
            ("" if r.get("hidden") else f" — {_clip(r.get('detail'), 200)}")
        body += _clean_lines([line], tokens, str(r["claim_id"]))
    if not body:
        body = _clean_lines([f"- {x}" for x in (reasons or [])[:6]], tokens, "the check")
    hidden_claims = {str(b.get("claim")) for b in blames if b.get("hidden")} | \
        {str(r.get("claim_id")) for r in results if r.get("hidden")}
    prev_open = previous.get("open") or {}
    resolved = sorted(k for k in set(prev_open) - set(ids_now)
                      if str(prev_open.get(k)) not in hidden_claims)
    if len(body) > MAX_LINES - 3:
        more = len(body) - (MAX_LINES - 4)
        body = body[:MAX_LINES - 4] + [f"- … and {more} more line(s): run `vacant check`"]
    only_flags = bool(ids_now) and all(str(c).startswith("flag:") for c in ids_now.values()) \
        and not any(r.get("status") != "PASS" and r.get("required", True) for r in results)
    lines = [FLAG_HEADER if only_flags else FEEDBACK_HEADER, *body]
    if resolved:
        lines.append(f"Resolved since the last check: {len(resolved)}.")
    lines.append(FOOTER)
    return "\n".join(lines), {"open": ids_now, "t": time.time()}


# ── 給人的報告 ───────────────────────────────────────────────────────

_GRADE_WORDS = {
    "provable": "provable (the check was re-run on the rebuilt workspace: it fails right after "
                "this step, with this value at this place)",
    "lineage_exact": "traced to an input (the same value is in content that was read)",
    "lineage_internal": "traced through earlier steps (value matching; an inference)",
    "heuristic": "heuristic (an inference; no re-run evidence)",
    "gap": "unobserved (the change was not recorded; nobody is blamed)",
}


def _actor(a: dict[str, Any] | None) -> str:
    if not a:
        return "—"
    who = f"{a.get('platform')}:{a.get('agent_type') or 'main'}"
    if a.get("agent"):
        who += f"#{str(a['agent'])[:10]}"
    if a.get("model"):
        who += f" (model {a['model']}, as claimed)"
    return who


def render_report(blames: list[dict[str, Any]], results: list[dict[str, Any]], *,
                  outcome: str | None, coverage: dict[str, Any], why_open: str | None = None,
                  contract_task: str | None = None) -> str:
    """給人的未解問題清單（Markdown）。有問題就一條一條列，**不省略**。"""
    lines = [f"# Vacant — open issues{f' for {contract_task}' if contract_task else ''}", ""]
    open_required = [r for r in results if r.get("status") != "PASS" and r.get("required", True)]
    open_advisory = [r for r in results if r.get("status") != "PASS" and not r.get("required", True)]
    lines.append(f"- outcome of the last check: **{outcome or '?'}**"
                 + (f" — {why_open}" if why_open else ""))
    lines.append(f"- required checks not passing: {len(open_required)}; "
                 f"advisory: {len(open_advisory)}")
    lines.append(f"- recorded steps: {coverage.get('steps', 0)}; unrecorded changes (gaps): "
                 f"{coverage.get('gaps', 0)}; steps without a post-tool event: "
                 f"{coverage.get('post_missing', 0)}")
    lines.append("- signing: the trace is signed with a key on this machine, same account as "
                 "the agent ⇒ tampering is detectable, not impossible")
    lines.append("")
    if not blames and not open_required and not open_advisory:
        lines.append("Nothing open.")
        return "\n".join(lines) + "\n"
    for i, b in enumerate(blames, 1):
        loc = b.get("location") or {}
        lines.append(f"## {i}. {b.get('claim') or 'flag'} — {_where(loc)}")
        if b.get("value") or loc.get("value"):
            lines.append(f"- value: `{_clip(b.get('value') or loc.get('value'), 200)}`")
        for e in b.get("expected") or []:
            lines.append(f"- expected: `{e.get('value')}` ({e.get('note') or e.get('path')})")
        lines.append(f"- check: {_clip(b.get('detail') or '', 300)}")
        lines.append(f"- where it came from: **{b.get('fault_class')}**, "
                     f"{_GRADE_WORDS.get(str(b.get('confidence')), b.get('confidence'))}")
        if b.get("step"):
            st = b["step"]
            lines.append(f"- step {st.get('n')} ({st.get('tool')}) by {_actor(st.get('actor'))}")
        if b.get("candidates"):
            lines.append("- could be any of: " + ", ".join(
                f"step {c.get('n')} by {_actor(c.get('actor'))}" for c in b["candidates"]))
        src = b.get("source") or {}
        if src:
            lines.append(f"- source: {json.dumps(src, ensure_ascii=False)[:300]}")
        chain = [c for c in b.get("chain") or []]
        if chain:
            lines.append("- trail: " + " ← ".join(
                (f"step {c['n']} {c.get('via')}" if c.get("n") is not None else str(c.get("via")))
                for c in chain[:8]))
        rr = b.get("rerun") or {}
        if rr.get("before"):
            lines.append(f"- re-run of `{rr.get('claim')}`: before step {rr.get('step')} → "
                         f"{rr['before'].get('status')}, after → {rr['after'].get('status')}"
                         f"{' (value appears here)' if rr['after'].get('value_here') else ''}")
        if b.get("note"):
            lines.append(f"- note: {b['note']}")
        lines.append("")
    blamed = {b.get("claim") for b in blames}
    rest = [r for r in open_required + open_advisory if r.get("claim_id") not in blamed]
    if rest:
        lines.append("## Other open checks (no location to trace)")
        for r in rest:
            lines.append(f"- {r['claim_id']}: {r['status']} — {_clip(r.get('detail'), 300)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def human_summary(blames: list[dict[str, Any]], results: list[dict[str, Any]],
                  report_path: pathlib.Path | None, *, why_open: str | None) -> str:
    """一段短訊息（Claude Code `systemMessage`、`vacant do` 的輸出）。"""
    n_req = sum(1 for r in results if r.get("status") != "PASS" and r.get("required", True))
    n_adv = sum(1 for r in results if r.get("status") != "PASS" and not r.get("required", True))
    if not (n_req or n_adv or blames):
        return ""
    parts = [f"Vacant: {n_req} required check(s) still not passing"
             + (f", {n_adv} advisory" if n_adv else "")
             + (f" ({why_open})" if why_open else "") + "."]
    for b in blames[:3]:
        loc = b.get("location") or {}
        st = b.get("step") or {}
        parts.append(f"• {b.get('claim')}: {_where(loc)}"
                     + (f" = {_clip(b.get('value') or loc.get('value'), 40)}"
                        if (b.get('value') or loc.get('value')) else "")
                     + f" [{b.get('fault_class')}, {b.get('confidence')}"
                     + (f", step {st.get('n')}" if st else "") + "]")
    if report_path is not None:
        parts.append(f"Full list: {report_path}")
    return "\n".join(parts)
