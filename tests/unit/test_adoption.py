"""Unit tests for `vacant.reputation.adoption` + the aggregator hook.

Covers:
- 24h-72h windowing (`AdoptionEvent.is_within_window`)
- self-adoption rejection
- duplicate dedup on `(source, source_call_id, downstream)`
- distinct-downstream count
- aggregator `record_adoption` updates the `adoption` Beta posterior
- unknown-vacant rejection at the aggregator boundary
"""

from __future__ import annotations

import pytest

from vacant.core.constants import (
    ADOPTION_SIGNAL_MAX_WINDOW_S,
    ADOPTION_SIGNAL_MIN_WINDOW_S,
)
from vacant.core.crypto import keygen
from vacant.core.types import VacantId, VacantState
from vacant.reputation import (
    AdoptionEvent,
    AdoptionLedger,
    AdoptionLedgerError,
    Aggregator,
    InvalidSignalError,
    VacantContext,
)


def _vid() -> VacantId:
    _sk, vk = keygen()
    return VacantId.from_verify_key(vk)


# --- windowing --------------------------------------------------------------


def test_within_window_at_lower_bound() -> None:
    src = _vid()
    dst = _vid()
    ev = AdoptionEvent(
        source_vid=src,
        downstream_vid=dst,
        source_call_id="c1",
        source_ts=1_000_000.0,
        adoption_ts=1_000_000.0 + ADOPTION_SIGNAL_MIN_WINDOW_S,
    )
    assert ev.is_within_window() is True


def test_within_window_at_upper_bound() -> None:
    src, dst = _vid(), _vid()
    ev = AdoptionEvent(
        source_vid=src,
        downstream_vid=dst,
        source_call_id="c1",
        source_ts=1_000_000.0,
        adoption_ts=1_000_000.0 + ADOPTION_SIGNAL_MAX_WINDOW_S,
    )
    assert ev.is_within_window() is True


def test_too_soon_is_rejected() -> None:
    src, dst = _vid(), _vid()
    ev = AdoptionEvent(
        source_vid=src,
        downstream_vid=dst,
        source_call_id="c1",
        source_ts=1_000_000.0,
        adoption_ts=1_000_000.0 + 60,  # 1 minute later
    )
    assert ev.is_within_window() is False
    with pytest.raises(AdoptionLedgerError):
        AdoptionLedger().attest(ev)


def test_too_late_is_rejected() -> None:
    src, dst = _vid(), _vid()
    ev = AdoptionEvent(
        source_vid=src,
        downstream_vid=dst,
        source_call_id="c1",
        source_ts=1_000_000.0,
        adoption_ts=1_000_000.0 + ADOPTION_SIGNAL_MAX_WINDOW_S + 1,
    )
    assert ev.is_within_window() is False
    with pytest.raises(AdoptionLedgerError):
        AdoptionLedger().attest(ev)


# --- ledger semantics -------------------------------------------------------


def _in_window_event(
    src: VacantId, dst: VacantId, *, call_id: str = "c1", substrate: str = "default"
) -> AdoptionEvent:
    return AdoptionEvent(
        source_vid=src,
        downstream_vid=dst,
        source_call_id=call_id,
        source_ts=1_000_000.0,
        adoption_ts=1_000_000.0 + ADOPTION_SIGNAL_MIN_WINDOW_S + 1,
        substrate=substrate,
    )


def test_self_adoption_rejected() -> None:
    me = _vid()
    ev = _in_window_event(me, me)
    with pytest.raises(AdoptionLedgerError):
        AdoptionLedger().attest(ev)


def test_duplicate_rejected() -> None:
    src, dst = _vid(), _vid()
    ledger = AdoptionLedger()
    ledger.attest(_in_window_event(src, dst))
    with pytest.raises(AdoptionLedgerError):
        ledger.attest(_in_window_event(src, dst))


def test_same_downstream_different_call_id_allowed() -> None:
    src, dst = _vid(), _vid()
    ledger = AdoptionLedger()
    ledger.attest(_in_window_event(src, dst, call_id="c1"))
    ledger.attest(_in_window_event(src, dst, call_id="c2"))
    assert len(ledger) == 2


