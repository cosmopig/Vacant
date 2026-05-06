"""VacantEnvelope sign/verify/serialize tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import EMPTY_PREV_HASH, VacantId
from vacant.protocol import (
    A2AMessage,
    A2APart,
    EnvelopeFormatError,
    EnvelopeSignatureError,
    VacantEnvelope,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)


def _make_pair():  # type: ignore[no-untyped-def]
    sk_a, vk_a = keygen()
    sk_b, vk_b = keygen()
    return (
        sk_a,
        VacantId.from_verify_key(vk_a),
        sk_b,
        VacantId.from_verify_key(vk_b),
    )


def _envelope(*, sk, frm, to, seq=1, prev=EMPTY_PREV_HASH):  # type: ignore[no-untyped-def]
    payload = A2AMessage(role="ROLE_USER", parts=[A2APart(type="text", text="hello")])
    env = VacantEnvelope(
        from_vacant_id=frm,
        to_vacant_id=to,
        sequence_no=seq,
        timestamp=datetime(2026, 5, 6, tzinfo=UTC),
        prev_envelope_hash=prev,
        payload=payload,
        idempotency_key="idem-1",
    ).signed(sk)
    return env


# --- sign/verify -----------------------------------------------------------


def test_envelope_sign_verify_roundtrip() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    env = _envelope(sk=sk_a, frm=frm, to=to)
    assert env.verify(frm.verify_key()) is True


def test_envelope_unsigned_does_not_verify() -> None:
    _sk_a, frm, _sk_b, to = _make_pair()
    env = VacantEnvelope(
        from_vacant_id=frm,
        to_vacant_id=to,
        sequence_no=1,
        timestamp=datetime.now(UTC),
        payload=A2AMessage(parts=[A2APart(text="x")]),
    )
    assert env.verify(frm.verify_key()) is False


def test_envelope_tamper_payload_breaks_signature() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    env = _envelope(sk=sk_a, frm=frm, to=to)
    tampered = env.model_copy(update={"payload": A2AMessage(parts=[A2APart(text="hijacked")])})
    assert tampered.verify(frm.verify_key()) is False


def test_envelope_tamper_seq_breaks_signature() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    env = _envelope(sk=sk_a, frm=frm, to=to)
    bad = env.model_copy(update={"sequence_no": 999})
    assert bad.verify(frm.verify_key()) is False


def test_envelope_tamper_prev_hash_breaks_signature() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    env = _envelope(sk=sk_a, frm=frm, to=to)
    bad = env.model_copy(update={"prev_envelope_hash": b"\xff" * 32})
    assert bad.verify(frm.verify_key()) is False


def test_envelope_wrong_pubkey_does_not_verify() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    env = _envelope(sk=sk_a, frm=frm, to=to)
    _other_sk, other_vk = keygen()
    assert env.verify(other_vk) is False


def test_verify_or_raise_raises_on_bad_sig() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    env = _envelope(sk=sk_a, frm=frm, to=to)
    bad = env.model_copy(update={"sequence_no": 999})
    with pytest.raises(EnvelopeSignatureError):
        bad.verify_or_raise(frm.verify_key())


def test_envelope_seq_must_be_positive() -> None:
    _sk_a, frm, _sk_b, to = _make_pair()
    with pytest.raises(ValueError):
        VacantEnvelope(
            from_vacant_id=frm,
            to_vacant_id=to,
            sequence_no=0,
            timestamp=datetime.now(UTC),
            payload=A2AMessage(),
        )


def test_envelope_prev_hash_must_be_32_bytes() -> None:
    _sk_a, frm, _sk_b, to = _make_pair()
    with pytest.raises(Exception):  # noqa: B017 (pydantic ValidationError)
        VacantEnvelope(
            from_vacant_id=frm,
            to_vacant_id=to,
            sequence_no=1,
            timestamp=datetime.now(UTC),
            prev_envelope_hash=b"\x00" * 4,
            payload=A2AMessage(),
        )


# --- chain hash ------------------------------------------------------------


def test_compute_hash_deterministic() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    env = _envelope(sk=sk_a, frm=frm, to=to)
    assert env.compute_hash() == env.compute_hash()


def test_compute_hash_changes_when_seq_changes() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    a = _envelope(sk=sk_a, frm=frm, to=to, seq=1)
    b = _envelope(sk=sk_a, frm=frm, to=to, seq=2)
    assert a.compute_hash() != b.compute_hash()


# --- A2A wire round-trip ---------------------------------------------------


def test_a2a_jsonrpc_roundtrip() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    env = _envelope(sk=sk_a, frm=frm, to=to)
    body = to_a2a_jsonrpc(env)
    assert body["jsonrpc"] == "2.0"
    assert body["method"] == "message/send"
    parsed = from_a2a_jsonrpc(body)
    assert parsed.from_vacant_id == frm
    assert parsed.to_vacant_id == to
    assert parsed.sequence_no == 1
    assert parsed.payload.parts[0].text == "hello"
    # And it still verifies under the original sender's pubkey.
    assert parsed.verify(frm.verify_key()) is True


def test_from_a2a_jsonrpc_missing_metadata_raises() -> None:
    body = {"params": {"message": {"role": "ROLE_USER", "parts": [], "metadata": {}}}}
    with pytest.raises(EnvelopeFormatError):
        from_a2a_jsonrpc(body)


def test_from_a2a_jsonrpc_invalid_hex_raises() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    env = _envelope(sk=sk_a, frm=frm, to=to)
    body = to_a2a_jsonrpc(env)
    body["params"]["message"]["metadata"]["urn:vacant:v1"]["from_vacant_id"] = "not-hex"
    with pytest.raises(EnvelopeFormatError):
        from_a2a_jsonrpc(body)


def test_envelope_signing_dict_includes_all_fields() -> None:
    """Regression: signing payload must include from/to/seq/ts/prev/idem/payload."""
    sk_a, frm, _sk_b, to = _make_pair()
    env = _envelope(sk=sk_a, frm=frm, to=to)
    sd = env.signing_dict()
    for k in ("from", "to", "seq", "ts", "prev", "idem", "payload"):
        assert k in sd


# --- timestamp normalisation -----------------------------------------------


def test_envelope_naive_timestamp_treated_as_utc() -> None:
    sk_a, frm, _sk_b, to = _make_pair()
    naive_ts = datetime(2026, 5, 6, 12, 0, 0)  # no tzinfo
    payload = A2AMessage(parts=[A2APart(text="x")])
    env = VacantEnvelope(
        from_vacant_id=frm,
        to_vacant_id=to,
        sequence_no=1,
        timestamp=naive_ts,
        payload=payload,
    ).signed(sk_a)
    assert env.verify(frm.verify_key()) is True
    # Wire round-trip preserves UTC offset.
    body = to_a2a_jsonrpc(env)
    parsed = from_a2a_jsonrpc(body)
    assert parsed.verify(frm.verify_key()) is True
    _ = timedelta  # silence unused
