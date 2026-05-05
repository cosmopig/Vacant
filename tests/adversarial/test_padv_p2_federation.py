"""Padv P2 — adversarial tests for `vacant.identity.federation`.

Spec anchors:
- `architecture/components/P2_identity.md` §3.5 (federated attestation),
  §D5 (federation roadmap)
- `architecture/research/T4_attestation_bootstrap.md` (M-of-N evolution)
- `architecture/decisions/D005_padv_p2_findings.md` (rotation-replay
  closure, hostile new_root residual risk)
- `dispatch/Padv_review.md` §"Federation root impersonation"
"""

from __future__ import annotations

import pytest

from vacant.core.crypto import SigningKey, keygen
from vacant.core.types import VacantId
from vacant.identity.errors import FederationError
from vacant.identity.federation import (
    FederatedAttestation,
    RootSet,
    issue_root_signature,
    rotate_root,
    sign_rotation,
    verify_federated,
)


def _make_roots(n: int) -> tuple[list[VacantId], list[SigningKey]]:
    pairs = [keygen() for _ in range(n)]
    return (
        [VacantId.from_verify_key(vk) for _, vk in pairs],
        [sk for sk, _ in pairs],
    )


# --- Attack 1: cross-claim signature replay ----------------------------------
# Defense (P): the signing payload includes `claim`. A signature for
# (subject, claim_A) does not validate for (subject, claim_B).


def test_attack_signature_replay_across_claims_rejected() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject = VacantId.from_verify_key(keygen()[1])

    sigs_a = [
        issue_root_signature(root=ids[i], root_signing_key=sks[i], subject=subject, claim="claim-A")
        for i in (0, 1)
    ]
    # Attacker takes the (subject, claim-A) signatures and tries to attach
    # them to a (subject, claim-B) attestation.
    forged = FederatedAttestation(subject=subject, claim="claim-B", signatures=sigs_a)
    assert verify_federated(forged, rs) is False


# --- Attack 2: cross-subject signature replay --------------------------------
# Defense (P): the signing payload includes `subject.pubkey_bytes`.


def test_attack_signature_replay_across_subjects_rejected() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject_a = VacantId.from_verify_key(keygen()[1])
    subject_b = VacantId.from_verify_key(keygen()[1])

    sigs_a = [
        issue_root_signature(root=ids[i], root_signing_key=sks[i], subject=subject_a, claim="x")
        for i in (0, 1)
    ]
    forged = FederatedAttestation(subject=subject_b, claim="x", signatures=sigs_a)
    assert verify_federated(forged, rs) is False


# --- Attack 3: rotation signature replay against a revived rootset -----------
# Defense (P): rotation payload includes `rootset.state_hash()`. A quorum's
# signatures for a rotation under one rootset state cannot be replayed
# against a different rootset state, even if `(old, new)` would be a valid
# pair under both. (Padv-P2 finding D005 §1.)


def test_attack_rotation_signature_replay_against_revived_rootset() -> None:
    ids, sks = _make_roots(5)
    rs0 = RootSet(threshold=2, roots=tuple(ids))
    new_id = VacantId.from_verify_key(keygen()[1])

    # Quorum signs rotation (ids[2] -> new_id) under rs0.
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
    # The legitimate rotation succeeds under rs0.
    rs1 = rotate_root(rs0, old_root=ids[2], new_root=new_id, signatures=rotation_sigs)
    assert ids[2] not in rs1.roots
    assert new_id in rs1.roots

    # Attack: rs1 later rotates back to a state that re-includes ids[2]
    # and excludes new_id (e.g. via a recovery rotation).
    recovery_sigs = [
        sign_rotation(
            rootset=rs1,
            root=ids[0],
            root_signing_key=sks[0],
            old_root=new_id,
            new_root=ids[2],
        ),
        sign_rotation(
            rootset=rs1,
            root=ids[1],
            root_signing_key=sks[1],
            old_root=new_id,
            new_root=ids[2],
        ),
    ]
    rs2 = rotate_root(rs1, old_root=new_id, new_root=ids[2], signatures=recovery_sigs)
    assert ids[2] in rs2.roots
    assert new_id not in rs2.roots

    # Attacker now replays the ORIGINAL rotation_sigs against rs2.
    # rs2.state_hash() != rs0.state_hash() (membership differs in ids[2]
    # vs new_id positions), so the original signatures don't validate under
    # the new payload.
    with pytest.raises(FederationError):
        rotate_root(rs2, old_root=ids[2], new_root=new_id, signatures=rotation_sigs)


# --- Attack 4: rotation signature replay across distinct rootsets ------------
# Defense (P): two unrelated rootsets that both happen to contain ids[0]
# cannot share rotation signatures.


def test_attack_rotation_replay_across_unrelated_rootsets_rejected() -> None:
    ids, sks = _make_roots(5)
    other_ids, _ = _make_roots(4)  # 4 fresh + ids[0] reused
    other_rs = RootSet(threshold=2, roots=(ids[0], *other_ids))

    rs = RootSet(threshold=2, roots=tuple(ids))
    new_id = VacantId.from_verify_key(keygen()[1])

    # Quorum signs rotation (ids[1] -> new_id) under rs.
    sigs = [
        sign_rotation(
            rootset=rs,
            root=ids[0],
            root_signing_key=sks[0],
            old_root=ids[1],
            new_root=new_id,
        ),
    ]
    # Rotation under `other_rs` happens to also have ids[1] absent and
    # new_id absent — but ids[1] IS NOT in other_rs. Force the other case:
    # try to use the signature against `rs` where ids[1] IS present. The
    # state_hash differs because membership differs.
    # Build a near-twin rootset with one root substituted.
    twin_roots = (ids[0], ids[2], ids[3], ids[4], VacantId.from_verify_key(keygen()[1]))
    twin = RootSet(threshold=2, roots=twin_roots)
    # Reusing `sigs` against `twin` should fail signature verification
    # because twin.state_hash() != rs.state_hash().
    new_for_twin = VacantId.from_verify_key(keygen()[1])
    with pytest.raises(FederationError):
        rotate_root(twin, old_root=ids[0], new_root=new_for_twin, signatures=sigs)
    _ = other_rs


