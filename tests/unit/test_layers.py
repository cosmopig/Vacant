"""L0-L3 layered identity promotion + type-level safety."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import assert_type

import pytest

from vacant.core.crypto import SigningKey, VerifyKey, keygen
from vacant.core.types import (
    BehaviorBundle,
    CapabilityCard,
    Logbook,
    SubstrateSpec,
    VacantId,
)
from vacant.identity import (
    L0Identity,
    L1Identity,
    L3Identity,
    LayerPromotionError,
    issue_attestation,
    promote_to_l1,
    promote_to_l2,
    promote_to_l3,
    vacant_id_did_key,
)
from vacant.identity.layers import b58encode


def _make_l0_l1(sk: SigningKey, vk: VerifyKey, logbook: Logbook) -> tuple[L0Identity, L1Identity]:
    vid = VacantId.from_verify_key(vk)
    logbook.append("genesis", {}, sk)
    l0 = L0Identity(vacant_id=vid)
    return l0, promote_to_l1(l0, logbook)


def _make_signed_card(sk: SigningKey, vid: VacantId) -> CapabilityCard:
    return CapabilityCard(
        vacant_id=vid,
        capability_text="translate",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)


# --- did:key encoding --------------------------------------------------------


def test_did_key_starts_with_did_key_z(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    _sk, vk = test_keypair
    vid = VacantId.from_verify_key(vk)
    did = vacant_id_did_key(vid)
    assert did.startswith("did:key:z")


def test_did_key_round_trip_distinct_keys() -> None:
    _sk1, vk1 = keygen()
    _sk2, vk2 = keygen()
    a = vacant_id_did_key(VacantId.from_verify_key(vk1))
    b = vacant_id_did_key(VacantId.from_verify_key(vk2))
    assert a != b


def test_b58encode_known_vector() -> None:
    # "Hello World" -> base58 (Bitcoin alphabet) -> "JxF12TrwUP45BMd"
    assert b58encode(b"Hello World") == "JxF12TrwUP45BMd"


def test_b58encode_preserves_leading_zero() -> None:
    assert b58encode(b"\x00\x00\x01") == "112"


# --- L0 → L1 -----------------------------------------------------------------


def test_promote_to_l1_with_valid_chain(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    _l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    assert l1.vacant_id == VacantId.from_verify_key(vk)


def test_promote_to_l1_rejects_wrong_key(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    fresh_logbook.append("genesis", {}, sk)
    _wrong_sk, wrong_vk = keygen()
    l0 = L0Identity(vacant_id=VacantId.from_verify_key(wrong_vk))
    with pytest.raises(LayerPromotionError):
        promote_to_l1(l0, fresh_logbook)


# --- L1 → L2 -----------------------------------------------------------------


def test_promote_to_l2_with_signed_card(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    _l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    card = _make_signed_card(sk, l1.vacant_id)
    l2 = promote_to_l2(l1, card)
    assert l2.capability_card is card


def test_promote_to_l2_rejects_card_for_other_id(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    _l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    other_sk, other_vk = keygen()
    other_card = _make_signed_card(other_sk, VacantId.from_verify_key(other_vk))
    with pytest.raises(LayerPromotionError):
        promote_to_l2(l1, other_card)


def test_promote_to_l2_rejects_unsigned_card(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    _l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    unsigned = CapabilityCard(
        vacant_id=l1.vacant_id,
        capability_text="x",
        substrate_spec=SubstrateSpec(),
    )
    with pytest.raises(LayerPromotionError):
        promote_to_l2(l1, unsigned)


# --- L2 → L3 -----------------------------------------------------------------


def _make_attesters(n: int):
    return [keygen() for _ in range(n)]


def test_promote_to_l3_with_three_attesters(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    _l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    l2 = promote_to_l2(l1, _make_signed_card(sk, l1.vacant_id))
    attesters = _make_attesters(3)
    atts = [
        issue_attestation(
            attester=VacantId.from_verify_key(av),
            attestee=l2.vacant_id,
            claim="not-sock-puppet",
            attester_signing_key=ask,
        )
        for ask, av in attesters
    ]
    l3 = promote_to_l3(l2, atts)
    assert len(l3.attestations) == 3


def test_promote_to_l3_requires_distinct_attesters(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    _l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    l2 = promote_to_l2(l1, _make_signed_card(sk, l1.vacant_id))
    ask, av = keygen()
    one_attester = VacantId.from_verify_key(av)
    atts = [
        issue_attestation(
            attester=one_attester,
            attestee=l2.vacant_id,
            claim=f"voucher-{i}",
            attester_signing_key=ask,
        )
        for i in range(3)
    ]
    with pytest.raises(LayerPromotionError):
        promote_to_l3(l2, atts)


def test_promote_to_l3_rejects_attestations_for_other_subject(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    _l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    l2 = promote_to_l2(l1, _make_signed_card(sk, l1.vacant_id))
    other_sk, other_vk = keygen()
    other_id = VacantId.from_verify_key(other_vk)
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
    _ = other_sk


def test_promote_to_l3_rejects_expired_attestations(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    _l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    l2 = promote_to_l2(l1, _make_signed_card(sk, l1.vacant_id))
    long_ago = datetime.now(UTC) - timedelta(days=365)
    almost_long_ago = long_ago + timedelta(seconds=1)
    expired_atts = []
    for _ in range(3):
        ask, avk = keygen()
        expired_atts.append(
            issue_attestation(
                attester=VacantId.from_verify_key(avk),
                attestee=l2.vacant_id,
                claim="x",
                attester_signing_key=ask,
                issued_at=long_ago,
                expires_at=almost_long_ago,
            )
        )
    with pytest.raises(LayerPromotionError):
        promote_to_l3(l2, expired_atts)


def test_promote_to_l3_rejects_non_attestation_types(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    _l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    l2 = promote_to_l2(l1, _make_signed_card(sk, l1.vacant_id))
    with pytest.raises(LayerPromotionError):
        promote_to_l3(l2, ["not", "attestations"])
    with pytest.raises(LayerPromotionError):
        promote_to_l3(l2, "definitely not a list")


# --- type-level safety -------------------------------------------------------


def takes_l3(_: L3Identity) -> str:
    return "ok"


def test_l3_signature_at_runtime_with_assert_type(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    """Static-flavoured runtime assertion using `typing.assert_type`.

    `assert_type` is a no-op at runtime but is checked by mypy. The
    inverse case — passing `L1Identity` to `takes_l3` — is documented in
    the PR description with a `mypy reveal_type` snippet because mypy
    rejects it as an `[arg-type]` error.
    """
    sk, vk = test_keypair
    _l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    assert_type(l1, L1Identity)

    bundle = BehaviorBundle(system_prompt="x")
    _ = bundle  # silence unused
    l2 = promote_to_l2(l1, _make_signed_card(sk, l1.vacant_id))
    atts = []
    for _ in range(3):
        ask, avk = keygen()
        atts.append(
            issue_attestation(
                attester=VacantId.from_verify_key(avk),
                attestee=l2.vacant_id,
                claim="x",
                attester_signing_key=ask,
            )
        )
    l3 = promote_to_l3(l2, atts)
    assert_type(l3, L3Identity)
    assert takes_l3(l3) == "ok"


def test_layer_dids_match_vacant_id(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    l0, l1 = _make_l0_l1(sk, vk, fresh_logbook)
    l2 = promote_to_l2(l1, _make_signed_card(sk, l1.vacant_id))
    assert l0.did() == l1.did() == l2.did() == vacant_id_did_key(l1.vacant_id)
