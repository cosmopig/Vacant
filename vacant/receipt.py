"""產品委派收據：把本次請求、答案與信任狀綁成可獨立驗證的啟動憑證。

信任狀承擔「誰交付、誰審、是否稽核」；本收據再補上產品 gate 所需的完整綁定：
request_id、task、check、risk、答案全文雜湊、信任狀雜湊、完整 resident 身分與鏈頭。
外部 agent 只有在收據驗章且所有雜湊重算一致後才可啟動。

誠實邊界：這能 prevents controller 內的軟體旁路與收據竄改（key custody 假設下）；
同一 OS 使用者或 root 仍可繞過 controller 直接啟動 agent，部署層需另以 sandbox/ACL 限制。
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

from . import crypto
from .canonical import canonical_bytes
from .envelope import ReviewEnvelope
from .identity import Identity, PublicIdentity
from .trustcard import verify_trust_card

RECEIPT_VERSION = 1
RECEIPT_KIND = "vacant.delegation.receipt"

_TOP_LEVEL_FIELDS = {
    "v", "kind", "request_id", "request_sha256", "task_sha256", "tests_sha256",
    "risk", "task_id", "answer_sha256", "trust_card_sha256", "verified",
    "trust_on", "audit", "reviews", "attempts", "substrate", "signer", "ts_ms", "sig",
}
_AUDIT_FIELDS = {"performed", "passed"}
_REVIEW_FIELDS = {"count", "passed"}
_SIGNER_FIELDS = {"vacant_id", "pub", "stream_id", "branch_id", "chain_head"}


class ReceiptError(ValueError):
    """收據格式、綁定或簽章任一處不成立。"""


@dataclass(frozen=True)
class VerifiedReceipt:
    """已通過密碼學與內容綁定驗證的收據；是否准許啟動仍由 GatePolicy 決定。"""

    request_id: str
    task_id: str
    signer_id: str
    verified: bool
    trust_on: bool
    audit_performed: bool
    audit_passed: bool | None
    review_count: int
    review_passed: int
    attempts: int
    receipt: dict[str, Any]


def sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def request_sha256(*, task: str, tests: dict, risk: str, request_id: str) -> str:
    return sha256_canonical({
        "request_id": request_id,
        "task": task,
        "tests": tests,
        "risk": risk,
    })


def make_delegation_receipt(
    identity: Identity,
    *,
    request_id: str,
    task: str,
    tests: dict,
    risk: str,
    task_id: str,
    answer: str,
    trust_card: dict[str, Any],
    verified: bool,
    attempts: int,
    stream_id: str,
    branch_id: str,
    chain_head: str,
    substrate: str,
    ts_ms: int,
) -> dict[str, Any]:
    """簽發一張完整綁定的產品委派收據。"""
    audit = trust_card.get("audit", {})
    reviews = trust_card.get("reviews", [])
    claim: dict[str, Any] = {
        "v": RECEIPT_VERSION,
        "kind": RECEIPT_KIND,
        "request_id": request_id,
        "request_sha256": request_sha256(
            task=task, tests=tests, risk=risk, request_id=request_id),
        "task_sha256": sha256_text(task),
        "tests_sha256": sha256_canonical(tests),
        "risk": risk,
        "task_id": task_id,
        "answer_sha256": sha256_text(answer),
        "trust_card_sha256": sha256_canonical(trust_card),
        "verified": bool(verified),
        "trust_on": bool(trust_card.get("trust_on")),
        "audit": {
            "performed": bool(audit.get("performed")),
            "passed": audit.get("passed"),
        },
        "reviews": {
            "count": len(reviews),
            "passed": sum(1 for r in reviews if r.get("verdict") == "PASS"),
        },
        "attempts": int(attempts),
        "substrate": substrate,
        "signer": {
            "vacant_id": identity.vacant_id,
            "pub": crypto.pub_to_hex(identity.pub),
            "stream_id": stream_id,
            "branch_id": branch_id,
            "chain_head": chain_head,
        },
        "ts_ms": int(ts_ms),
    }
    return {**claim, "sig": identity.sign(canonical_bytes(claim)).hex()}


def _require_schema(receipt: dict[str, Any]) -> None:
    if not isinstance(receipt, dict) or set(receipt) != _TOP_LEVEL_FIELDS:
        raise ReceiptError("receipt schema mismatch")
    if receipt.get("v") != RECEIPT_VERSION or receipt.get("kind") != RECEIPT_KIND:
        raise ReceiptError("unsupported receipt version or kind")
    if not isinstance(receipt.get("request_id"), str) or not receipt["request_id"]:
        raise ReceiptError("invalid request_id")
    if not isinstance(receipt.get("risk"), str) or not receipt["risk"]:
        raise ReceiptError("invalid risk")
    if not isinstance(receipt.get("substrate"), str) or not receipt["substrate"]:
        raise ReceiptError("invalid substrate")
    if not isinstance(receipt.get("task_id"), str) or not receipt["task_id"]:
        raise ReceiptError("invalid task_id")
    for key in ("request_sha256", "task_sha256", "tests_sha256", "answer_sha256",
                "trust_card_sha256"):
        value = receipt.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ReceiptError(f"invalid {key}")
        try:
            bytes.fromhex(value)
        except ValueError as exc:
            raise ReceiptError(f"invalid {key}") from exc
    if type(receipt.get("verified")) is not bool or type(receipt.get("trust_on")) is not bool:
        raise ReceiptError("verified/trust_on must be boolean")
    if not isinstance(receipt.get("attempts"), int) or isinstance(receipt["attempts"], bool) \
            or receipt["attempts"] < 1:
        raise ReceiptError("invalid attempts")
    if not isinstance(receipt.get("ts_ms"), int) or isinstance(receipt["ts_ms"], bool):
        raise ReceiptError("invalid ts_ms")
    if not isinstance(receipt.get("audit"), dict) or set(receipt["audit"]) != _AUDIT_FIELDS:
        raise ReceiptError("invalid audit claim")
    if type(receipt["audit"].get("performed")) is not bool:
        raise ReceiptError("invalid audit performed flag")
    audit_passed = receipt["audit"].get("passed")
    if audit_passed is not None and type(audit_passed) is not bool:
        raise ReceiptError("invalid audit result")
    if not isinstance(receipt.get("reviews"), dict) or set(receipt["reviews"]) != _REVIEW_FIELDS:
        raise ReceiptError("invalid review claim")
    for key in _REVIEW_FIELDS:
        value = receipt["reviews"].get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ReceiptError(f"invalid reviews.{key}")
    if receipt["reviews"]["passed"] > receipt["reviews"]["count"]:
        raise ReceiptError("review pass count exceeds total")
    if not isinstance(receipt.get("signer"), dict) or set(receipt["signer"]) != _SIGNER_FIELDS:
        raise ReceiptError("invalid signer claim")
    if any(not isinstance(receipt["signer"].get(k), str) or not receipt["signer"][k]
           for k in _SIGNER_FIELDS):
        raise ReceiptError("invalid signer fields")
    sig = receipt.get("sig")
    if not isinstance(sig, str) or len(sig) != 128:
        raise ReceiptError("invalid receipt signature")


def verify_delegation_receipt(
    receipt: dict[str, Any],
    *,
    task: str,
    tests: dict,
    risk: str,
    answer: str,
    trust_card: dict[str, Any],
    anchor_pub_hex: str,
    request_id: str | None = None,
) -> VerifiedReceipt:
    """嚴格驗證收據與當前物件的完整綁定；失敗一律 raise ReceiptError。"""
    _require_schema(receipt)
    signer = receipt["signer"]
    if request_id is not None and receipt["request_id"] != request_id:
        raise ReceiptError("request_id mismatch")
    if not hmac.compare_digest(signer["pub"], anchor_pub_hex):
        raise ReceiptError("receipt signer is not anchored in registry")
    try:
        pub = crypto.pub_from_hex(signer["pub"])
    except (TypeError, ValueError) as exc:
        raise ReceiptError("invalid signer public key") from exc
    if crypto.vacant_id_from_pubkey(pub) != signer["vacant_id"]:
        raise ReceiptError("signer identity binding mismatch")

    claim = {k: receipt[k] for k in receipt if k != "sig"}
    try:
        sig = bytes.fromhex(receipt["sig"])
    except ValueError as exc:
        raise ReceiptError("invalid receipt signature") from exc
    if not crypto.verify(pub, canonical_bytes(claim), sig):
        raise ReceiptError("receipt signature verification failed")

    expected = {
        "request_sha256": request_sha256(
            task=task, tests=tests, risk=risk, request_id=receipt["request_id"]),
        "task_sha256": sha256_text(task),
        "tests_sha256": sha256_canonical(tests),
        "answer_sha256": sha256_text(answer),
        "trust_card_sha256": sha256_canonical(trust_card),
    }
    for key, value in expected.items():
        if not hmac.compare_digest(receipt[key], value):
            raise ReceiptError(f"{key} mismatch")
    if receipt["risk"] != risk:
        raise ReceiptError("risk mismatch")
    if trust_card.get("task_id") != receipt["task_id"]:
        raise ReceiptError("trust card task_id mismatch")
    if trust_card.get("signer_pub_hex") != anchor_pub_hex:
        raise ReceiptError("trust card signer is not anchored in registry")
    if not verify_trust_card(trust_card, pub_hex=anchor_pub_hex):
        raise ReceiptError("trust card signature verification failed")
    deliverer = trust_card.get("deliverer", {})
    card_vacant_id = deliverer.get("vacant_id")
    card_stream_id = deliverer.get("stream_id")
    card_chain_head = trust_card.get("chain_head")
    if not isinstance(card_vacant_id, str) or not card_vacant_id \
            or not signer["vacant_id"].endswith(card_vacant_id):
        raise ReceiptError("trust card deliverer mismatch")
    if not isinstance(card_stream_id, str) or not card_stream_id \
            or not signer["stream_id"].endswith(card_stream_id):
        raise ReceiptError("trust card stream mismatch")
    if not isinstance(card_chain_head, str) or not card_chain_head \
            or not signer["chain_head"].endswith(card_chain_head):
        raise ReceiptError("trust card chain head mismatch")
    if receipt["trust_on"] != bool(trust_card.get("trust_on")):
        raise ReceiptError("trust mode mismatch")
    card_audit = trust_card.get("audit", {})
    if receipt["audit"] != {
        "performed": bool(card_audit.get("performed")),
        "passed": card_audit.get("passed"),
    }:
        raise ReceiptError("audit claim mismatch")
    reviews = trust_card.get("reviews", [])
    if receipt["reviews"] != {
        "count": len(reviews),
        "passed": sum(1 for r in reviews if r.get("verdict") == "PASS"),
    }:
        raise ReceiptError("review claim mismatch")
    seen_reviewers: set[str] = set()
    for review in reviews:
        if not isinstance(review, dict):
            raise ReceiptError("invalid review object")
        try:
            envelope = ReviewEnvelope.from_json(review["envelope"])
            reviewer_pub_hex = review["reviewer_pub_hex"]
            reviewer_pub = crypto.pub_from_hex(reviewer_pub_hex)
        except (KeyError, TypeError, ValueError) as exc:
            raise ReceiptError("invalid review envelope") from exc
        reviewer_id = crypto.vacant_id_from_pubkey(reviewer_pub)
        if reviewer_id != envelope.reviewer_id or reviewer_id in seen_reviewers:
            raise ReceiptError("reviewer identity binding or uniqueness failed")
        seen_reviewers.add(reviewer_id)
        if reviewer_id == signer["vacant_id"]:
            raise ReceiptError("deliverer cannot review itself")
        if review.get("sig") != envelope.sig:
            raise ReceiptError("review signature field mismatch")
        if not envelope.verify_sig(PublicIdentity(reviewer_id, reviewer_pub)):
            raise ReceiptError("review signature verification failed")
        if envelope.target_id != signer["vacant_id"] \
                or envelope.target_stream_id != signer["stream_id"] \
                or envelope.branch_id != signer["branch_id"] \
                or envelope.task_id != receipt["task_id"] \
                or envelope.substrate != receipt["substrate"]:
            raise ReceiptError("review target binding mismatch")
        verdict = review.get("verdict")
        expected_scores = 1.0 if verdict == "PASS" else 0.0 if verdict == "FAIL" else None
        if expected_scores is None or not envelope.scores \
                or any(float(score) != expected_scores for score in envelope.scores.values()):
            raise ReceiptError("review verdict does not match signed scores")
        weight = review.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight < 0:
            raise ReceiptError("invalid review weight")

    return VerifiedReceipt(
        request_id=receipt["request_id"],
        task_id=receipt["task_id"],
        signer_id=signer["vacant_id"],
        verified=receipt["verified"],
        trust_on=receipt["trust_on"],
        audit_performed=receipt["audit"]["performed"],
        audit_passed=receipt["audit"]["passed"],
        review_count=receipt["reviews"]["count"],
        review_passed=receipt["reviews"]["passed"],
        attempts=receipt["attempts"],
        receipt=receipt,
    )
