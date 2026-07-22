"""Vacant MCP server — 工具面 v2（12 §3：把信任閘道生態暴露成 MCP 工具）。

入口 agent（Hermes / Claude / 任一 MCP client）在自己的 config 把這支註冊成
mcp_server，於是它「有」了 vacant：不改一行碼，只靠設定連上一個更好+可究責的腦。

工具面 v2（12 §3）：
  - delegate    ：主工具。把有客觀 check 的 coding 子任務交給信任生態，回答案＋信任狀。
  - trust_card  ：取某次 delegate 的完整信任狀 JSON。
  - residents   ：名冊（信用/觀測/flags，INSUFFICIENT_DATA/PROBATION 如實顯示）。
  - report      ：人類仲裁回灌（最強標籤）。
  - scoreboard  ：trust off/on 配對＋成本（每次使用都是一筆試次）。
  - verify_fix  ：保留（單腦 verify-fix，不經生態；見其 docstring）。

廢止（12 §3，工具面 v2 取代）：a2a_call / get_reputation / submit_review 與 EchoSubstrate
玩具 host 整段移除——舊面把「路由到玩具 expert」當賣點，v2 直接暴露真閘道 delegate；
無驗簽的 submit_review 是洞（credit-memory v1 改動3），review 只能由 delegate 內部的
簽章 ReviewEnvelope 通道產生。

誠實邊界：delegate 需要真模型（VACANT_MCP_MODEL）；未設時回 error，絕不靜默退回假腦。
頂層 import 不建 Ecosystem（lazy `_eco()`），避免 import 副作用炸測試/炸 client 啟動。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from vacant.trustcard import render_trust_card, card_json

mcp = FastMCP("vacant")

# --- lazy singleton：延遲到第一次工具呼叫才建生態（避免 import 副作用）----------
_ECO = None


def _eco():
    """回傳進程內唯一的 Ecosystem（root=~/.vacant-mcp，VACANT_MCP_ROOT 可覆寫）。

    需要真模型：有 VACANT_MCP_MODEL → LMStudioBrain；沒設 → 拋 RuntimeError
    （由各工具的 try/except 轉成 error 字串）。不靜默用假腦。
    """
    global _ECO
    if _ECO is not None:
        return _ECO
    model = os.environ.get("VACANT_MCP_MODEL")
    if not model:
        raise RuntimeError(
            "delegate/residents/scoreboard 需要真模型：請在 vacant MCP server 上設 "
            "VACANT_MCP_MODEL（並可選 VACANT_MCP_BASE、VACANT_MCP_API）"
        )
    # 與 verify_fix 用同一個預設（單一事實：VACANT_MCP_BASE 未設＝本機 LM Studio）。
    # 部署到 VM/遠端一律顯式設 env，不寫死機器 IP（G10／17 §P0-7）。
    base = os.environ.get("VACANT_MCP_BASE", "http://localhost:1234")
    api = os.environ.get("VACANT_MCP_API", "responses")
    from vacant.brains import LMStudioBrain
    from vacant.ecosystem import Ecosystem

    brain = LMStudioBrain(base, model, api=api, timeout=600, max_tokens=None)
    root = Path(os.path.expanduser(os.environ.get("VACANT_MCP_ROOT", "~/.vacant-mcp")))
    _ECO = Ecosystem(root, brain)
    return _ECO


def _err(where: str, e: Exception) -> str:
    return json.dumps({"error": f"{where}: {type(e).__name__}: {e}"}, ensure_ascii=False)


# --- 純函式實作（工具薄包這些，測試直接呼叫純函式）------------------------------
def _delegate_impl(task: str, tests: dict, risk: str = "normal") -> str:
    try:
        eco = _eco()
        r = eco.delegate(task, tests, risk=risk)
    except Exception as e:  # MCP 工具不可拋——例外轉 JSON error 字串
        return _err("delegate failed", e)
    return (
        f"{r['answer']}\n\n"
        f"── trust card ──\n"
        f"{render_trust_card(r['trust_card'])}\n\n"
        f"task_id={r['task_id']}"
    )


def _trust_card_impl(task_id: str) -> str:
    try:
        eco = _eco()
        card = eco.trust_card(task_id)
    except Exception as e:
        return _err("trust_card failed", e)
    if card is None:
        return json.dumps({"error": f"no trust card for task_id={task_id}"},
                          ensure_ascii=False)
    return card_json(card)


def _residents_impl() -> str:
    try:
        eco = _eco()
        rows = eco.roster()
    except Exception as e:
        return _err("residents failed", e)
    lines = [
        f"{'name':<12} {'tier':<9} {'credit':>7} {'n_obs':>6} {'deliv':>6} "
        f"{'eps':>4} chain flags",
    ]
    for r in rows:
        flags = "，".join(r["flags"]) if r["flags"] else "-"
        lines.append(
            f"{r['name']:<12} {r['tier']:<9} {r['credit']:>7.3f} {r['n_obs']:>6.1f} "
            f"{r['deliveries']:>6} {r['episodes']:>4} "
            f"{'ok' if r['chain_ok'] else 'BAD':<5} {flags}"
        )
    return "\n".join(lines)


def _report_impl(task_id: str, verdict: str, evidence: str = "") -> str:
    try:
        eco = _eco()
        ack = eco.report(task_id, verdict, evidence=evidence)
    except Exception as e:
        return _err("report failed", e)
    return json.dumps(ack, ensure_ascii=False)


def _scoreboard_impl() -> str:
    try:
        eco = _eco()
        sb = eco.scoreboard()
    except Exception as e:
        return _err("scoreboard failed", e)

    def _rate(b):
        return f"{b['pass']}/{b['n']}" + (f" ({b['pass'] / b['n']:.0%})" if b["n"] else "")

    off, on = sb["off"], sb["on"]
    return (
        f"trust OFF: pass {_rate(off)}｜calls {off['calls']}\n"
        f"trust ON : pass {_rate(on)}｜calls {on['calls']}\n"
        f"paired_delta (on−off pass-rate): {sb['paired_delta']}"
    )


# --- MCP 工具（薄包純函式）------------------------------------------------------
@mcp.tool()
def delegate(task: str, tests: dict, risk: str = "normal") -> str:
    """THE PREFERRED PATH for any coding subtask with an objective check. Instead of
    writing the code yourself, hand it to Vacant's trusted, accountable resident
    ecosystem: the task is routed (by reputation) to a resident, generated on Vacant's
    local model with relevant memory injected, cross-reviewed by K signed peer
    reviewers, probabilistically audited, and delivered WITH a trust card (who
    delivered, their credit/observations/flags, who reviewed, audit status, chain
    head, signature). Use this whenever correctness is objectively checkable — you get
    a better answer AND accountable provenance you can show.

    `tests` is a CHECK-SPEC (the objective bar the answer must clear), ONE of:
      {"type":"equals","value":"<exact answer>"}
      {"type":"contains","value":"<substring>","ignore_case":true}
      {"type":"regex","pattern":"<regex>"}
      {"type":"json_schema","schema":{...}}
      {"type":"run_python","code":"assert solve('ab')=='ba'"}   # code must define solve(...)
    (`run_python` example: the resident must return code defining `solve`, and your
    asserts call it — the delivered answer is the code that passes.)

    `risk` is a hint ("normal"/"high") for downstream policy; defaults to "normal".

    Returns: the answer, then a three-line rendered trust card, then task_id (use it
    with trust_card / report). On any failure returns a JSON error string (never raises).
    """
    return _delegate_impl(task, tests, risk)


@mcp.tool()
def trust_card(task_id: str) -> str:
    """Fetch the FULL trust card JSON for a prior delegate call (by its task_id):
    deliverer identity + credit/observations/flags, every signed peer review, audit
    status, chain head, and host signature. Returns a JSON error string if unknown."""
    return _trust_card_impl(task_id)


@mcp.tool()
def residents() -> str:
    """Show the resident roster: each resident's tier, credit score, observation count,
    deliveries, episodes, chain integrity, and flags. Flags render honestly —
    INSUFFICIENT_DATA (n<30 observations) and PROBATION are shown as-is, never hidden."""
    return _residents_impl()


@mcp.tool()
def report(task_id: str, verdict: str, evidence: str = "") -> str:
    """Human arbitration feed-back (the strongest label): report the real outcome of a
    delegated task by task_id. verdict e.g. "PASS"/"FAIL"/"FAULT"; a fault verdict
    emits a slash event. Returns a JSON ack."""
    return _report_impl(task_id, verdict, evidence)


@mcp.tool()
def scoreboard() -> str:
    """Paired trust OFF vs ON evidence: pass counts, call counts (cost), and the paired
    pass-rate delta. Every delegate call — trust on or off — is one trial recorded here."""
    return _scoreboard_impl()


@mcp.tool()
def verify_fix(prompt: str, check: dict, draft: str = "", k: int = 3) -> str:
    """Strengthen YOUR OWN answer to a task that has an OBJECTIVE check. vacant runs a
    verify-fix loop on its local model: generate -> run `check` -> if it fails, retry with
    feedback (up to k times) -> return the first answer that PASSES, plus a signed attestation
    you can show as proof. Use this ONLY when correctness is objectively checkable (NOT for
    opinions or style). `check` must be ONE of:
      {"type":"equals","value":"<exact answer>"}
      {"type":"contains","value":"<substring>","ignore_case":true}
      {"type":"regex","pattern":"<regex>"}
      {"type":"json_schema","schema":{...}}
      {"type":"run_python","code":"<python asserts calling solve(...), the function your answer must define>"}
    `draft` (optional): your current answer — if it already passes, vacant returns it with 0
    extra model calls. Returns JSON: {answer, verified, calls, attestation}."""
    model = os.environ.get("VACANT_MCP_MODEL")
    if not model:
        return json.dumps({"error": "verify_fix disabled: set VACANT_MCP_MODEL (and optionally "
                                    "VACANT_MCP_BASE, VACANT_MCP_API) on the vacant MCP server"})
    from vacant.agent import Vacant
    from vacant.brains import LMStudioBrain
    from vacant.checks import compile_check
    try:
        verifier = compile_check(check)
    except Exception as e:
        return json.dumps({"error": f"bad check spec: {type(e).__name__}: {e}"})
    base = os.environ.get("VACANT_MCP_BASE", "http://localhost:1234")
    api = os.environ.get("VACANT_MCP_API", "responses")
    brain = LMStudioBrain(base, model, api=api, max_tokens=1024)
    v = Vacant(brain, k=int(k))
    cd = str(check.get("type", "custom"))

    # 可觀測：VACANT_TRACE 設定時，把「verify-fix 迴圈每一步 + 結論」記成 JSONL（A 層語意追蹤）。
    steps: list[dict] = []

    def _sink(attempt: int, ans: str, ok: bool) -> None:
        steps.append({"attempt": attempt, "passed": bool(ok),
                      "ans_sha": hashlib.sha256((ans or "").encode()).hexdigest()[:12]})

    def _emit(answer: str, verified: bool, calls: int, att: dict | None) -> str:
        tp = os.environ.get("VACANT_TRACE")
        if tp:
            rec = {"ts": time.time(), "t": time.strftime("%H:%M:%S"), "tool": "verify_fix",
                   "check": cd, "draft_used": bool(draft and verified and calls == 0),
                   "k": int(k), "attempts": steps, "calls": calls, "verified": verified,
                   "attestation_vacant_id": (att or {}).get("vacant_id")}
            try:
                with open(tp, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception:
                pass
        return json.dumps({"answer": answer, "verified": verified, "calls": calls,
                           "attestation": att}, ensure_ascii=False)

    # draft 快路徑：Hermes 自己已經對了就不再生成（0 額外算力，但仍給簽章憑證）
    if draft and verifier(draft):
        return _emit(draft, True, 0, v.attest(prompt, draft, check_desc=cd, verified=True))
    r = v.solve(prompt, verifier, check_desc=cd, on_step=_sink)
    return _emit(r.answer, r.verified, r.calls, r.attestation)


if __name__ == "__main__":
    mcp.run(transport="stdio")
