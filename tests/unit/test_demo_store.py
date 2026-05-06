"""Unit tests for `vacant.mvp.demo_store` (Pfix2 §B1)."""

from __future__ import annotations

import pytest

from vacant.mvp.demo_store import EVENT_KINDS, DemoStore


def test_record_and_read_round_trip() -> None:
    with DemoStore(":memory:") as store:
        store.record(scenario="law_firm", kind="call", payload={"tick": 1, "ok": True})
        store.record(scenario="law_firm", kind="review", payload={"x": 1.0})
        events = store.read(scenario="law_firm")
    assert len(events) == 2
    assert {e.kind for e in events} == {"call", "review"}
    assert events[0].payload["tick"] == 1


def test_filter_by_kind() -> None:
    with DemoStore(":memory:") as store:
        for k in EVENT_KINDS:
            store.record(scenario="law_firm", kind=k, payload={"k": k})
        calls = store.read(scenario="law_firm", kind="call")
        spawns = store.read(scenario="law_firm", kind="spawn")
    assert len(calls) == 1
    assert calls[0].kind == "call"
    assert len(spawns) == 1


def test_filter_by_scenario() -> None:
    with DemoStore(":memory:") as store:
        store.record(scenario="a", kind="call", payload={})
        store.record(scenario="b", kind="call", payload={})
        store.record(scenario="a", kind="call", payload={})
        assert store.count(scenario="a") == 2
        assert store.count(scenario="b") == 1


def test_unknown_kind_rejected() -> None:
    with DemoStore(":memory:") as store, pytest.raises(ValueError):
        store.record(scenario="x", kind="not_a_real_kind", payload={})


def test_metric_series_returns_named_metric_only() -> None:
    with DemoStore(":memory:") as store:
        store.record(
            scenario="x",
            kind="metric",
            payload={"name": "lat_p99", "value": 1.5},
            ts=1.0,
        )
        store.record(
            scenario="x",
            kind="metric",
            payload={"name": "lat_p99", "value": 2.5},
            ts=2.0,
        )
        store.record(
            scenario="x",
            kind="metric",
            payload={"name": "other_metric", "value": 99.0},
            ts=3.0,
        )
        series = store.metric_series("x", "lat_p99")
    assert series == [(1.0, 1.5), (2.0, 2.5)]


def test_record_batch() -> None:
    with DemoStore(":memory:") as store:
        n = store.record_batch(
            "x",
            [("call", {"i": 1}), ("call", {"i": 2}), ("review", {"i": 3})],
            ts_start=0.0,
            ts_step=1.0,
        )
        events = store.read(scenario="x")
    assert n == 3
    assert [e.ts for e in events] == [0.0, 1.0, 2.0]


def test_clear_scenario_only() -> None:
    with DemoStore(":memory:") as store:
        store.record(scenario="a", kind="call", payload={})
        store.record(scenario="b", kind="call", payload={})
        store.clear(scenario="a")
        assert store.count(scenario="a") == 0
        assert store.count(scenario="b") == 1


def test_scenarios_list() -> None:
    with DemoStore(":memory:") as store:
        store.record(scenario="b", kind="call", payload={})
        store.record(scenario="a", kind="call", payload={})
        assert store.scenarios() == ["a", "b"]
