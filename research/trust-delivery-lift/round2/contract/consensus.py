"""Consensus contract from >=2 blind authors (structural agreement only)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from contract.canonical import canonical_dumps, sha256_obj
from contract.filing_contract import (
    FROZEN_AT,
    compile_contract_independent,
    compile_contract_primary,
    compile_contract_question_only,
)


def _clause_key(clause: dict) -> str:
    return str(clause["op"])


def _params_for_op(clause: dict) -> dict[str, Any]:
    skip = {"id", "op"}
    return {k: v for k, v in sorted(clause.items()) if k not in skip}


def build_consensus(authors: list[dict]) -> dict[str, Any]:
    """authors: list of full contract dicts with same task_id."""
    op_inclusion: dict[str, int] = defaultdict(int)
    op_param_votes: dict[str, list[dict]] = defaultdict(list)
    for contract in authors:
        seen_ops = set()
        for clause in contract["clauses"]:
            op = _clause_key(clause)
            seen_ops.add(op)
            op_param_votes[op].append(_params_for_op(clause))
        for op in seen_ops:
            op_inclusion[op] += 1

    consensus_clauses: list[dict] = []
    missing: list[str] = []
    decomposition: dict[str, Any] = {}

    for op, count in sorted(op_inclusion.items()):
        decomposition[op] = {"authors_including": count, "in_consensus": count >= 2}
        if count < 2:
            missing.append(op)
            continue
        # pick param dict that appears in >=2 authors (exact match)
        param_counts: dict[str, int] = defaultdict(int)
        param_example: dict[str, dict] = {}
        for params in op_param_votes[op]:
            key = canonical_dumps(params)
            param_counts[key] += 1
            param_example[key] = params
        chosen = None
        for key, c in param_counts.items():
            if c >= 2:
                chosen = param_example[key]
                break
        if chosen is None:
            missing.append(f"{op}:param_split")
            decomposition[op]["param_agreement"] = False
            continue
        decomposition[op]["param_agreement"] = True
        consensus_clauses.append({"id": f"CC_{op}", "op": op, **chosen})

    task_id = authors[0]["task_id"]
    body = {
        "v": 1,
        "task_id": task_id,
        "profile": "consensus",
        "requester": "consensus_rule_ge2_authors",
        "owner_escalate": "contract_owner@requester",
        "frozen_at": FROZEN_AT,
        "author_ids": ["A_primary", "B_independent", "C_question_only"],
        "clauses": consensus_clauses,
        "decomposition": decomposition,
        "missing_or_split": missing,
    }
    body["sha256"] = sha256_obj({k: v for k, v in body.items() if k != "sha256"})
    return body


def compile_three_authors(question: Mapping[str, Any]) -> list[dict]:
    return [
        compile_contract_primary(question),
        compile_contract_independent(question),
        compile_contract_question_only(question),
    ]


def aggregate_opcode_agreement_rates(questions: list[dict]) -> dict[str, Any]:
    """Pool across tasks: how often each op is in 0/1/2/3 authors."""
    op_counts = defaultdict(lambda: [0, 0, 0, 0])  # 0,1,2,3 authors
    ship_disagree = 0
    n = 0
    from contract.executor import execute_contract
    from pathlib import Path
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "filing"))
    from offline_audit import page_text_for_question  # noqa: E402

    for q in questions:
        authors = compile_three_authors(q)
        for contract in authors:
            for clause in contract["clauses"]:
                pass
        cons = build_consensus(authors)
        for op, meta in cons["decomposition"].items():
            c = meta["authors_including"]
            op_counts[op][c] += 1
        n += 1
    rates = {}
    for op, bucket in op_counts.items():
        rates[op] = {
            "n_tasks_with_op": sum(bucket[1:4]),
            "authors_1": bucket[1],
            "authors_2": bucket[2],
            "authors_3": bucket[3],
            "consensus_eligible_pct": bucket[2] + bucket[3],
        }
    return {"n_tasks": n, "per_opcode": rates}