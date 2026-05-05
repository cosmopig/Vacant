"""Hypothesis: a chain of N peer attestations always rejects a tampered link."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from vacant.core.crypto import keygen
from vacant.core.types import VacantId
from vacant.identity.attestation import (
    PeerAttestation,
    issue_attestation,
    verify_attestation,
)


def _make_chain(n: int) -> list[PeerAttestation]:
    pairs = [keygen() for _ in range(n + 1)]
    out: list[PeerAttestation] = []
    for i in range(n):
        atter_sk, atter_vk = pairs[i]
        _, attestee_vk = pairs[i + 1]
        out.append(
            issue_attestation(
                attester=VacantId.from_verify_key(atter_vk),
                attestee=VacantId.from_verify_key(attestee_vk),
                claim=f"vouch-{i}",
                attester_signing_key=atter_sk,
            )
        )
    return out


@given(
    n=st.integers(min_value=2, max_value=8),
    target_idx=st.integers(min_value=0, max_value=7),
    new_claim=st.text(min_size=1, max_size=8),
)
@settings(max_examples=40, deadline=None)
def test_tampered_link_breaks_chain(n: int, target_idx: int, new_claim: str) -> None:
    chain = _make_chain(n)
    idx = target_idx % len(chain)
    bad = chain[idx].model_copy(update={"claim": new_claim or "x"})
    assert verify_attestation(bad) == (new_claim == chain[idx].claim)


@given(n=st.integers(min_value=1, max_value=8))
@settings(max_examples=20, deadline=None)
def test_full_chain_verifies_when_untouched(n: int) -> None:
    chain = _make_chain(n)
    assert all(verify_attestation(a) for a in chain)


@given(
    n=st.integers(min_value=1, max_value=5),
    bad_signature=st.binary(min_size=64, max_size=64),
)
@settings(max_examples=30, deadline=None)
def test_random_signature_breaks_chain(n: int, bad_signature: bytes) -> None:
    chain = _make_chain(n)
    bad = chain[0].model_copy(update={"signature": bad_signature})
    assert verify_attestation(bad) is False


@given(n=st.integers(min_value=1, max_value=5))
@settings(max_examples=10, deadline=None)
def test_swap_attestee_breaks_chain(n: int) -> None:
    chain = _make_chain(n)
    if n < 2:
        return
    other = chain[1].attestee
    bad = chain[0].model_copy(update={"attestee": other})
    assert verify_attestation(bad) is False


def test_freshness_window_excludes_old_attestations() -> None:
    sk, vk = keygen()
    other_sk, other_vk = keygen()
    a_id = VacantId.from_verify_key(vk)
    b_id = VacantId.from_verify_key(other_vk)
    far_past = datetime.now(UTC) - timedelta(days=900)
    att = issue_attestation(
        attester=a_id,
        attestee=b_id,
        claim="x",
        attester_signing_key=sk,
        issued_at=far_past,
        expires_at=far_past + timedelta(days=1),
    )
    assert verify_attestation(att) is False
    _ = other_sk
