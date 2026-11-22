import json
import pytest
from codec import dumps, loads
from service import Usage

DAY = ("2025-01-01T00:00:00+00:00", "2025-01-02T00:00:00+00:00")


def test_end_is_exclusive_and_empty_window_zero():
    usage = Usage()
    usage.add("a", "2025-01-02T00:00:00+00:00", 5)
    assert usage.query("a", *DAY) == 0
    assert usage.query("a", DAY[1], DAY[1]) == 0
    with pytest.raises(ValueError, match="end precedes start"):
        usage.query("a", DAY[1], DAY[0])


def test_offsets_compare_in_utc_including_fall_back():
    usage = Usage()
    usage.add("a", "2025-11-02T01:30:00-04:00", 1)
    usage.add("a", "2025-11-02T01:30:00-05:00", 2)
    assert usage.query("a", "2025-11-02T05:00:00+00:00", "2025-11-02T06:00:00+00:00") == 1
    assert usage.query("a", "2025-11-02T06:00:00+00:00", "2025-11-02T07:00:00+00:00") == 2


def test_add_invalidates_tenant_cache():
    usage = Usage()
    usage.add("a", "2025-01-01T12:00:00+00:00", 3)
    assert usage.query("a", *DAY) == 3
    usage.add(" a ", "2025-01-01T13:00:00+01:00", 4)
    assert usage.query("a", *DAY) == 7
    assert usage.query("b", *DAY) == 0


def test_event_ids_and_errors():
    usage = Usage()
    usage.add("a", "2025-01-01T12:00:00+00:00", 3, event_id="e")
    usage.add("a", "2025-01-01T13:00:00+01:00", 3, event_id="e")
    assert usage.count() == 1
    with pytest.raises(ValueError, match="event conflict"):
        usage.add("a", "2025-01-01T12:00:00+00:00", 4, event_id="e")
    assert usage.query("a", *DAY) == 3
    with pytest.raises(ValueError, match="time must include an offset"):
        usage.add("a", "2025-01-01T12:00:00", 1)
    for bad in (-1, True):
        with pytest.raises(ValueError, match="units must be an integer >= 0"):
            usage.add("a", "2025-01-01T12:00:00+00:00", bad)


def test_codec_round_trip_keeps_ids():
    raw = json.dumps([
        {"tenant": "a", "time": "2025-01-01T12:00:00+02:00", "units": 1, "id": "x"},
        {"tenant": "a", "time": "2025-01-01T10:00:00+00:00", "units": 1, "id": "x"},
        {"tenant": "b", "time": "2025-01-01T09:00:00+00:00", "units": 2},
    ])
    usage = loads(raw)
    assert usage.count() == 2
    rows = json.loads(dumps(usage))
    assert rows == [
        {"tenant": "a", "time": "2025-01-01T10:00:00+00:00", "units": 1, "id": "x"},
        {"tenant": "b", "time": "2025-01-01T09:00:00+00:00", "units": 2},
    ]
    with pytest.raises(ValueError, match="event conflict"):
        loads(json.dumps([
            {"tenant": "a", "time": "2025-01-01T10:00:00+00:00", "units": 1, "id": "x"},
            {"tenant": "b", "time": "2025-01-01T10:00:00+00:00", "units": 1, "id": "x"},
        ]))
    exported = usage.export()
    exported[0]["units"] = 99
    assert usage.export()[0]["units"] == 1
