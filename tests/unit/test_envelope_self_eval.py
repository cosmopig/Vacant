"""A3 — `SelfEval` in `A2AMessage` round-trips through the A2A wire format
AND is covered by the envelope signature.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import EMPTY_PREV_HASH, VacantId
from vacant.protocol import (
    A2AMessage,
    A2APart,
    SelfEval,
    VacantEnvelope,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)


def _envelope(
    *, sk, vk, to_vid: VacantId, payload: A2AMessage, sequence_no: int = 1
) -> VacantEnvelope:
    from_vid = VacantId.from_verify_key(vk)
    return VacantEnvelope(
        from_vacant_id=from_vid,
        to_vacant_id=to_vid,
        sequence_no=sequence_no,
        timestamp=datetime.now(UTC),
        prev_envelope_hash=EMPTY_PREV_HASH,
        payload=payload,
        idempotency_key="idem-1",
    ).signed(sk)


def test_self_eval_defaults_to_none() -> None:
    msg = A2AMessage(role="ROLE_AGENT", parts=[A2APart(type="text", text="ok")])
    assert msg.self_eval is None
    can = msg.canonical_dict()
    assert can["selfEval"] is None


def test_self_eval_field_bounds() -> None:
    with pytest.raises((ValueError, TypeError)):
        SelfEval(factual=1.5)
    with pytest.raises((ValueError, TypeError)):
        SelfEval(confidence=-0.1)
    # All defaults at 0.5 must construct cleanly.
    se = SelfEval()
    assert se.factual == pytest.approx(0.5)
    assert se.confidence == pytest.approx(0.5)


def test_self_eval_dims_dict_excludes_confidence() -> None:
    se = SelfEval(
        factual=0.9, logical=0.8, relevance=0.7, honesty=0.6, adoption=0.5, confidence=0.4
    )
    dims = se.dims_dict()
    assert set(dims.keys()) == {"factual", "logical", "relevance", "honesty", "adoption"}
    assert "confidence" not in dims


def test_envelope_round_trips_with_self_eval() -> None:
    """Wire encode/decode preserves the SelfEval object verbatim."""
    sk, vk = keygen()
    _sk_to, vk_to = keygen()
    to_vid = VacantId.from_verify_key(vk_to)
    se = SelfEval(
        factual=0.95, logical=0.85, relevance=0.75, honesty=0.65, adoption=0.55, confidence=0.42
    )
    payload = A2AMessage(
        role="ROLE_AGENT",
        parts=[A2APart(type="text", text="answer")],
        self_eval=se,
    )
    env = _envelope(sk=sk, vk=vk, to_vid=to_vid, payload=payload)
    wire = to_a2a_jsonrpc(env)
    # The wire form must surface selfEval at params.message.selfEval.
    assert "selfEval" in wire["params"]["message"]
    parsed = from_a2a_jsonrpc(wire)
    assert parsed.payload.self_eval == se


def test_envelope_signature_covers_self_eval() -> None:
    """Tamper test: flipping a self_eval value invalidates the signature.

    This is the load-bearing property — the responder can't lie about
    their self-assessment because it's in the signing payload.
    """
    sk, vk = keygen()
    _sk_to, vk_to = keygen()
    to_vid = VacantId.from_verify_key(vk_to)
    payload = A2AMessage(
        role="ROLE_AGENT",
        parts=[A2APart(type="text", text="answer")],
        self_eval=SelfEval(factual=0.9, confidence=0.9),
    )
    env = _envelope(sk=sk, vk=vk, to_vid=to_vid, payload=payload)
    assert env.verify(env.from_vacant_id.verify_key()) is True

    # Mutate self_eval to a different value but keep the same signature →
    # verification must fail.
    tampered_payload = payload.model_copy(
        update={"self_eval": SelfEval(factual=0.1, confidence=0.1)}
    )
    tampered_env = env.model_copy(update={"payload": tampered_payload})
    assert tampered_env.verify(tampered_env.from_vacant_id.verify_key()) is False


def test_envelope_without_self_eval_does_not_emit_selfEval_key() -> None:
    """Back-compat: an envelope with no self_eval should round-trip
    cleanly through `from_a2a_jsonrpc` (selfEval omitted)."""
    sk, vk = keygen()
    _sk_to, vk_to = keygen()
    to_vid = VacantId.from_verify_key(vk_to)
    payload = A2AMessage(role="ROLE_AGENT", parts=[A2APart(type="text", text="x")])
    env = _envelope(sk=sk, vk=vk, to_vid=to_vid, payload=payload)
    wire = to_a2a_jsonrpc(env)
    assert "selfEval" not in wire["params"]["message"]
    parsed = from_a2a_jsonrpc(wire)
    assert parsed.payload.self_eval is None
