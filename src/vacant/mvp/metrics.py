"""8 metrics for the P7 dashboard (P7_mvp.md §3) plus 7 Layer 9
health indicators from THEORY_V5 §Layer 9.

Each metric is exposed as:
- `compute_*(snapshot) -> value` -- pure function over a `MetricsSnapshot`.
- `MetricsWriter` -- accumulates the values plus a timestamp into an
  in-memory deque (and serialises to a SQLite `metrics` table when one
  is provided) so the dashboard can plot time series.

The snapshot is a frozen dataclass that any caller (a scenario, a unit
test, or the dashboard itself) can build from the registry + the
aggregator + the per-scenario `ScenarioResult`. It does NOT depend on
any I/O; pure compute.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import Counter, deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from statistics import mean, quantiles
from typing import Any

from vacant.composite import ChildManifest
from vacant.core.crypto import sign, verify
from vacant.core.types import VacantId, VacantState
from vacant.reputation import Aggregator, Beta5D

__all__ = [
    "METRIC_NAMES",
    "MetricsSnapshot",
    "MetricsWriter",
    "compute_all",
    "compute_cold_start_uplift",
    "compute_controller_diversity",
    "compute_custody_uncertain_count",
    "compute_d_spawn_ratio",
    "compute_dispatch_p99_latency",
    "compute_exploration_ratio",
    "compute_graduation_rate",
    "compute_lineage_capability_drift",
    "compute_lineage_depth_distribution",
    "compute_peer_review_density",
    "compute_registry_consistency",
    "compute_reputation_distribution",
    "compute_same_controller_detection_rate",
    "compute_signature_verify_throughput",
    "compute_substrate_diversity",
]


METRIC_NAMES: tuple[str, ...] = (
    "reputation_distribution",
    "cold_start_uplift",
    "same_controller_detection_rate",
    "lineage_depth_distribution",
    "graduation_rate",
    "dispatch_p99_latency",
    "signature_verify_throughput",
    "registry_consistency_under_concurrency",
    # --- Layer 9 health indicators (THEORY_V5 §Layer 9) ------------------
    "d_spawn_ratio",
    "exploration_ratio",
    "custody_uncertain_count",
    "lineage_capability_drift",
    "substrate_diversity",
    "controller_diversity",
    "peer_review_density",
)


@dataclass(frozen=True)
class MetricsSnapshot:
    """Inputs to the metrics module. All optional -- missing fields
    return zero or empty for the corresponding metric."""

    aggregator: Aggregator | None = None
    vacants: dict[VacantId, dict[str, Any]] = field(default_factory=dict)
    """vid -> {state: VacantState, parent_id: VacantId|None, n_calls: int}."""

    manifests: tuple[ChildManifest, ...] = ()
    graduations: tuple[float, ...] = ()
    """Unix timestamps of successful graduations."""

    dispatch_latencies_ms: tuple[float, ...] = ()
    """Wall-clock latencies of `call_capability` in milliseconds."""

    same_controller_eval: dict[str, int] = field(default_factory=dict)
    """{'true_positives': N, 'flagged_total': N} from the adversarial set."""

    registry_writes_attempted: int = 0
    registry_writes_seq_monotonic: int = 0
    """Counters for the concurrent-writers metric."""

    # --- Layer 9 inputs (THEORY_V5 §Layer 9) ---------------------------------

    spawn_events: tuple[dict[str, Any], ...] = ()
    """Each entry shape: `{"path": "D1|D2|D3|D4|D5|B|C|Z", "ts": float}`.
    Powers `d_spawn_ratio` — the share of births that came from agent
    self-replication (D-paths) vs transitional / bootstrap paths."""

    caller_selections: tuple[dict[str, Any], ...] = ()
    """Each entry: `{"was_exploration": bool, "ts": float}` recording
    whether the caller's UCB selection came from the exploration pool
    (INSUFFICIENT_DATA candidates) vs the greedy top-k. Powers
    `exploration_ratio` — V5 §3.6(a)."""

    custody_uncertain_vids: frozenset[VacantId] = field(default_factory=frozenset)
    """Vacant IDs flagged `custody_uncertain` by the heartbeat watcher
    (consecutive missed `HEARTBEAT_SUNK` rounds past the threshold).
    Powers `custody_uncertain_count` — V5 §4.2."""

    lineage_embeddings: dict[VacantId, tuple[tuple[float, ...], ...]] = field(default_factory=dict)
    """Per-lineage-root: tuple of recent member embeddings (STYLO Vec16).
    `lineage_capability_drift` averages the L2 distance from the root's
    earliest embedding to the most recent member embedding, per lineage."""

    peer_review_events: tuple[dict[str, Any], ...] = ()
    """Each entry: `{"target_vid": VacantId, "ts": float}`. Powers
    `peer_review_density` — avg reviews per active vacant per week
    (THEORY_V5 §Layer 9)."""


# --- 1. reputation_distribution -------------------------------------------


def compute_reputation_distribution(snap: MetricsSnapshot) -> dict[str, float]:
    """Return per-dimension mean and stdev across all active vacants."""
    if snap.aggregator is None:
        return {}
    out: dict[str, list[float]] = {
        "factual": [],
        "logical": [],
        "relevance": [],
        "honesty": [],
        "adoption": [],
    }
    for (vid, _sub), rep in snap.aggregator._posteriors.items():
        ctx = snap.aggregator._contexts.get(vid)
        if ctx is None or ctx.state not in (VacantState.ACTIVE, VacantState.LOCAL):
            continue
        for dim, mu in rep.means().items():
            out[dim].append(mu)
    summary: dict[str, float] = {}
    for dim, values in out.items():
        if not values:
            summary[f"mean_{dim}"] = 0.0
            summary[f"n_{dim}"] = 0.0
        else:
            summary[f"mean_{dim}"] = mean(values)
            summary[f"n_{dim}"] = float(len(values))
    return summary


# --- 2. cold_start_uplift -------------------------------------------------


def compute_cold_start_uplift(snap: MetricsSnapshot) -> float:
    """Fraction of calls that went to *new* vacants (n_eff < N_MIN_FOR_STABLE_SCORE
    on any dim). Higher = more exploration. Returns 0 when no calls are
    recorded."""
    from vacant.core.constants import N_MIN_FOR_STABLE_SCORE

    if snap.aggregator is None:
        return 0.0
    new_calls = 0
    total_calls = 0
    for vid, meta in snap.vacants.items():
        n = int(meta.get("n_calls", 0))
        total_calls += n
        rep: Beta5D | None = None
        for sub in ("default", "claude-sonnet-4-6", "gpt-4o", "local-ollama-llama3"):
            r = snap.aggregator._posteriors.get((vid, sub))
            if r is not None:
                rep = r
                break
        if rep is None:
            new_calls += n
            continue
        if any(n_eff < N_MIN_FOR_STABLE_SCORE for n_eff in rep.n_effs().values()):
            new_calls += n
    return (new_calls / total_calls) if total_calls else 0.0


# --- 3. same_controller_detection_rate ------------------------------------


def compute_same_controller_detection_rate(snap: MetricsSnapshot) -> float:
    """True-positive rate of the same-controller signal on the adversarial
    set: TP / (TP + FN). Computed from the dashboard's adversarial run."""
    eval_ = snap.same_controller_eval
    tp = eval_.get("true_positives", 0)
    fn = eval_.get("false_negatives", 0)
    return (tp / (tp + fn)) if (tp + fn) else 0.0


