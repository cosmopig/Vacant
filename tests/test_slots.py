import copy
import json

import pytest

import codec
from cli import dispatch
from service import first_slot, slots


def test_half_open_touching_busy_does_not_conflict():
    busy = [["2025-01-01T09:30:00+00:00", "2025-01-01T10:00:00+00:00"]]
    got = slots("2025-01-01T09:00:00+00:00", "2025-01-01T10:30:00+00:00", busy, 30)
    assert got == [
        {"start": "2025-01-01T09:00:00+00:00", "end": "2025-01-01T09:30:00+00:00"},
        {"start": "2025-01-01T10:00:00+00:00", "end": "2025-01-01T10:30:00+00:00"},
    ]


def test_step_and_union_of_overlapping_busy():
    busy = [["2025-01-01T09:20:00+00:00", "2025-01-01T09:40:00+00:00"],
            ["2025-01-01T09:10:00+00:00", "2025-01-01T09:25:00+00:00"]]
    got = slots("2025-01-01T09:00:00+00:00", "2025-01-01T10:00:00+00:00", busy, 10, step=5)
    assert [s["start"][11:16] for s in got] == ["09:00", "09:40", "09:45", "09:50"]


def test_offsets_and_dst_use_elapsed_time():
    # US fall-back: 01:30-04:00 and 01:30-05:00 are the same wall clock, different instants.
    got = slots("2025-11-02T01:00:00-04:00", "2025-11-02T02:00:00-05:00", [], 60)
    assert got == [
        {"start": "2025-11-02T05:00:00+00:00", "end": "2025-11-02T06:00:00+00:00"},
        {"start": "2025-11-02T06:00:00+00:00", "end": "2025-11-02T07:00:00+00:00"},
    ]
    busy = [["2025-11-02T01:30:00-05:00", "2025-11-02T01:45:00-05:00"]]
    got = slots("2025-11-02T01:00:00-04:00", "2025-11-02T02:00:00-05:00", busy, 30)
    assert [s["start"] for s in got] == [
        "2025-11-02T05:00:00+00:00", "2025-11-02T05:30:00+00:00", "2025-11-02T06:00:00+00:00"]


def test_limits_and_empty_window():
    s, e = "2025-01-01T09:00:00+00:00", "2025-01-01T10:00:00+00:00"
    assert slots(s, s, [], 30) == []
    assert slots(s, e, [], 10, limit=0) == []
    assert len(slots(s, e, [], 10, limit=2)) == 2
    assert first_slot(s, e, [], 30)["start"] == s
    for bad in (-1, True, 1.5):
        with pytest.raises(ValueError, match="limit must be an integer >= 0"):
            slots(s, e, [], 10, limit=bad)


def test_validation_messages():
    s, e = "2025-01-01T09:00:00+00:00", "2025-01-01T10:00:00+00:00"
    with pytest.raises(ValueError, match="time must include an offset"):
        slots("2025-01-01T09:00:00", e, [], 10)
    with pytest.raises(ValueError, match="time must include an offset"):
        slots("nope", e, [], 10)
    with pytest.raises(ValueError, match="end precedes start"):
        slots(e, s, [], 10)
    for bad in (0, True, 1.0):
        with pytest.raises(ValueError, match="duration must be an integer >= 1"):
            slots(s, e, [], bad)
        with pytest.raises(ValueError, match="step must be an integer >= 1"):
            slots(s, e, [], 10, step=bad)
    with pytest.raises(ValueError, match="invalid busy interval"):
        slots(s, e, [[e, s]], 10, limit=0)
    with pytest.raises(ValueError, match="time must include an offset"):
        slots(s, e, [["2025-01-01T09:00:00", e]], 10, limit=0)


def test_inputs_not_mutated():
    busy = [["2025-01-01T09:40:00+00:00", "2025-01-01T09:50:00+00:00"],
            ["2025-01-01T09:10:00+00:00", "2025-01-01T09:20:00+00:00"]]
    before = copy.deepcopy(busy)
    slots("2025-01-01T09:00:00+00:00", "2025-01-01T10:00:00+00:00", busy, 10)
    assert busy == before


def test_codec_legacy_v2_and_roundtrip():
    legacy = [["2025-01-01T10:00:00+01:00", "2025-01-01T11:00:00+01:00"],
              ["2025-01-01T08:00:00+00:00", "2025-01-01T08:30:00+00:00"]]
    assert codec.loads(json.dumps(legacy)) == legacy
    out = json.loads(codec.dumps(legacy))
    assert out == {"version": 2, "busy": [
        {"start": "2025-01-01T09:00:00+00:00", "end": "2025-01-01T10:00:00+00:00"},
        {"start": "2025-01-01T08:00:00+00:00", "end": "2025-01-01T08:30:00+00:00"}]}
    assert codec.loads(codec.dumps(legacy)) == [
        ["2025-01-01T09:00:00+00:00", "2025-01-01T10:00:00+00:00"],
        ["2025-01-01T08:00:00+00:00", "2025-01-01T08:30:00+00:00"]]
    assert codec.loads(codec.dumps([])) == []
    assert codec.loads(json.dumps({"version": 2, "busy": []})) == []
    with pytest.raises(ValueError):
        codec.loads(json.dumps({"version": 3, "busy": []}))
    with pytest.raises(ValueError, match="invalid busy interval"):
        codec.loads(json.dumps([["2025-01-01T09:00:00+00:00", "2025-01-01T08:00:00+00:00"]]))


def test_cli_dispatch_v2():
    got = dispatch({"start": "2025-01-01T09:00:00+00:00", "end": "2025-01-01T10:00:00+00:00",
                    "busy": {"version": 2, "busy": [
                        {"start": "2025-01-01T09:00:00+00:00", "end": "2025-01-01T09:30:00+00:00"}]},
                    "duration": 30})
    assert got == [{"start": "2025-01-01T09:30:00+00:00", "end": "2025-01-01T10:00:00+00:00"}]