def test_distinct_downstreams_dedup() -> None:
    src, d1, d2 = _vid(), _vid(), _vid()
    ledger = AdoptionLedger()
    ledger.attest(_in_window_event(src, d1, call_id="c1"))
    ledger.attest(_in_window_event(src, d2, call_id="c2"))
    ledger.attest(_in_window_event(src, d1, call_id="c3"))  # d1 adopts again, different call
    assert ledger.distinct_downstreams(src) == {d1, d2}


def test_substrate_filter() -> None:
    src, dst = _vid(), _vid()
    ledger = AdoptionLedger()
    ledger.attest(_in_window_event(src, dst, call_id="c1", substrate="A"))
    ledger.attest(_in_window_event(src, dst, call_id="c2", substrate="B"))
    assert {ev.substrate for ev in ledger.for_source(src, substrate="A")} == {"A"}


# --- aggregator integration --------------------------------------------------


@pytest.mark.asyncio
async def test_aggregator_record_adoption_updates_posterior() -> None:
    src, dst = _vid(), _vid()
    contexts = {
        src: VacantContext(vacant_id=src, base_model_family="X", state=VacantState.ACTIVE),
        dst: VacantContext(vacant_id=dst, base_model_family="Y", state=VacantState.ACTIVE),
    }
    agg = Aggregator(contexts)
    ev = _in_window_event(src, dst, substrate="default")

    rep_before = await agg.get_reputation(src, "default")
    adoption_before = rep_before.adoption.alpha + rep_before.adoption.beta

    await agg.record_adoption(ev)
    rep_after = await agg.get_reputation(src, "default")
    adoption_after = rep_after.adoption.alpha + rep_after.adoption.beta

    # Some weight got added; alpha+beta strictly increased.
    assert adoption_after > adoption_before


@pytest.mark.asyncio
async def test_aggregator_rejects_unknown_source() -> None:
    src, dst = _vid(), _vid()
    contexts = {
        dst: VacantContext(vacant_id=dst, base_model_family="Y", state=VacantState.ACTIVE),
    }
    agg = Aggregator(contexts)
    with pytest.raises(InvalidSignalError):
        await agg.record_adoption(_in_window_event(src, dst))


@pytest.mark.asyncio
async def test_aggregator_rejects_out_of_window() -> None:
    """The aggregator forwards to the ledger; out-of-window events must
    raise AdoptionLedgerError before any posterior update happens."""
    src, dst = _vid(), _vid()
    contexts = {
        src: VacantContext(vacant_id=src, base_model_family="X", state=VacantState.ACTIVE),
        dst: VacantContext(vacant_id=dst, base_model_family="Y", state=VacantState.ACTIVE),
    }
    agg = Aggregator(contexts)
    bad = AdoptionEvent(
        source_vid=src,
        downstream_vid=dst,
        source_call_id="c1",
        source_ts=1_000_000.0,
        adoption_ts=1_000_000.0 + 5,
    )
    with pytest.raises(AdoptionLedgerError):
        await agg.record_adoption(bad)
    # Posterior unchanged.
    rep = await agg.get_reputation(src, "default")
    assert rep.adoption.alpha == 1.0 and rep.adoption.beta == 3.0  # priors


@pytest.mark.asyncio
async def test_adoption_count_reflects_distinct_downstreams() -> None:
    src = _vid()
    d1, d2 = _vid(), _vid()
    contexts = {
        src: VacantContext(vacant_id=src, base_model_family="X", state=VacantState.ACTIVE),
        d1: VacantContext(vacant_id=d1, base_model_family="Y", state=VacantState.ACTIVE),
        d2: VacantContext(vacant_id=d2, base_model_family="Z", state=VacantState.ACTIVE),
    }
    agg = Aggregator(contexts)
    await agg.record_adoption(_in_window_event(src, d1, call_id="c1"))
    await agg.record_adoption(_in_window_event(src, d2, call_id="c2"))
    await agg.record_adoption(_in_window_event(src, d1, call_id="c3"))
    assert agg.adoption_count(src) == 2
