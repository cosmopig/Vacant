"""Vacant MCP server（架構規格 §5 egress）。

Hermes 在 ~/.hermes/config.yaml 把這支註冊成 mcp_server。於是 Hermes 的 LLM 要對外
調用時，看到的工具是 mcp_vacant_a2a_call —— 呼叫即「穿過 vacant 的責任閘道」：
簽章信封 → 信譽路由 → 對端 ingress 驗章/把關 → 跑 → 簽 result 回 → 寫 logbook。
這讓 Hermes「有」vacant：不改 Hermes 一行碼，只靠設定連上。
"""
from __future__ import annotations
import hashlib, json, os, time
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from vacant.host import Host
from vacant.substrate import EchoSubstrate
from vacant.tasks import NICHE_SOLVERS, NICHES

ROOT = Path(os.path.expanduser("~/.vacant-mcp"))
_SID = EchoSubstrate().substrate_id
_host = Host(ROOT, substrate=EchoSubstrate(p_base=1.0))  # expert 確定解對，聚焦在閘道/信任

def _ensure(name, niches):
    if (ROOT / name / "trust" / "vacant_id").exists():
        _host.adopt(name)
    else:
        _host.mint(name, niches=niches)

_ensure("hermes_caller", [])          # Hermes 的對外身份
_ensure("expert_a", list(NICHES))     # 被路由到的持久專家
_ensure("expert_b", list(NICHES))

def _task(niche, inp):
    expected = str(NICHE_SOLVERS[niche](inp))
    tid = hashlib.sha256(f"{niche}:{inp}".encode()).hexdigest()[:12]
    return {"task_id": tid, "niche": niche, "input": inp, "expected": expected,
            "prompt": f"[{niche}] {inp}", "check": lambda a, _e=expected: str(a) == _e}

mcp = FastMCP("vacant")

@mcp.tool()
def a2a_call(capability: str, input: str) -> str:
    """Delegate a task to a trusted, accountable vacant expert through the Vacant responsibility gateway (the call is cryptographically signed, reputation-routed, and logged). capability must be one of: reverse, caesar3, sort_chars, sum_digits, vowel_count. Returns the expert's answer plus provenance."""
    if capability not in NICHE_SOLVERS:
        return f"unknown capability '{capability}'. valid: {list(NICHES)}"
    oc = _host.gateway("hermes_caller").call(capability, _task(capability, input))
    return (f"answer={oc.answer} | served by vacant …{oc.callee_id[-8:]} on substrate={oc.substrate} "
            f"| signed+logged, verifier_correct={oc.correct}")

@mcp.tool()
def get_reputation(capability: str) -> str:
    """Look up the reputation leaderboard of vacant experts for a capability (one of: reverse, caesar3, sort_chars, sum_digits, vowel_count)."""
    board = _host.registry.leaderboard(capability, _SID)
    return "; ".join(f"…{v[-8:]}={s:.2f}" for v, s in board) or "no reputation data yet"

# submit_review 已廢止對外（credit-memory v1 改動3）：無驗簽 review 是洞。
# review 只能由 delegate/a2a_call 內部的簽章 ReviewEnvelope 通道產生。

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