# --- 4. lineage_depth_distribution ----------------------------------------


def compute_lineage_depth_distribution(snap: MetricsSnapshot) -> dict[int, int]:
    """Histogram: depth -> count. Depth 0 = root, depth 1 = root's child, ..."""
    by_id = {vid: meta for vid, meta in snap.vacants.items()}
    depths: Counter[int] = Counter()
    for vid in by_id:
        depth = 0
        cur = vid
        seen: set[VacantId] = set()
        while True:
            if cur in seen:
                break
            seen.add(cur)
            parent = by_id.get(cur, {}).get("parent_id")
            if parent is None:
                break
            depth += 1
            cur = parent
        depths[depth] += 1
    return dict(depths)


# --- 5. graduation_rate ----------------------------------------------------


def compute_graduation_rate(snap: MetricsSnapshot, *, window_s: float = 86_400.0) -> float:
    """Graduations per spawn event in the same window.

    THEORY_V5 §Layer 9 defines this as
    `|grad events| / |spawn events|`. The earlier implementation
    divided by the composite-count instead, which produced a number
    in a different unit (graduations/composite/window) and made the
    dashboard read inversely to what the theory intended.

    Returns 0.0 when there are no spawn events in the window (no
    denominator) — that matches the V5 semantics of "the network
    hasn't produced any spawns yet, so graduation_rate is undefined;
    treat as 0 for plotting".
    """
    cutoff = time.time() - window_s
    recent_grads = [t for t in snap.graduations if t >= cutoff]
    recent_spawns = [
        e for e in snap.spawn_events if float(e.get("ts", 0)) >= cutoff
    ]
    if not recent_spawns:
        return 0.0
    return len(recent_grads) / len(recent_spawns)


