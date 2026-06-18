"""Vacant MCP server（架構規格 §5 egress）。

Hermes 在 ~/.hermes/config.yaml 把這支註冊成 mcp_server。於是 Hermes 的 LLM 要對外
調用時，看到的工具是 mcp_vacant_a2a_call —— 呼叫即「穿過 vacant 的責任閘道」：
簽章信封 → 信譽路由 → 對端 ingress 驗章/把關 → 跑 → 簽 result 回 → 寫 logbook。
這讓 Hermes「有」vacant：不改 Hermes 一行碼，只靠設定連上。
"""
from __future__ import annotations
import hashlib, os
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

@mcp.tool()
def submit_review(vacant_id_suffix: str, capability: str, score: float) -> str:
    """Submit a 5-dim review (score 0..1) about a vacant expert for a capability; recorded as a signed, accountable review feeding reputation."""
    target = next((c.vacant_id for c in _host.registry.discover(capability)
                   if c.vacant_id.endswith(vacant_id_suffix)), None)
    if not target:
        return f"no expert ending …{vacant_id_suffix} for {capability}"
    s = max(0.0, min(1.0, float(score)))
    _host.registry.record_review(_host.vacant_id("hermes_caller"), target, _SID,
                                 {d: s for d in ("factual","logical","relevance","honesty","adoption")})
    return f"review recorded for …{target[-8:]} ({capability}={s:.2f})"

if __name__ == "__main__":
    mcp.run(transport="stdio")
