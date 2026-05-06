"""Unit tests for `vacant.core.types`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from vacant.core.crypto import SigningKey, VerifyKey, keygen
from vacant.core.errors import HashChainError, TypeIntegrityError
from vacant.core.types import (
    EMPTY_PREV_HASH,
    BehaviorBundle,
    CapabilityCard,
    Logbook,
    LogEntry,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)

# --- VacantId ----------------------------------------------------------------


def test_vacantid_equality_and_hash(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    _sk, vk = test_keypair
    vid_a = VacantId.from_verify_key(vk)
    vid_b = VacantId(pubkey_bytes=bytes(vk))
    assert vid_a == vid_b
    assert hash(vid_a) == hash(vid_b)
    assert {vid_a, vid_b} == {vid_a}


def test_vacantid_hex_and_short(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    _sk, vk = test_keypair
    vid = VacantId.from_verify_key(vk)
    assert vid.hex() == bytes(vk).hex()
    assert len(vid.short()) == 12
    assert str(vid).startswith("vacant:")


def test_vacantid_rejects_wrong_pubkey_length() -> None:
    with pytest.raises(ValidationError):
        VacantId(pubkey_bytes=b"too short")


def test_vacantid_verify_key_roundtrip(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    _sk, vk = test_keypair
    vid = VacantId.from_verify_key(vk)
    assert bytes(vid.verify_key()) == bytes(vk)


# --- LogEntry / Logbook ------------------------------------------------------


def test_logbook_starts_empty(fresh_logbook: Logbook) -> None:
    assert fresh_logbook.entries == []
    assert fresh_logbook.latest_hash() == EMPTY_PREV_HASH


def test_logbook_append_then_verify_chain(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    fresh_logbook.append("genesis", {"name": "alice"}, sk)
    fresh_logbook.append("call", {"capability": "translate"}, sk)
    fresh_logbook.append("review", {"score": 0.9}, sk)
    assert len(fresh_logbook.entries) == 3
    assert fresh_logbook.verify_chain(vk) is True


def test_logbook_chain_links_via_prev_hash(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    e1 = fresh_logbook.append("a", {}, sk)
    e2 = fresh_logbook.append("b", {}, sk)
    assert e1.prev_hash == EMPTY_PREV_HASH
    assert e2.prev_hash == e1.compute_hash()


def test_logbook_tampered_payload_breaks_chain(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    fresh_logbook.append("a", {"v": 1}, sk)
    fresh_logbook.append("b", {"v": 2}, sk)
    bad = fresh_logbook.entries[0].model_copy(update={"payload": {"v": 999}})
    fresh_logbook.entries[0] = bad
    assert fresh_logbook.verify_chain(vk) is False
    with pytest.raises(HashChainError):
        fresh_logbook.verify_chain_or_raise(vk)


def test_logbook_tampered_signature_breaks_chain(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    fresh_logbook.append("a", {}, sk)
    bad = fresh_logbook.entries[0].model_copy(update={"signature": b"\x00" * 64})
    fresh_logbook.entries[0] = bad
    assert fresh_logbook.verify_chain(vk) is False


def test_logbook_reorder_breaks_chain(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    fresh_logbook.append("a", {}, sk)
    fresh_logbook.append("b", {}, sk)
    fresh_logbook.append("c", {}, sk)
    fresh_logbook.entries[0], fresh_logbook.entries[2] = (
        fresh_logbook.entries[2],
        fresh_logbook.entries[0],
    )
    assert fresh_logbook.verify_chain(vk) is False


def test_logbook_wrong_pubkey_fails(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    fresh_logbook.append("a", {}, sk)
    _sk2, vk2 = keygen()
    assert fresh_logbook.verify_chain(vk2) is False


def test_logentry_kind_must_be_nonempty() -> None:
    with pytest.raises(ValidationError):
        LogEntry(
            kind="  ",
            ts=datetime.now(UTC),
            payload={},
            prev_hash=EMPTY_PREV_HASH,
            signature=b"\x00",
        )


def test_logentry_prev_hash_must_be_correct_length() -> None:
    with pytest.raises(ValidationError):
        LogEntry(
            kind="a",
            ts=datetime.now(UTC),
            payload={},
            prev_hash=b"\x00" * 4,
            signature=b"\x00",
        )


def test_logbook_naive_timestamp_is_normalised_to_utc(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    naive_ts = datetime(2026, 5, 5, 12, 0, 0)
    fresh_logbook.append("a", {}, sk, ts=naive_ts)
    assert fresh_logbook.entries[0].ts.tzinfo is not None
    assert fresh_logbook.verify_chain(vk) is True


def test_logbook_explicit_timestamps_keep_chain(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    fresh_logbook.append("a", {}, sk, ts=t0)
    fresh_logbook.append("b", {}, sk, ts=t0 + timedelta(seconds=1))
    assert fresh_logbook.verify_chain(vk) is True


def test_logbook_payload_with_unserialisable_value_fails(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    with pytest.raises(TypeIntegrityError):
        fresh_logbook.append("a", {"bad": object()}, sk)


# --- SubstrateSpec -----------------------------------------------------------


def test_substrate_spec_canonical_bytes_is_deterministic() -> None:
    s1 = SubstrateSpec(allowed_substrates=["a", "b"], policy={"x": 1, "y": 2})
    s2 = SubstrateSpec(allowed_substrates=["a", "b"], policy={"y": 2, "x": 1})
    assert s1.canonical_bytes() == s2.canonical_bytes()


def test_substrate_spec_rejects_blank_entries() -> None:
    with pytest.raises(ValidationError):
        SubstrateSpec(allowed_substrates=[""])


# --- BehaviorBundle ----------------------------------------------------------


def test_behavior_bundle_auto_hashes() -> None:
    bb = BehaviorBundle(system_prompt="be helpful", tool_whitelist=["search", "translate"])
    assert bb.bundle_hash != b""
    assert len(bb.bundle_hash) == 32


def test_behavior_bundle_hash_independent_of_tool_order() -> None:
    a = BehaviorBundle(system_prompt="x", tool_whitelist=["a", "b"])
    b = BehaviorBundle(system_prompt="x", tool_whitelist=["b", "a"])
    assert a.bundle_hash == b.bundle_hash


def test_behavior_bundle_rejects_wrong_supplied_hash() -> None:
    with pytest.raises(TypeIntegrityError):
        BehaviorBundle(system_prompt="x", bundle_hash=b"\x00" * 32)


def test_behavior_bundle_accepts_correct_supplied_hash() -> None:
    bb1 = BehaviorBundle(system_prompt="x")
    bb2 = BehaviorBundle(system_prompt="x", bundle_hash=bb1.bundle_hash)
    assert bb1 == bb2


# --- CapabilityCard ----------------------------------------------------------


def test_capability_card_signed_then_verifies(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    sk, vk = test_keypair
    card = CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="translate ZH<->EN",
        substrate_spec=SubstrateSpec(allowed_substrates=["claude-sonnet-4-6"]),
    ).signed(sk)
    assert card.verify() is True


def test_capability_card_unsigned_does_not_verify(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    _sk, vk = test_keypair
    card = CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="x",
        substrate_spec=SubstrateSpec(),
    )
    assert card.verify() is False


def test_capability_card_tampered_text_fails(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    sk, vk = test_keypair
    card = CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="original",
        substrate_spec=SubstrateSpec(),
    ).signed(sk)
    tampered = card.model_copy(update={"capability_text": "evil"})
    assert tampered.verify() is False


def test_capability_card_rejects_zero_halo_version(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    _sk, vk = test_keypair
    with pytest.raises(ValidationError):
        CapabilityCard(
            vacant_id=VacantId.from_verify_key(vk),
            capability_text="x",
            substrate_spec=SubstrateSpec(),
            halo_version=0,
        )


# --- VacantState -------------------------------------------------------------


def test_vacant_state_has_local_member() -> None:
    assert VacantState.LOCAL == "LOCAL"
    assert {s.value for s in VacantState} == {
        "LOCAL",
        "ACTIVE",
        "HIBERNATING",
        "STALE",
        "SUNK",
        "ARCHIVED",
    }


# --- ResidentForm ------------------------------------------------------------


def _build_form(sk: SigningKey, vk: VerifyKey, *, with_card: bool = True) -> ResidentForm:
    vid = VacantId.from_verify_key(vk)
    lb = Logbook()
    lb.append("genesis", {"name": "test"}, sk)
    bb = BehaviorBundle(system_prompt="be honest")
    spec = SubstrateSpec(allowed_substrates=["mock"])
    card: CapabilityCard | None = None
    if with_card:
        card = CapabilityCard(
            vacant_id=vid,
            capability_text="demo",
            substrate_spec=spec,
        ).signed(sk)
    return ResidentForm(
        identity=vid,
        logbook=lb,
        behavior_bundle=bb,
        substrate_spec=spec,
        capability_card=card,
    )


def test_resident_form_verifies_self(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    sk, vk = test_keypair
    assert _build_form(sk, vk).verify_self() is True


def test_resident_form_without_card_still_verifies(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    sk, vk = test_keypair
    assert _build_form(sk, vk, with_card=False).verify_self() is True


def test_resident_form_card_with_wrong_id_fails(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    sk, vk = test_keypair
    form = _build_form(sk, vk)
    _sk2, vk2 = keygen()
    bad_card = CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk2),
        capability_text="x",
        substrate_spec=SubstrateSpec(),
    ).signed(_sk2)
    form2 = form.model_copy(update={"capability_card": bad_card})
    assert form2.verify_self() is False


def test_resident_form_tampered_logbook_fails(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    sk, vk = test_keypair
    form = _build_form(sk, vk)
    bad = form.logbook.entries[0].model_copy(update={"payload": {"hijacked": True}})
    form.logbook.entries[0] = bad
    assert form.verify_self() is False


def test_resident_form_default_state_is_local(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    sk, vk = test_keypair
    assert _build_form(sk, vk).runtime_state == VacantState.LOCAL
