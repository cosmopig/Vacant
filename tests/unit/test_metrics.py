"""Smoke tests for `vacant.mvp.metrics`. Pure-compute functions only —
the dashboard's Streamlit wiring is exercised by the slow integration
test (`tests/integration/test_mvp_full.py`).
"""

from __future__ import annotations

import time

import pytest

from vacant.core.crypto import keygen, sign
from vacant.core.types import VacantId, VacantState
from vacant.mvp.metrics import (
    METRIC_NAMES,
    MetricsSnapshot,
    MetricsWriter,
    compute_all,
    compute_cold_start_uplift,
    compute_dispatch_p99_latency,
    compute_graduation_rate,
    compute_lineage_depth_distribution,
    compute_registry_consistency,
    compute_reputation_distribution,
    compute_same_controller_detection_rate,
    compute_signature_verify_throughput,
)
from vacant.reputation import Aggregator, VacantContext


def _vid() -> VacantId:
    return VacantId.from_verify_key(keygen()[1])


def _ctx(state: VacantState = VacantState.ACTIVE) -> VacantContext:
    return VacantContext(
        vacant_id=_vid(),
        base_model_family="claude",
        state=state,
        capability_text="x",
    )


def test_metric_names_match_compute_all_keys() -> None:
    snap = MetricsSnapshot()
    out = compute_all(snap)
    # compute_all emits the 8 metric names plus a couple of "_ms"/"_pct"
    # variants -- ensure each METRIC_NAMES entry has a corresponding key.
    keys = set(out.keys())
    aliases = {
        "dispatch_p99_latency": "dispatch_p99_latency_ms",
        "signature_verify_throughput": "signature_verify_throughput_per_s",
        "registry_consistency_under_concurrency": "registry_consistency_pct",
    }
    for n in METRIC_NAMES:
        assert (n in keys) or (aliases[n] in keys)


def test_empty_snapshot_returns_zeros() -> None:
    snap = MetricsSnapshot()
    assert compute_reputation_distribution(snap) == {}
    assert compute_cold_start_uplift(snap) == 0.0
    assert compute_same_controller_detection_rate(snap) == 0.0
    assert compute_lineage_depth_distribution(snap) == {}
    assert compute_graduation_rate(snap) == 0.0
    assert compute_dispatch_p99_latency(snap) == 0.0
    # Empty registry-writes counter ⇒ vacuously consistent (1.0).
    assert compute_registry_consistency(snap) == 1.0


def test_reputation_distribution_with_aggregator() -> None:
    a, b = _ctx(), _ctx()
    agg = Aggregator(contexts={a.vacant_id: a, b.vacant_id: b})
    snap = MetricsSnapshot(
        aggregator=agg,
        vacants={
            a.vacant_id: {"state": VacantState.ACTIVE, "n_calls": 10},
            b.vacant_id: {"state": VacantState.ACTIVE, "n_calls": 0},
        },
    )
    # Force a posterior on a.
    import asyncio

    asyncio.run(agg.get_reputation(a.vacant_id, "default"))
    summary = compute_reputation_distribution(snap)
    assert "mean_factual" in summary
    assert summary["n_factual"] >= 1.0


def test_lineage_depth_distribution_counts_chains() -> None:
    root = _vid()
    child = _vid()
    grand = _vid()
    snap = MetricsSnapshot(
        vacants={
            root: {"state": VacantState.ACTIVE, "parent_id": None},
            child: {"state": VacantState.ACTIVE, "parent_id": root},
            grand: {"state": VacantState.ACTIVE, "parent_id": child},
        }
    )
    dist = compute_lineage_depth_distribution(snap)
    # Depths: root=0, child=1, grand=2.
    assert dist.get(0) == 1
    assert dist.get(1) == 1
    assert dist.get(2) == 1


def test_graduation_rate_counts_recent_24h() -> None:
    now = time.time()
    snap = MetricsSnapshot(
        graduations=(now - 1, now - 60, now - 86_400 * 2),  # 2 fresh, 1 stale
    )
    rate = compute_graduation_rate(snap)
    assert rate == pytest.approx(2.0)


def test_dispatch_p99_latency_picks_high_quantile() -> None:
    snap = MetricsSnapshot(
        dispatch_latencies_ms=tuple(float(x) for x in range(1, 101)),
    )
    p99 = compute_dispatch_p99_latency(snap)
    assert 90 <= p99 <= 100


def test_same_controller_detection_rate_summarises_eval() -> None:
    snap = MetricsSnapshot(
        same_controller_eval={"true_positives": 8, "false_negatives": 2},
    )
    rate = compute_same_controller_detection_rate(snap)
    assert rate == pytest.approx(0.8)


def test_registry_consistency_ratio() -> None:
    snap = MetricsSnapshot(
        registry_writes_attempted=100,
        registry_writes_seq_monotonic=100,
    )
    assert compute_registry_consistency(snap) == 1.0


def test_metrics_writer_records_emits_and_filters() -> None:
    w = MetricsWriter()
    w.emit("foo", 1)
    w.emit("foo", 2)
    w.emit("bar", 3)
    assert sorted(v for _, v in w.filter("foo")) == [1, 2]


def test_metrics_writer_emit_all_runs_compute_all() -> None:
    snap = MetricsSnapshot()
    w = MetricsWriter()
    out = w.emit_all(snap)
    assert "reputation_distribution" in out
    assert len(w.samples) == len(out)


def test_signature_verify_throughput_uses_real_keys() -> None:
    sk, _vk = keygen()
    payload = b"x" * 32
    _ = sign(sk, payload)  # warm up
    rate = compute_signature_verify_throughput(n_signatures=8)
    assert rate > 0.0
