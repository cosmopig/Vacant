"""Shared scenario harness: builds vacants, seeds aggregator + composite
runtime, exposes a `ScenarioResult` shape for the integration test +
dashboard to consume.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from vacant.core.crypto import SigningKey, keygen
from vacant.core.types import (
    BehaviorBundle,
    CapabilityCard,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.reputation import Aggregator, Beta5D, VacantContext

if TYPE_CHECKING:
    from vacant.mvp.demo_store import DemoStore

__all__ = [
    "ScenarioResult",
    "VacantSeed",
    "build_vacant",
    "record_metric_snapshot",
    "reputation_snapshot",
    "seeded_random",
]


@dataclass
class VacantSeed:
    """A blueprint for instantiating a vacant in a scenario."""

    name: str
    capability_text: str
    base_model_family: str = "claude"
    state: VacantState = VacantState.ACTIVE
    attestation_level: str = "L1"
    allowed_substrates: tuple[str, ...] = ("mock",)
    tool_whitelist: tuple[str, ...] = ()


@dataclass
class ScenarioResult:
    """Snapshot produced by `run(...)` for every scenario.

    `vacants` -- VacantId.hex() -> {state, capability, mu_per_dim}
    `events` -- list of structured log dicts in execution order
    `reputation` -- {(vid_hex, substrate): {dim: mu}}
    `metrics` -- per-scenario metrics computed during the run
    """

    name: str
    seed: int
    vacants: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    reputation: dict[str, dict[str, float]] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    logbook_chains_ok: bool = True


def seeded_random(seed: int) -> random.Random:
    """Return a fresh `random.Random` for reproducible scenarios."""
    return random.Random(seed)


def build_vacant(
    seed: VacantSeed,
    rng: random.Random,
) -> tuple[SigningKey, ResidentForm]:
    """Build a `ResidentForm` + signing key from a seed blueprint.

    The keypair is always fresh (Ed25519 generation cannot be seeded
    via stdlib random); callers wanting bit-exact identity should pin
    the keypair externally. For scenario reproducibility we don't
    depend on identity bytes -- just on relative ordering + counts.
    """
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    bundle = BehaviorBundle(
        system_prompt=f"You are a {seed.capability_text} vacant.",
        tool_whitelist=list(seed.tool_whitelist),
    )
    spec = SubstrateSpec(allowed_substrates=list(seed.allowed_substrates))
    lb = Logbook()
    lb.append(
        "GENESIS",
        {"name": seed.name, "capability": seed.capability_text, "rng_token": rng.random()},
        sk,
    )
    card = CapabilityCard(
        vacant_id=vid,
        capability_text=seed.capability_text,
        substrate_spec=spec,
    ).signed(sk)
    return sk, ResidentForm(
        identity=vid,
        logbook=lb,
        behavior_bundle=bundle,
        substrate_spec=spec,
        runtime_state=seed.state,
        capability_card=card,
    )


def context_from_form(form: ResidentForm, seed: VacantSeed) -> VacantContext:
    return VacantContext(
        vacant_id=form.identity,
        base_model_family=seed.base_model_family,
        state=seed.state,
        capability_text=seed.capability_text,
        attestation_level=seed.attestation_level,
    )


def reputation_snapshot(
    aggregator: Aggregator,
    vid: VacantId,
    *,
    substrate: str = "default",
) -> dict[str, float]:
    """Read the per-dim mean for a vacant's posterior on `substrate`."""
    rep: Beta5D | None = aggregator._posteriors.get((vid, substrate))
    if rep is None:
        return {}
    return rep.means()


def record_metric_snapshot(
    *,
    store: DemoStore | None,
    scenario: str,
    aggregator: Aggregator,
    vacants: dict[VacantId, dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
    ts: float | None = None,
) -> None:
    """Compute the cheap subset of P7 metrics + reputation distribution and
    write them into `store` as `metric` events.

    No-op when `store is None`; this lets the integration test path
    skip the demo-db side effect. Heavy metrics (signature throughput
    benchmark, registry consistency) are NOT computed here -- the
    dashboard pulls those from `metrics.compute_all` once at render
    time.
    """
    if store is None:
        return

    from vacant.mvp.metrics import (
        MetricsSnapshot as _MS,
    )
    from vacant.mvp.metrics import (
        compute_lineage_depth_distribution,
        compute_reputation_distribution,
    )

    # Build a Snapshot with the data we have. `vacants` may be empty for
    # scenarios that don't track per-vacant metadata; the metrics are
    # robust to that.
    snap = _MS(
        aggregator=aggregator,
        vacants=({} if vacants is None else dict(vacants)),
    )
    payload_dist = compute_reputation_distribution(snap)
    store.record(
        scenario=scenario,
        kind="metric",
        payload={"name": "reputation_distribution", "value": payload_dist},
        ts=ts,
    )
    store.record(
        scenario=scenario,
        kind="metric",
        payload={
            "name": "lineage_depth_distribution",
            "value": compute_lineage_depth_distribution(snap),
        },
        ts=ts,
    )
    if extra:
        for name, value in extra.items():
            store.record(
                scenario=scenario,
                kind="metric",
                payload={"name": name, "value": value},
                ts=ts,
            )