# --- Attack 5: outsider signature with claimed root membership ---------------
# Defense (P): per-root signature verify under the *claimed* root's pubkey.
# An outsider's signature submitted as a member's contribution gets zero
# credit because the claimed root's pubkey doesn't validate it.


def test_attack_outsider_signature_claiming_membership_rejected() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    subject = VacantId.from_verify_key(keygen()[1])

    outsider_sk, _ = keygen()
    # Build a real signature from outsider, but tag the root as ids[0].
    real = issue_root_signature(
        root=ids[0], root_signing_key=outsider_sk, subject=subject, claim="x"
    )
    # Plus one legitimate signature from ids[1].
    legit = issue_root_signature(root=ids[1], root_signing_key=sks[1], subject=subject, claim="x")
    att = FederatedAttestation(subject=subject, claim="x", signatures=[real, legit])
    # Only one valid signature — below threshold.
    assert verify_federated(att, rs) is False


# --- Attack 6: rotation with new_root equal to old_root ----------------------
# Defense (P): rotation requires `new_root NOT in rootset` — including the
# case `new_root == old_root` (which IS in the rootset).


def test_attack_rotation_new_equals_old_rejected() -> None:
    ids, sks = _make_roots(5)
    rs = RootSet(threshold=2, roots=tuple(ids))
    sigs = [
        sign_rotation(
            rootset=rs,
            root=ids[0],
            root_signing_key=sks[0],
            old_root=ids[2],
            new_root=ids[2],
        ),
        sign_rotation(
            rootset=rs,
            root=ids[1],
            root_signing_key=sks[1],
            old_root=ids[2],
            new_root=ids[2],
        ),
    ]
    with pytest.raises(FederationError):
        rotate_root(rs, old_root=ids[2], new_root=ids[2], signatures=sigs)


# --- Attack 7: state_hash distinguishes thresholds ---------------------------
# Defense (P): the state hash includes the threshold; two rootsets with
# the same roots but different thresholds have distinct state hashes.


def test_attack_state_hash_distinguishes_thresholds() -> None:
    ids, _ = _make_roots(5)
    rs2 = RootSet(threshold=2, roots=tuple(ids))
    rs3 = RootSet(threshold=3, roots=tuple(ids))
    assert rs2.state_hash() != rs3.state_hash()


# --- Attack 8: state_hash invariant under root order -------------------------
# Defense (P): the state hash sorts root pubkeys; two rootsets that differ
# only in declared order are equivalent state-wise.


def test_attack_state_hash_invariant_under_root_order() -> None:
    ids, _ = _make_roots(5)
    rs_a = RootSet(threshold=2, roots=tuple(ids))
    rs_b = RootSet(threshold=2, roots=tuple(reversed(ids)))
    assert rs_a.state_hash() == rs_b.state_hash()


# --- Attack 9: rotate-out-then-back-in replay --------------------------------
# Defense (P): `revision` counter monotonically increments per rotation, so
# two rootsets with identical membership but different rotation history have
# distinct state hashes. This blocks the "membership-cycle" replay where
# a rotation signature would otherwise be valid against any membership-
# equivalent state. (D005 §1 second iteration.)


def test_attack_rotate_out_then_back_in_replay_rejected() -> None:
    ids, sks = _make_roots(5)
    rs0 = RootSet(threshold=2, roots=tuple(ids))
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
    # Recovery: rotate new_id back out, ids[2] back in.
    recovery_sigs = [
        sign_rotation(
            rootset=rs1,
            root=ids[0],
            root_signing_key=sks[0],
            old_root=new_id,
            new_root=ids[2],
        ),
        sign_rotation(
            rootset=rs1,
            root=ids[1],
            root_signing_key=sks[1],
            old_root=new_id,
            new_root=ids[2],
        ),
    ]
    rs2 = rotate_root(rs1, old_root=new_id, new_root=ids[2], signatures=recovery_sigs)

    # rs2 has the same MEMBERSHIP as rs0, but revision differs (0 → 2).
    assert sorted(r.pubkey_bytes for r in rs2.roots) == sorted(r.pubkey_bytes for r in rs0.roots)
    assert rs2.revision != rs0.revision
    assert rs2.state_hash() != rs0.state_hash()

    # Replay original rotation_sigs against rs2 — must be rejected.
    with pytest.raises(FederationError):
        rotate_root(rs2, old_root=ids[2], new_root=new_id, signatures=rotation_sigs)


# --- Attack 10: revision counter cannot go backwards -------------------------
# Defense (P): `revision >= 0` is enforced; rotation always increments.


def test_attack_revision_cannot_be_negative() -> None:
    ids, _ = _make_roots(5)
    with pytest.raises(FederationError):
        RootSet(threshold=2, roots=tuple(ids), revision=-1)