# --- 6. dispatch_p99_latency ----------------------------------------------


def compute_dispatch_p99_latency(snap: MetricsSnapshot) -> float:
    """Wall-clock p99 of dispatch latencies (ms). Returns 0 with <2 samples."""
    samples = list(snap.dispatch_latencies_ms)
    if len(samples) < 2:
        return float(samples[0]) if samples else 0.0
    qs = quantiles(samples, n=100)
    return float(qs[98])  # 99th quantile (index 98 of 99 cuts)


# --- 7. signature_verify_throughput ---------------------------------------


def compute_signature_verify_throughput(
    *,
    n_signatures: int = 1000,
) -> float:
    """Verifications per second on a freshly generated batch.
    Cheap microbenchmark; runs synchronously."""
    from vacant.core.crypto import keygen

    sk, vk = keygen()
    payload = b"the quick brown fox jumps over the lazy dog"
    sigs = [sign(sk, payload) for _ in range(n_signatures)]
    t0 = time.perf_counter()
    for sig in sigs:
        if not verify(vk, payload, sig):
            return 0.0
    elapsed = time.perf_counter() - t0
    return n_signatures / elapsed if elapsed > 0 else 0.0


# --- 8. registry_consistency_under_concurrency ----------------------------


def compute_registry_consistency(snap: MetricsSnapshot) -> float:
    """% of registry writes that preserved sequence-no monotonicity under
    concurrent writers. 100% under correct behaviour; <100% indicates
    a regression."""
    attempted = snap.registry_writes_attempted
    if attempted == 0:
        return 1.0
    return snap.registry_writes_seq_monotonic / attempted


# --- Layer 9 health indicators (THEORY_V5 §Layer 9) -----------------------


def _shannon_entropy(counts: Iterable[int]) -> float:
    """Shannon entropy in bits over a non-empty iterable of integer counts.

    Returns 0.0 for the empty / single-bucket case; otherwise
    `-Σ p_i log2(p_i)`. Used by `substrate_diversity` and
    `controller_diversity` per V5 §Layer 9.
    """
    cs = [c for c in counts if c > 0]
    if not cs:
        return 0.0
    total = sum(cs)
    return float(-sum((c / total) * math.log2(c / total) for c in cs))


def compute_d_spawn_ratio(snap: MetricsSnapshot) -> float:
    """Share of births that came from D-path agent self-replication
    (D1-D5) vs total spawns (D + B + C + Z). V5 §Layer 9 lists this as
    *"網路成熟度核心指標，目標 > 0.7"*. Returns 0.0 with no events."""
    if not snap.spawn_events:
        return 0.0
    d = sum(1 for e in snap.spawn_events if str(e.get("path", "")).startswith("D"))
    return d / len(snap.spawn_events)


def compute_exploration_ratio(snap: MetricsSnapshot) -> float:
    """Fraction of caller selections that hit the UCB exploration pool
    (INSUFFICIENT_DATA candidates) rather than the greedy top-k.
    V5 §3.6(a): without exploration the network freezes into an
    oligopoly; the dashboard wants this >= 0.20 in healthy steady state."""
    if not snap.caller_selections:
        return 0.0
    n_exp = sum(1 for s in snap.caller_selections if bool(s.get("was_exploration", False)))
    return n_exp / len(snap.caller_selections)


def compute_custody_uncertain_count(snap: MetricsSnapshot) -> int:
    """Number of vacants flagged `custody_uncertain` (consecutive
    missed `HEARTBEAT_SUNK` past the threshold). V5 §4.2 — sunk
    heartbeat is the *keypair custody attestation*, so a missing
    heartbeat past threshold is a real security signal, not a
    benign liveness flap."""
    return len(snap.custody_uncertain_vids)


def compute_lineage_capability_drift(snap: MetricsSnapshot) -> dict[str, float]:
    """Per-lineage L2 drift from the root's earliest STYLO embedding to
    the most recent member embedding. V5 §4.3 — the *lineage* is what
    evolves, not the individual; this metric quantifies that drift.

    Returns `{lineage_root_short: float, ...}`. Empty when no lineage
    embeddings are recorded.
    """
    out: dict[str, float] = {}
    for root_vid, embeddings in snap.lineage_embeddings.items():
        if len(embeddings) < 2:
            continue
        first = embeddings[0]
        last = embeddings[-1]
        # L2 distance; tuples must be same dim — silently skip if not.
        if len(first) != len(last):
            continue
        d2 = sum((a - b) ** 2 for a, b in zip(first, last, strict=True))
        out[root_vid.short()] = math.sqrt(d2)
    return out


