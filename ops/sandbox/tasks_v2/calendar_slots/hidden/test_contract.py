import copy
import pytest
from service import slots
from codec import dumps, loads

def test_slots_fallback_elapsed_and_touching_busy():
    # SPEC §1
    # SPEC §2
    busy = [["2025-11-02T01:30:00-04:00","2025-11-02T01:00:00-05:00"]]
    before = copy.deepcopy(busy)
    result = slots("2025-11-02T01:00:00-04:00", "2025-11-02T02:00:00-05:00", busy, 30)
    assert [row["start"] for row in result] == ["2025-11-02T05:00:00+00:00", "2025-11-02T06:00:00+00:00", "2025-11-02T06:30:00+00:00"]
    assert busy == before

def test_slots_limit_validation_empty_and_wire():
    # SPEC §1
    # SPEC §3
    # SPEC §4
    start, end = "2025-01-01T00:00:00+00:00", "2025-01-01T01:00:00+00:00"
    assert slots(start, start, [], 1) == []
    assert slots(start, end, [], 10, step=15, limit=0) == []
    assert len(slots(start, end, [], 10, step=15, limit=2)) == 2
    for keyword, value, message in [("duration",0,"duration must be an integer >= 1"), ("step",False,"step must be an integer >= 1"), ("limit",-1,"limit must be an integer >= 0")]:
        args = dict(duration=10, step=None, limit=None)
        args[keyword] = value
        with pytest.raises(ValueError, match="^"+message+"$"):
            slots(start, end, [], **args)
    with pytest.raises(ValueError, match="^invalid busy interval$"):
        slots(start, end, [[end,start]], 10, limit=0)
    assert loads(dumps([])) == []
    assert loads('[["'+start+'","'+end+'"]]') == [[start,end]]
    offset = [["2025-01-01T01:00:00+01:00", "2025-01-01T02:00:00+01:00"]]
    assert loads(dumps(offset)) == [[start,end]]

def test_slots_naive_time_and_backwards_window():
    # SPEC §2
    with pytest.raises(ValueError, match="^time must include an offset$"):
        slots("2025-01-01", "2025-01-02T00:00:00Z", [], 1)
    with pytest.raises(ValueError, match="^end precedes start$"):
        slots("2025-01-02T00:00:00Z", "2025-01-01T00:00:00Z", [], 1)
