"""產品委派 receipt：完整綁定 request/check/answer/card，任一竄改都不能過 gate。"""

from __future__ import annotations

import copy

import pytest

from vacant.ecosystem import Ecosystem, PRODUCT_ROSTER
from vacant.receipt import ReceiptError, verify_delegation_receipt

CHECK = {
    "type": "run_python",
    "code": "assert solve('abc') == 'cba'\nassert solve('') == ''",
}


class GoodBrain:
    name = "good"

    def generate(self, prompt: str) -> str:
        return "def solve(s):\n    return s[::-1]"


def _issued(tmp_path):
    eco = Ecosystem(tmp_path, GoodBrain(), roster=PRODUCT_ROSTER, k_reviewers=2)
    result = eco.delegate(
        "Reverse a string.", CHECK, risk="normal", issue_receipt=True,
        request_id="req_123", max_attempts=3, output_mode="auto",
    )
    receipt = result["receipt"]
    anchor = eco.registry.card(receipt["signer"]["vacant_id"])
    assert anchor is not None
    return result, anchor.pub_hex


def _verify(result, pub):
    return verify_delegation_receipt(
        result["receipt"],
        task="Reverse a string.",
        tests=CHECK,
        risk="normal",
        answer=result["answer"],
        trust_card=result["trust_card"],
        anchor_pub_hex=pub,
        request_id="req_123",
    )


def test_receipt_roundtrip_is_task_and_answer_bound(tmp_path):
    result, pub = _issued(tmp_path)
    verified = _verify(result, pub)
    assert verified.request_id == "req_123"
    assert verified.task_id == result["task_id"]
    assert verified.verified is True
    assert verified.trust_on is True
    assert verified.audit_performed and verified.audit_passed
    assert verified.review_count == 2
    assert verified.attempts == 1
    assert (tmp_path / "receipts" / "req_123.json").exists()


@pytest.mark.parametrize("mutation", [
    "task", "tests", "risk", "answer", "card", "signature", "anchor", "request_id",
])
def test_receipt_rejects_every_binding_tamper(tmp_path, mutation):
    result, pub = _issued(tmp_path)
    task, tests, risk = "Reverse a string.", CHECK, "normal"
    answer, card, request_id = result["answer"], result["trust_card"], "req_123"
    receipt = copy.deepcopy(result["receipt"])
    if mutation == "task":
        task = "Different task"
    elif mutation == "tests":
        tests = {"type": "equals", "value": "x"}
    elif mutation == "risk":
        risk = "high"
    elif mutation == "answer":
        answer += "\n# changed"
    elif mutation == "card":
        card = {**card, "task_id": "different"}
    elif mutation == "signature":
        receipt["sig"] = "0" * 128
    elif mutation == "anchor":
        pub = "00" * 32
    elif mutation == "request_id":
        request_id = "another_request"
    result["receipt"] = receipt
    with pytest.raises(ReceiptError):
        verify_delegation_receipt(
            receipt, task=task, tests=tests, risk=risk, answer=answer,
            trust_card=card, anchor_pub_hex=pub, request_id=request_id,
        )


def test_receipt_schema_is_strict(tmp_path):
    result, pub = _issued(tmp_path)
    result["receipt"]["unexpected"] = True
    with pytest.raises(ReceiptError, match="schema"):
        _verify(result, pub)


def test_request_id_cannot_be_reissued(tmp_path):
    eco = Ecosystem(tmp_path, GoodBrain(), roster=PRODUCT_ROSTER, k_reviewers=2)
    kwargs = dict(
        task="Reverse a string.", tests=CHECK, issue_receipt=True,
        request_id="same_request", output_mode="auto",
    )
    eco.delegate(**kwargs)
    with pytest.raises(ValueError, match="already been used"):
        eco.delegate(**kwargs)
