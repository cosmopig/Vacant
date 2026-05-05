"""RuntimeLoop + LogbookStore tests."""

from __future__ import annotations

import pytest

from vacant.core.crypto import SigningKey, VerifyKey, keygen
from vacant.core.types import (
    BehaviorBundle,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.runtime.errors import InvalidEventError
from vacant.runtime.loop import RuntimeLoop
from vacant.runtime.state_machine import Event
from vacant.runtime.store import InMemoryLogbookStore


def _make_form(state: VacantState = VacantState.ACTIVE) -> tuple[ResidentForm, SigningKey]:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    lb = Logbook()
    lb.append("genesis", {}, sk)
    return (
        ResidentForm(
            identity=vid,
            logbook=lb,
            behavior_bundle=BehaviorBundle(system_prompt="x"),
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
            runtime_state=state,
        ),
        sk,
    )


@pytest.mark.asyncio
async def test_loop_persists_logbook_after_event() -> None:
    form, sk = _make_form(VacantState.HIBERNATING)
    store = InMemoryLogbookStore()
    loop = RuntimeLoop(form=form, signing_key=sk, store=store)
    await loop.submit(Event.REVIVE_REQUESTED)
    assert loop.state == VacantState.ACTIVE
    persisted = await store.load(form.identity)
    assert persisted is not None
    assert persisted is form.logbook


@pytest.mark.asyncio
async def test_loop_rejects_invalid_event() -> None:
    form, sk = _make_form(VacantState.SUNK)
    store = InMemoryLogbookStore()
    loop = RuntimeLoop(form=form, signing_key=sk, store=store)
    with pytest.raises(InvalidEventError):
        await loop.submit(Event.CALL_RECEIVED)
    assert loop.state == VacantState.SUNK


@pytest.mark.asyncio
async def test_loop_append_log_writes_and_persists() -> None:
    form, sk = _make_form()
    store = InMemoryLogbookStore()
    loop = RuntimeLoop(form=form, signing_key=sk, store=store)
    entry = await loop.append_log("custom", {"k": "v"})
    assert entry.kind == "custom"
    assert (await store.load(form.identity)) is form.logbook


@pytest.mark.asyncio
async def test_loop_heartbeat_scheduler_uses_current_state() -> None:
    form, sk = _make_form(VacantState.ACTIVE)
    store = InMemoryLogbookStore()
    loop = RuntimeLoop(form=form, signing_key=sk, store=store)
    sched = loop.heartbeat_scheduler()
    entry = await sched.tick()
    assert entry.payload["liveness"] is True
    # Mutate state via the loop and verify scheduler picks up the new state.
    await loop.submit(Event.REVIEW_RECEIVED)  # no-op stays ACTIVE
    entry2 = await sched.tick()
    assert entry2.payload["liveness"] is True


@pytest.mark.asyncio
async def test_in_memory_store_round_trip(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    sk, vk = test_keypair
    vid = VacantId.from_verify_key(vk)
    store = InMemoryLogbookStore()
    assert (await store.load(vid)) is None
    assert (await store.has(vid)) is False
    lb = Logbook()
    lb.append("genesis", {}, sk)
    await store.save(vid, lb)
    assert (await store.has(vid)) is True
    assert (await store.load(vid)) is lb
    assert len(store) == 1
