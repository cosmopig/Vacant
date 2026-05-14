"""P1 — runtime: state machine, heartbeat, shadow-self drift, spawn (D1-D5)."""

from vacant.runtime.errors import (
    ConsentError,
    InvalidEventError,
    RuntimeError_,
    SpawnError,
)
from vacant.runtime.heartbeat import (
    HeartbeatScheduler,
    heartbeat_kind,
    heartbeat_payload,
    heartbeat_period_s,
)
from vacant.runtime.loop import RuntimeLoop
from vacant.runtime.redteam import (
    Probe,
    ProbeCategory,
    ProbeResult,
    ProbeVerdict,
    default_catalog,
    pick_probe,
    score_probe_response,
)
from vacant.runtime.shadow_self import (
    AnchorDistribution,
    compute_drift,
    compute_embedding,
    drift_log_entry,
    is_drifting,
)
from vacant.runtime.spawn import (
    BIRTH_KIND,
    SPAWN_KIND,
    ParentConsent,
    SpawnResult,
    consent,
    make_d4_consent,
    spawn_capability_fork,
    spawn_clone_with_mutation,
    spawn_cross_substrate_respawn,
    spawn_lineage_merge,
    spawn_subagent_bud,
)
from vacant.runtime.state_machine import (
    Event,
    VacantStateMachine,
    can_be_called,
    can_review,
    is_runnable,
    requires_revive,
)
from vacant.runtime.store import InMemoryLogbookStore, LogbookStore

__all__ = [
    "BIRTH_KIND",
    "SPAWN_KIND",
    "AnchorDistribution",
    "ConsentError",
    "Event",
    "HeartbeatScheduler",
    "InMemoryLogbookStore",
    "InvalidEventError",
    "LogbookStore",
    "ParentConsent",
    "Probe",
    "ProbeCategory",
    "ProbeResult",
    "ProbeVerdict",
    "RuntimeError_",
    "RuntimeLoop",
    "SpawnError",
    "SpawnResult",
    "VacantStateMachine",
    "can_be_called",
    "can_review",
    "compute_drift",
    "compute_embedding",
    "consent",
    "default_catalog",
    "drift_log_entry",
    "heartbeat_kind",
    "heartbeat_payload",
    "heartbeat_period_s",
    "is_drifting",
    "is_runnable",
    "make_d4_consent",
    "pick_probe",
    "requires_revive",
    "score_probe_response",
    "spawn_capability_fork",
    "spawn_clone_with_mutation",
    "spawn_cross_substrate_respawn",
    "spawn_lineage_merge",
    "spawn_subagent_bud",
]