def compute_substrate_diversity(snap: MetricsSnapshot) -> float:
    """Shannon entropy (bits) over `substrate_primary` across all
    Active/Hibernating vacants. V5 §Layer 9 lists this as a health
    indicator — higher = less monoculture risk if any single substrate
    vendor degrades or revokes API access."""
    counts: Counter[str] = Counter()
    for vid, meta in snap.vacants.items():
        state = meta.get("state")
        if state not in (VacantState.ACTIVE, VacantState.HIBERNATING, VacantState.LOCAL):
            continue
        primary = str(meta.get("substrate_primary", "unknown"))
        counts[primary] += 1
    return _shannon_entropy(counts.values())


def compute_controller_diversity(snap: MetricsSnapshot) -> float:
    """Shannon entropy over `controller_id` across all Active vacants.
    V5 §Layer 9 — pair-bar against `same_controller_detection_rate` to
    distinguish "many independent operators" (high entropy, low
    detection) from "one operator across many vacants" (low entropy,
    high detection)."""
    counts: Counter[str] = Counter()
    for vid, meta in snap.vacants.items():
        state = meta.get("state")
        if state not in (VacantState.ACTIVE, VacantState.LOCAL):
            continue
        controller = str(meta.get("controller_id", "unknown"))
        counts[controller] += 1
    return _shannon_entropy(counts.values())


def compute_peer_review_density(
    snap: MetricsSnapshot, *, window_s: float = 7 * 86_400.0
) -> float:
    """Average peer reviews per Active vacant per `window_s` (default
    1 week). V5 §4.2(e) claims a healthy network should give a new
    vacant 30+ peer reviews in its first week — this is the
    quantitative shape of that claim."""
    n_active = sum(
        1
        for meta in snap.vacants.values()
        if meta.get("state") in (VacantState.ACTIVE, VacantState.HIBERNATING)
    )
    if n_active == 0:
        return 0.0
    cutoff = time.time() - window_s
    n_reviews_in_window = sum(1 for ev in snap.peer_review_events if float(ev.get("ts", 0)) >= cutoff)
    return n_reviews_in_window / n_active


# --- aggregate ------------------------------------------------------------


def compute_all(snap: MetricsSnapshot) -> dict[str, Any]:
    """Run every metric and return a flat dict."""
    return {
        "reputation_distribution": compute_reputation_distribution(snap),
        "cold_start_uplift": compute_cold_start_uplift(snap),
        "same_controller_detection_rate": compute_same_controller_detection_rate(snap),
        "lineage_depth_distribution": compute_lineage_depth_distribution(snap),
        "graduation_rate": compute_graduation_rate(snap),
        "dispatch_p99_latency_ms": compute_dispatch_p99_latency(snap),
        "signature_verify_throughput_per_s": compute_signature_verify_throughput(),
        "registry_consistency_pct": compute_registry_consistency(snap) * 100.0,
        # --- Layer 9 health indicators -------------------------------------
        "d_spawn_ratio": compute_d_spawn_ratio(snap),
        "exploration_ratio": compute_exploration_ratio(snap),
        "custody_uncertain_count": compute_custody_uncertain_count(snap),
        "lineage_capability_drift": compute_lineage_capability_drift(snap),
        "substrate_diversity": compute_substrate_diversity(snap),
        "controller_diversity": compute_controller_diversity(snap),
        "peer_review_density": compute_peer_review_density(snap),
    }


# --- writer ---------------------------------------------------------------


@dataclass
class MetricsWriter:
    """In-memory ring buffer of (ts, metric_name, value) triples for
    time-series plotting. Configurable max length."""

    max_points: int = 5000
    samples: deque[tuple[float, str, Any]] = field(default_factory=lambda: deque(maxlen=5000))
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def emit(self, name: str, value: Any) -> None:
        self.samples.append((time.time(), name, value))

    def emit_all(self, snap: MetricsSnapshot) -> dict[str, Any]:
        values = compute_all(snap)
        for k, v in values.items():
            self.emit(k, v)
        return values

    def filter(self, name: str) -> Iterable[tuple[float, Any]]:
        return [(ts, val) for ts, n, val in self.samples if n == name]
