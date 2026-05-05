"""Padv P2 — adversarial tests for `vacant.identity.layers` (L0-L3).

Spec anchors:
- `architecture/components/P2_identity.md` §2 (D2 four-layer defense),
  §3.3 (attestation tiers)
- `dispatch/Padv_review.md` §"L3 promotion via colluding L1s"
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import (
    CapabilityCard,
    Logbook,
    SubstrateSpec,
    VacantId,
)
from vacant.identity import (
    L0Identity,
    LayerPromotionError,
    issue_attestation,
    promote_to_l1,
    promote_to_l2,
    promote_to_l3,
)


def _make_l1_l2(sk, vk):  # type: ignore[no-untyped-def]
    vid = VacantId.from_verify_key(vk)
    lb = Logbook()
    lb.append("genesis", {}, sk)
    l1 = promote_to_l1(L0Identity(vacant_id=vid), lb)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    return promote_to_l2(l1, card)


# --- Attack 1: L1 logbook from a different vacant ----------------------------
# Defense (P): `promote_to_l1` verifies the chain against `l0.vacant_id`.
# A logbook signed by anyone *else's* key fails verification.


def test_attack_l1_promotion_with_foreign_logbook_rejected() -> None:
    _victim_sk, victim_vk = keygen()
    attacker_sk, _attacker_vk = keygen()

    l0 = L0Identity(vacant_id=VacantId.from_verify_key(victim_vk))
    foreign_lb = Logbook()
    foreign_lb.append("genesis", {}, attacker_sk)

    with pytest.raises(LayerPromotionError):
        promote_to_l1(l0, foreign_lb)


# --- Attack 2: L2 cap-card with id-match-but-attacker-signature --------------
# Defense (P): the cap card's signature is verified under
# `card.vacant_id.verify_key()`. Setting `card.vacant_id = victim_id` while
# signing with the attacker's key fails because the *bytes* of the pubkey
# embedded in `vacant_id` won't validate the attacker's signature.


def test_attack_l2_cap_card_with_attacker_signature_rejected() -> None:
    victim_sk, victim_vk = keygen()
    l2 = _make_l1_l2(victim_sk, victim_vk)

    attacker_sk, _ = keygen()
    forged_card = CapabilityCard(
        vacant_id=l2.vacant_id,
        capability_text="evil",
        substrate_spec=SubstrateSpec(),
    ).signed(attacker_sk)

    # The card's `verify()` returns False because `vacant_id`'s pubkey
    # doesn't match the signing key.
    assert forged_card.verify() is False
    with pytest.raises(LayerPromotionError):
        promote_to_l2(l2, forged_card)  # already-l2 reuse irrelevant — promotion ID-checks


# --- Attack 3: L3 promotion with attestations to a different attestee --------
# Defense (P): each attestation's `attestee` field is checked against
# `l2.vacant_id` before signature verification.


def test_attack_l3_attestations_for_other_attestee_rejected() -> None:
    sk, vk = keygen()
    l2 = _make_l1_l2(sk, vk)

    # Build 3 valid attestations but for a *different* attestee.
    other_id = VacantId.from_verify_key(keygen()[1])
    bad = []
    for _ in range(3):
        ask, avk = keygen()
        bad.append(
            issue_attestation(
                attester=VacantId.from_verify_key(avk),
                attestee=other_id,
                claim="x",
                attester_signing_key=ask,
            )
        )
    with pytest.raises(LayerPromotionError):
        promote_to_l3(l2, bad)


# --- Attack 4: L3 sybil — same controller signs as N distinct keypairs ------
# Documented residual risk (THEORY_V5 §0.3 "Controller-as-root").
# Defense level (D, NOT P): at the *identity* layer, distinct keypairs look
# distinct (this is by design — the network can't observe controllers
# directly). The downweighting happens at P3 via same-controller
# signal (T5_same_controller). This test documents the layer's contract:
# `promote_to_l3` ACCEPTS N distinct keys even if they're controlled by
# one operator. Don't regress that property.


def test_attack_l3_distinct_keys_pass_at_identity_layer_residual_risk() -> None:
    """One controller can mint N keypairs and produce N "distinct" attesters.
    This passes promote_to_l3. The downweighting happens at the reputation
    layer (P3) via T5 same-controller detection. Regression test ensures
    the identity layer continues to defer to P3 on this.
    """
    sk, vk = keygen()
    l2 = _make_l1_l2(sk, vk)

    # Single attacker mints 3 keypairs and self-signs.
    attestations = []
    for _ in range(3):
        ask, avk = keygen()
        attestations.append(
            issue_attestation(
                attester=VacantId.from_verify_key(avk),
                attestee=l2.vacant_id,
                claim="not-sock-puppet",
                attester_signing_key=ask,
            )
        )
    l3 = promote_to_l3(l2, attestations)
    assert len(l3.attestations) == 3  # accepted at identity layer; P3 downweights


# --- Attack 5: L3 mixing — 2 valid + 1 attestee-swap rejected ----------------
# Defense (P): the validator iterates all entries; ANY mismatched attestee
# raises before counting distinct attesters.


def test_attack_l3_mixed_valid_and_swapped_rejected() -> None:
    sk, vk = keygen()
    l2 = _make_l1_l2(sk, vk)

    good = []
    for _ in range(2):
        ask, avk = keygen()
        good.append(
            issue_attestation(
                attester=VacantId.from_verify_key(avk),
                attestee=l2.vacant_id,
                claim="x",
                attester_signing_key=ask,
            )
        )
    other_id = VacantId.from_verify_key(keygen()[1])
    ask, avk = keygen()
    swapped = issue_attestation(
        attester=VacantId.from_verify_key(avk),
        attestee=other_id,
        claim="x",
        attester_signing_key=ask,
    )
    with pytest.raises(LayerPromotionError):
        promote_to_l3(l2, [*good, swapped])


# --- Attack 6: L3 promotion with stale (just-expired) attestations -----------
# Defense (P): `verify_attestation` checks `now <= expires_at`. Promotion
# rejects if any attestation expired even by 1 second.


def test_attack_l3_just_expired_attestation_rejected() -> None:
    sk, vk = keygen()
    l2 = _make_l1_l2(sk, vk)

    nearly_now = datetime.now(UTC) - timedelta(hours=1)
    # 3 attestations that expired 30 minutes ago.
    expired_atts = []
    for _ in range(3):
        ask, avk = keygen()
        expired_atts.append(
            issue_attestation(
                attester=VacantId.from_verify_key(avk),
                attestee=l2.vacant_id,
                claim="x",
                attester_signing_key=ask,
                issued_at=nearly_now - timedelta(days=30),
                expires_at=nearly_now - timedelta(minutes=30),
            )
        )
    with pytest.raises(LayerPromotionError):
        promote_to_l3(l2, expired_atts)


# --- Attack 7: L1 logbook with tampered middle entry --------------------------
# Defense (P): hash chain detects in-place mutation regardless of position.


def test_attack_l1_logbook_with_tampered_middle_entry_rejected(test_keypair, fresh_logbook) -> None:  # type: ignore[no-untyped-def]
    sk, vk = test_keypair
    fresh_logbook.append("genesis", {}, sk)
    fresh_logbook.append("e1", {"v": 1}, sk)
    fresh_logbook.append("e2", {"v": 2}, sk)
    # Tamper the middle entry's payload.
    fresh_logbook.entries[1] = fresh_logbook.entries[1].model_copy(update={"payload": {"v": 999}})
    l0 = L0Identity(vacant_id=VacantId.from_verify_key(vk))
    with pytest.raises(LayerPromotionError):
        promote_to_l1(l0, fresh_logbook)
