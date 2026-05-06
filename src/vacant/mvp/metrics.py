"""8 metrics for the P7 dashboard (P7_mvp.md §3).

Each metric is exposed as:
- `compute_*(snapshot) -> value` -- pure function over a `MetricsSnapshot`.
- `MetricsWriter` -- accumulates the 8 values plus a timestamp into an
  in-memory deque (and serialises to a SQLite `metrics` table when one
  is provided) so the dashboard can plot time series.

The snapshot is a frozen dataclass that any caller (a scenario, a unit
test, or the dashboard itself) can build from the registry + the
aggregator + the per-scenario `ScenarioResult`. It does NOT depend on
any I/O; pure compute.
"""

from __future__ import annotations

import asyncio
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
    "compute_dispatch_p99_latency",
    "compute_graduation_rate",
    "compute_lineage_depth_distribution",
    "compute_registry_consistency",
    "compute_reputation_distribution",
    "compute_same_controller_detection_rate",
    "compute_signature_verify_throughput",
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
    """Graduations per (composite, time-window)."""
    n_composites = sum(1 for meta in snap.vacants.values() if meta.get("is_composite", False))
    n_composites = max(n_composites, 1)
    cutoff = time.time() - window_s
    recent = [t for t in snap.graduations if t >= cutoff]
    return len(recent) / n_composites


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
