"""Blinded peer-review primitives (THEORY_V5 §3.9 #4)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vacant.core.crypto import SigningKey
from vacant.core.types import VacantId
from vacant.reputation.blinded_review import (
    BLINDED_COMMITMENT_SCHEME,
    BlindedReviewBatch,
    RevealEnvelope,
    commit_reviewer,
    make_blinded_review_record,
    make_reveal_envelope,
    unblind_record,
    verify_reveal,
)


def _ids() -> tuple[SigningKey, str, str]:
    sk = SigningKey.generate()
    pub_hex = bytes(sk.verify_key).hex()
    target_vid = VacantId(pubkey_bytes=bytes(SigningKey.generate().verify_key))
    return sk, pub_hex, target_vid.hex()


def _now() -> str:
    return datetime.now(UTC).isoformat()


# --- primitives ----------------------------------------------------------


def test_commit_reviewer_returns_32_byte_commitment_and_nonce() -> None:
    sk, pub_hex, target_hex = _ids()
    commitment, nonce = commit_reviewer(
        reviewer_pubkey=bytes.fromhex(pub_hex), target_vid_hex=target_hex
    )
    assert len(commitment) == 32
    assert len(nonce) == 32


def test_commit_reviewer_is_deterministic_with_explicit_nonce() -> None:
    sk, pub_hex, target_hex = _ids()
    nonce = b"\x42" * 32
    c1, _ = commit_reviewer(
        reviewer_pubkey=bytes.fromhex(pub_hex), target_vid_hex=target_hex, nonce=nonce
    )
    c2, _ = commit_reviewer(
        reviewer_pubkey=bytes.fromhex(pub_hex), target_vid_hex=target_hex, nonce=nonce
    )
    assert c1 == c2


def test_commit_reviewer_rejects_wrong_pubkey_length() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        commit_reviewer(reviewer_pubkey=b"\x00" * 16, target_vid_hex="deadbeef")


def test_commit_reviewer_rejects_wrong_nonce_length() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        commit_reviewer(
            reviewer_pubkey=b"\x00" * 32, target_vid_hex="x", nonce=b"\x01" * 8
        )


# --- reveal envelope -----------------------------------------------------


def test_reveal_envelope_round_trips_through_dict() -> None:
    sk, pub_hex, target_hex = _ids()
    commitment, nonce = commit_reviewer(
        reviewer_pubkey=bytes.fromhex(pub_hex), target_vid_hex=target_hex
    )
    env = make_reveal_envelope(
        reviewer_signing_key=sk,
        nonce=nonce,
        commitment=commitment,
        target_vid_hex=target_hex,
    )
    d = env.to_dict()
    restored = RevealEnvelope.from_dict(d)
    assert restored == env


def test_verify_reveal_accepts_well_formed_envelope() -> None:
    sk, pub_hex, target_hex = _ids()
    commitment, nonce = commit_reviewer(
        reviewer_pubkey=bytes.fromhex(pub_hex), target_vid_hex=target_hex
    )
    env = make_reveal_envelope(
        reviewer_signing_key=sk,
        nonce=nonce,
        commitment=commitment,
        target_vid_hex=target_hex,
    )
    assert verify_reveal(env) is True


def test_verify_reveal_rejects_tampered_pubkey() -> None:
    sk, pub_hex, target_hex = _ids()
    commitment, nonce = commit_reviewer(
        reviewer_pubkey=bytes.fromhex(pub_hex), target_vid_hex=target_hex
    )
    env = make_reveal_envelope(
        reviewer_signing_key=sk,
        nonce=nonce,
        commitment=commitment,
        target_vid_hex=target_hex,
    )
    # Try to claim the commitment was for a different reviewer.
    other = bytes(SigningKey.generate().verify_key).hex()
    tampered = env.__class__(
        commitment_hex=env.commitment_hex,
        reviewer_pubkey_hex=other,
        nonce_hex=env.nonce_hex,
        target_vid_hex=env.target_vid_hex,
        scheme=env.scheme,
        signature_hex=env.signature_hex,
    )
    assert verify_reveal(tampered) is False


def test_verify_reveal_rejects_wrong_scheme() -> None:
    sk, pub_hex, target_hex = _ids()
    commitment, nonce = commit_reviewer(
        reviewer_pubkey=bytes.fromhex(pub_hex), target_vid_hex=target_hex
    )
    env = make_reveal_envelope(
        reviewer_signing_key=sk,
        nonce=nonce,
        commitment=commitment,
        target_vid_hex=target_hex,
    )
    bad = env.__class__(
        commitment_hex=env.commitment_hex,
        reviewer_pubkey_hex=env.reviewer_pubkey_hex,
        nonce_hex=env.nonce_hex,
        target_vid_hex=env.target_vid_hex,
        scheme="bogus-scheme-v999",
        signature_hex=env.signature_hex,
    )
    assert verify_reveal(bad) is False


# --- blinded record + unblind round trip ---------------------------------


def test_make_blinded_review_record_produces_pair() -> None:
    sk, _pub_hex, target_hex = _ids()
    record, env = make_blinded_review_record(
        reviewer_signing_key=sk,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.7, "logical": 0.7, "relevance": 0.7},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="00" * 32,
        claim="test",
        issued_at_iso=_now(),
    )
    # Record has commitment fields, not plaintext reviewer.
    assert "reviewer" not in record
    assert "reviewer_commitment" in record
    assert record["commitment_scheme"] == BLINDED_COMMITMENT_SCHEME
    # Envelope is consistent.
    assert env.commitment_hex == record["reviewer_commitment"]
    assert env.target_vid_hex == target_hex


def test_unblind_record_recovers_reviewer_when_paired_correctly() -> None:
    sk, pub_hex, target_hex = _ids()
    record, env = make_blinded_review_record(
        reviewer_signing_key=sk,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.8, "logical": 0.8, "relevance": 0.8},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="aa" * 32,
        claim="unblind test",
        issued_at_iso=_now(),
    )
    unblinded = unblind_record(record, env)
    assert unblinded is not None
    assert unblinded["reviewer"] == pub_hex
    assert "reviewer_commitment" not in unblinded
    # Other fields preserved.
    assert unblinded["target"] == target_hex
    assert unblinded["dimensions"]["factual"] == 0.8


def test_unblind_rejects_mismatched_envelope() -> None:
    """An envelope from a different (record, reviewer) pair must not
    pair with this record — otherwise an attacker could mix reveals."""
    sk1, _p1, target_hex = _ids()
    sk2 = SigningKey.generate()
    record, _env_from_sk1 = make_blinded_review_record(
        reviewer_signing_key=sk1,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.5, "logical": 0.5, "relevance": 0.5},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="bb" * 32,
        claim="x",
        issued_at_iso=_now(),
    )
    # Build a wholly different envelope from sk2.
    other_commitment, other_nonce = commit_reviewer(
        reviewer_pubkey=bytes(sk2.verify_key), target_vid_hex=target_hex
    )
    bad_env = make_reveal_envelope(
        reviewer_signing_key=sk2,
        nonce=other_nonce,
        commitment=other_commitment,
        target_vid_hex=target_hex,
    )
    assert unblind_record(record, bad_env) is None


def test_unblind_rejects_target_mismatch() -> None:
    sk, _pub_hex, target_hex = _ids()
    record, env = make_blinded_review_record(
        reviewer_signing_key=sk,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.5, "logical": 0.5, "relevance": 0.5},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="cc" * 32,
        claim="x",
        issued_at_iso=_now(),
    )
    # Mutate the record's target post-signing — record signature now
    # fails to verify on the modified payload.
    record_bad = dict(record)
    record_bad["target"] = "ee" * 32
    assert unblind_record(record_bad, env) is None


# --- batch accumulator ---------------------------------------------------


def test_batch_buffers_and_reveals_only_when_threshold_met() -> None:
    target_hex = bytes(SigningKey.generate().verify_key).hex()
    batch = BlindedReviewBatch(min_reveal_size=3)
    assert batch.pending_count == 0
    assert batch.is_ready_to_reveal() is False

    pairs = []
    for _ in range(2):
        sk = SigningKey.generate()
        record, env = make_blinded_review_record(
            reviewer_signing_key=sk,
            target_vid_hex=target_hex,
            dimensions={"factual": 0.6, "logical": 0.6, "relevance": 0.6},
            substrate="peer-review:heuristic",
            call_envelope_id_hex="aa" * 32,
            claim="x",
            issued_at_iso=_now(),
        )
        batch.add(record, env)
        pairs.append((record, env, sk))

    # 2 < 3 → not ready
    assert batch.pending_count == 2
    assert batch.is_ready_to_reveal() is False
    assert batch.flush_reveals() == []

    # Add the third
    sk3 = SigningKey.generate()
    rec3, env3 = make_blinded_review_record(
        reviewer_signing_key=sk3,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.6, "logical": 0.6, "relevance": 0.6},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="aa" * 32,
        claim="x",
        issued_at_iso=_now(),
    )
    batch.add(rec3, env3)
    pairs.append((rec3, env3, sk3))

    assert batch.is_ready_to_reveal() is True
    unblinded = batch.flush_reveals()
    assert len(unblinded) == 3
    revealed_reviewers = {row["reviewer"] for row in unblinded}
    expected = {bytes(p[2].verify_key).hex() for p in pairs}
    assert revealed_reviewers == expected
    # Buffer cleared after a successful flush.
    assert batch.pending_count == 0


def test_batch_rejects_add_with_mismatched_envelope() -> None:
    target_hex = bytes(SigningKey.generate().verify_key).hex()
    batch = BlindedReviewBatch(min_reveal_size=2)
    sk1 = SigningKey.generate()
    sk2 = SigningKey.generate()
    record_1, _env_1 = make_blinded_review_record(
        reviewer_signing_key=sk1,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.5, "logical": 0.5, "relevance": 0.5},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="01" * 32,
        claim="x",
        issued_at_iso=_now(),
    )
    _r2, env_2 = make_blinded_review_record(
        reviewer_signing_key=sk2,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.5, "logical": 0.5, "relevance": 0.5},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="02" * 32,
        claim="x",
        issued_at_iso=_now(),
    )
    with pytest.raises(ValueError, match="commitment_hex"):
        batch.add(record_1, env_2)


def test_batch_drops_bad_pair_and_keeps_good_rows() -> None:
    """A single bad (record, envelope) pair must NOT stall the batch.
    `flush_reveals` drops the bad pair, bumps `dropped_pairs_count`,
    and returns the good rows."""
    target_hex = bytes(SigningKey.generate().verify_key).hex()
    batch = BlindedReviewBatch(min_reveal_size=2)

    sk1 = SigningKey.generate()
    r1, e1 = make_blinded_review_record(
        reviewer_signing_key=sk1,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.5, "logical": 0.5, "relevance": 0.5},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="01" * 32,
        claim="x",
        issued_at_iso=_now(),
    )
    batch.add(r1, e1)

    # Second pair: corrupt the envelope's signature so verify_reveal fails.
    sk2 = SigningKey.generate()
    r2, e2 = make_blinded_review_record(
        reviewer_signing_key=sk2,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.5, "logical": 0.5, "relevance": 0.5},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="02" * 32,
        claim="x",
        issued_at_iso=_now(),
    )
    bad_e2 = e2.__class__(
        commitment_hex=e2.commitment_hex,
        reviewer_pubkey_hex=e2.reviewer_pubkey_hex,
        nonce_hex=e2.nonce_hex,
        target_vid_hex=e2.target_vid_hex,
        scheme=e2.scheme,
        signature_hex="00" * 64,  # Invalid signature
    )
    batch.add(r2, bad_e2)

    assert batch.is_ready_to_reveal() is True
    unblinded = batch.flush_reveals()
    assert len(unblinded) == 1
    assert unblinded[0]["reviewer"] == bytes(sk1.verify_key).hex()
    assert batch.dropped_pairs_count == 1
    # Buffer cleared after flush (good rows emitted, bad ones dropped).
    assert batch.pending_count == 0


def test_batch_requires_distinct_reviewers_not_just_distinct_commitments() -> None:
    """A single attacker submitting `min_reveal_size` commitments with
    different nonces must NOT be able to flush themselves alone.

    Threshold is by distinct reviewer pubkey, not by row count.
    """
    target_hex = bytes(SigningKey.generate().verify_key).hex()
    batch = BlindedReviewBatch(min_reveal_size=3)

    # ONE reviewer producing three commitments (different nonces).
    sk = SigningKey.generate()
    for i in range(3):
        rec, env = make_blinded_review_record(
            reviewer_signing_key=sk,
            target_vid_hex=target_hex,
            dimensions={"factual": 0.5, "logical": 0.5, "relevance": 0.5},
            substrate="peer-review:heuristic",
            call_envelope_id_hex=f"{i:02x}" * 32,
            claim=f"row-{i}",
            issued_at_iso=_now(),
        )
        batch.add(rec, env)

    assert batch.pending_count == 3
    assert batch.distinct_reviewers == 1
    # NOT ready: only one distinct reviewer.
    assert batch.is_ready_to_reveal() is False
    assert batch.flush_reveals() == []
    assert batch.pending_count == 3  # nothing was flushed

    # Add one more distinct reviewer → still 2 distinct, not enough.
    sk2 = SigningKey.generate()
    rec2, env2 = make_blinded_review_record(
        reviewer_signing_key=sk2,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.5, "logical": 0.5, "relevance": 0.5},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="ff" * 32,
        claim="row-extra",
        issued_at_iso=_now(),
    )
    batch.add(rec2, env2)
    assert batch.distinct_reviewers == 2
    assert batch.is_ready_to_reveal() is False

    # Add a third distinct reviewer → now ready.
    sk3 = SigningKey.generate()
    rec3, env3 = make_blinded_review_record(
        reviewer_signing_key=sk3,
        target_vid_hex=target_hex,
        dimensions={"factual": 0.5, "logical": 0.5, "relevance": 0.5},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="fe" * 32,
        claim="row-extra2",
        issued_at_iso=_now(),
    )
    batch.add(rec3, env3)
    assert batch.distinct_reviewers == 3
    assert batch.is_ready_to_reveal() is True
    unblinded = batch.flush_reveals()
    # All 5 rows unblind (3 from sk + sk2 + sk3).
    assert len(unblinded) == 5
