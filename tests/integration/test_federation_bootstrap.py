"""Slow integration: 2-of-5 federation bootstrap, partial-failure tolerance,
and rotation preserving pre-rotation attestations.
"""

from __future__ import annotations

import pytest

from vacant.core.crypto import SigningKey, keygen
from vacant.core.types import VacantId
from vacant.identity.federation import (
    FederatedAttestation,
    RootSet,
    issue_root_signature,
    rotate_root,
    sign_rotation,
    verify_federated,
)

pytestmark = pytest.mark.slow


def _make_roots(n: int) -> tuple[list[VacantId], list[SigningKey]]:
    pairs = [keygen() for _ in range(n)]
    return (
        [VacantId.from_verify_key(vk) for _, vk in pairs],
        [sk for sk, _ in pairs],
    )


def test_bootstrap_2_of_5_full_quorum_verifies() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject = VacantId.from_verify_key(keygen()[1])
    sigs = [
        issue_root_signature(
            root=ids[i], root_signing_key=sks[i], subject=subject, claim="bootstrap"
        )
        for i in (0, 1, 2)
    ]
    att = FederatedAttestation(subject=subject, claim="bootstrap", signatures=sigs)
    assert verify_federated(att, rs) is True


def test_bootstrap_2_of_5_with_one_invalid_root_still_verifies() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject = VacantId.from_verify_key(keygen()[1])
    good = [
        issue_root_signature(root=ids[i], root_signing_key=sks[i], subject=subject, claim="x")
        for i in (0, 1)
    ]
    # ids[2] presents a bogus signature.
    rs2 = good[0].model_copy(update={"root": ids[2]})
    sigs = [rs2, good[0], good[1]]
    att = FederatedAttestation(subject=subject, claim="x", signatures=sigs)
    assert verify_federated(att, rs) is True


def test_bootstrap_2_of_5_with_two_invalid_roots_fails() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject = VacantId.from_verify_key(keygen()[1])
    good = issue_root_signature(root=ids[0], root_signing_key=sks[0], subject=subject, claim="x")
    forged_for_1 = good.model_copy(update={"root": ids[1]})
    forged_for_2 = good.model_copy(update={"root": ids[2]})
    att = FederatedAttestation(
        subject=subject, claim="x", signatures=[good, forged_for_1, forged_for_2]
    )
    # Only one valid signature (good); below threshold = 2.
    assert verify_federated(att, rs) is False


def test_pre_rotation_attestation_still_verifies_against_prior_rootset() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject = VacantId.from_verify_key(keygen()[1])
    pre_sigs = [
        issue_root_signature(
            root=ids[i], root_signing_key=sks[i], subject=subject, claim="pre-rotate"
        )
        for i in (0, 1)
    ]
    pre_att = FederatedAttestation(subject=subject, claim="pre-rotate", signatures=pre_sigs)

    new_sk, new_vk = keygen()
    new_id = VacantId.from_verify_key(new_vk)
    rotation_sigs = [
        sign_rotation(
            rootset=rs, root=ids[0], root_signing_key=sks[0], old_root=ids[2], new_root=new_id
        ),
        sign_rotation(
            rootset=rs, root=ids[1], root_signing_key=sks[1], old_root=ids[2], new_root=new_id
        ),
    ]
    rotated = rotate_root(rs, old_root=ids[2], new_root=new_id, signatures=rotation_sigs)

    # Old (pre-rotation) rootset still verifies the pre-rotation attestation
    # (the contract documented in federation.py: callers verifying historical
    # attestations should use the rootset that was active at issuance time).
    assert verify_federated(pre_att, rs) is True
    # Membership has changed.
    assert ids[2] not in rotated.roots
    assert new_id in rotated.roots
    _ = new_sk
