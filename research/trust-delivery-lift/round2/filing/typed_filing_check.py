"""Contract-backed check (legacy TypedVerdict surface). VACANT executes frozen contract only."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contract.executor import execute_contract  # noqa: E402
from contract.filing_contract import compile_contract_primary  # noqa: E402

_NUM = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)")


def _scale_to_mult(scale: Any) -> float:
    if scale is None:
        return 1.0
    if isinstance(scale, (int, float)) and scale < 20:
        return float(10 ** int(scale))
    s = str(scale).lower()
    if "million" in s:
        return 1e6
    if "billion" in s:
        return 1e9
    if "thousand" in s:
        return 1e3
    return 1.0


def parse_header_scale(page_text: str) -> float:
    t = page_text.lower()
    if "in billions" in t or "(billions)" in t:
        return 1e9
    if "in millions" in t or "(millions)" in t:
        return 1e6
    if "in thousands" in t:
        return 1e3
    return 1.0


@dataclass
class TypedVerdict:
    ok: bool
    reason: str


def _answer_payload(ans: Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(ans.get("answer"), dict):
        return ans["answer"]
    return ans


def _numbers_in_line(line: str) -> list[float]:
    out = []
    for m in _NUM.findall(line):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def check_answer_typed(
    row: Mapping[str, Any],
    page_text: str,
    *,
    gold: Mapping[str, Any] | None = None,
    for_audit: bool = False,
    question: Mapping[str, Any] | None = None,
) -> TypedVerdict:
    """Execute requester contract deterministically (question required for clause parameters)."""
    _ = for_audit, gold
    q = question or row
    contract = compile_contract_primary(q)
    receipt = execute_contract(contract, row, page_text)
    if receipt.aggregate == "PASS":
        return TypedVerdict(True, "ok")
    if receipt.aggregate == "ESCALATE":
        fail = next((c for c in receipt.clauses if c.verdict == "ESCALATE"), receipt.clauses[-1])
        return TypedVerdict(False, f"escalate:{fail.detail}")
    fail = next((c for c in receipt.clauses if c.verdict == "FAIL"), receipt.clauses[-1])
    return TypedVerdict(False, fail.detail)