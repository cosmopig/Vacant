"""Federation rootset + M-of-N attestation tests."""

from __future__ import annotations

import pytest

from vacant.core.crypto import SigningKey, keygen
from vacant.core.types import VacantId
from vacant.identity.errors import FederationError
from vacant.identity.federation import (
    FederatedAttestation,
    RootSet,
    default_mvp_rootset,
    issue_root_signature,
    rotate_root,
    sign_rotation,
    verify_federated,
)


def _make_roots(n: int) -> tuple[list[VacantId], list[SigningKey]]:
    pairs = [keygen() for _ in range(n)]
    return (
        [VacantId.from_verify_key(vk) for _sk, vk in pairs],
        [sk for sk, _vk in pairs],
    )


def test_default_mvp_rootset_is_2_of_5() -> None:
    ids, _ = _make_roots(5)
    rs = default_mvp_rootset(vacant_ids=ids)
    assert rs.threshold == 2
    assert rs.n == 5


def test_default_mvp_rootset_requires_explicit_ids() -> None:
    with pytest.raises(FederationError):
        default_mvp_rootset()


def test_default_mvp_rootset_rejects_short_input() -> None:
    ids, _ = _make_roots(3)
    with pytest.raises(FederationError):
        default_mvp_rootset(vacant_ids=ids)


def test_rootset_rejects_threshold_below_one() -> None:
    ids, _ = _make_roots(5)
    with pytest.raises(FederationError):
        RootSet(threshold=0, roots=tuple(ids))


def test_rootset_rejects_threshold_above_count() -> None:
    ids, _ = _make_roots(3)
    with pytest.raises(FederationError):
        RootSet(threshold=4, roots=tuple(ids))


def test_rootset_rejects_duplicates() -> None:
    ids, _ = _make_roots(2)
    with pytest.raises(FederationError):
        RootSet(threshold=1, roots=(ids[0], ids[0]))


def test_verify_federated_passes_at_threshold() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject_id = VacantId.from_verify_key(keygen()[1])
    sigs = [
        issue_root_signature(root=ids[i], root_signing_key=sks[i], subject=subject_id, claim="ok")
        for i in (0, 1)
    ]
    att = FederatedAttestation(subject=subject_id, claim="ok", signatures=sigs)
    assert verify_federated(att, rs) is True


def test_verify_federated_fails_below_threshold() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject = VacantId.from_verify_key(keygen()[1])
    one_sig = [
        issue_root_signature(root=ids[0], root_signing_key=sks[0], subject=subject, claim="ok")
    ]
    att = FederatedAttestation(subject=subject, claim="ok", signatures=one_sig)
    assert verify_federated(att, rs) is False


def test_verify_federated_ignores_non_member_signatures() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject = VacantId.from_verify_key(keygen()[1])
    outsider_sk, outsider_vk = keygen()
    outsider_id = VacantId.from_verify_key(outsider_vk)
    sigs = [
        issue_root_signature(
            root=outsider_id, root_signing_key=outsider_sk, subject=subject, claim="ok"
        ),
        issue_root_signature(root=ids[0], root_signing_key=sks[0], subject=subject, claim="ok"),
    ]
    att = FederatedAttestation(subject=subject, claim="ok", signatures=sigs)
    # Only one in-set signature — below threshold.
    assert verify_federated(att, rs) is False


def test_verify_federated_dedupes_repeated_signer() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject = VacantId.from_verify_key(keygen()[1])
    one = issue_root_signature(root=ids[0], root_signing_key=sks[0], subject=subject, claim="ok")
    att = FederatedAttestation(subject=subject, claim="ok", signatures=[one, one])
    assert verify_federated(att, rs) is False


def test_rotate_root_swaps_with_quorum() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    new_sk, new_vk = keygen()
    new_id = VacantId.from_verify_key(new_vk)
    sigs = [
        sign_rotation(
            rootset=rs, root=ids[0], root_signing_key=sks[0], old_root=ids[2], new_root=new_id
        ),
        sign_rotation(
            rootset=rs, root=ids[1], root_signing_key=sks[1], old_root=ids[2], new_root=new_id
        ),
    ]
    rotated = rotate_root(rs, old_root=ids[2], new_root=new_id, signatures=sigs)
    assert new_id in rotated.roots
    assert ids[2] not in rotated.roots
    _ = new_sk


def test_rotate_root_rejects_below_quorum() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    new_id = VacantId.from_verify_key(keygen()[1])
    sigs = [
        sign_rotation(
            rootset=rs, root=ids[0], root_signing_key=sks[0], old_root=ids[2], new_root=new_id
        ),
    ]
    with pytest.raises(FederationError):
        rotate_root(rs, old_root=ids[2], new_root=new_id, signatures=sigs)


def test_rotate_root_rejects_unknown_old_root() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    new_id = VacantId.from_verify_key(keygen()[1])
    outsider = VacantId.from_verify_key(keygen()[1])
    with pytest.raises(FederationError):
        rotate_root(rs, old_root=outsider, new_root=new_id, signatures=[])
    _ = sks


def test_rotate_root_rejects_duplicate_new_root() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    sigs = [
        sign_rotation(
            rootset=rs, root=ids[0], root_signing_key=sks[0], old_root=ids[2], new_root=ids[3]
        ),
        sign_rotation(
            rootset=rs, root=ids[1], root_signing_key=sks[1], old_root=ids[2], new_root=ids[3]
        ),
    ]
    with pytest.raises(FederationError):
        rotate_root(rs, old_root=ids[2], new_root=ids[3], signatures=sigs)
