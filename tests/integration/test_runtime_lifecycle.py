"""Slow integration test: simulate ACTIVE → HIBERNATING → STALE → SUNK with
heartbeats fired throughout, asserting the logbook stays valid end-to-end.
"""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import (
    BehaviorBundle,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.runtime.heartbeat import (
    HEARTBEAT_KIND_DEFAULT,
    HEARTBEAT_KIND_SUNK,
    HeartbeatScheduler,
)

pytestmark = pytest.mark.slow


@pytest.mark.asyncio
async def test_full_lifecycle_logbook_stays_valid() -> None:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    lb = Logbook()
    lb.append("genesis", {"name": "lifecycle-test"}, sk)

    form = ResidentForm(
        identity=vid,
        logbook=lb,
        behavior_bundle=BehaviorBundle(system_prompt="x"),
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        runtime_state=VacantState.ACTIVE,
    )

    state = form.runtime_state

    async def fast_sleep(_: float) -> None:
        return None

    sched = HeartbeatScheduler(
        logbook=form.logbook,
        signing_key=sk,
        state_provider=lambda: state,
        sleep=fast_sleep,
    )

    # ACTIVE: 3 heartbeats
    for _ in range(3):
        await sched.tick()

    # → HIBERNATING: 2 heartbeats
    state = VacantState.HIBERNATING
    for _ in range(2):
        await sched.tick()

    # → STALE: 1 heartbeat
    state = VacantState.STALE
    await sched.tick()

    # → SUNK: 4 custody attestations
    state = VacantState.SUNK
    for _ in range(4):
        await sched.tick()

    # Chain still verifies after the lifecycle.
    assert form.logbook.verify_chain(vk) is True

    kinds = [e.kind for e in form.logbook.entries]
    # genesis + 3 active + 2 hibernating + 1 stale + 4 sunk
    assert kinds.count(HEARTBEAT_KIND_DEFAULT) == 6
    assert kinds.count(HEARTBEAT_KIND_SUNK) == 4

    # Last 4 entries must all be custody attestations.
    for entry in form.logbook.entries[-4:]:
        assert entry.kind == HEARTBEAT_KIND_SUNK
        assert entry.payload["liveness"] is False
        assert entry.payload["key_in_custody"] is True
