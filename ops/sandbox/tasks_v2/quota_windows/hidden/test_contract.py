import pytest
from service import Usage
from codec import dumps, loads

def test_usage_half_open_offset_fallback_and_cache():
    # SPEC §1
    # SPEC §2
    u = Usage()
    start, end = "2025-11-02T01:00:00-04:00", "2025-11-02T01:00:00-05:00"
    assert u.query("a", start, end) == 0
    u.add("a", end, 8)
    u.add("a", "2025-11-02T01:30:00-04:00", 2)
    u.add("b", start, 9)
    assert u.query("a", start, end) == 2
    assert u.query("b", start, end) == 9
    assert u.query("a", start, start) == 0

def test_usage_ids_wire_and_errors():
    # SPEC §3
    # SPEC §4
    u = loads('[{"tenant":"a","time":"2025-01-01T00:00:00+00:00","units":1}]')
    u.add("a", "2025-01-01T01:00:00+01:00", 2, "id")
    u = loads(dumps(u))
    u.add("a", "2025-01-01T00:00:00+00:00", 2, "id")
    assert u.count() == 2
    with pytest.raises(ValueError, match="^event conflict$"):
        u.add("b", "2025-01-01T00:00:00+00:00", 2, "id")
    with pytest.raises(ValueError, match="^time must include an offset$"):
        u.add("a", "2025-01-01", 2)
    with pytest.raises(ValueError, match="^units must be an integer >= 0$"):
        u.add("a", "2025-01-01T00:00:00+00:00", True)
    rows = u.export()
    rows[0]["units"] = 999
    assert u.export()[0]["units"] == 1

def test_usage_invalid_bounds_and_empty_tenant():
    # SPEC §1
    # SPEC §2
    u = Usage()
    with pytest.raises(ValueError, match="^end precedes start$"):
        u.query("a", "2025-01-02T00:00:00+00:00", "2025-01-01T00:00:00+00:00")
    assert u.query("unknown", "2025-01-01T00:00:00+00:00", "2025-01-02T00:00:00+00:00") == 0
