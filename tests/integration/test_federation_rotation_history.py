"""A8 / D016 — `RootSetHistory` regression tests.

The contract under test:

1. Pre-rotation attestations remain verifiable after rotation, by
   looking up the issuance revision in the history.
2. A new attestation tagged with a stale revision (e.g. an attacker
   replaying a leaked old-revision signature into a fresh envelope)
   is detectable: signatures collected for the wrong revision will
   not validate inside the envelope's claimed revision because the
   `signing_payload` digest mixes the revision in.
3. A signature over the *current* revision cannot be moved into an
   envelope claiming the *prior* revision.
4. The history rejects gaps in the rotation chain.
5. `build_federated_attestation` ergonomically tags new attestations
   with the current revision.
"""

from __future__ import annotations

import pytest

from vacant.core.crypto import SigningKey, keygen
from vacant.core.types import VacantId
from vacant.identity.errors import FederationError
from vacant.identity.federation import (
    FederatedAttestation,
    RootSet,
    RootSetHistory,
    build_federated_attestation,
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


def _bootstrap_history() -> tuple[RootSetHistory, list[VacantId], list[SigningKey]]:
    ids, sks = _make_roots(5)
    rs0 = RootSet(threshold=2, roots=tuple(ids))
    return RootSetHistory.from_initial(rs0), ids, sks


def _rotate_once(
    history: RootSetHistory,
    ids: list[VacantId],
    sks: list[SigningKey],
    *,
    old_root_idx: int,
    new_root: VacantId,
) -> RootSetHistory:
    current = history.current
    sigs = [
        sign_rotation(
            rootset=current,
            root=ids[i],
            root_signing_key=sks[i],
            old_root=ids[old_root_idx],
            new_root=new_root,
        )
        for i in (0, 1)
    ]
    return history.apply_rotation(old_root=ids[old_root_idx], new_root=new_root, signatures=sigs)


# --- 1. Pre-rotation attestations still verify after rotation -----------------


def test_pre_rotation_attestation_verifies_via_history() -> None:
    history, ids, sks = _bootstrap_history()
    subject = VacantId.from_verify_key(keygen()[1])

    # Issue under revision 0.
    sigs = [
        issue_root_signature(
            root=ids[i],
            root_signing_key=sks[i],
            subject=subject,
            claim="pre-rotate",
            issued_under_revision=0,
        )
        for i in (0, 1)
    ]
    pre_att = build_federated_attestation(
        history=history, subject=subject, claim="pre-rotate", signatures=sigs
    )
    assert pre_att.issued_under_revision == 0

    # Rotate. ids[2] -> new_id.
    new_id = VacantId.from_verify_key(keygen()[1])
    history = _rotate_once(history, ids, sks, old_root_idx=2, new_root=new_id)
    assert history.current_revision == 1
    assert ids[2] not in history.current.roots
    assert new_id in history.current.roots

    # Pre-rotation attestation must still verify against the history,
    # even though the *current* rootset has changed.
    assert verify_federated(pre_att, history) is True

    # Sanity: also verifies against the explicit revision-0 rootset.
    assert verify_federated(pre_att, history.at(0)) is True


def test_pre_rotation_attestation_verifies_after_two_rotations() -> None:
    history, ids, sks = _bootstrap_history()
    subject = VacantId.from_verify_key(keygen()[1])

    sigs = [
        issue_root_signature(
            root=ids[i],
            root_signing_key=sks[i],
            subject=subject,
            claim="ancient",
            issued_under_revision=0,
        )
        for i in (0, 1)
    ]
    att = build_federated_attestation(
        history=history, subject=subject, claim="ancient", signatures=sigs
    )

    # Two successive rotations.
    new_a = VacantId.from_verify_key(keygen()[1])
    history = _rotate_once(history, ids, sks, old_root_idx=2, new_root=new_a)
    new_b = VacantId.from_verify_key(keygen()[1])
    history = _rotate_once(history, ids, sks, old_root_idx=3, new_root=new_b)

    assert history.current_revision == 2
    assert verify_federated(att, history) is True


# --- 2. Stale-revision-issued attestations are detectable ---------------------


def test_attestation_tagged_with_stale_revision_after_rotation_fails() -> None:
    """A revision-0 envelope cannot be silently re-tagged as revision 1.

    Without payload binding, an attacker holding a signature collected
    for revision 0 could re-emit it inside an envelope claiming the
    current revision is 1, hoping verifiers compare against the new
    rootset. The signing payload mixes the revision in, so the
    signature will not validate.
    """
    history, ids, sks = _bootstrap_history()
    subject = VacantId.from_verify_key(keygen()[1])

    # Collect signatures for revision 0.
    rev0_sigs = [
        issue_root_signature(
            root=ids[i],
            root_signing_key=sks[i],
            subject=subject,
            claim="x",
            issued_under_revision=0,
        )
        for i in (0, 1)
    ]

    # Rotate.
    new_id = VacantId.from_verify_key(keygen()[1])
    history = _rotate_once(history, ids, sks, old_root_idx=2, new_root=new_id)

    # Attacker re-tags the revision-0 sigs into a revision-1 envelope.
    forged = FederatedAttestation(
        subject=subject,
        claim="x",
        signatures=rev0_sigs,
        issued_under_revision=1,
    )
    assert verify_federated(forged, history) is False
    assert verify_federated(forged, history.current) is False


def test_signature_for_current_revision_cannot_be_moved_to_prior_envelope() -> None:
    history, ids, sks = _bootstrap_history()
    subject = VacantId.from_verify_key(keygen()[1])

    # Rotate first; now current is revision 1.
    new_id = VacantId.from_verify_key(keygen()[1])
    history = _rotate_once(history, ids, sks, old_root_idx=2, new_root=new_id)

    # Collect signatures under revision 1.
    rev1_sigs = [
        issue_root_signature(
            root=ids[i],
            root_signing_key=sks[i],
            subject=subject,
            claim="x",
            issued_under_revision=1,
        )
        for i in (0, 1)
    ]

    # Attacker tries to claim these were issued under the prior revision.
    forged_to_rev0 = FederatedAttestation(
        subject=subject,
        claim="x",
        signatures=rev1_sigs,
        issued_under_revision=0,
    )
    assert verify_federated(forged_to_rev0, history) is False


def test_attestation_with_revision_outside_history_rejected() -> None:
    history, ids, sks = _bootstrap_history()
    subject = VacantId.from_verify_key(keygen()[1])

    # An attestation claiming revision 99 — history only has revision 0.
    sigs = [
        issue_root_signature(
            root=ids[i],
            root_signing_key=sks[i],
            subject=subject,
            claim="x",
            issued_under_revision=99,
        )
        for i in (0, 1)
    ]
    att = FederatedAttestation(
        subject=subject, claim="x", signatures=sigs, issued_under_revision=99
    )
    assert verify_federated(att, history) is False


# --- 3. RootSetHistory invariants --------------------------------------------


def test_history_rejects_gap_in_rotation_chain() -> None:
    ids, _ = _make_roots(5)
    rs0 = RootSet(threshold=2, roots=tuple(ids), revision=0)
    # Manually-constructed bogus revision-2 (skips revision 1).
    ids2 = list(ids)
    ids2[2] = VacantId.from_verify_key(keygen()[1])
    rs2 = RootSet(threshold=2, roots=tuple(ids2), revision=2)
    with pytest.raises(FederationError, match="revision\\["):
        RootSetHistory(revisions=(rs0, rs2))


def test_history_from_initial_requires_revision_zero() -> None:
    ids, _ = _make_roots(5)
    rs1 = RootSet(threshold=2, roots=tuple(ids), revision=1)
    with pytest.raises(FederationError, match="revision must be 0"):
        RootSetHistory.from_initial(rs1)


def test_history_extend_requires_dense_revision() -> None:
    history, ids, _ = _bootstrap_history()
    ids2 = list(ids)
    ids2[2] = VacantId.from_verify_key(keygen()[1])
    skipped = RootSet(threshold=2, roots=tuple(ids2), revision=5)
    with pytest.raises(FederationError, match="must be 1"):
        history.extend(skipped)


def test_history_at_returns_correct_revision() -> None:
    history, ids, sks = _bootstrap_history()
    new_a = VacantId.from_verify_key(keygen()[1])
    history = _rotate_once(history, ids, sks, old_root_idx=2, new_root=new_a)

    assert history.at(0).revision == 0
    assert history.at(1).revision == 1
    assert ids[2] in history.at(0).roots
    assert ids[2] not in history.at(1).roots


def test_history_at_unknown_revision_raises() -> None:
    history, _, _ = _bootstrap_history()
    with pytest.raises(FederationError):
        history.at(7)


# --- 4. build_federated_attestation tags with current revision ---------------


def test_build_federated_attestation_tags_with_current_revision() -> None:
    history, ids, sks = _bootstrap_history()
    new_id = VacantId.from_verify_key(keygen()[1])
    history = _rotate_once(history, ids, sks, old_root_idx=2, new_root=new_id)
    assert history.current_revision == 1

    subject = VacantId.from_verify_key(keygen()[1])
    sigs = [
        issue_root_signature(
            root=ids[i],
            root_signing_key=sks[i],
            subject=subject,
            claim="post-rotate",
            issued_under_revision=1,
        )
        for i in (0, 1)
    ]
    att = build_federated_attestation(
        history=history, subject=subject, claim="post-rotate", signatures=sigs
    )
    assert att.issued_under_revision == 1
    assert verify_federated(att, history) is True


# --- 5. Backward-compat path: single RootSet still works for revision 0 -----


def test_verify_with_single_rootset_demands_matching_revision() -> None:
    ids, sks = _make_roots(5)
    rs0 = RootSet(threshold=2, roots=tuple(ids), revision=0)

    # Build an attestation that legitimately claims revision 1.
    new_id = VacantId.from_verify_key(keygen()[1])
    rotation_sigs = [
        sign_rotation(
            rootset=rs0,
            root=ids[i],
            root_signing_key=sks[i],
            old_root=ids[2],
            new_root=new_id,
        )
        for i in (0, 1)
    ]
    rs1 = rotate_root(rs0, old_root=ids[2], new_root=new_id, signatures=rotation_sigs)
    assert rs1.revision == 1

    subject = VacantId.from_verify_key(keygen()[1])
    rev1_sigs = [
        issue_root_signature(
            root=ids[i],
            root_signing_key=sks[i],
            subject=subject,
            claim="rev1",
            issued_under_revision=1,
        )
        for i in (0, 1)
    ]
    att = FederatedAttestation(
        subject=subject, claim="rev1", signatures=rev1_sigs, issued_under_revision=1
    )

    # Verifying against rs0 (revision 0) must fail — revision mismatch.
    assert verify_federated(att, rs0) is False
    # Verifying against rs1 (revision 1) succeeds.
    assert verify_federated(att, rs1) is True
