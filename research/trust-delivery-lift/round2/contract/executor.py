"""Deterministic contract execution — VACANT has no discretion (PASS/FAIL/ESCALATE only)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from contract.canonical import sha256_obj

_VERDICT = Literal["PASS", "FAIL", "ESCALATE"]
_NUM = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)")


@dataclass
class ClauseResult:
    clause_id: str
    verdict: _VERDICT
    span: str
    detail: str


@dataclass
class ExecutionReceipt:
    contract_sha256: str
    executor_sha256: str
    clauses: list[ClauseResult] = field(default_factory=list)

    @property
    def aggregate(self) -> _VERDICT:
        if any(c.verdict == "FAIL" for c in self.clauses):
            return "FAIL"
        if any(c.verdict == "ESCALATE" for c in self.clauses):
            return "ESCALATE"
        return "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_sha256": self.contract_sha256,
            "executor_sha256": self.executor_sha256,
            "aggregate": self.aggregate,
            "clauses": [
                {"clause_id": c.clause_id, "verdict": c.verdict, "span": c.span, "detail": c.detail}
                for c in self.clauses
            ],
        }


EXECUTOR_VERSION = "vacant.contract.executor/1"


def executor_hash() -> str:
    return sha256_obj({"v": EXECUTOR_VERSION, "opcodes": sorted(_OPCODES)})


def _numbers_in_line(line: str) -> list[float]:
    out = []
    for m in _NUM.findall(line):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def _parse_header_scale(page_text: str) -> float:
    t = page_text.lower()
    if "in billions" in t or "(billions)" in t:
        return 1e9
    if "in millions" in t or "(millions)" in t:
        return 1e6
    if "in thousands" in t:
        return 1e3
    return 1.0


def _scale_mult(s: Any) -> float:
    if s is None:
        return 1.0
    if isinstance(s, (int, float)) and float(s) < 20:
        return float(10 ** int(s))
    sl = str(s).lower()
    if "billion" in sl:
        return 1e9
    if "million" in sl:
        return 1e6
    if "thousand" in sl:
        return 1e3
    return 1.0


def _answer_payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(row.get("answer"), dict):
        return row["answer"]
    return row


def _op_status_found(ctx: dict, clause: dict) -> ClauseResult:
    ans = ctx["ans"]
    required = clause.get("required_fields", ["value", "span", "scale"])
    cid = clause["id"]
    st = str(ans.get("status", "")).lower()
    if st == "not_found":
        if clause.get("allow_not_found"):
            return ClauseResult(cid, "PASS", "", "not_found_allowed")
        return ClauseResult(cid, "FAIL", "", "not_found")
    missing = [f for f in required if not ans.get(f)]
    if missing:
        return ClauseResult(cid, "FAIL", str(ans.get("span", "")), f"missing:{','.join(missing)}")
    return ClauseResult(cid, "PASS", str(ans.get("span", "")), "ok")


def _op_provenance_span(ctx: dict, clause: dict) -> ClauseResult:
    ans, page = ctx["ans"], ctx["page_text"]
    span = str(ans.get("span", ""))
    cid = clause["id"]
    if not span:
        return ClauseResult(cid, "FAIL", "", "missing_span")
    if span not in page:
        return ClauseResult(cid, "FAIL", span, "span_not_in_page_text")
    return ClauseResult(cid, "PASS", span, "ok")


def _op_value_in_span_numbers(ctx: dict, clause: dict) -> ClauseResult:
    ans = ctx["ans"]
    cid = clause["id"]
    span = str(ans.get("span", ""))
    try:
        shown = float(ans.get("value"))
    except (TypeError, ValueError):
        return ClauseResult(cid, "FAIL", span, "bad_value")
    tol = float(clause.get("tolerance_relative", 0.001))
    floor = float(clause.get("tolerance_floor", 0.5))
    nums = _numbers_in_line(span)
    if not nums:
        return ClauseResult(cid, "FAIL", span, "no_numbers_in_span")
    if not any(abs(abs(shown) - abs(n)) <= max(floor, tol * abs(n)) for n in nums):
        return ClauseResult(cid, "FAIL", span, "value_not_in_span_numbers")
    return ClauseResult(cid, "PASS", span, "ok")


def _op_scale_header_consistency(ctx: dict, clause: dict) -> ClauseResult:
    ans, page = ctx["ans"], ctx["page_text"]
    cid = clause["id"]
    if ans.get("scale") is None:
        return ClauseResult(cid, "PASS", str(ans.get("span", "")), "no_answer_scale_skip")
    header = _parse_header_scale(page)
    ans_scale = _scale_mult(ans.get("scale"))
    if header >= 1e6 and ans_scale >= 1e9:
        return ClauseResult(cid, "FAIL", str(ans.get("span", "")), "scale_mismatch")
    if header >= 1e6 and 1 < ans_scale <= 1e3:
        return ClauseResult(cid, "FAIL", str(ans.get("span", "")), "scale_mismatch")
    if header >= 1e9 and 1 < ans_scale <= 1e6:
        return ClauseResult(cid, "FAIL", str(ans.get("span", "")), "scale_mismatch")
    return ClauseResult(cid, "PASS", str(ans.get("span", "")), "ok")


def _op_unit_if_declared(ctx: dict, clause: dict) -> ClauseResult:
    ans = ctx["ans"]
    cid = clause["id"]
    required = str(clause.get("unit", "USD")).upper()
    if "unit" not in ans:
        return ClauseResult(cid, "PASS", str(ans.get("span", "")), "unit_not_declared_skip")
    if str(ans["unit"]).upper() != required:
        return ClauseResult(cid, "FAIL", str(ans.get("span", "")), "unit_mismatch")
    return ClauseResult(cid, "PASS", str(ans.get("span", "")), "ok")


def _op_multi_column_escalate(ctx: dict, clause: dict) -> ClauseResult:
    """Semantic: which table column is immaterial without requester-pinned period — ESCALATE, never guess."""
    ans = ctx["ans"]
    cid = clause["id"]
    span = str(ans.get("span", ""))
    nums = _numbers_in_line(span)
    threshold = int(clause.get("distinct_numbers_escalate_above", 2))
    if len(nums) > threshold:
        return ClauseResult(cid, "ESCALATE", span, "multi_column_period_not_in_contract")
    return ClauseResult(cid, "PASS", span, "ok")


_OPCODES = {
    "status_found_fields": _op_status_found,
    "provenance_span_substr": _op_provenance_span,
    "value_in_span_numbers": _op_value_in_span_numbers,
    "scale_header_consistency": _op_scale_header_consistency,
    "unit_if_declared": _op_unit_if_declared,
    "multi_column_escalate": _op_multi_column_escalate,
}


def execute_contract(contract: Mapping[str, Any], answer_row: Mapping[str, Any], page_text: str) -> ExecutionReceipt:
    ans = _answer_payload(answer_row)
    ctx = {"ans": ans, "page_text": page_text}
    contract_sha = contract.get("sha256") or sha256_obj({k: v for k, v in contract.items() if k != "sha256"})
    results: list[ClauseResult] = []
    for clause in contract["clauses"]:
        op = clause["op"]
        fn = _OPCODES.get(op)
        if fn is None:
            results.append(ClauseResult(clause["id"], "ESCALATE", "", f"unknown_op:{op}"))
            continue
        results.append(fn(ctx, clause))
    return ExecutionReceipt(contract_sha256=contract_sha, executor_sha256=executor_hash(), clauses=results)


def receipt_agree(a: ExecutionReceipt, b: ExecutionReceipt) -> bool:
    return a.to_dict() == b.to_dict()